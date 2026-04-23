# AGENTS.md - Personal Knowledge Base Schema

> Adapted from [Andrej Karpathy's LLM Knowledge Base](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) architecture.
> Instead of ingesting external articles, this system compiles knowledge from your own AI conversations.

## The Compiler Analogy

```
daily/          = source code    (your conversations - the raw material)
LLM             = compiler       (extracts and organizes knowledge)
knowledge/      = executable     (structured, queryable knowledge base)
lint            = test suite     (health checks for consistency)
queries         = runtime        (using the knowledge)
```

You don't manually organize your knowledge. You have conversations, and the LLM handles the synthesis, cross-referencing, and maintenance.

---

## Architecture

### Layer 1: `daily/` - Conversation Logs (Immutable Source)

Daily logs capture what happened in your AI coding sessions. These are the "raw sources" - append-only, never edited after the fact.

```
daily/
├── 2026-04-01.md
├── 2026-04-02.md
├── ...
```

Each file follows this format:

```markdown
# Daily Log: YYYY-MM-DD

## Sessions

### Session (HH:MM) - Brief Title

**Context:** What the user was working on.

**Key Exchanges:**
- User asked about X, assistant explained Y
- Decided to use Z approach because...
- Discovered that W doesn't work when...

**Decisions Made:**
- Chose library X over Y because...
- Architecture: went with pattern Z

**Lessons Learned:**
- Always do X before Y to avoid...
- The gotcha with Z is that...

**Action Items:**
- [ ] Follow up on X
- [ ] Refactor Y when time permits
```

### Layer 2: `knowledge/` - Compiled Knowledge (LLM-Owned)

The LLM owns this directory entirely. Humans read it but rarely edit it directly.

```
knowledge/
├── index.md              # Master catalog - every article with one-line summary
├── log.md                # Append-only chronological build log
├── concepts/             # Atomic knowledge articles
├── connections/          # Cross-cutting insights linking 2+ concepts
└── qa/                   # Filed query answers (compounding knowledge)
```

### Layer 3: This File (AGENTS.md)

The schema that tells the LLM how to compile and maintain the knowledge base. This is the "compiler specification."

---

## Structural Files

### `knowledge/index.md` - Master Catalog

A table listing every knowledge article. This is the primary retrieval mechanism - the LLM reads this FIRST when answering any query, then selects relevant articles to read in full.

Format:

```markdown
# Knowledge Base Index

| Article | Summary | Compiled From | Updated |
|---------|---------|---------------|---------|
| [[concepts/supabase-auth]] | Row-level security patterns and JWT gotchas | daily/2026-04-02.md | 2026-04-02 |
| [[connections/auth-and-webhooks]] | Token verification patterns shared across Supabase auth and Stripe webhooks | daily/2026-04-02.md, daily/2026-04-04.md | 2026-04-04 |
```

### `knowledge/log.md` - Build Log

Append-only chronological record of every compile, query, and lint operation.

Format:

```markdown
# Build Log

## [2026-04-01T14:30:00] compile | Daily Log 2026-04-01
- Source: daily/2026-04-01.md
- Articles created: [[concepts/nextjs-project-structure]], [[concepts/tailwind-setup]]
- Articles updated: (none)

## [2026-04-02T09:00:00] query | "How do I handle auth redirects?"
- Consulted: [[concepts/supabase-auth]], [[concepts/nextjs-middleware]]
- Filed to: [[qa/auth-redirect-handling]]
```

---

## Article Formats

### Concept Articles (`knowledge/concepts/`)

One article per atomic piece of knowledge. These are facts, patterns, decisions, preferences, and lessons extracted from your conversations.

```markdown
---
title: "Concept Name"
aliases: [alternate-name, abbreviation]
tags: [domain, topic]
sources:
  - "daily/2026-04-01.md"
  - "daily/2026-04-03.md"
created: 2026-04-01
updated: 2026-04-03
---

# Concept Name

[2-4 sentence core explanation]

## Key Points

- [Bullet points, each self-contained]

## Details

[Deeper explanation, encyclopedia-style paragraphs]

## Related Concepts

- [[concepts/related-concept]] - How it connects

## Sources

- [[daily/2026-04-01.md]] - Initial discovery during project setup
- [[daily/2026-04-03.md]] - Updated after debugging session
```

### Connection Articles (`knowledge/connections/`)

Cross-cutting synthesis linking 2+ concepts. Created when a conversation reveals a non-obvious relationship.

```markdown
---
title: "Connection: X and Y"
connects:
  - "concepts/concept-x"
  - "concepts/concept-y"
sources:
  - "daily/2026-04-04.md"
created: 2026-04-04
updated: 2026-04-04
---

# Connection: X and Y

## The Connection

[What links these concepts]

## Key Insight

[The non-obvious relationship discovered]

## Evidence

[Specific examples from conversations]

## Related Concepts

- [[concepts/concept-x]]
- [[concepts/concept-y]]
```

### Q&A Articles (`knowledge/qa/`)

Filed answers from queries. Every complex question answered by the system can be permanently stored, making future queries smarter.

```markdown
---
title: "Q: Original Question"
question: "The exact question asked"
consulted:
  - "concepts/article-1"
  - "concepts/article-2"
filed: 2026-04-05
---

# Q: Original Question

## Answer

[The synthesized answer with [[wikilinks]] to sources]

## Sources Consulted

- [[concepts/article-1]] - Relevant because...
- [[concepts/article-2]] - Provided context on...

## Follow-Up Questions

- What about edge case X?
- How does this change if Y?
```

---

## Core Operations

### 1. Compile (daily/ -> knowledge/)

When processing a daily log:

1. Read the daily log file
2. Read `knowledge/index.md` to understand current knowledge state
3. Read existing articles that may need updating
4. For each piece of knowledge found in the log:
   - If an existing concept article covers this topic: UPDATE it with new information, add the daily log as a source
   - If it's a new topic: CREATE a new `concepts/` article
5. If the log reveals a non-obvious connection between 2+ existing concepts: CREATE a `connections/` article
6. UPDATE `knowledge/index.md` with new/modified entries
7. APPEND to `knowledge/log.md`

**Important guidelines:**
- A single daily log may touch 3-10 knowledge articles
- Prefer updating existing articles over creating near-duplicates
- Use Obsidian-style `[[wikilinks]]` with full relative paths from knowledge/
- Write in encyclopedia style - factual, concise, self-contained
- Every article must have YAML frontmatter
- Every article must link back to its source daily logs

### 2. Query (Ask the Knowledge Base)

1. Read `knowledge/index.md` (the master catalog)
2. Based on the question, identify 3-10 relevant articles from the index
3. Read those articles in full
4. Synthesize an answer with `[[wikilink]]` citations
5. If `--file-back` is specified: create a `knowledge/qa/` article and update index.md and log.md

**Why this works without RAG:** At personal knowledge base scale (50-500 articles), the LLM reading a structured index outperforms cosine similarity. The LLM understands what the question is really asking and selects pages accordingly. Embeddings find similar words; the LLM finds relevant concepts.

### 3. Lint (Health Checks)

Seven checks, run periodically:

1. **Broken links** - `[[wikilinks]]` pointing to non-existent articles
2. **Orphan pages** - Articles with zero inbound links from other articles
3. **Orphan sources** - Daily logs that haven't been compiled yet
4. **Stale articles** - Source daily log changed since article was last compiled
5. **Contradictions** - Conflicting claims across articles (requires LLM judgment)
6. **Missing backlinks** - A links to B but B doesn't link back to A
7. **Sparse articles** - Below 200 words, likely incomplete

Output: a markdown report with severity levels (error, warning, suggestion).

---

## Conventions

- **Wikilinks:** Use Obsidian-style `[[path/to/article]]` without `.md` extension
- **Writing style:** Encyclopedia-style, factual, third-person where appropriate
- **Dates:** ISO 8601 (YYYY-MM-DD for dates, full ISO for timestamps in log.md)
- **File naming:** lowercase, hyphens for spaces (e.g., `supabase-row-level-security.md`)
- **Frontmatter:** Every article must have YAML frontmatter with at minimum: title, sources, created, updated
- **Sources:** Always link back to the daily log(s) that contributed to an article

## Vault Path Resolution

The compiler supports an external local vault path. Resolution order:

1. `KB_VAULT_DIR` environment variable
2. `.codex/vault.local` file (single-line absolute or relative path)
3. Repository root (default)

All runtime content (`daily/`, `knowledge/`, `reports/`, and `.memory-compiler/`) is resolved inside the selected vault root.

---

## Full Project Structure

``` 
llm-personal-kb/
|-- .codex/
|   |-- config.toml                  # Enables Codex hooks + default model settings
|   |-- hooks.json                   # Repo-local hook configuration for Codex
|-- .gitignore                       # Excludes runtime state, temp files, caches
|-- AGENTS.md                        # This file - schema + full technical reference
|-- README.md                        # Concise overview + quick start
|-- pyproject.toml                   # Dependencies (at root so hooks can find it)
|-- daily/                           # "Source code" - conversation logs (immutable)
|-- knowledge/                       # "Executable" - compiled knowledge (LLM-owned)
|   |-- index.md                     #   Master catalog - THE retrieval mechanism
|   |-- log.md                       #   Append-only build log
|   |-- concepts/                    #   Atomic knowledge articles
|   |-- connections/                 #   Cross-cutting insights linking 2+ concepts
|   |-- qa/                          #   Filed query answers (compounding knowledge)
|-- scripts/                         # CLI tools
|   |-- compile.py                   #   Compile daily logs -> knowledge articles
|   |-- query.py                     #   Ask questions (index-guided, no RAG)
|   |-- lint.py                      #   7 health checks
|   |-- flush.py                     #   Extract memories from conversations (background)
|   |-- config.py                    #   Path constants
|   |-- utils.py                     #   Shared helpers
|   |-- llm.py                       #   Codex CLI non-interactive helper
|-- hooks/                           # Codex hooks
|   |-- session-start.py             #   Injects knowledge into every session
|   |-- stop.py                      #   Extracts conversation -> daily log at turn end
|-- reports/                         # Lint reports (gitignored)
```

---

## Hook System (Automatic Capture)

Codex discovers repo-local hooks in `.codex/hooks.json`. Hooks are currently behind a feature flag, enabled in `.codex/config.toml`. Per the current Codex docs, hooks are experimental and temporarily disabled on Windows.

### `.codex/config.toml`

```toml
model = "gpt-5.4"
model_reasoning_effort = "medium"

[features]
codex_hooks = true
```

### `.codex/hooks.json` Format

```json
{
  "hooks": {
    "SessionStart": [{ "matcher": "startup|resume", "hooks": [{ "type": "command", "command": "python3 hooks/session-start.py", "timeout": 15 }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "python3 hooks/stop.py", "timeout": 15 }] }]
  }
}
```

Repo-local hooks are preferable because they travel with the repository and keep behavior consistent across machines. The commands resolve from the git root so they still work when Codex is launched from a subdirectory.

### Hook Details

**`session-start.py`** (SessionStart)
- Pure local I/O, no API calls, runs in under 1 second
- Reads `knowledge/index.md` and the most recent daily log
- Outputs JSON to stdout: `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}`
- Codex sees the knowledge base index at the start of every session
- Max context: 20,000 characters

**`stop.py`** (Stop)
- Reads hook input from stdin (JSON with `session_id`, `turn_id`, `transcript_path`, `cwd`)
- Extracts a short trailing transcript window instead of waiting for session close
- Spawns `scripts/flush.py` as a background process
- Returns `{"continue": true}` so the current turn ends normally
- Recursion guard: exits immediately if `CODEX_INVOKED_BY` env var is set

**Why `Stop` instead of `SessionEnd` / `PreCompact`?** Codex currently exposes `Stop`, but not Claude-style `SessionEnd` or `PreCompact` hooks. Running memory extraction after each completed turn preserves the same architecture and intent: durable lessons are captured automatically without waiting for the session to close.

### Background Flush Process (`flush.py`)

Spawned by the `Stop` hook as a background process:
- **Windows:** `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` flags
- **Mac/Linux:** `start_new_session=True`

This ensures `flush.py` survives after the hook process exits.

**What flush.py does:**
1. Sets `CODEX_INVOKED_BY=memory_flush` env var (prevents recursive hook firing)
2. Reads the pre-extracted conversation context from the temp `.md` file
3. Skips if context is empty or if the same `session_id + turn_id` was flushed within 60 seconds
4. Reads the tail of today's daily log to reduce duplicate notes across adjacent turns
5. Calls `codex exec` through `scripts/llm.py`
6. Codex decides what's worth saving and returns structured notes or `FLUSH_OK`
7. Appends only non-empty, non-duplicate results to `daily/YYYY-MM-DD.md`
8. Cleans up temp context file
9. **Post-flush auto-compilation:** If today's daily log has changed since its last compilation (hash comparison against `state.json`), spawns `compile.py` as another detached background process. This means successful Codex flushes propagate into `knowledge/` without waiting for a cron job or end-of-day window.

### JSONL Transcript Format

Codex provides a `transcript_path` in hook input. The extractor is intentionally tolerant because transcript payloads can vary by runtime version. It handles both nested and flat JSONL shapes, including:

```python
entry = json.loads(line)
msg = entry.get("message", {})
role = msg.get("role", "")     # "user" or "assistant"
content = msg.get("content", "")  # string or list of content blocks
```

Content can be a string or a list of blocks (`{"type": "text", "text": "..."}` dicts).

---

## Script Details

### compile.py - The Compiler

Uses `codex exec` with a JSON schema for structured output:

```python
result = subprocess.run(
    [
        "codex", "exec", "--json", "--ephemeral",
        "--disable", "codex_hooks", "--sandbox", "read-only",
        "--output-schema", schema_path, "-"
    ],
    input=prompt_text,
)
```

- Builds a prompt with: AGENTS.md schema, current index, all existing articles, and the daily log
- The model returns a structured write plan instead of editing files directly
- `utils.apply_write_operations()` applies validated `write` / `append` operations locally
- Incremental: tracks SHA-256 hashes of daily logs in `state.json`, skips unchanged files
- Tracks token usage from Codex CLI's JSON events

**CLI:**
```bash
python3 scripts/compile.py              # compile new/changed only
python3 scripts/compile.py --all        # force recompile everything
python3 scripts/compile.py --file daily/2026-04-01.md
python3 scripts/compile.py --dry-run
```

### query.py - Index-Guided Retrieval

Loads the entire knowledge base into context (index + all articles). No RAG.

At personal KB scale (50-500 articles), the LLM reading a structured index outperforms vector similarity. The LLM understands what you're really asking; cosine similarity just finds similar words.

**CLI:**
```bash
python3 scripts/query.py "What auth patterns do I use?"
python3 scripts/query.py "What's my error handling strategy?" --file-back
```

With `--file-back`, the model returns both the answer and a structured write plan for the Q&A article, updated index, and build log entry. This is the compounding loop - every question makes the KB smarter.

### lint.py - Health Checks

Seven checks:

| Check | Type | Catches |
|-------|------|---------|
| Broken links | Structural | `[[wikilinks]]` to non-existent articles |
| Orphan pages | Structural | Articles with zero inbound links |
| Orphan sources | Structural | Daily logs not yet compiled |
| Stale articles | Structural | Source logs changed since compilation |
| Missing backlinks | Structural | A links to B but B doesn't link back |
| Sparse articles | Structural | Under 200 words |
| Contradictions | LLM | Conflicting claims across articles |

**CLI:**
```bash
python3 scripts/lint.py                    # all checks
python3 scripts/lint.py --structural-only  # skip LLM check (free)
```

Reports saved to `reports/lint-YYYY-MM-DD.md`.

---

## State Tracking

`.memory-compiler/state.json` tracks:
- `ingested` - map of daily log filenames to SHA-256 hashes, compilation timestamps, token usage, and model metadata
- `query_count` - total queries run
- `last_lint` - timestamp of most recent lint
- `total_input_tokens` / `total_output_tokens` / `total_tokens` - cumulative Codex CLI usage
- `total_cost` - cumulative best-effort cost estimate when the active model has a local price mapping

`.memory-compiler/last-flush.json` tracks flush deduplication (`session_id`, `turn_id`, `timestamp`).

Both are gitignored and regenerated automatically.

---

## Dependencies

`pyproject.toml` (at project root):
- `tzdata>=2024.1` - Timezone data
- Python 3.12+

No API key is required when the user is already authenticated in Codex CLI.
Runtime requirements:
- `codex` must be on `PATH`
- `codex login status` must report an active session
- Repo-local `.codex/config.toml` sets the default model and hook flag

`uv` is optional for development convenience, but the runtime path for hooks and scripts uses plain `python3`.

---

## Costs

This CLI-native port does not rely on direct API billing.

Operational usage now depends on:
- Your Codex account limits and login method
- The model selected in Codex config
- The size of `daily/`, `knowledge/`, and prompt context

The project records token usage from Codex CLI in `.memory-compiler/state.json`, but it does not attempt to compute API-style dollar costs.

---

## Customization

### Additional Article Types

Add directories like `people/`, `projects/`, `tools/` to `knowledge/`. Define the article format in this file (AGENTS.md) and update `utils.py`'s `list_wiki_articles()` to include them.

### Obsidian Integration

The knowledge base is pure markdown with `[[wikilinks]]` - works natively in Obsidian. Point a vault at `knowledge/` for graph view, backlinks, and search.

### Scaling Beyond Index-Guided Retrieval

At ~2,000+ articles / ~2M+ tokens, the index becomes too large for the context window. At that point, add hybrid RAG (keyword + semantic search) as a retrieval layer before the LLM. See Karpathy's recommendation of `qmd` by Tobi Lutke for search at scale.
