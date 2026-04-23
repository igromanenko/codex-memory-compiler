# AGENTS.md - Codex Memory Compiler Spec / Спецификация компилятора

This file is both the compiler contract for Codex and the human-readable schema of the knowledge base. / Этот файл одновременно является контрактом для Codex и человекочитаемой схемой базы знаний.

The project follows the personal knowledge-base idea popularized by Andrej Karpathy:
- conversations become source logs / разговоры становятся исходным сырьем
- the model compiles them into structured wiki pages / модель компилирует их в структурированные wiki-страницы
- future sessions start with the compiled knowledge / будущие сессии стартуют уже с накопленным знанием

## 1. Goal / Цель

Build a durable markdown wiki from real Codex work sessions. / Построить долговечную markdown-вики из реальных рабочих сессий Codex.

The system should:
- preserve important project context / сохранять важный проектный контекст
- avoid duplicate notes / избегать дублей
- keep raw logs separate from compiled knowledge / отделять сырые логи от скомпилированного знания
- work both for one repo and for many repos connected to one vault / работать и для одного репозитория, и для многих репозиториев с общим vault

## 2. Two Supported Modes / Два поддерживаемых режима

### Single Repo Mode / Режим одного репозитория

Use this when one repo is the whole project. / Используйте, когда один репозиторий и есть весь проект.

- Vault root defaults to this repository root. / Корень vault по умолчанию совпадает с корнем этого репозитория.
- `daily/`, `knowledge/`, `reports/`, `.memory-compiler/` live here.

### Shared Vault Mode / Режим общего vault

Use this when many repos belong to one product. / Используйте, когда продукт состоит из многих репозиториев.

- This repo stays the compiler implementation. / Этот репозиторий остается реализацией компилятора.
- Work repos get repo-local `.codex/` hook files. / Рабочие репозитории получают локальные `.codex/` hook-файлы.
- All work repos write into one external vault. / Все рабочие репозитории пишут в один внешний vault.
- The external vault can be opened in Obsidian. / Внешний vault можно открыть в Obsidian.

## 3. Path Resolution / Разрешение путей

### Compiler root / Корень компилятора

The compiler code always lives in this repository. / Код компилятора всегда живет в этом репозитории.

### Project root / Корень проекта

The active project root is:
1. `KB_PROJECT_ROOT` if provided
2. otherwise this compiler repo root

This is important for shared-vault mode. / Это важно для режима общего vault.

When hooks are installed into an external repo, the hook command sets:

```bash
env KB_PROJECT_ROOT=/path/to/work-repo python3 /path/to/codex-memory-compiler/hooks/stop.py
```

That lets one compiler serve many repos safely. / Это позволяет одному compiler repo безопасно обслуживать много репозиториев.

### Vault root / Корень vault

Priority / Приоритет:
1. `KB_VAULT_DIR`
2. `.codex/vault.local` inside the active project root
3. active project root itself

All runtime content is resolved inside the selected vault root:
- `daily/`
- `knowledge/`
- `reports/`
- `.memory-compiler/`

## 4. Repository Layout / Структура репозитория

```text
.codex/                         Codex config / конфигурация Codex
daily/                          append-only source logs / append-only дневные логи
knowledge/
  index.md                      master catalog / главный каталог
  log.md                        build log / журнал сборки
  concepts/                     atomic pages / атомарные статьи
  connections/                  cross-topic pages / связи между темами
  qa/                           filed answers / сохраненные ответы
hooks/
  session-start.py              inject wiki context / подмешивает контекст вики
  stop.py                       captures transcript window / ловит хвост транскрипта
scripts/
  compile.py                    daily -> knowledge
  query.py                      answer from wiki
  lint.py                       health checks
  flush.py                      extract durable notes from transcript
  config.py                     path and vault resolution
  llm.py                        non-interactive codex exec wrapper
  install_repo_hooks.py         mass installer for external repos
reports/                        lint outputs / отчеты lint
```

## 5. Core Data Model / Базовая модель данных

### `daily/` = source code / исходники

Daily logs are append-only session notes extracted from real Codex work. / Daily logs — это append-only заметки из реальных сессий Codex.

Format / Формат:

```markdown
# Daily Log: YYYY-MM-DD

## Sessions

### Session (HH:MM)

**Context:** What the user was doing.

**Key Exchanges:**
- Important request or explanation

**Decisions Made:**
- Decision with reason

**Lessons Learned:**
- Durable insight or gotcha

**Action Items:**
- [ ] Optional follow-up
```

Rules / Правила:
- append-only / только дописываем
- no cleanup rewriting unless there is a real corruption / не переписываем задним числом без реальной причины
- keep only high-signal facts / сохраняем только высокосигнальные факты

### `knowledge/` = compiled wiki / скомпилированная вики

This is the durable knowledge layer. / Это долговременный слой знаний.

Humans may read it, but the compiler owns its structure. / Люди могут читать его, но структурой управляет компилятор.

## 6. Knowledge Article Types / Типы статей

### 6.1 `knowledge/index.md`

The master catalog. / Главный каталог.

It is the first file read during retrieval. / Это первый файл, который читается при поиске ответа.

Format / Формат:

```markdown
# Knowledge Base Index

| Article | Summary | Compiled From | Updated |
|---------|---------|---------------|---------|
| [[concepts/auth]] | Auth flow and token caveats | daily/2026-04-20.md | 2026-04-20 |
```

### 6.2 `knowledge/log.md`

Append-only build log for compile/query/lint activity. / Append-only журнал compile/query/lint операций.

Format / Формат:

```markdown
# Build Log

## [2026-04-20T14:30:00+03:00] compile | 2026-04-20.md
- Source: daily/2026-04-20.md
- Articles created: [[concepts/auth]]
- Articles updated: (none)
```

### 6.3 Concept pages / Концепты

One atomic idea per file. / Один атомарный кусок знания на файл.

Typical content / Типичное содержание:
- architecture facts / факты об архитектуре
- repo ownership / распределение ответственности
- debugging lessons / уроки после отладки
- preferences and patterns / рабочие паттерны и предпочтения

Format / Формат:

```markdown
---
title: "Concept Name"
aliases: [short-name]
tags: [domain, topic]
sources:
  - "daily/2026-04-20.md"
created: 2026-04-20
updated: 2026-04-20
---

# Concept Name

Short explanation.

## Key Points

- Self-contained point

## Details

Longer explanation.

## Related Concepts

- [[concepts/other-concept]] - relation

## Sources

- [[daily/2026-04-20.md]] - origin
```

### 6.4 Connection pages / Связи

Create these when one session reveals a non-obvious relationship between two or more concepts. / Создавайте их, когда сессия показывает неочевидную связь между двумя или более концептами.

Format / Формат:

```markdown
---
title: "Connection: X and Y"
connects:
  - "concepts/x"
  - "concepts/y"
sources:
  - "daily/2026-04-20.md"
created: 2026-04-20
updated: 2026-04-20
---

# Connection: X and Y

## The Connection

What links them.

## Key Insight

The important shared pattern.

## Evidence

Specific evidence from sessions.
```

### 6.5 Q&A pages / Q&A-страницы

Store complex answered questions for future reuse. / Храните сложные уже отвеченные вопросы для повторного использования.

Format / Формат:

```markdown
---
title: "Q: Original question"
question: "Original question"
consulted:
  - "concepts/x"
  - "concepts/y"
filed: 2026-04-20
---

# Q: Original question

## Answer

Synthesized answer with [[wikilinks]].

## Sources Consulted

- [[concepts/x]] - why relevant
```

## 7. Operations / Операции

### 7.1 Compile / Компиляция

Purpose / Задача:
- read one or more daily logs
- update existing concept pages when possible
- create new concept pages only when needed
- create connection pages for cross-cutting insights
- update `knowledge/index.md`
- append to `knowledge/log.md`

Compile should prefer updating over duplicating. / Компиляция должна предпочитать обновление существующего материала, а не создание дублей.

### 7.2 Query / Запрос

Purpose / Задача:
- read `knowledge/index.md`
- identify relevant pages
- read those pages fully
- synthesize an answer
- optionally file the answer back into `knowledge/qa/`

The project is intentionally index-guided, not embedding-first. / Проект специально построен на index-guided retrieval, а не на embeddings-first подходе.

### 7.3 Lint / Проверка

Minimum structural checks / Минимальные структурные проверки:
- broken wikilinks / битые wikilinks
- orphan pages / страницы без входящих ссылок
- orphan source logs / нескомпилированные daily logs
- stale pages / устаревшие статьи
- missing backlinks / отсутствующие обратные ссылки
- sparse pages / слишком короткие статьи
- contradictions when LLM check is enabled / противоречия при включенной LLM-проверке

## 8. Hook Lifecycle / Жизненный цикл hooks

### SessionStart

Triggered when Codex starts or resumes. / Срабатывает при старте или возобновлении сессии Codex.

It should:
- read the active vault's `knowledge/index.md`
- read the tail of the latest daily log
- inject both into the new session context

### Stop

Triggered after a completed turn. / Срабатывает после завершенного хода.

It should:
- read the transcript JSONL
- extract a recent window of user and assistant turns
- save the extracted window into a temporary file
- spawn `flush.py` as a detached background process
- return `{"continue": true}`

### Flush

Triggered by `Stop`. / Запускается из `Stop`.

It should:
- avoid duplicate flushes for the same turn
- compare against today's existing daily log tail
- call `codex exec`
- append only durable, non-trivial notes
- trigger compilation if today's daily log changed

## 9. Script Contract / Контракт скриптов

### `scripts/llm.py`

- wraps non-interactive `codex exec`
- requires active `codex login`
- does not use `OPENAI_API_KEY`

### `scripts/install_repo_hooks.py`

- installs repo-local `.codex/` files into external repos
- supports scanning a parent directory with many child repos
- supports explicit extra repos
- supports one shared external vault

### `scripts/config.py`

- resolves compiler root
- resolves active project root
- resolves active vault root
- exposes canonical paths used by the rest of the scripts

## 10. Writing Rules / Правила написания

Use these rules for compiled wiki content:
- use factual, compact prose / используйте фактический и компактный стиль
- prefer self-contained pages / предпочитайте самодостаточные страницы
- prefer stable names / используйте стабильные имена файлов
- use lowercase kebab-case filenames / имена файлов в lowercase kebab-case
- use ISO dates / даты в ISO формате
- use Obsidian-style `[[wikilinks]]` without `.md` / используйте wikilinks без `.md`
- keep source attribution in every page / каждая статья должна ссылаться на источники
- prefer updates over near-duplicates / обновляйте, а не плодите похожие страницы

## 11. Safety Rules / Правила безопасности

- Runtime writes must stay inside the active vault. / Runtime-записи должны оставаться внутри активного vault.
- Hooks must stay lightweight and non-blocking. / Hooks должны быть легкими и не блокировать пользовательский ход.
- `flush.py` and `compile.py` may run in the background. / `flush.py` и `compile.py` могут работать в фоне.
- A failed model call must not corrupt the vault. / Ошибка модели не должна ломать vault.
- The compiler must tolerate empty or partially initialized vaults. / Компилятор должен терпимо работать с пустым или частично инициализированным vault.

## 12. Recommended Deployment Pattern / Рекомендуемый паттерн разворачивания

### One-folder project / Проект из одной папки

- clone this repo
- keep knowledge inside this repo
- work here directly in Codex

### Multi-repo product / Продукт из многих репозиториев

- clone this repo once
- choose one external vault
- run `scripts/install_repo_hooks.py` against all work repos
- keep daily and compiled wiki content in the external vault
- open that vault in Obsidian if desired

## 13. Example Multi-Repo Installation / Пример установки для multi-repo проекта

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
- all git repos inside `/path/to/product-repos`
- one local cluster repo
- any extra backend, API, infra, or service repos listed with `--repo`
- one shared external vault for the whole product

## 14. Runtime Assumptions / Предпосылки рантайма

- `codex` must be on `PATH`
- `codex login status` must report an active session
- Python 3.12+ is expected
- `uv` is optional and not required for runtime hooks
- hooks are expected to be unavailable on Windows while Codex keeps that limitation
