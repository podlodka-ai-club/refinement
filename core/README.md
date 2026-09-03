# Memory Curator — Core

Самообучающийся агент для структурированной базы знаний. Строит граф над `.md` файлами, обеспечивает целостность через enforced схему (xmemory), сам улучшается с каждой итерацией.

## Архитектура

```
Агент (opencode / Claude Code) извлекает знания из сессии
    ↓ candidates (JSON: type, title, content_summary, tags, evidence)
MCP-сервер: curator_session_capture
    ↓
gatekeeper.py (6 правил: длина, теги, шум, дубликаты) = self-review бэкенда
    ↓
backend: xmemory (primary, schema-enforced) / SQLite (local)
    ↓                                    ↘ сетевой сбой (UC6):
sync_engine.py → .md (через Router)        локальная БД + outbox
    ↓                                    ↘ восстановление: curator sync
improve_loop.py (автономно: дубликаты, stale, противоречия)
    ↓
eval_runner.py (gate: изменение только если метрики улучшились)
    ↓
observability.py (JSONL лог всех действий)
```

**Ключевое решение:** извлечение знаний делает сам агент (LLM уже есть там),
бэкенд управляет данными: валидация, хранение, write-back, improve. В бэкенде
нет LLM-вызовов — нет внешних зависимостей на критическом пути.

## Установка

```bash
cd core
python -m venv .venv
.venv/bin/pip install -e .
```

## Запуск

### Локально (без внешних сервисов)
```bash
MEMORY_BACKEND=local curator-mcp-server
```

### С xmemory (требуется API-ключ)
```bash
MEMORY_BACKEND=xmemory XMEMORY_API_KEY=your-key curator-mcp-server
```

## MCP-тулзы

| Тул | Описание |
|-----|----------|
| `curator_session_capture` | Принять кандидатов от агента → gatekeeper → preview → сохранение (auto_approve) |
| `curator_query` | Поиск фактов по типу / тегам / статусу / тексту |
| `curator_status` | Статистика: total_facts, by_type, by_status |
| `curator_improve` | Запуск автономного improve: дубликаты + stale + противоречия + eval gate |
| `curator_feedback` | Статистика использования: топ запросов, забытые факты |
| `curator_routes` | Текущие правила маршрутизации фактов по папкам |

## Approval Flow (как работает подтверждение)

1. Агент извлекает кандидатов из сессии, делает self-review (вызывает `curator_query`, убирает известное)
2. `curator_session_capture(candidates=[...])` без `auto_approve` → gatekeeper фильтрует
3. Сервер показывает preview: approved (✅ с типом/сводкой/тегами) и rejected (⛔ с причинами)
4. **НЕ сохраняет автоматически** — пользователь решает: всё / выборочно / отказ
5. Для сохранения: повторный вызов с теми же (или выбранными) candidates и `auto_approve: true`

## CLI

```bash
curator save      # кандидаты (JSON из stdin) → gatekeeper → y/N → БД + .md
curator save -y   # то же без подтверждения (скрипты/бенчмарки)
curator sync      # пуш offline-outbox в xmemory (после восстановления сети)
curator get 'kotlin'
curator status / report / improve / routes / start / stop
```

Пример:
```bash
echo '[{"type":"Reference","title":"...","content_summary":"...","tags":["kotlin"]}]' | curator save -y
```

## Self-review (два уровня)

**Агент (до отправки):** скилл инструктирует вызвать `curator_query` и убрать уже известные факты.
**Бэкенд (gatekeeper, `gatekeeper.py`):** 6 правил на каждого кандидата:
- Длина заголовка (10-200 символов)
- Длина описания (>20)
- Шум-паттерны («поменять цвет», «сдвинуть на 2px»)
- Обязательные теги
- Проверка на дубликаты (Jaccard similarity по title)
- LLM в бэкенде не нужен — валидация детерминированная

## Offline-fallback (UC6)

При недоступности xmemory (сеть/VPN/5xx):
- записи идут в локальную БД (`~/.curator/knowledge.db`) + outbox (`~/.curator/outbox.db`)
- чтения деградируют на локальную БД
- при восстановлении: `curator sync` пушит outbox в xmemory (идемпотентно по title)
- 4xx — ошибка запроса, деградации нет

## Конфигурация

### Extraction rules (правила извлечения — для агента/скилла)
Файл `~/.curator/extraction-rules.yaml` — читает агент при извлечении кандидатов (не бэкенд):
```yaml
focus:
  - "Технические правила и паттерны (kotlin, jvm, compose, android)"
  - "Архитектурные решения и их обоснования"
ignore:
  - "Конкретные баги и их фиксы"
  - "Временные решения и workaround'ы"
```
> Backlog: заменяется «картой» участника 1 (watch_for/targets) — единый конфиг проекта.

### Router Protocol (модульная маршрутизация)
`curator/routing/interface.py` — контракт `Router`. Участник 1 реализует свой `RoutingRouter` с чтением `routing.yaml`. Подключение: `ROUTER_CLASS=your.module.YourRouter`.

DefaultRouter (по умолчанию): сохраняет всё в `session/{type}.md`.

## Демо-режимы

```bash
.venv/bin/python3 -c "from curator.demo import run_time_lapse; run_time_lapse()"
.venv/bin/python3 -c "from curator.demo import run_ingest_demo; run_ingest_demo()"
.venv/bin/python3 -c "from curator.demo import run_durability_demo; run_durability_demo()"
.venv/bin/python3 -c "from curator.demo import run_opencode_demo; run_opencode_demo(3)"
.venv/bin/python3 -c "from curator.demo import run_demo; run_demo()"
```

## Тесты

```bash
.venv/bin/python -m pytest tests/ -v --ignore=tests/smoke
```

## MCP конфигурация

```json
{
  "mcpServers": {
    "memory-curator": {
      "command": "curator-mcp-server",
      "env": {
        "MEMORY_BACKEND": "xmemory",
        "CURATOR_BASE_DIR": "~/Documents/AI/personal/learnings",
        "AUTO_MODE": "false"
      }
    }
  }
}
```