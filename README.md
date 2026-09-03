---
type: Index
project: Memory Curator
---

# Memory Curator

Фоновый агент памяти для opencode и Claude Code: извлекает проверенные знания
из сессий и `.md`-документации, хранит их с валидацией, автономно улучшает
память (дубликаты, устаревание, противоречия) и возвращает знания обратно
в документацию.

**Hacker Sprint #2** · podlodka-ai-club/refinement · трек «Агент, который помнит»

## Проблема

Знания из AI-сессий умирают вместе с чатом. `.md`-базы растут, в них копятся
дубликаты и устаревшие правила, противоречия никто не разрешает — и агент
каждый раз начинает с нуля вместо того, чтобы переиспользовать опыт.

## Как работает

Извлечение знаний делает сам агент (opencode сейчас, любой MCP-клиент —
Claude Code — по тому же контракту). Агент и есть LLM с полным контекстом
сессии, бэкенд управляет данными: валидация, хранение, write-back, автономное
улучшение. LLM-вызовов в бэкенде нет — критический путь не зависит от внешних сервисов.

```
Агент (opencode сейчас · любой MCP-клиент по тому же контракту)
    │  candidates: готовые факты (type, title, summary, tags, evidence)
    ▼
MCP-сервер / CLI — единый контракт candidates
    ├─ gatekeeper    валидация: качество, шум-паттерны, дубликаты
    ├─ backend       xmemory (primary) / SQLite (offline + outbox)
    ├─ write-back    approved-факт возвращается в .md
    └─ improve loop  автономно (worker, раз в сутки):
                    дубликаты → консолидация · stale → deprecation ·
                    противоречия → resolution (verified > hypothesis) ·
                    телеметрия использования (совет человеку, не приговор) ·
                    eval gate перед изменениями
```

Offline-fallback (UC6): при недоступности xmemory (сеть / VPN / 5xx) записи
уходят в локальную SQLite + offline-outbox, чтения деградируют на локальную
базу. При восстановлении `curator sync` допушивает очередь — идемпотентно по
title. 4xx — ошибка запроса, деградации нет.

## Как измеряется прогресс

Каждое требование хакатона закрыто тестом, имя теста = ID требования.
**21 тест на 16 требований** (UC6 покрыт 6 сценариями):

```bash
cd core && .venv/bin/python -m pytest tests/requirements/ -v
```

| Блок | Тесты | Что проверяют |
|------|-------|---------------|
| R1-R6 | 6 | минимальные требования: поток задач, цикл урока, изменение поведения, рестарты, реальные данные, дельта до/после |
| N1-N5 | 5 | доп. блоки: забывание, противоречия, eval-гейт, human-in-the-loop, observability |
| X1-X4 | 4 | номинация xmemory: durability (smoke, VPN), схема, primary-backend, наглядность |
| UC6 | 6 | offline-fallback: store / query / 4xx / идемпотентность / sync |

Трассировочная матрица — [core/tests/requirements/README.md](core/tests/requirements/README.md):
требование → тест → статус. Тесты называются по ID требований и ходят только
через публичные API — рефакторинг внутренностей не может «обнулить» тест.

Почему так: реальная регрессия — fallback писал в `:memory:` и терял данные
при рестарте, при полностью зелёном юнит-сьюте. Тесты проверяли код, а не
требование. Requirement-тест R4 упал бы в тот же день.

## Попробовать за 2 минуты

```bash
git clone https://github.com/podlodka-ai-club/refinement.git
cd refinement
./install.sh --opencode      # Windows: install.bat --opencode
# разработка (тесты):
cd core && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q --ignore=tests/smoke   # все зелёные
.venv/bin/curator demo                                       # полный цикл жизни знания
```

`curator demo` прогоняет на изолированной tmp-базе весь жизненный цикл —
**реальными вызовами** (те же функции, что в проде): кандидаты → gatekeeper
(7 принято / 3 отклонено с причинами) → write-back в .md → query → improve
(дубликат консолидирован, противоречие разрешено) → телеметрия (что реально
читают) → финальный статус. `--keep` оставит файлы для осмотра.

Подключить к своему агенту (opencode): скилл `/curator-save` + MCP-конфиг —
[docs/getting-started.md](docs/getting-started.md).

## Два варианта развёртывания

| | Локальный | xmemory (primary) |
|--|-----------|-------------------|
| Что нужно | ничего — SQLite идёт в комплекте | `XMEMORY_API_KEY` + `XMEMORY_INSTANCE_ID` |
| Включение | `MEMORY_BACKEND=local` | `MEMORY_BACKEND=xmemory` |
| Хранение | `~/.curator/knowledge.db` | облако xmemory, schema-enforced |
| Сеть | не нужна | нужна; сбой (сеть/VPN/5xx) → авто-fallback на локальную SQLite + offline-outbox |
| Восстановление | — | `curator sync` допушивает outbox, идемпотентно по title |

## Структура

| Папка | Что |
|-------|-----|
| `core/` | ядро (Python): backend/ (xmemory + SQLite + outbox), gatekeeper, improve_loop, sync_engine, MCP-сервер, CLI |
| `core/tests/requirements/` | тесты требований — имя теста = ID требования |
| `design/` | архитектура: requirements, spec, decision-log, playbook-routing (контракт Блока 1), backlog |
| `demo/` | демо/защита: чеклист записи видео, сценарий, путеводитель по коду |
| `docs/` | day-to-day: getting-started |

## Статус

- **Ядро (Блок 2) — готово**: candidates-контракт, gatekeeper, xmemory +
  SQLite fallback с offline-outbox, write-back в .md, improve loop с
  eval-гейтом, демо-тур `curator demo`. 175 тестов (174 зелёных + 1
  smoke-пропуск), включая 21 тест-требование *(на 29.08)*
- **Карта (Блок 1) — в процессе**: routing.yaml — что извлекать из сессий и
  куда складывать в документацию проекта. Контракт стыка —
  [design/playbook-routing.md](design/playbook-routing.md)
- **Бенчмарки (Блок 3) — в процессе**: A/B — одинаковые задачи с плагином и
  без, дельта ревью-замечаний

## Роадмап

- **Карта проекта (Блок 1)**: routing.yaml + MapRouter поверх Router Protocol —
  что извлекать из сессий и куда складывать в docs
- **Бенчмарки (Блок 3)**: A/B-задачи с плагином и без, дельта ревью-замечаний
- **Двусторонняя .md-синка**: ручная правка файла → авто-переиндексация
- **Multi-user**: сейчас Git для .md + UPSERT/LWW для фактов; CRDT — при
  реальной одновременной правке

Полный список: [design/backlog.md](design/backlog.md)

## Команда

| Блок | Кто | Зона |
|------|-----|------|
| Ядро | Участник 2 | backend, gatekeeper, improve loop, MCP, CLI |
| Карта | Участник 1 | routing.yaml + скиллы: что и куда извлекать |
| Бенчмарки | Участник 3 | измерение эффективности на реальных задачах |

## Ссылки

- Репозиторий команды: https://github.com/podlodka-ai-club/refinement
- xmemory: https://xmemory.ai
