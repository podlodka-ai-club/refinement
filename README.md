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
    ├─ write-back    approved-факт возвращается в .md (по типам или
    │                по темам карты проекта — MapRouter)
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
./install.sh          # Windows: install.bat
# разработка (тесты):
cd core && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q --ignore=tests/smoke   # все зелёные
.venv/bin/curator demo                                       # полный цикл жизни знания
```

`./install.sh` — без вопросов: сам найдёт opencode / Claude Code, впишет
MCP-сервер, команды `/curator-*`, скиллы и worker. Перезапусти харнес —
готово. База — `~/memory-cursor` (см. `curator status`).

`curator demo` прогоняет на изолированной tmp-базе весь жизненный цикл —
**реальными вызовами** (те же функции, что в проде): кандидаты → gatekeeper
(7 принято / 3 отклонено с причинами) → write-back в .md → query → improve
(дубликат консолидирован, противоречие разрешено) → телеметрия (что реально
читают) → финальный статус. `--keep` оставит файлы для осмотра.

Подробный гайд: [docs/getting-started.md](docs/getting-started.md).

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
| `design/` | архитектура: requirements, spec, decision-log, playbook-routing (контракт Router), backlog |
| `demo/` | демо/защита: чеклист записи видео, сценарий, путеводитель по коду |
| `docs/` | day-to-day: getting-started |

## Статус

- **Ядро — готово**: candidates-контракт, gatekeeper, xmemory + SQLite
  fallback с offline-outbox, write-back в .md, improve loop с eval-гейтом,
  реестр типов с описаниями, демо-тур. **290 тестов** (288 зелёных +
  2 VPN-пропуска), включая 21 тест-требование
- **Карта документации (Егор) — готова и интегрирована**: скилл
  mapping-documentation генерирует карту проекта, ядро читает её
  (`MapRouter`): маршрутизация фактов по темам, `mode`-дисциплина записи
  (update/append/readonly), команда `/curator-create-map`
- **Установка — одна команда**: `./install.sh` / `install.bat`, без
  вопросов, автодетект opencode / Claude Code

## Роадмап

- **Упаковка**: pipx/uv-установка без клона репо (скиллы и команды —
  в package data)
- **`curator pull`**: слить чужие факты из xmemory в локальную — первая
  ступень командной синхронизации
- **Двусторонняя .md-синка**: ручная правка файла → авто-переиндексация
- **Multi-user**: сейчас Git для .md + UPSERT/LWW для фактов; CRDT — при
  реальной одновременной правке

Полный список: [design/backlog.md](design/backlog.md)

## Команда

| Блок | Кто | Зона |
|------|-----|------|
| Ядро | Участник 2 | backend, gatekeeper, improve loop, MCP, CLI |
| Карта | Егор | mapping-documentation: карта проекта, MapRouter, скиллы |

## Ссылки

- Репозиторий команды: https://github.com/podlodka-ai-club/refinement
- xmemory: https://xmemory.ai
