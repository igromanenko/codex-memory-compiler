# IDE Troubleshooting

This guide covers the most common IDE-side problems when working with this repository in Codex and IntelliJ IDEA / PyCharm.

## What This Guide Is For

Use this guide when the repository on disk is correct, but the IDE shows stale files, missing files, empty diffs, or old hook errors.

Typical symptoms:

- the project tree still shows deleted files like `hooks/pre-compact.py`
- new files such as `.codex/hooks.json`, `hooks/stop.py`, `CODEX_USAGE.md`, or tests do not appear
- the commit tool window shows a file, but the diff preview is blank
- Codex shows an old hook error such as `SessionStart hook (failed) code 127` even after the hook command was fixed

## Current Expected Repository State

The Codex-native version of the project should include:

- `.codex/config.toml`
- `.codex/hooks.json`
- `hooks/session-start.py`
- `hooks/stop.py`
- `scripts/llm.py`
- `CODEX_USAGE.md`

The Claude-specific hook setup should no longer be used.

## Current Expected Hook Commands

The active hook commands are:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "command": "python3 hooks/session-start.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "command": "python3 hooks/stop.py"
          }
        ]
      }
    ]
  }
}
```

If your IDE or Codex still behaves as if hooks are running through `uv` or `.claude/settings.json`, you are almost certainly looking at stale state.

## First Things To Try

### 1. Synchronize the IDE

In IntelliJ IDEA:

- `File -> Synchronize`
- shortcut: `Ctrl+Alt+Y`

This forces the IDE to refresh the virtual file system from disk.

### 2. Reopen the Project

Close the project and open it again from the real repository path:

```text
/home/i/IdeaProjects/codex-memory-compiler
```

This matters if the IDE has cached an older tree or attached an editor tab to a deleted file revision.

### 3. Restart the IDE

If the tree and commit window still disagree:

- close IntelliJ IDEA completely
- reopen the project

### 4. Invalidate Caches

If the tree still shows deleted files or blank diffs:

- `File -> Invalidate Caches / Restart`
- choose invalidate and restart

This is the heavy reset for broken IDEA file-index state.

## If The Project Tree Looks Wrong

If the project tree still shows old files:

- confirm the real files on disk with a terminal
- compare that with the tree in the IDE

Useful commands:

```bash
pwd
find . -maxdepth 3 -type f | sort
git status --short
```

If the terminal shows the right files and the IDE does not, the problem is IDE refresh, not repository state.

## If The Diff Preview Is Blank

This usually means the IDE commit UI is holding onto stale document state.

Try this sequence:

1. close the diff tab
2. run `File -> Synchronize`
3. reopen the changed file from the commit pane
4. if still blank, restart the IDE

If needed, verify the diff in terminal:

```bash
git diff -- README.md
git diff -- CODEX_USAGE.md
git diff -- .codex/hooks.json
```

If terminal diff is present but the IDE pane is empty, the repository is fine and the UI cache is stale.

## If Codex Still Reports Hook Exit Code 127

Code `127` usually means `command not found`.

For this repository, that typically means Codex is still trying to execute an old hook command such as:

- `uv run ...`
- a command from `.claude/settings.json`
- a shell command that depends on expansion not available in the current hook runner

The fixed commands are plain `python3` commands:

```bash
python3 hooks/session-start.py
python3 hooks/stop.py
```

Verify them manually:

```bash
python3 hooks/session-start.py
printf '{"session_id":"manual-test","turn_id":"manual-turn","transcript_path":"/tmp/nope.jsonl"}' | python3 hooks/stop.py
```

If those work in terminal but Codex still shows code `127`, restart Codex so it reloads `.codex/hooks.json`.

## Why `.idea/` Is Ignored

Local JetBrains files are machine-specific and often cause noise in the commit panel.

This repository ignores:

```text
.idea/
```

That keeps the commit view focused on actual project files instead of editor metadata.

## Sanity Check Commands

If you want to verify the project state quickly:

```bash
python3 -m py_compile scripts/*.py hooks/*.py
python3 -m unittest discover -s tests -v
python3 hooks/session-start.py
python3 scripts/query.py "What retrieval approach does this knowledge base prefer?"
```

## If You Need The Deeper Technical Explanation

Use:

- [README.md](/home/i/IdeaProjects/codex-memory-compiler/README.md)
- [CODEX_USAGE.md](/home/i/IdeaProjects/codex-memory-compiler/CODEX_USAGE.md)
- [AGENTS.md](/home/i/IdeaProjects/codex-memory-compiler/AGENTS.md)
