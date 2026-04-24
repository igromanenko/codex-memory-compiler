"""
Stop hook - captures the latest conversation turns for memory extraction.

Codex currently exposes `Stop` instead of Claude-style `SessionEnd` or
`PreCompact`. This hook therefore acts as the memory capture trigger after
each completed turn. It extracts recent transcript context and spawns
`scripts/flush.py` as a background process.

The hook itself does no API calls - only local file I/O for speed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Recursion guard: if we were spawned by flush.py, exit immediately.
if os.environ.get("CODEX_INVOKED_BY"):
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from config import FLUSH_LOG_FILE, STATE_DIR

SCRIPTS_DIR = ROOT / "scripts"
FLUSH_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

try:
    logging.basicConfig(
        filename=str(FLUSH_LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [stop-hook] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
except OSError:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [stop-hook] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

MAX_TURNS = 8
MAX_CONTEXT_CHARS = 12_000
MIN_TURNS_TO_FLUSH = 1


def _content_to_text(content: object) -> str:
    """Normalize Codex transcript content blocks into plain text."""
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            text_parts.append(block)
            continue

        if not isinstance(block, dict):
            continue

        text = block.get("text")
        if isinstance(text, str):
            text_parts.append(text)

    return "\n".join(text_parts)


def _extract_message(entry: dict) -> tuple[str, str] | None:
    """Return a user/assistant message from old or current Codex JSONL shapes."""
    payload = entry.get("payload")
    if (
        entry.get("type") == "response_item"
        and isinstance(payload, dict)
        and payload.get("type") == "message"
    ):
        role = payload.get("role", "")
        content = payload.get("content", "")
        return str(role), _content_to_text(content)

    msg = entry.get("message")
    if isinstance(msg, dict):
        role = msg.get("role", "")
        content = msg.get("content", "")
        return str(role), _content_to_text(content)

    role = entry.get("role", "")
    if role:
        return str(role), _content_to_text(entry.get("content", ""))

    return None


def _is_injected_context_message(role: str, text: str) -> bool:
    """Skip Codex-injected AGENTS/environment context that is not user dialogue."""
    if role != "user":
        return False

    stripped = text.lstrip()
    return stripped.startswith("# AGENTS.md instructions for ") and "<environment_context>" in text


def _resolve_transcript_path(hook_input: dict) -> str:
    for key in (
        "transcript_path",
        "transcriptPath",
        "transcript",
        "conversation_path",
        "conversationPath",
    ):
        value = hook_input.get(key, "")
        if isinstance(value, str) and value:
            return value
    return ""


def _safe_filename_component(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return safe or "unknown"


def _select_recent_turns(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    recent = turns[-MAX_TURNS:]
    if any(role == "user" for role, _ in recent):
        return recent

    last_user = next((turn for turn in reversed(turns[:-MAX_TURNS]) if turn[0] == "user"), None)
    if last_user is None:
        return recent

    if len(recent) >= MAX_TURNS:
        recent = recent[-(MAX_TURNS - 1) :]
    return [last_user, *recent]


def extract_conversation_context(transcript_path: Path) -> tuple[str, int]:
    """Read JSONL transcript and extract the latest conversation turns."""
    turns: list[tuple[str, str]] = []

    with open(transcript_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = _extract_message(entry)
            if message is None:
                continue
            role, content = message
            if role not in ("user", "assistant"):
                continue

            if isinstance(content, str) and content.strip():
                if _is_injected_context_message(role, content):
                    continue
                label = "User" if role == "user" else "Assistant"
                turns.append((role, f"**{label}:** {content.strip()}\n"))

    recent = _select_recent_turns(turns)
    context = "\n".join(formatted for _, formatted in recent)

    if len(context) > MAX_CONTEXT_CHARS:
        context = context[-MAX_CONTEXT_CHARS:]
        boundary = context.find("\n**")
        if boundary > 0:
            context = context[boundary + 1 :]

    return context, len(recent)


def main() -> None:
    try:
        raw_input = sys.stdin.read()
        try:
            hook_input: dict = json.loads(raw_input)
        except json.JSONDecodeError:
            fixed_input = re.sub(r'(?<!\\)\\(?!["\\])', r"\\\\", raw_input)
            hook_input = json.loads(fixed_input)
    except (json.JSONDecodeError, ValueError, EOFError) as exc:
        logging.error("Failed to parse stdin: %s", exc)
        print(json.dumps({"continue": True}))
        return

    session_id = hook_input.get("session_id", "unknown")
    turn_id = hook_input.get("turn_id", "unknown")
    transcript_path_str = _resolve_transcript_path(hook_input)

    logging.info("Stop fired: session=%s turn=%s", session_id, turn_id)

    if not transcript_path_str or not isinstance(transcript_path_str, str):
        logging.info("SKIP: no transcript path (keys=%s)", sorted(hook_input.keys()))
        print(json.dumps({"continue": True}))
        return

    transcript_path = Path(transcript_path_str)
    if not transcript_path.exists():
        logging.info("SKIP: transcript missing: %s", transcript_path_str)
        print(json.dumps({"continue": True}))
        return

    try:
        context, turn_count = extract_conversation_context(transcript_path)
    except Exception as exc:
        logging.error("Context extraction failed: %s", exc)
        print(json.dumps({"continue": True}))
        return

    if not context.strip():
        logging.info("SKIP: empty context")
        print(json.dumps({"continue": True}))
        return

    if turn_count < MIN_TURNS_TO_FLUSH:
        logging.info("SKIP: only %d turns (min %d)", turn_count, MIN_TURNS_TO_FLUSH)
        print(json.dumps({"continue": True}))
        return

    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe_session_id = _safe_filename_component(str(session_id))
    safe_turn_id = _safe_filename_component(str(turn_id))
    context_file = STATE_DIR / f"stop-flush-{safe_session_id}-{safe_turn_id}-{timestamp}.md"
    context_file.write_text(context, encoding="utf-8")

    flush_script = SCRIPTS_DIR / "flush.py"
    cmd = [
        sys.executable,
        str(flush_script),
        str(context_file),
        session_id,
        turn_id,
    ]

    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    try:
        subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
        logging.info(
            "Spawned flush.py for session %s turn %s (%d turns, %d chars)",
            session_id,
            turn_id,
            turn_count,
            len(context),
        )
    except Exception as exc:
        logging.error("Failed to spawn flush.py: %s", exc)

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
