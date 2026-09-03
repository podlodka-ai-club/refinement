# Путеводитель по Memory Curator

---

## 1. Вся система — один взгляд

```
   Источники знаний
   ┌───────────────────────────┐    ┌───────────────────────────┐
   │ Сессия агента (opencode) │    │  .md файлы (learnings/)    │
   │ Агент сам LLM: извлекает  │    │  ingest.py: детерминиро-  │
   │ знания + self-review       │    │  ванный парсинг секций    │
   │ через curator_query       │    │                           │
   └────────────┬──────────────┘    └────────────┬──────────────┘
                │ candidates                      │ ProposedFact
                ▼                                 │
   ┌────────────────────────────────────────┐    │
   │  MCP-сервер / CLI — единый контракт    │◄───┘
   │  server.py, control.py                 │
   │  Gatekeeper: 6 правил валидации         │
   │  (длина, теги, шум, дубликаты)         │
   └───────────────┬────────────────────────┘
          approved ┴─ rejected («причина»)
                   │
                   ▼
        ┌────────────────────────┐
        │     Memory Backend      │
        │  xmemory (primary)     │ ← enforced schema, SaaS
        │  SQLite (offline)      │ ← сеть/5xx: файл + outbox
        └────────────┬───────────┘    восстановление: curator sync
                     │ + write-back: sync_engine.py → .md
                     ▼
        ┌────────────────────────┐
        │  Improve Loop           │ ← worker.py --daemon (раз в сутки)
        │  · дубликаты → консолидация
        │  · устаревшие → deprecation
        │  · противоречия → resolution (verified > hypothesis)
        │  · телеметрия использования (совет человеку, не приговор)
        └────────────┬───────────┘
             ┌───────┴────────┐
             ▼                ▼
        Eval Gate        Observability
        eval_runner.py   observability.py
   «стало лучше? применяем»  JSONL лог всех действий
```

**Ключевое:** извлечение делает сам агент (он уже LLM с полным контекстом
сессии), бэкенд управляет данными. LLM-вызовов в бэкенде нет.

## 2. Карта файлов: что за что отвечает

### 🧠 Ядро (пишут и читают факты)

| Файл | Что делает (простыми словами) | Как проверить |
|------|------------------------------|---------------|
| `models.py` | Типы данных: факт, запрос, связь, граф | `grep "StructuredFact" curator/models.py` |
| `backend/interface.py` | Контракт: что должен уметь любой бэкенд | `grep "def store_fact" curator/backend/interface.py` |
| `backend/xmemory.py` | xmemory SaaS через REST; при сети/5xx — offline-fallback в файловую SQLite + outbox | `pytest tests/requirements/test_uc_fallback.py -v` |
| `backend/local.py` | SQLite на диске — локальный бэкенд и offline-fallback | `.venv/bin/python3 -c "from curator.backend.local import LocalBackend; print(LocalBackend(':memory:').health_check())"` |
| `outbox.py` | Offline-очередь отложенных записей в xmemory (идемпотентно по title) | `pytest tests/requirements/test_uc_fallback.py -v` |

### 📥 Вход (откуда берутся факты)

| Файл | Что делает (простыми словами) | Как проверить |
|------|------------------------------|---------------|
| `analyzers/ingest.py` | Читает `.md` из learnings/ — превращает секции в факты | `DEMO_MODE=ingest .venv/bin/python3 -c "from curator.demo import run_ingest_demo; run_ingest_demo()"` |
| `session_reader.py` | Читает **реальные** сессии из `opencode.db` (для демо) | `pytest tests/unit/test_demo.py -v` |

> Извлечение из сессий делает **сам агент** (opencode-скилл `/curator-save`):
> сам извлекает кандидатов, делает self-review через `curator_query`, передаёт
> готовый JSON в MCP. В бэкенде LLM нет.

### 🛡️ Фильтр (human-in-the-loop)

| Файл | Что делает (простыми словами) | Как проверить |
|------|------------------------------|---------------|
| `gatekeeper.py` | 6 правил: короткий заголовок, шум-паттерны, нет тегов, дубликат | `pytest tests/unit/test_gatekeeper.py -v` |

### 🔄 Улучшение (автономный фон)

| Файл | Что делает (простыми словами) | Как проверить |
|------|------------------------------|---------------|
| `improve_loop.py` | Поиск дубликатов + устаревших + противоречий + разрешение | `pytest tests/unit/test_improve_loop.py -v` |
| `eval_runner.py` | Перед применением улучшения — проверяет метрики | `pytest tests/unit/test_eval_runner.py -v` |
| `observability.py` | JSONL лог: «когда, что, почему, eval до/после» | `cat ~/.curator/improve_events.jsonl` |
| `retrieval_feedback.py` | Считает сколько раз каждый факт запрашивали | `pytest tests/unit/test_retrieval_feedback.py -v` |
| `worker.py` | Автономный демон: раз в сутки improve + телеметрия | `MEMORY_BACKEND=local .venv/bin/curator status` |

### 🖥️ Интерфейсы наружу

| Файл | Что делает (простыми словами) | Как проверить |
|------|------------------------------|---------------|
| `server.py` | MCP-сервер: 6 тулзов (capture, query, status, improve, feedback, routes) | `pytest tests/unit/test_server_output.py tests/unit/test_session_capture.py -v` |
| `control.py` | CLI `curator`: save, get, sync, status, report, improve, start/stop | `.venv/bin/curator status` |
| `sync_engine.py` | Write-back: факт из approve возвращается в `.md` | `pytest tests/integration/test_sync_engine.py -v` |
| `server_log.py` | Лог вызовов сервера в `~/.curator/server.log` | `cat ~/.curator/server.log` |
| `demo.py` | Демо-сценарии: compare, time-lapse, ingest, opencode, durability | `DEMO_MODE=timelapse .venv/bin/python3 -c "from curator.demo import run_time_lapse; run_time_lapse()"` |

### 🧭 Роутинг и конфигурация

| Файл | Что делает (простыми словами) | Как проверить |
|------|------------------------------|---------------|
| `routing/interface.py` | Контракт Router — точка подключения (реализован MapRouter) | `pytest tests/unit/test_routing.py -v` |
| `routing/default.py` | DefaultRouter — сохраняет в `session/{type}.md` | `pytest tests/unit/test_routing.py -v` |
| `~/.curator/extraction-rules.yaml` | Правила извлечения (focus/ignore) — читает **агент** при извлечении кандидатов | `cat ~/.curator/extraction-rules.yaml` |

## 3. Жизненный цикл одного факта

```
ШАГ 1: Появление
   Источник: агент (opencode / Claude Code) передаёт candidates (сессия)
             ИЛИ .md файл через ingest
   Файлы: server.py (MCP) / control.py (CLI) / ingest.py
   Получаем: ProposedFact (сырой, не проверен)

ШАГ 2: Валидация
   Файл: gatekeeper.py
   Проверяет: длина >10, описание >20, есть теги, не шум, не дубликат
   Если дубликат → «отклонено: уже есть 'X'»
   Если ок → StructuredFact (готов к сохранению)

ШАГ 3: Сохранение (после подтверждения пользователем)
   Файлы: backend/xmemory.py (primary) или backend/local.py (offline)
   xmemory — schema-enforced, живёт в облаке
   Сеть/5xx → локальная SQLite + запись в outbox (восстановление: curator sync)
   Статус: verified

ШАГ 3.5: Write-back
   Файл: sync_engine.py + routing/
   Факт дописывается в .md: session/{type}.md

ШАГ 4: Использование
   Файл: retrieval_feedback.py
   Когда кто-то делает curator_query — счётчик +1 для этого факта

ШАГ 5: Улучшение (автономно, раз в сутки — worker.py)
   Файл: improve_loop.py
   · Дубликаты (Jaccard similarity по заголовкам) → консолидация
   · Устаревшие (hypothesis/deprecated) → deprecation
   · Противоречия (общие теги + противоположные выводы) → resolution

ШАГ 6: Eval gate
   Файл: eval_runner.py
   Перед применением → проверка что coverage не упал, база не схлопнулась
   · Ок → применяем
   · Не ок → блокируем, пишем в observability

ШАГ 7: Телеметрия использования (worker.py)
   Файл: worker.py (RetrievalFeedback — observability)
   Телеметрия показывает человеку, что давно не читалось.
   Решение за человеком: таймерного decay нет — время не делает
   факт ложным. Устаревание — семантическое (hypothesis по eval-гейту,
   проигравшие противоречий) или руками.

ШАГ 8: Логирование
   Файл: observability.py
   JSONL запись: что сделали, какие факты, eval до/после, применено/отклонено
```

## 4. Шесть файлов для демо-видео

Открой эти вкладки в IDE перед записью. Порядок как в `demo-checklist.md`:

| # | Файл | Что показываешь | Текст для видео |
|---|------|----------------|-----------------|
| 1 | `demo.py` | `run_time_lapse()` | «Сессии накапливаются: знания растут с каждым прогоном» |
| 2 | `demo.py` | `run_ingest_demo()` | «.md файлы → факты. До индексации query → 0, после → N» |
| 3 | `session_reader.py` | `run_opencode_demo()` | «Реальные сессии из opencode.db, не синтетика» |
| 4 | `demo.py` | `run_durability_demo()` | «Записали в xmemory → перезапустили → данные на месте» |
| 5 | `improve_loop.py` | `_pick_winner()` | «Противоречия разрешаются: verified бьёт hypothesis» |
| 6 | `eval_runner.py` | `EvalAction.improved` | «Перед изменением — eval gate проверяет метрики» |

И два финальных: `design/requirements.md` — матрица требований; терминал
`pytest tests/ -q --ignore=tests/smoke` — все зелёные.

## 5. Как устроены тесты

```
tests/                      178 всего
├── requirements/   21 — ГЛАВНЫЙ suite: 1 тест = 1 требование хакатона
│                     R1-R6 (must) · N1-N5 (nice) · X1-X4 (xmemory) · UC6×6
│                     Трассировочная матрица: tests/requirements/README.md
├── unit/           110 — компоненты: gatekeeper, improve, eval, routing,
│                     sync, ingest, demo, session_capture, server_output
├── integration/     32 — вместе: LocalBackend CRUD, sync_engine, dedup
├── e2e/             10 — сквозные: store→improve→consolidate
└── smoke/            5 — все бэкенды живы (пропуск без VPN/ключей)
```

Запуск: `.venv/bin/python -m pytest tests/ -q --ignore=tests/smoke`

## 6. Чек-лист «Я понимаю» (10 вопросов)

Если на все отвечаешь «да» — готов к защите:

- [ ] **1.** Я могу показать где живут данные: xmemory (облако) и SQLite (`~/.curator/knowledge.db`, offline-fallback + outbox)
- [ ] **2.** Я могу объяснить что делает Gatekeeper: 6 правил, фильтрует кандидатов перед сохранением
- [ ] **3.** Я могу показать как факт попадает в систему: агент извлекает → candidates → MCP → gatekeeper → backend
- [ ] **4.** Я могу запустить `run_time_lapse()` и объяснить рост фактов от сессии к сессии
- [ ] **5.** Я могу запустить `run_ingest_demo()`: до индексации query=0, после — N
- [ ] **6.** Я могу запустить `run_durability_demo()`: данные в xmemory переживают рестарт (нужен VPN)
- [ ] **7.** Я могу открыть `improve_loop.py` и показать `_pick_winner()` — разрешение противоречий
- [ ] **8.** Я могу открыть `eval_runner.py` и показать `EvalAction.improved` — eval gate
- [ ] **9.** Я могу открыть `observability.py` — JSONL лог всех improve-действий
- [ ] **10.** Я могу запустить `pytest tests/ -q --ignore=tests/smoke` и показать что все тесты проходят
