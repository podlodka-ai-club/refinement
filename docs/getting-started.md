# Memory Curator — Быстрый старт

> Начать использовать сегодня. Без погружения в кишки.

## 0. Установка за 3 команды

```bash
git clone <repo> && cd memory-curator/core
pip install -e ".[dev]"
curator install --opencode   # или --claude; без флага спросит
```

`install --opencode` впишет MCP-сервер в конфиг opencode
(`~/.config/opencode/opencode.json`), поставит скилл curator-save и поднимет
worker самоулучшения. После установки перезапусти opencode — готово.
`install --claude` — то же для Claude Code: `.mcp.json` в проекте + скилл.

## 1. Первый запуск (TERMINAL)

```bash
cd <путь-к-репо>/memory-curator/core

# Установить
.venv/bin/pip install -e ".[dev]"

# Посмотреть что уже есть в базе
MEMORY_BACKEND=local curator status

# Тур: полный цикл жизни знания за 1 минуту
# (gatekeeper → write-back → query → improve → auto-decay, всё на изолированной базе)
curator demo            # посмотреть и удалить
curator demo --keep     # оставить файлы для осмотра

# Запустить worker daemon (авто-улучшение раз в сутки)
MEMORY_BACKEND=local curator start
```

## 2. OpenCode (замена /save-knowledge)

После перезапуска OpenCode появятся команды:

| Команда | Что делает | Было раньше |
|---------|-----------|-------------|
| `/curator-save` | Агент извлекает знания из сессии → self-review → кандидаты → gatekeeper → preview → сохранить | `/save-knowledge` |
| `/curator-status` | Сколько фактов, по типам и статусам | Не было |
| `/curator-query "kotlin"` | Поиск фактов перед работой | Не было |
| `/curator-report` | Статус + топ запросов | Не было |

Бесшовная миграция: вместо `/save-knowledge` → `/curator-save`. Под капотом — MCP-сервер.
Извлечение делает сам агент (он LLM), бэкенд управляет данными — LLM-вызовов в сервере нет.

Скилл `.agents/skills/curator-save/` добавляет проактивный триггер: агент
сам предлагает сохранить проверенное знание по ходу сессии. Подключение в
opencode — симлинком: `ln -s <repo>/.agents/skills/curator-save
~/.config/opencode/skills/curator-save`.

## 2а. Claude Code

`integrations/claude-code/` — `.mcp.json` (MCP-сервер), скилл и инструкция
подключения за 3 шага: [README](../integrations/claude-code/README.md).

## 2б. Маршрутизация по карте документации (MapRouter)

Ядро умеет читать карту формата скилла mapping-documentation (темы →
таргеты, mode update/append/readonly):

```bash
# карта: <base_dir>/DOCUMENTATION-MAP.md (или env CURATOR_MAP)
ROUTER_CLASS=curator.routing.map_router.MapRouter curator-mcp-server
```

Порядок решения: путь от агента (скилл разрулил glob) → теги ∩ токены
имени темы → явное `types:` темы → нет матча: report + дефолт.
Подробности и мнения: [design/integration-map-router.md](../design/integration-map-router.md).

## 2в. Демонстрация заявленного

E2E-сценарий `core/tests/e2e/test_full_lifecycle.py` — связный прогон всей
заявки (capture с мусором, upsert, query, improve с eval-гейтом, жизненный
цикл в .md, rebuild, decay, offline-fallback): полный скрипт демо. Прогон с
выводом: `pytest tests/e2e/test_full_lifecycle.py -v`.

## 3. Все команды (TERMINAL)

| Команда | Что делает |
|---------|-----------|
| `curator start` | Запустить worker daemon в фоне |
| `curator stop` | Остановить worker |
| `curator status` | Worker жив? Фактов в базе? Последний improve? |
| `curator report` | Сводка за всё время: топ запросов, improve события, забытые факты |
| `curator report -d 3` | Сводка за последние 3 дня |
| `curator save` | Кандидаты (JSON из stdin, извлекает агент) → gatekeeper → подтверждение → сохранить |
| `curator save -y` | То же без подтверждения (скрипты/бенчмарки) |
| `curator get "kotlin"` | Поиск фактов |
| `curator improve` | Ручной запуск improve цикла |
| `curator routes` | Правила маршрутизации фактов по папкам |
| `curator sync` | Пуш offline-outbox в xmemory (после восстановления сети) |
| `curator demo` | Тур: полный жизненный цикл знания на изолированной базе (для быстрой проверки) |

## 4. План на 2 недели

| Когда | Что делать | Команда |
|-------|-----------|---------|
| **Сегодня** | Запустить worker | `curator start` |
| **В течение дня** | Сохранять знания из сессий | `/curator-save` в OpenCode |
| **Перед задачей** | Поискать релевантные правила | `/curator-query "kotlin"` |
| **Раз в 3 дня** | Проверить что улучшается | `curator report -d 3` |
| **Пятница** | Итоги недели | `curator report` |
| **Перед демкой** | Полный отчёт за 2 недели | `curator report` |

Worker делает всё в фоне. Ты только смотришь `curator report` когда удобно.

## 5. Что происходит в фоне (автономно)

Раз в сутки worker просыпается и:

1. **Дубликаты** — находит → consolidation (с eval-проверкой)
2. **Устаревшие** — hypothesis/deprecated → deprecation (с eval-проверкой)
3. **Противоречия** — детект + авто-разрешение (verified > hypothesis > deprecated)
4. **Авто-decay** — unused >30д → hypothesis, unused >90д → deprecated
5. **Observability** — JSONL запись всех действий с метриками до/после

Интервал: `IMPROVE_INTERVAL_MINUTES` (default: 1440 = сутки).

## 6. Конфигурация

```bash
# Локальный бэкенд (SQLite) — для разработки
export MEMORY_BACKEND=local

# xmemory бэкенд — для прода
export MEMORY_BACKEND=xmemory
export XMEMORY_API_KEY=<your-key>
export XMEMORY_INSTANCE_ID=<your-instance-id>

# Интервал improve (минуты)
export IMPROVE_INTERVAL_MINUTES=1440  # сутки
```

## 7. Где что лежит

| Что | Где |
|-----|-----|
| `curator` CLI | `.venv/bin/curator` |
| Worker лог | `~/.curator/worker.log` |
| Offline-outbox | `~/.curator/outbox.db` |
| Improve-лог | `~/.curator/improve_events.jsonl` |
| Usage-статистика | `~/.curator/usage.json` |
| Worker отчёты | `~/.curator/reports/improve_*.json` |
| База SQLite (local) | `~/.curator/knowledge.db` |