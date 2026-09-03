# Memory Curator — Быстрый старт

> Начать использовать сегодня. Без погружения в кишки.

## 0. Установка

```bash
git clone <repo> memory-curator
cd memory-curator
./install.sh --opencode      # mac/linux · Windows: install.bat --opencode
```

Скрипт сам поставит python-пакет и запустит `curator install` (то же
руками: `cd core && python -m venv .venv && .venv/bin/pip install -e . &&
.venv/bin/curator install --opencode`).

Единственный вопрос установки — **куда класть базу знаний** (любой путь,
по умолчанию `~/memory-curator`; это просто папка с `.md` — можно положить
внутрь репо проекта, чтобы база жила в гите; создастся при первом
сохранении; сменить потом — env `CURATOR_BASE_DIR` в конфиге).

Инсталлер сам впишет в opencode: MCP-сервер (тулзы `curator_*`), все
команды `/curator-*`, оба скилла (curator-save и mapping-documentation)
и поднимет worker самоулучшения. Перезапусти opencode — готово.
`--claude` — то же для Claude Code: `.mcp.json` в проекте + слэш-команды
`~/.claude/commands/` + скиллы.

Разработка (тесты): `pip install -e ".[dev]"` — клиенту `[dev]` не нужен.

## 1. Первый запуск (TERMINAL)

```bash
# Тур: полный цикл жизни знания за 1 минуту
# (gatekeeper → write-back → query → improve → телеметрия, всё на изолированной базе)
curator demo            # посмотреть и удалить
curator demo --keep     # оставить файлы для осмотра

# Статус базы / worker
curator status

# Запустить worker daemon (авто-улучшение раз в сутки)
curator start
```

## 2. Команды (появляются после install)

| Команда | Что делает |
|---------|-----------|
| `/curator-save` | Извлечь знания из сессии → self-review → gatekeeper → preview → сохранить |
| `/curator-create-map` | Построить карту документации проекта (скилл mapping-documentation) и подключить маршрутизацию |
| `/curator-status` | Сколько фактов, по типам (с описаниями-словарём) и статусам |
| `/curator-query "kotlin"` | Поиск фактов перед работой |
| `/curator-report` | Статус + топ запросов + improve-лог |
| `/curator-start` / `/curator-stop` / `/curator-worker` | Управление фоновым worker |

Извлечение делает сам агент (он LLM), бэкенд управляет данными —
LLM-вызовов в сервере нет.

## 2а. Куда кладутся знания

База — выбранная при установке папка (дефолт `~/memory-curator`). Внутри:
`session/{type}.md` с фактами и `index.md`-навигация. `.md` читаются
человеком и git'ом; смена пути — env `CURATOR_BASE_DIR` в конфиге
opencode (секция `mcp.memory-curator`) или в `.mcp.json` проекта.

## 2б. Карта документации проекта (маршрутизация по темам)

Хочешь, чтобы знания раскладывались не по типам, а по темам проекта
(«архитектура → docs/architecture.md», «стиль → style/…»)? Это делает
**карта документации** — и она уже подключена: при установке пишется
`ROUTER_CLASS=MapRouter`, без карты он молча работает как дефолт.

**Флоу — без настройки:**

1. В opencode открой проект с документацией и набери `/curator-create-map`.
2. Скилл mapping-documentation (Егора) построит карту: сам спросит границы
   поиска и куда сохранить — укажи `DOCUMENTATION-MAP.md` внутри базы.
3. Готово: факты из сессий едут по темам карты.

Карта — Markdown с YAML-темами:

```yaml
---
topics:
  - name: architecture          # имя = теги для матчинга (короче — лучше)
    types: [Reference]          # опционально: какие типы фактов сюда
    targets:
      - path: docs/architecture.md
        mode: update            # update = перезапись | append = не трогать существущее | readonly = не писать
---
```

Порядок маршрутизации: путь от агента (скилл разрулил glob-таргет, поле
`source_file` кандидата) → теги ∩ токены имени темы → явное `types:` →
нет матча: честный дефолт `session/{type}.md`. `on_unmatched` виден в
stderr сервера.
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
| `curator install [--opencode\|--claude] [--base-dir ПУТЬ]` | Установить в opencode / Claude Code: MCP + команды + скиллы + worker |
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
2. **Устаревшие** — hypothesis → deprecation (с eval-проверкой)
3. **Противоречия** — детект + авто-разрешение (verified > hypothesis > deprecated)
4. **Телеметрия** — usage-статистика (`curator report`, `/curator-report`):
   какие знания читают, какие забыты — совет человеку, автоматика не казнит
   (таймерного decay нет: время не делает факт ложным)
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