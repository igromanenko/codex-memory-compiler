"""Codex CLI helpers for non-interactive model calls."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
CODEX_CONFIG_FILE = ROOT_DIR / ".codex" / "config.toml"


@dataclass(slots=True)
class UsageStats:
    """Normalized token usage data from Codex CLI exec output."""

    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class LLMResult:
    """Response payload normalized for the KB scripts."""

    text: str
    usage: UsageStats
    cost_usd: float | None
    model: str | None
    response_id: str | None = None


def _resolve_model(model: str | None = None) -> str | None:
    if model:
        return model

    env_model = os.getenv("CODEX_MODEL")
    if env_model:
        return env_model

    if CODEX_CONFIG_FILE.exists():
        try:
            config = tomllib.loads(CODEX_CONFIG_FILE.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError):
            return None
        configured_model = config.get("model")
        if isinstance(configured_model, str):
            return configured_model

    return None


@lru_cache(maxsize=1)
def _codex_binary() -> str:
    binary = shutil.which("codex")
    if not binary:
        raise RuntimeError("Codex CLI is not installed or not on PATH")
    return binary


@lru_cache(maxsize=1)
def ensure_codex_login() -> None:
    """Fail fast if Codex CLI is unavailable or not authenticated."""
    result = subprocess.run(
        [_codex_binary(), "login", "status"],
        check=False,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    combined = "\n".join(part for part in [stdout, stderr] if part).strip()

    if result.returncode == 0 and "logged in" in combined.lower():
        return

    message = combined or "unknown authentication error"
    raise RuntimeError(
        "Codex CLI is not authenticated. Run `codex login` first. "
        f"Status output: {message}"
    )


def _build_exec_prompt(prompt: str, instructions: str | None = None) -> str:
    if not instructions:
        return prompt

    return (
        f"{instructions.strip()}\n\n"
        "## Task\n\n"
        f"{prompt.strip()}\n"
    )


def _normalize_usage(raw_usage: dict[str, Any] | None) -> UsageStats:
    if not raw_usage:
        return UsageStats()

    input_tokens = int(raw_usage.get("input_tokens", 0) or 0)
    cached_input_tokens = int(raw_usage.get("cached_input_tokens", 0) or 0)
    output_tokens = int(raw_usage.get("output_tokens", 0) or 0)
    return UsageStats(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def _parse_exec_output(stdout: str) -> tuple[str, UsageStats, str | None]:
    """Parse Codex JSONL output and extract the final assistant message."""
    last_message = ""
    usage = UsageStats()
    thread_id = None

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        event = json.loads(line)
        event_type = event.get("type")

        if event_type == "thread.started":
            thread_id = event.get("thread_id")
            continue

        if event_type == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    last_message = text
            continue

        if event_type == "turn.completed":
            usage = _normalize_usage(event.get("usage"))

    return last_message, usage, thread_id


def _extract_exec_error(stdout: str, stderr: str) -> str:
    """Best-effort extraction of a human-readable Codex CLI error."""
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "error":
            message = event.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

        if event.get("type") == "turn.failed":
            error = event.get("error", {})
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()

    stderr = stderr.strip()
    if stderr:
        return stderr

    stdout = stdout.strip()
    if stdout:
        return stdout

    return "codex exec returned a non-zero status"


def _run_codex_exec(
    prompt: str,
    *,
    instructions: str | None = None,
    model: str | None = None,
    schema_path: Path | None = None,
) -> LLMResult:
    ensure_codex_login()

    resolved_model = _resolve_model(model)
    cmd = [
        _codex_binary(),
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--disable",
        "codex_hooks",
        "--sandbox",
        "read-only",
        "-C",
        str(ROOT_DIR),
    ]
    if resolved_model:
        cmd.extend(["-m", resolved_model])
    if schema_path is not None:
        cmd.extend(["--output-schema", str(schema_path)])
    cmd.append("-")

    process = subprocess.run(
        cmd,
        check=False,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        input=_build_exec_prompt(prompt, instructions=instructions),
    )

    if process.returncode != 0:
        raise RuntimeError(_extract_exec_error(process.stdout or "", process.stderr or ""))

    text, usage, thread_id = _parse_exec_output(process.stdout)
    if not text:
        error = _extract_exec_error(process.stdout or "", process.stderr or "")
        if error != "codex exec returned a non-zero status":
            raise RuntimeError(error)
        raise RuntimeError("Codex CLI returned no assistant message")

    return LLMResult(
        text=text,
        usage=usage,
        cost_usd=None,
        model=resolved_model,
        response_id=thread_id,
    )


def run_text_response(
    prompt: str,
    *,
    instructions: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
    max_output_tokens: int | None = None,
) -> LLMResult:
    """Generate plain-text output using `codex exec`."""
    del reasoning_effort, verbosity, max_output_tokens
    return _run_codex_exec(prompt, instructions=instructions, model=model)


def run_json_response(
    prompt: str,
    *,
    schema_name: str,
    schema: dict[str, Any],
    instructions: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
) -> tuple[dict[str, Any], LLMResult]:
    """Generate JSON that must conform to the provided schema."""
    del schema_name, reasoning_effort, max_output_tokens

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
    ) as handle:
        handle.write(json.dumps(schema))
        schema_path = Path(handle.name)

    try:
        result = _run_codex_exec(
            prompt,
            instructions=instructions,
            model=model,
            schema_path=schema_path,
        )
    finally:
        schema_path.unlink(missing_ok=True)

    try:
        parsed = json.loads(result.text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Codex CLI returned invalid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Structured response root must be a JSON object")

    return parsed, result
