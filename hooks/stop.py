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

from config import FLUSH_LOG_FILE

SCRIPTS_DIR = ROOT / "scripts"
STATE_DIR = SCRIPTS_DIR
FLUSH_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(FLUSH_LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [stop-hook] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

MAX_TURNS = 8
MAX_CONTEXT_CHARS = 12_000
MIN_TURNS_TO_FLUSH = 1


def extract_conversation_context(transcript_path: Path) -> tuple[str, int]:
    """Read JSONL transcript and extract the latest conversation turns."""
    turns: list[str] = []

    with open(transcript_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = entry.get("message", {})
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
            else:
                role = entry.get("role", "")
                content = entry.get("content", "")

            if role not in ("user", "assistant"):
                continue

            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                content = "\n".join(text_parts)

            if isinstance(content, str) and content.strip():
                label = "User" if role == "user" else "Assistant"
                turns.append(f"**{label}:** {content.strip()}\n")

    recent = turns[-MAX_TURNS:]
    context = "\n".join(recent)

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
    transcript_path_str = hook_input.get("transcript_path", "")

    logging.info("Stop fired: session=%s turn=%s", session_id, turn_id)

    if not transcript_path_str or not isinstance(transcript_path_str, str):
        logging.info("SKIP: no transcript path")
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
    context_file = STATE_DIR / f"stop-flush-{session_id}-{turn_id}-{timestamp}.md"
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
