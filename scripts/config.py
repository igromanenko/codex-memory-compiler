"""Path constants and configuration for the personal knowledge base."""

import os
from pathlib import Path
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
HOOKS_DIR = ROOT_DIR / "hooks"
AGENTS_FILE = ROOT_DIR / "AGENTS.md"

VAULT_OVERRIDE_ENV = "KB_VAULT_DIR"
VAULT_OVERRIDE_FILE = ROOT_DIR / ".codex" / "vault.local"
STATE_SUBDIR = ".memory-compiler"


def _resolve_vault_dir() -> Path:
    """Resolve vault directory from env/file override, falling back to repo root."""
    override = os.getenv(VAULT_OVERRIDE_ENV, "").strip()
    if not override and VAULT_OVERRIDE_FILE.exists():
        override = VAULT_OVERRIDE_FILE.read_text(encoding="utf-8").strip()

    if not override:
        return ROOT_DIR

    candidate = Path(override).expanduser()
    if not candidate.is_absolute():
        candidate = (ROOT_DIR / candidate).resolve()
    return candidate


VAULT_DIR = _resolve_vault_dir()
DAILY_DIR = VAULT_DIR / "daily"
KNOWLEDGE_DIR = VAULT_DIR / "knowledge"
CONCEPTS_DIR = KNOWLEDGE_DIR / "concepts"
CONNECTIONS_DIR = KNOWLEDGE_DIR / "connections"
QA_DIR = KNOWLEDGE_DIR / "qa"
REPORTS_DIR = VAULT_DIR / "reports"
STATE_DIR = VAULT_DIR / STATE_SUBDIR

INDEX_FILE = KNOWLEDGE_DIR / "index.md"
LOG_FILE = KNOWLEDGE_DIR / "log.md"
STATE_FILE = STATE_DIR / "state.json"
FLUSH_STATE_FILE = STATE_DIR / "last-flush.json"
FLUSH_LOG_FILE = STATE_DIR / "flush.log"
COMPILE_LOG_FILE = STATE_DIR / "compile.log"

# ── Timezone ───────────────────────────────────────────────────────────
TIMEZONE = "America/Chicago"


def now_iso() -> str:
    """Current time in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current date in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
