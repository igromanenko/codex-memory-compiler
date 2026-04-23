# Codex Memory Compiler

Build a wiki from Codex conversations. / Собирает вики-базу знаний из диалогов Codex.

This repository follows Andrej Karpathy's "LLM knowledge base" idea:
- `daily/` = raw source logs / сырой слой разговоров
- `knowledge/` = compiled wiki / скомпилированная вики
- `AGENTS.md` = compiler rules / правила компилятора

## Why This Exists / Зачем это нужно

- Work in Codex as usual. / Вы работаете в Codex как обычно.
- Important decisions and lessons are saved into daily logs. / Важные решения и выводы попадают в daily logs.
- Daily logs are compiled into reusable wiki pages. / Daily logs компилируются в wiki-страницы.
- New Codex sessions start with your current knowledge base. / Новые сессии Codex стартуют уже с вашей базой знаний.

## Two Modes / Два режима

### 1. Single Repo Mode / Режим "один репозиторий"

Use this when one repository is the whole project. / Используйте, если весь проект живет в одном репозитории.

- `daily/`, `knowledge/`, `reports/`, `.memory-compiler/` live inside this repo.
- Nothing else is required. / Ничего дополнительно подключать не нужно.

### 2. Shared Vault Mode / Режим "общий vault"

Use this when the product spans many repos. / Используйте, если система разбита на много репозиториев.

- This repo stays the compiler. / Этот репозиторий остается компилятором.
- Working repos get local `.codex/` hook files. / Рабочие репозитории получают свои `.codex/` hook-файлы.
- All of them write into one external vault. / Все они пишут в один внешний vault.
- The external vault works well as an Obsidian wiki. / Внешний vault удобно открывать как Obsidian-вики.

## Requirements / Требования

```bash
codex --version
codex login status
python3 --version
```

Need / Нужно:
- `codex` on `PATH`
- active Codex login / активный вход в Codex
- Python 3.12+

Optional / Опционально:

```bash
uv sync
```

or / или

```bash
python3 -m venv .venv
.venv/bin/pip install tzdata
```

`uv` is optional. Runtime hooks use plain `python3`. / `uv` необязателен. Runtime hooks работают через обычный `python3`.

## Quick Start / Быстрый старт

### Single Repo Mode / Один репозиторий

1. Clone this repo. / Клонируйте этот репозиторий.
2. Make sure Codex login works. / Проверьте, что Codex авторизован.
3. Open this repo in Codex. / Откройте этот репозиторий в Codex.
4. Work normally. Hooks save memory automatically. / Работайте как обычно. Hooks сохраняют память автоматически.

### Shared Vault Mode / Общий vault

1. Choose the vault path. / Выберите путь к vault.
2. Install repo-local hook files into every working repo. / Установите repo-local hooks во все рабочие репозитории.
3. Open any connected repo in Codex. / Открывайте любой подключенный репозиторий в Codex.
4. All sessions write into the same wiki. / Все сессии будут писать в одну вики.

Example / Пример:

```bash
python3 scripts/install_repo_hooks.py \
  --scan-dir /path/to/product-repos \
  --repo /path/to/infra-repo \
  --repo /path/to/api-repo \
  --repo /path/to/frontend-repo \
  --vault /path/to/shared-product-vault
```

That command:
- scans every git repo directly inside `/path/to/product-repos`
- also connects any extra repos listed with `--repo`
- writes `.codex/config.toml`, `.codex/hooks.json`, `.codex/vault.local`
- points all of them at one shared vault

## How It Works / Как это работает

```text
Codex session starts
-> SessionStart hook injects current wiki context
-> you work in the repo
-> Stop hook captures the last transcript window
-> flush.py writes durable notes into daily/YYYY-MM-DD.md
-> compile.py updates knowledge/
-> next session starts with the refreshed index and recent log
```

Main pieces / Основные части:
- `hooks/session-start.py` injects `knowledge/index.md` and the latest daily log tail.
- `hooks/stop.py` extracts recent transcript text and launches background flush.
- `scripts/flush.py` appends high-signal notes into `daily/`.
- `scripts/compile.py` turns daily logs into wiki pages.
- `scripts/query.py` answers questions from the wiki.
- `scripts/lint.py` checks wiki health.

## Main Commands / Основные команды

```bash
python3 scripts/compile.py
python3 scripts/compile.py --all
python3 scripts/query.py "What patterns do I use?"
python3 scripts/query.py "What patterns do I use?" --file-back
python3 scripts/lint.py
python3 scripts/install_repo_hooks.py --repo /path/to/repo --vault /path/to/vault
```

## Vault Resolution / Как выбирается vault

Priority / Приоритет:
1. `KB_VAULT_DIR`
2. `.codex/vault.local`
3. repository root / корень репозитория

For hooks installed into external repos, the compiler uses `KB_PROJECT_ROOT` to read that repo's local `.codex/vault.local`. / Для hooks, установленных в чужие репозитории, компилятор использует `KB_PROJECT_ROOT`, чтобы читать локальный `.codex/vault.local` именно того репозитория.

## Repository Map / Карта репозитория

```text
.codex/                     local Codex config / локальная конфигурация Codex
daily/                      raw conversation logs / сырые дневные логи
knowledge/                  compiled wiki / скомпилированная вики
hooks/                      SessionStart and Stop hooks / hooks SessionStart и Stop
scripts/                    compiler, query, lint, flush, installer / скрипты
reports/                    lint reports / отчеты lint
AGENTS.md                   compiler specification / спецификация компилятора
CODEX_USAGE.md              operator guide / практическая инструкция
```

## Open Next / Что открыть дальше

- [CODEX_USAGE.md](CODEX_USAGE.md) for step-by-step setup and operations. / Для пошаговой настройки и работы.
- [AGENTS.md](AGENTS.md) for the compiler rules and file formats. / Для правил компилятора и форматов файлов.
- [IDE_TROUBLESHOOTING.md](IDE_TROUBLESHOOTING.md) for local IDE refresh problems. / Для проблем с IDE и stale state.
