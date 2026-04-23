# Codex Usage / Работа с Codex

This file is the practical operator guide. / Это практическая инструкция для запуска и ежедневной работы.

## 1. What You Need / Что нужно

Required / Обязательно:

```bash
codex --version
codex login status
python3 --version
```

Expected / Ожидается:
- `codex login status` says `Logged in`
- Python 3.12+
- Linux or macOS preferred

Optional / Опционально:

```bash
uv sync
```

or / или

```bash
python3 -m venv .venv
.venv/bin/pip install tzdata
```

The runtime path does not depend on `uv`. / Runtime-путь не зависит от `uv`.

## 2. Choose Your Storage Mode / Выберите режим хранения

### Mode A: Local Repo Storage / Локальное хранение в репозитории

Use this when one repo is one project. / Используйте, если один репозиторий и есть весь проект.

Behavior / Поведение:
- `daily/`, `knowledge/`, `reports/`, `.memory-compiler/` stay in this repo
- no external vault is needed / внешний vault не нужен

### Mode B: Shared External Vault / Общий внешний vault

Use this when many repos belong to one system. / Используйте, если система состоит из многих репозиториев.

Behavior / Поведение:
- this repo stays the compiler / этот репозиторий остается компилятором
- working repos only get `.codex/` files / рабочие репозитории получают только `.codex/`
- all knowledge is stored in one external vault / все знания хранятся в одном внешнем vault

## 3. Manual Setup For One Repo / Ручная настройка для одного репозитория

If you want the default local mode, you only need this repo itself. / Если нужен локальный режим по умолчанию, достаточно этого репозитория.

Open it in Codex and keep these files enabled:
- `.codex/config.toml`
- `.codex/hooks.json`

Current runtime hooks are plain commands:

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

## 4. Mass Setup For Many Repos / Массовая настройка для многих репозиториев

Use the installer script. / Используйте installer script.

### Generic Example / Общий пример

```bash
python3 scripts/install_repo_hooks.py \
  --scan-dir /path/to/parent-with-many-repos \
  --repo /path/to/extra-repo-1 \
  --repo /path/to/extra-repo-2 \
  --vault /path/to/shared-vault
```

What it does / Что он делает:
- scans immediate child repos from `--scan-dir`
- adds explicit repos from `--repo`
- creates `.codex/config.toml`
- creates `.codex/hooks.json`
- writes `.codex/vault.local` if `--vault` is passed
- replaces old empty `.codex` placeholder files with a real `.codex/` directory

### Multi-Repo Product Example / Пример для multi-repo продукта

```bash
python3 scripts/install_repo_hooks.py \
  --scan-dir /path/to/product-repos \
  --repo /path/to/local-cluster-repo \
  --repo /path/to/legacy-backend-repo \
  --repo /path/to/api-repo \
  --repo /path/to/infra-repo \
  --repo /path/to/service-repo \
  --vault /path/to/shared-product-vault
```

This connects:
- all git repos directly inside `/path/to/product-repos`
- one local cluster repo
- any extra backend, API, infra, or service repos listed with `--repo`
- one shared external vault for the whole product

## 5. How Hook Routing Works / Как работает маршрутизация hooks

The installer writes hook commands that point back to this compiler repo. / Installer пишет hook-команды, которые указывают обратно на этот compiler repo.

Example shape / Общая форма:

```bash
env KB_PROJECT_ROOT=/path/to/work-repo python3 /path/to/codex-memory-compiler/hooks/stop.py
```

Important detail / Важная деталь:
- `KB_PROJECT_ROOT` tells the compiler which repo's `.codex/vault.local` should be used
- this allows one compiler repo to serve many work repos safely

## 6. What Happens During A Session / Что происходит во время сессии

### SessionStart

- reads `knowledge/index.md`
- reads the tail of the latest daily log
- injects both into the new Codex session

### Stop

- reads recent transcript lines
- writes a temporary context file
- launches `flush.py` in the background
- never blocks the user turn on purpose

### Flush

- deduplicates repeated turns
- asks `codex exec` what is worth saving
- appends durable notes into `daily/YYYY-MM-DD.md`
- triggers `compile.py` if today's daily log changed

### Compile

- updates `knowledge/index.md`
- creates or updates `knowledge/concepts/`
- creates `knowledge/connections/` when needed
- appends to `knowledge/log.md`

## 7. Daily Workflow / Ежедневный workflow

1. Open any connected repo in Codex. / Откройте любой подключенный репозиторий в Codex.
2. Work normally. / Работайте как обычно.
3. Let Stop hook capture durable knowledge. / Stop hook сам сохранит важные знания.
4. Open the vault in Obsidian if you want to browse the wiki. / При желании откройте vault в Obsidian.
5. Run manual commands when you need direct control. / При необходимости запускайте ручные команды.

## 8. Manual Commands / Ручные команды

### Compile / Компиляция

```bash
python3 scripts/compile.py
python3 scripts/compile.py --all
python3 scripts/compile.py --file daily/2026-04-23.md
python3 scripts/compile.py --dry-run
```

### Query / Запрос к базе знаний

```bash
python3 scripts/query.py "What auth patterns do I use?"
python3 scripts/query.py "What auth patterns do I use?" --file-back
```

### Lint / Проверка целостности

```bash
python3 scripts/lint.py
python3 scripts/lint.py --structural-only
```

### Reinstall Hooks / Переустановить hooks

```bash
python3 scripts/install_repo_hooks.py --repo /path/to/repo --vault /path/to/vault
```

## 9. Vault Resolution / Как выбирается vault

Priority / Приоритет:
1. `KB_VAULT_DIR`
2. `.codex/vault.local` under `KB_PROJECT_ROOT`
3. current compiler repo root

Use cases / Сценарии:
- one repo only -> do nothing, local storage is fine
- many repos, one wiki -> use `.codex/vault.local` in each connected repo
- temporary override -> use `KB_VAULT_DIR`

## 10. Health Check / Быстрая проверка установки

Run / Запустите:

```bash
python3 hooks/session-start.py
python3 scripts/compile.py --dry-run
python3 scripts/lint.py --structural-only
```

Look for / Что проверить:
- `session-start.py` returns JSON
- `compile.py --dry-run` sees daily logs correctly
- `lint.py` finishes without path errors

For a connected external repo, also check that its `.codex/` files exist:

```bash
ls -la /path/to/repo/.codex
```

## 11. Common Problems / Частые проблемы

### `.codex` is a file, not a directory / `.codex` оказался файлом, а не папкой

The installer handles empty placeholder files automatically. / Installer автоматически заменяет пустой placeholder-файл.

If it is a non-empty file, move it away first. / Если это непустой файл, сначала вручную уберите его.

### Hooks run but nothing is saved / Hooks отрабатывают, но ничего не сохраняется

Check:
- `codex login status`
- vault path in `.codex/vault.local`
- `.memory-compiler/flush.log` inside the active vault

### The wrong vault is used / Используется не тот vault

Check:
- `KB_VAULT_DIR`
- repo-local `.codex/vault.local`
- hook command contains the correct `KB_PROJECT_ROOT`

### `uv` is missing / Нет `uv`

This is not a blocker. / Это не блокер.

Use plain Python:

```bash
python3 -m venv .venv
.venv/bin/pip install tzdata
```

## 12. Recommended Structure For Teams / Рекомендуемая схема для команд

- keep this repo as the shared compiler / держите этот репозиторий как общий compiler
- keep one external vault per product / держите один внешний vault на продукт
- connect every work repo with `install_repo_hooks.py` / подключайте все рабочие репозитории через installer
- open the vault in Obsidian for browsing / открывайте vault в Obsidian для навигации
- keep `daily/` append-only / храните `daily/` как append-only слой
- let `knowledge/` be the long-term wiki / используйте `knowledge/` как долгоживущую вики
