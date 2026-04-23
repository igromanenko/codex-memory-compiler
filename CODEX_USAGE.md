# Using This Project With Codex

This guide explains how to run the memory compiler through Codex CLI, what parts are automatic, and what to do when something goes wrong.

## What This Project Does

The project turns Codex conversations into a personal markdown knowledge base.

It keeps the original three-layer architecture:

- `daily/` is the raw source layer. It stores append-only daily notes extracted from conversations.
- `knowledge/` is the compiled layer. It stores structured concept, connection, and Q&A articles.
- `AGENTS.md` is the compiler spec. It tells the model how to structure articles, logs, and lint rules.

In practice the loop is:

```text
Codex session starts
-> SessionStart hook injects index + recent log
-> you work normally in Codex
-> Stop hook captures recent transcript
-> flush.py appends durable notes into daily/YYYY-MM-DD.md
-> compile.py turns daily logs into knowledge articles
-> query.py and lint.py operate on the compiled knowledge base
```

## Requirements

You need:

- `codex` installed and available on `PATH`
- an active Codex login
- `python3` available on `PATH`

Check that first:

```bash
codex --version
codex login status
python3 --version
```

If `uv` is not installed, that is not a blocker. A plain virtualenv is enough:

```bash
python3 -m venv .venv
.venv/bin/pip install tzdata
```

If `codex login status` does not say `Logged in`, run:

```bash
codex login
```

## Important Runtime Rule

The project is designed to work in Codex CLI mode without `OPENAI_API_KEY`.

All model-backed operations go through non-interactive `codex exec`, not through the OpenAI API SDK. That means:

- no API key is needed
- your Codex account limits still apply
- if Codex is rate-limited, `compile/query/lint/flush` can fail until the limit resets

## Use A Personal Vault Directory

By default, this repository acts as the vault root. To store knowledge in another local path (for example a project vault), set one of these overrides:

1. Local override file in this repo:

```bash
echo "/home/i/projects/project1/project1_vault" > .codex/vault.local
```

2. Environment variable:

```bash
export KB_VAULT_DIR=/home/i/projects/project1/project1_vault
```

Override priority is:

1. `KB_VAULT_DIR`
2. `.codex/vault.local`
3. repository root (default)

With an override, runtime data goes to that vault path:

- `daily/`
- `knowledge/`
- `reports/`
- `.memory-compiler/` (state + logs)

## Hook Configuration

Repo-local hook config lives in:

- [`.codex/config.toml`](/home/i/IdeaProjects/codex-memory-compiler/.codex/config.toml)
- [`.codex/hooks.json`](/home/i/IdeaProjects/codex-memory-compiler/.codex/hooks.json)

Current hook commands are intentionally simple:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python3 hooks/session-start.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 hooks/stop.py"
          }
        ]
      }
    ]
  }
}
```

This is deliberate:

- it avoids `uv` at runtime
- it avoids shell substitutions like `$(git rev-parse ...)`
- it reduces the chance of hook startup failures such as exit code `127`

## Automatic Parts

### SessionStart

[hooks/session-start.py](/home/i/IdeaProjects/codex-memory-compiler/hooks/session-start.py) runs when Codex starts or resumes a session.

It:

- reads `knowledge/index.md` if it exists
- reads the tail of the most recent daily log
- returns JSON that Codex can inject into the model context

If the knowledge base is empty, SessionStart still succeeds and simply injects an empty-state context.

### Stop

[hooks/stop.py](/home/i/IdeaProjects/codex-memory-compiler/hooks/stop.py) runs after each completed turn.

It:

- reads the transcript path provided by Codex
- extracts a small recent window of user/assistant turns
- writes a temporary markdown context file into `scripts/`
- spawns `scripts/flush.py` as a detached background process
- returns `{"continue": true}` so the Codex turn finishes normally

The detach matters. Without it, `flush.py` can die together with the hook process before memory is written.

### Background Flush

[scripts/flush.py](/home/i/IdeaProjects/codex-memory-compiler/scripts/flush.py) runs in the background.

It:

- deduplicates repeated flushes for the same `session_id + turn_id`
- reads the tail of today's daily log to avoid adding the same memory twice
- runs `codex exec`
- appends durable notes into `daily/YYYY-MM-DD.md`
- after the configured hour, may trigger `compile.py` automatically

If `flush.py` succeeds, the temporary `stop-flush-...md` file is deleted. If one remains behind, the background process likely never finished.

## Manual Commands

You can run everything manually without relying on hooks.

### Compile

```bash
python3 scripts/compile.py
python3 scripts/compile.py --all
python3 scripts/compile.py --file daily/2026-04-23.md
python3 scripts/compile.py --dry-run
```

Use compile when:

- you added or edited a daily log
- auto-compilation has not happened yet
- you want to rebuild after changing article guidance in `AGENTS.md`

### Query

```bash
python3 scripts/query.py "What patterns do I use for auth?"
python3 scripts/query.py "How are daily logs used in this project?" --file-back
```

`--file-back` does two things on success:

- answers your question
- creates a Q&A article in `knowledge/qa/`, updates `knowledge/index.md`, and appends to `knowledge/log.md`

If the model call fails, the script now reports that the answer was not filed.

### Lint

```bash
python3 scripts/lint.py
python3 scripts/lint.py --structural-only
```

Use `--structural-only` when:

- you want a fast free check
- your Codex usage is low
- you only care about broken links, orphans, staleness, backlinks, and sparse pages

Use full lint when:

- you want contradiction detection
- you want the most realistic health check of the knowledge base

## How Retrieval Works

This project is intentionally not RAG-first.

The model reads:

1. `knowledge/index.md`
2. the relevant articles from `knowledge/concepts/`, `knowledge/connections/`, and `knowledge/qa/`
3. then synthesizes an answer

This works well at personal-KB scale because the index is small and semantically rich.

## How Writes Are Kept Safe

The model does not edit files directly.

Instead:

- `compile.py` and `query.py --file-back` ask Codex for a structured JSON write plan
- `scripts/utils.py` validates the operations
- writes are restricted to `knowledge/`

That protects the repository from accidental model-generated writes outside the knowledge base.

## Day-To-Day Workflow

A practical workflow is:

1. Open the repo in Codex.
2. Let SessionStart inject the current knowledge base.
3. Work normally.
4. Let Stop/flush append durable notes automatically.
5. Run `python3 scripts/compile.py` when you want those notes turned into articles.
6. Ask questions through `python3 scripts/query.py`.
7. Run `python3 scripts/lint.py` periodically.

## Verification Commands

If you want to confirm the installation is healthy:

```bash
python3 -m py_compile scripts/*.py hooks/*.py
python3 -m unittest discover -s tests -v
python3 hooks/session-start.py
python3 scripts/query.py "What retrieval approach does this knowledge base prefer?"
```

If you want to simulate a Stop hook manually:

```bash
cat >/tmp/sample-transcript.jsonl <<'EOF'
{"message":{"role":"user","content":"Remember that this project runs through Codex CLI."}}
{"message":{"role":"assistant","content":"I will preserve that as a durable note if it is worth saving."}}
EOF

printf '{"session_id":"manual-test","turn_id":"manual-turn","transcript_path":"/tmp/sample-transcript.jsonl"}' \
  | python3 hooks/stop.py
```

Then inspect:

- `scripts/flush.log`
- today's file in `daily/`

## Troubleshooting

### `SessionStart hook (failed) error: hook exited with code 127`

This usually means the hook command referenced something that is not installed or not on `PATH`.

This project now uses:

```text
python3 hooks/session-start.py
python3 hooks/stop.py
```

So check:

```bash
python3 --version
python3 hooks/session-start.py
```

### `codex exec` says you hit your usage limit

The project is healthy, but Codex is temporarily refusing model work.

What still works:

- SessionStart local context assembly
- structural lint
- local file inspection

What waits for limit reset:

- compile
- query
- file-back
- contradiction lint
- flush extraction

### A `stop-flush-...md` file stays in `scripts/`

That means `flush.py` did not complete.

Check:

- `scripts/flush.log`
- `codex login status`
- whether Codex is rate-limited

### `knowledge/qa/` did not get a new file after `--file-back`

That means the model call failed or was interrupted before write-back.

Re-run the command and inspect the printed error. The script now explicitly tells you whether the answer was filed.

### Hooks do not fire on Windows

Current Codex docs say hooks are experimental and temporarily disabled on Windows. In that environment, use the scripts manually.

## Files Worth Knowing

- [README.md](/home/i/IdeaProjects/codex-memory-compiler/README.md): short project overview
- [AGENTS.md](/home/i/IdeaProjects/codex-memory-compiler/AGENTS.md): compiler spec and deep technical reference
- [scripts/llm.py](/home/i/IdeaProjects/codex-memory-compiler/scripts/llm.py): non-interactive Codex CLI bridge
- [scripts/flush.py](/home/i/IdeaProjects/codex-memory-compiler/scripts/flush.py): memory extraction + auto-compile trigger
- [hooks/session-start.py](/home/i/IdeaProjects/codex-memory-compiler/hooks/session-start.py): context injection
- [hooks/stop.py](/home/i/IdeaProjects/codex-memory-compiler/hooks/stop.py): transcript capture and detached flush launch

## Operational Notes

- `daily/` and `knowledge/` are gitignored in this repo because they are user-specific generated state.
- The project works even if those directories do not exist yet; they are created lazily as needed.
- `uv` is optional. It is useful for development hygiene, but the runtime path intentionally uses plain `python3`.
- The model used for `codex exec` is controlled by `.codex/config.toml` or your Codex config.

If you need implementation details rather than operator instructions, use [AGENTS.md](/home/i/IdeaProjects/codex-memory-compiler/AGENTS.md).
