"""
Memory flush agent - extracts important knowledge from conversation context.

Spawned by the Codex Stop hook as a background process. Reads pre-extracted
conversation context from a .md file, uses non-interactive Codex CLI execution
to decide what's worth saving, and appends the result to today's daily log.

Usage:
    python3 scripts/flush.py <context_file.md> <session_id> [turn_id]
"""

from __future__ import annotations

# Recursion prevention: set this BEFORE any imports that might trigger Codex.
import os
os.environ["CODEX_INVOKED_BY"] = "memory_flush"

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from config import (
    COMPILE_LOG_FILE,
    DAILY_DIR,
    FLUSH_LOG_FILE,
    FLUSH_STATE_FILE,
    SCRIPTS_DIR,
    STATE_FILE as COMPILE_STATE_FILE,
)
from llm import run_text_response

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = FLUSH_LOG_FILE
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Set up file-based logging so we can verify the background process ran.
# The parent process sends stdout/stderr to DEVNULL (to avoid the inherited
# file handle bug on Windows), so this is our only observability channel.
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def load_flush_state() -> dict:
    if FLUSH_STATE_FILE.exists():
        try:
            return json.loads(FLUSH_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_flush_state(state: dict) -> None:
    FLUSH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    FLUSH_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def append_to_daily_log(content: str, section: str = "Session") -> None:
    """Append content to today's daily log."""
    today = datetime.now(timezone.utc).astimezone()
    log_path = DAILY_DIR / f"{today.strftime('%Y-%m-%d')}.md"

    if not log_path.exists():
        DAILY_DIR.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"# Daily Log: {today.strftime('%Y-%m-%d')}\n\n## Sessions\n\n## Memory Maintenance\n\n",
            encoding="utf-8",
        )

    time_str = today.strftime("%H:%M")
    entry = f"### {section} ({time_str})\n\n{content}\n\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


def read_today_log_tail(max_chars: int = 6_000) -> str:
    """Read the tail of today's daily log to reduce duplicate flushes."""
    today = datetime.now(timezone.utc).astimezone()
    log_path = DAILY_DIR / f"{today.strftime('%Y-%m-%d')}.md"
    if not log_path.exists():
        return "(nothing saved yet today)"

    content = log_path.read_text(encoding="utf-8").strip()
    if not content:
        return "(nothing saved yet today)"
    return content[-max_chars:]


def run_flush(context: str, existing_log_tail: str) -> str:
    """Use `codex exec` to extract durable knowledge from recent context."""

    prompt = f"""Review the conversation context below and respond with a concise summary
of important items that should be preserved in the daily log.
Do NOT use any tools - just return plain text.

Format your response as a structured daily log entry with these sections:

**Context:** [One line about what the user was working on]

**Key Exchanges:**
- [Important Q&A or discussions]

**Decisions Made:**
- [Any decisions with rationale]

**Lessons Learned:**
- [Gotchas, patterns, or insights discovered]

**Action Items:**
- [Follow-ups or TODOs mentioned]

Skip anything that is:
- Routine tool calls or file reads
- Content that's trivial or obvious
- Trivial back-and-forth or clarification exchanges
- Information that is already captured in today's daily log excerpt

Only include sections that have actual content. If nothing is worth saving,
respond with exactly: FLUSH_OK

## Today's Daily Log So Far

{existing_log_tail}

## Conversation Context

{context}"""

    try:
        result = run_text_response(
            prompt=prompt,
            instructions=(
                "You condense recent coding conversations into durable daily-log notes. "
                "Only preserve new, high-signal information."
            ),
            max_output_tokens=1_500,
            verbosity="low",
        )
        response = result.text
    except Exception as e:
        import traceback
        logging.error("Codex CLI error: %s\n%s", e, traceback.format_exc())
        response = f"FLUSH_ERROR: {type(e).__name__}: {e}"

    return response

def maybe_trigger_compilation() -> None:
    """Compile after flush when today's daily log changed since its last compile."""
    import subprocess as _sp

    now = datetime.now(timezone.utc).astimezone()

    # Check if today's log has already been compiled
    today_log = f"{now.strftime('%Y-%m-%d')}.md"
    compile_state_file = COMPILE_STATE_FILE
    if compile_state_file.exists():
        try:
            compile_state = json.loads(compile_state_file.read_text(encoding="utf-8"))
            ingested = compile_state.get("ingested", {})
            if today_log in ingested:
                # Already compiled today - check if the log has changed since
                from hashlib import sha256
                log_path = DAILY_DIR / today_log
                if log_path.exists():
                    current_hash = sha256(log_path.read_bytes()).hexdigest()[:16]
                    if ingested[today_log].get("hash") == current_hash:
                        return  # log unchanged since last compile
        except (json.JSONDecodeError, OSError):
            pass

    compile_script = SCRIPTS_DIR / "compile.py"
    if not compile_script.exists():
        return

    logging.info("Post-flush compilation triggered for %s", today_log)

    cmd = [sys.executable, str(compile_script)]

    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = _sp.CREATE_NEW_PROCESS_GROUP | _sp.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True

    try:
        COMPILE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        log_handle = open(str(COMPILE_LOG_FILE), "a")
        _sp.Popen(cmd, stdout=log_handle, stderr=_sp.STDOUT, cwd=str(ROOT), **kwargs)
    except Exception as e:
        logging.error("Failed to spawn compile.py: %s", e)


def main():
    if len(sys.argv) < 3:
        logging.error("Usage: %s <context_file.md> <session_id> [turn_id]", sys.argv[0])
        sys.exit(1)

    context_file = Path(sys.argv[1])
    session_id = sys.argv[2]
    turn_id = sys.argv[3] if len(sys.argv) > 3 else ""

    logging.info(
        "flush.py started for session %s turn %s, context: %s",
        session_id,
        turn_id or "(none)",
        context_file,
    )

    if not context_file.exists():
        logging.error("Context file not found: %s", context_file)
        return

    # Deduplication: skip if the same turn was flushed within 60 seconds.
    state = load_flush_state()
    if (
        state.get("session_id") == session_id
        and state.get("turn_id") == turn_id
        and time.time() - state.get("timestamp", 0) < 60
    ):
        logging.info("Skipping duplicate flush for session %s turn %s", session_id, turn_id)
        context_file.unlink(missing_ok=True)
        return

    # Read pre-extracted context
    context = context_file.read_text(encoding="utf-8").strip()
    if not context:
        logging.info("Context file is empty, skipping")
        context_file.unlink(missing_ok=True)
        return

    logging.info("Flushing session %s: %d chars", session_id, len(context))

    # Run the LLM extraction
    response = run_flush(context, read_today_log_tail())

    # Append to daily log
    if response.strip() == "FLUSH_OK":
        logging.info("Result: FLUSH_OK")
    elif "FLUSH_ERROR" in response:
        logging.error("Result: %s", response)
        append_to_daily_log(response, "Memory Flush")
    else:
        logging.info("Result: saved to daily log (%d chars)", len(response))
        append_to_daily_log(response, "Session")

    # Update dedup state
    save_flush_state(
        {
            "session_id": session_id,
            "turn_id": turn_id,
            "timestamp": time.time(),
        }
    )

    # Clean up context file
    context_file.unlink(missing_ok=True)

    # Auto-compilation: if today's daily log changed since its last compile,
    # trigger compile.py in the background.
    maybe_trigger_compilation()

    logging.info("Flush complete for session %s", session_id)


if __name__ == "__main__":
    main()
