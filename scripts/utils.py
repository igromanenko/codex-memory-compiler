"""Shared utilities for the personal knowledge base."""

import hashlib
import json
import re
from pathlib import Path

from config import (
    CONCEPTS_DIR,
    CONNECTIONS_DIR,
    DAILY_DIR,
    INDEX_FILE,
    KNOWLEDGE_DIR,
    LOG_FILE,
    QA_DIR,
    ROOT_DIR,
    STATE_FILE,
)


# ── State management ──────────────────────────────────────────────────

def load_state() -> dict:
    """Load persistent state from state.json."""
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    else:
        state = {}

    state.setdefault("ingested", {})
    state.setdefault("query_count", 0)
    state.setdefault("last_lint", None)
    state.setdefault("total_cost", 0.0)
    state.setdefault("total_input_tokens", 0)
    state.setdefault("total_output_tokens", 0)
    state.setdefault("total_tokens", 0)
    return state


def save_state(state: dict) -> None:
    """Save state to state.json."""
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def record_usage(state: dict, usage, cost_usd: float | None) -> None:
    """Merge usage counters into persistent state."""
    state["total_input_tokens"] = state.get("total_input_tokens", 0) + getattr(
        usage, "input_tokens", 0
    )
    state["total_output_tokens"] = state.get("total_output_tokens", 0) + getattr(
        usage, "output_tokens", 0
    )
    state["total_tokens"] = state.get("total_tokens", 0) + getattr(
        usage, "total_tokens", 0
    )
    if cost_usd is not None:
        state["total_cost"] = round(state.get("total_cost", 0.0) + cost_usd, 6)


# ── File hashing ──────────────────────────────────────────────────────

def file_hash(path: Path) -> str:
    """SHA-256 hash of a file (first 16 hex chars)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ── Slug / naming ─────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ── Wikilink helpers ──────────────────────────────────────────────────

def extract_wikilinks(content: str) -> list[str]:
    """Extract all [[wikilinks]] from markdown content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def wiki_article_exists(link: str) -> bool:
    """Check if a wikilinked article exists on disk."""
    path = KNOWLEDGE_DIR / f"{link}.md"
    return path.exists()


# ── Wiki content helpers ──────────────────────────────────────────────

def read_wiki_index() -> str:
    """Read the knowledge base index file."""
    if INDEX_FILE.exists():
        return INDEX_FILE.read_text(encoding="utf-8")
    return "# Knowledge Base Index\n\n| Article | Summary | Compiled From | Updated |\n|---------|---------|---------------|---------|"


def read_all_wiki_content() -> str:
    """Read index + all wiki articles into a single string for context."""
    parts = [f"## INDEX\n\n{read_wiki_index()}"]

    for subdir in [CONCEPTS_DIR, CONNECTIONS_DIR, QA_DIR]:
        if not subdir.exists():
            continue
        for md_file in sorted(subdir.glob("*.md")):
            rel = md_file.relative_to(KNOWLEDGE_DIR)
            content = md_file.read_text(encoding="utf-8")
            parts.append(f"## {rel}\n\n{content}")

    return "\n\n---\n\n".join(parts)


def list_wiki_articles() -> list[Path]:
    """List all wiki article files."""
    articles = []
    for subdir in [CONCEPTS_DIR, CONNECTIONS_DIR, QA_DIR]:
        if subdir.exists():
            articles.extend(sorted(subdir.glob("*.md")))
    return articles


def list_raw_files() -> list[Path]:
    """List all daily log files."""
    if not DAILY_DIR.exists():
        return []
    return sorted(DAILY_DIR.glob("*.md"))


# ── Index helpers ─────────────────────────────────────────────────────

def count_inbound_links(target: str, exclude_file: Path | None = None) -> int:
    """Count how many wiki articles link to a given target."""
    count = 0
    for article in list_wiki_articles():
        if article == exclude_file:
            continue
        content = article.read_text(encoding="utf-8")
        if f"[[{target}]]" in content:
            count += 1
    return count


def get_article_word_count(path: Path) -> int:
    """Count words in an article, excluding YAML frontmatter."""
    content = path.read_text(encoding="utf-8")
    # Strip frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:]
    return len(content.split())


def build_index_entry(rel_path: str, summary: str, sources: str, updated: str) -> str:
    """Build a single index table row."""
    link = rel_path.replace(".md", "")
    return f"| [[{link}]] | {summary} | {sources} | {updated} |"


def resolve_repo_path(rel_path: str) -> Path:
    """Resolve a repo-relative path and reject path traversal."""
    candidate = (ROOT_DIR / rel_path).resolve()
    root_resolved = ROOT_DIR.resolve()
    if candidate == root_resolved or root_resolved in candidate.parents:
        return candidate
    raise ValueError(f"Path escapes repository root: {rel_path}")


def apply_write_operations(
    operations: list[dict],
    allowed_prefixes: tuple[str, ...] = ("knowledge/",),
) -> None:
    """Apply structured write/append operations returned by the LLM."""
    for operation in operations:
        rel_path = operation["path"]
        mode = operation["operation"]
        content = operation["content"]
        if not any(rel_path.startswith(prefix) for prefix in allowed_prefixes):
            raise ValueError(f"Write operation outside allowed prefixes: {rel_path}")
        path = resolve_repo_path(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if mode == "write":
            path.write_text(content, encoding="utf-8")
            continue

        if mode != "append":
            raise ValueError(f"Unsupported write operation: {mode}")

        if not path.exists():
            prefix = "# Build Log\n\n" if path == LOG_FILE else ""
            path.write_text(prefix, encoding="utf-8")

        existing = path.read_text(encoding="utf-8")
        with open(path, "a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(content)
