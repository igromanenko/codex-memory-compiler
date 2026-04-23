# IDE Troubleshooting / Проблемы IDE

This file is for stale local state: IDE refresh problems, old hook config, and confusing Codex behavior. / Этот файл для stale local state: проблем с обновлением IDE, старых hook-конфигов и странного поведения Codex.

## 1. `.codex` Is A File, Not A Directory / `.codex` оказался файлом, а не папкой

Symptom / Симптом:
- the repo has `.codex` as a zero-byte file
- Codex cannot read `.codex/config.toml` or `.codex/hooks.json`

Fix / Исправление:
- run the installer script again
- it replaces an empty `.codex` file with a real `.codex/` directory

```bash
python3 scripts/install_repo_hooks.py --repo /path/to/repo --vault /path/to/vault
```

If `.codex` is a non-empty file, move it away manually first. / Если `.codex` — непустой файл, сначала вручную уберите его.

## 2. IDE Shows Old Hook Commands / IDE показывает старые hook-команды

Symptom / Симптом:
- IDE still shows `uv run ...`
- IDE still shows old `.claude/...` references
- files look correct on disk, but the editor view is stale

Fix / Исправление:
- refresh the project in the IDE
- invalidate caches if needed
- reopen the repo window

The current runtime hook style is plain `python3`, not `uv run`. / Текущий runtime hook style использует обычный `python3`, а не `uv run`.

## 3. Codex Uses The Wrong Vault / Codex пишет не в тот vault

Check in this order / Проверяйте в таком порядке:
1. `KB_VAULT_DIR`
2. `.codex/vault.local`
3. the hook command's `KB_PROJECT_ROOT`

For connected external repos, the hook command should look like this:

```bash
env KB_PROJECT_ROOT=/path/to/repo python3 /path/to/codex-memory-compiler/hooks/stop.py
```

## 4. Hooks Exist But Nothing Is Saved / Hooks есть, но ничего не сохраняется

Check / Проверьте:

```bash
codex login status
```

Then inspect the active vault logs:

```bash
ls -la /path/to/vault/.memory-compiler
tail -n 50 /path/to/vault/.memory-compiler/flush.log
```

Typical causes / Типичные причины:
- Codex is not logged in / Codex не залогинен
- the hook is pointed at the wrong project root / hook указывает не на тот project root
- the vault path is wrong / неверный путь vault
- the transcript window was empty / окно транскрипта оказалось пустым

## 5. SessionStart Does Not Inject Context / SessionStart не подмешивает контекст

Run manually / Запустите вручную:

```bash
python3 hooks/session-start.py
```

Expected / Ожидается:
- valid JSON on stdout
- no traceback

If it works manually but not inside Codex, refresh the repo and reopen the session. / Если вручную работает, а внутри Codex нет — обновите проект и переоткройте сессию.

## 6. Background Flush Or Compile Looks Stuck / Flush или compile зависли в фоне

Check the active vault state directory:

```bash
ls -la /path/to/vault/.memory-compiler
tail -n 100 /path/to/vault/.memory-compiler/flush.log
tail -n 100 /path/to/vault/.memory-compiler/compile.log
```

Useful signals / Полезные сигналы:
- `Stop fired`
- `Spawned flush.py`
- `Result: saved to daily log`
- `Post-flush compilation triggered`

## 7. Reinstall Everything Cleanly / Переустановить всё начисто

If hook files drifted, just reinstall them from this compiler repo:

```bash
python3 scripts/install_repo_hooks.py \
  --scan-dir /path/to/parent \
  --repo /path/to/extra-repo \
  --vault /path/to/shared-vault
```

That is the preferred recovery path. / Это и есть предпочтительный способ восстановления.
