"""
Compile daily conversation logs into structured knowledge articles.

This is the "LLM compiler" - it reads daily logs (source code) and produces
organized knowledge articles (the executable).

Usage:
    python3 scripts/compile.py                    # compile new/changed logs only
    python3 scripts/compile.py --all              # force recompile everything
    python3 scripts/compile.py --file daily/2026-04-01.md  # compile a specific log
    python3 scripts/compile.py --dry-run          # show what would be compiled
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import AGENTS_FILE, DAILY_DIR, KNOWLEDGE_DIR, now_iso
from llm import run_json_response
from utils import (
    apply_write_operations,
    file_hash,
    list_raw_files,
    list_wiki_articles,
    load_state,
    record_usage,
    read_wiki_index,
    save_state,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
COMPILE_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "created": {
            "type": "array",
            "items": {"type": "string"},
        },
        "updated": {
            "type": "array",
            "items": {"type": "string"},
        },
        "writes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "operation": {"type": "string", "enum": ["write", "append"]},
                    "content": {"type": "string"},
                },
                "required": ["path", "operation", "content"],
            },
        },
    },
    "required": ["created", "updated", "writes"],
}


def compile_daily_log(log_path: Path, state: dict) -> int:
    """Compile a single daily log into knowledge articles.

    Returns the total token count reported by Codex CLI.
    """
    log_content = log_path.read_text(encoding="utf-8")
    schema = AGENTS_FILE.read_text(encoding="utf-8")
    wiki_index = read_wiki_index()

    # Read existing articles for context
    existing_articles_context = ""
    existing = {}
    for article_path in list_wiki_articles():
        rel = article_path.relative_to(KNOWLEDGE_DIR)
        existing[str(rel)] = article_path.read_text(encoding="utf-8")

    if existing:
        parts = []
        for rel_path, content in existing.items():
            parts.append(f"### {rel_path}\n```markdown\n{content}\n```")
        existing_articles_context = "\n\n".join(parts)

    timestamp = now_iso()

    prompt = f"""You are a knowledge compiler. Your job is to read a daily conversation log
and extract knowledge into structured wiki articles.

## Schema (AGENTS.md)

{schema}

## Current Wiki Index

{wiki_index}

## Existing Wiki Articles

{existing_articles_context if existing_articles_context else "(No existing articles yet)"}

## Daily Log to Compile

**File:** {log_path.name}

{log_content}

## Your Task

Read the daily log above and compile it into wiki articles following the schema exactly.
Respond with JSON only.

### Rules:

1. **Extract key concepts** - Identify 3-7 distinct concepts worth their own article
2. **Create concept articles** in `knowledge/concepts/` - one `.md` file per concept
   - Use the exact article format from AGENTS.md (YAML frontmatter + sections)
   - Include `sources:` in frontmatter pointing to the daily log file
   - Use `[[concepts/slug]]` wikilinks to link to related concepts
   - Write in encyclopedia style - neutral, comprehensive
3. **Create connection articles** in `knowledge/connections/` if this log reveals non-obvious
   relationships between 2+ existing concepts
4. **Update existing articles** if this log adds new information to concepts already in the wiki
   - Read the existing article, add the new information, add the source to frontmatter
5. **Update knowledge/index.md** - Add new entries to the table
   - Each entry: `| [[path/slug]] | One-line summary | source-file | {timestamp[:10]} |`
6. **Append to knowledge/log.md** - Add a timestamped entry:
   ```
   ## [{timestamp}] compile | {log_path.name}
   - Source: daily/{log_path.name}
   - Articles created: [[concepts/x]], [[concepts/y]]
   - Articles updated: [[concepts/z]] (if any)
   ```

### JSON output contract:
- Return `created`: repo-relative wikilink targets created during this compile, without `.md`
- Return `updated`: repo-relative wikilink targets updated during this compile, without `.md`
- Return `writes`: a list of file operations
- Use `operation: "write"` with complete file contents for every new or updated article
- Always include a `write` operation for `knowledge/index.md` with the full updated file
- Use `operation: "append"` only for `knowledge/log.md`
- All file paths must be repo-relative, for example `knowledge/concepts/example.md`

### Quality standards:
- Every article must have complete YAML frontmatter
- Every article must link to at least 2 other articles via [[wikilinks]]
- Key Points section should have 3-5 bullet points
- Details section should have 2+ paragraphs
- Related Concepts section should have 2+ entries
- Sources section should cite the daily log with specific claims extracted
"""

    try:
        plan, result = run_json_response(
            prompt=prompt,
            instructions=(
                "You are a deterministic knowledge compiler. Only emit JSON that matches "
                "the requested schema. Do not wrap the JSON in markdown fences."
            ),
            schema_name="knowledge_compile_plan",
            schema=COMPILE_PLAN_SCHEMA,
            max_output_tokens=32_000,
        )
    except Exception as e:
        print(f"  Error: {e}")
        return 0

    apply_write_operations(plan["writes"])
    record_usage(state, result.usage, result.cost_usd)

    if result.cost_usd is not None:
        print(f"  Estimated cost: ${result.cost_usd:.4f}")
    print(
        "  Usage:"
        f" {result.usage.input_tokens} input,"
        f" {result.usage.output_tokens} output,"
        f" {result.usage.total_tokens} total"
    )

    # Update state
    rel_path = log_path.name
    state.setdefault("ingested", {})[rel_path] = {
        "hash": file_hash(log_path),
        "compiled_at": now_iso(),
        "cost_usd": result.cost_usd,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "total_tokens": result.usage.total_tokens,
        "model": result.model,
    }
    save_state(state)

    return result.usage.total_tokens


def main():
    parser = argparse.ArgumentParser(description="Compile daily logs into knowledge articles")
    parser.add_argument("--all", action="store_true", help="Force recompile all logs")
    parser.add_argument("--file", type=str, help="Compile a specific daily log file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be compiled")
    args = parser.parse_args()

    state = load_state()

    # Determine which files to compile
    if args.file:
        target = Path(args.file)
        if not target.is_absolute():
            target = DAILY_DIR / target.name
        if not target.exists():
            # Try resolving relative to project root
            target = ROOT_DIR / args.file
        if not target.exists():
            print(f"Error: {args.file} not found")
            sys.exit(1)
        to_compile = [target]
    else:
        all_logs = list_raw_files()
        if args.all:
            to_compile = all_logs
        else:
            to_compile = []
            for log_path in all_logs:
                rel = log_path.name
                prev = state.get("ingested", {}).get(rel, {})
                if not prev or prev.get("hash") != file_hash(log_path):
                    to_compile.append(log_path)

    if not to_compile:
        print("Nothing to compile - all daily logs are up to date.")
        return

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Files to compile ({len(to_compile)}):")
    for f in to_compile:
        print(f"  - {f.name}")

    if args.dry_run:
        return

    # Compile each file sequentially
    total_tokens = 0
    for i, log_path in enumerate(to_compile, 1):
        print(f"\n[{i}/{len(to_compile)}] Compiling {log_path.name}...")
        token_count = compile_daily_log(log_path, state)
        total_tokens += token_count
        print(f"  Done.")

    articles = list_wiki_articles()
    print(f"\nCompilation complete. Total tokens: {total_tokens}")
    print(f"Knowledge base: {len(articles)} articles")


if __name__ == "__main__":
    main()
