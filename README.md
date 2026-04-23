# Codex Memory Compiler

**Your Codex conversations compile themselves into a searchable knowledge base.**

This project keeps Karpathy's LLM knowledge-base architecture intact, but adapts the implementation for Codex CLI. Raw session history lands in `daily/`, structured knowledge is compiled into `knowledge/`, and retrieval stays index-guided rather than embedding-driven. The integration layer is fully CLI-native: Codex hooks drive capture, and the Python scripts call `codex exec` non-interactively instead of using an API SDK.

## What Changed For Codex CLI

- `AGENTS.md` remains the compiler spec and repository operating manual. Codex reads it natively.
- `.codex/hooks.json` replaces `.claude/settings.json`.
- Codex `SessionStart` still injects the knowledge base into new sessions.
- Codex has no `SessionEnd` or `PreCompact` hook today, so automatic memory capture runs from the `Stop` hook after each completed turn.
- `scripts/compile.py`, `scripts/query.py`, `scripts/lint.py`, and `scripts/flush.py` use `codex exec` as their LLM backend.
- No `OPENAI_API_KEY` is required when you are already logged into Codex CLI.

## Quick Start

1. Make sure Codex CLI is installed and authenticated:

```bash
codex --version
codex login status
```

2. Runtime dependencies are minimal. If you want an isolated environment for development, use either:

```bash
uv sync
```

or:

```bash
python3 -m venv .venv
.venv/bin/pip install tzdata
```

3. Open the repository in Codex. Repo-local `.codex/config.toml` enables hooks, and `.codex/hooks.json` registers `SessionStart` and `Stop`.

From there, each completed Codex turn can contribute durable notes to `daily/YYYY-MM-DD.md`. After `COMPILE_AFTER_HOUR` in `scripts/flush.py` (default `18` local time), the next successful flush triggers automatic compilation of that day's log.

## How It Works

```text
Codex turn -> Stop hook -> flush.py extracts durable notes
           -> daily/YYYY-MM-DD.md -> compile.py -> knowledge/concepts/, connections/, qa/
SessionStart hook -> inject index + recent log into next Codex session
```

- `hooks/session-start.py` injects `knowledge/index.md` plus the tail of the most recent daily log.
- `hooks/stop.py` extracts the latest transcript window and spawns `scripts/flush.py` in the background.
- `scripts/flush.py` runs `codex exec` to decide what is worth preserving and appends only new, high-signal notes.
- `scripts/compile.py` turns daily logs into structured concept and connection articles.
- `scripts/query.py` answers questions using index-guided retrieval and can file answers back into `knowledge/qa/`.
- `scripts/lint.py` runs structural checks and an optional contradiction pass.

## Key Commands

```bash
python3 scripts/compile.py
python3 scripts/compile.py --all
python3 scripts/query.py "What auth patterns do I use?"
python3 scripts/query.py "What auth patterns do I use?" --file-back
python3 scripts/lint.py
python3 scripts/lint.py --structural-only
```

## Environment

- Python 3.12+
- `codex` on `PATH`
- Active Codex login session via `codex login`

`uv` is optional and only useful if you want a managed virtualenv for development or test runs.

The project defaults to the model configured in `.codex/config.toml`, or whatever `codex exec` resolves in your local Codex setup.

## Custom Vault Path

By default, the vault is the repository root. You can point the compiler to a personal vault directory in two ways:

1. Local file override (recommended for per-repo setup):

```bash
echo "/home/i/projects/project1/project1_vault" > .codex/vault.local
```

2. Environment override:

```bash
export KB_VAULT_DIR=/home/i/projects/project1/project1_vault
```

When set, the scripts and hooks read/write `daily/`, `knowledge/`, `reports/`, and `.memory-compiler/` inside that vault path.

## Limitations

- Codex hooks are currently experimental.
- OpenAI's Codex hooks docs currently state that hooks are temporarily disabled on Windows.
- Because Codex does not expose `SessionEnd` or `PreCompact`, this port captures memory at `Stop` time instead.

## Technical Reference

See **[AGENTS.md](AGENTS.md)** for the full compiler specification: article formats, hook architecture, daily log schema, query/file-back behavior, lint checks, and customization points.

For an operator-focused guide on setup, hooks, commands, troubleshooting, and Codex-specific nuances, see **[CODEX_USAGE.md](CODEX_USAGE.md)**.

For IntelliJ IDEA / PyCharm refresh issues, stale diffs, and old hook-state problems, see **[IDE_TROUBLESHOOTING.md](IDE_TROUBLESHOOTING.md)**.
