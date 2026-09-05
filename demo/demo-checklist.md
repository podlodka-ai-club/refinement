# Демо-чеклист (выполнить и записать до 8 сентября)

> Записывать видео по этому чеклисту. Каждый шаг = пункт требований хакатона.
> Всё выполняется вручную. Оценка: 7-9 минут ролика.

## Подготовка (за день до записи)

- [ ] `cd core && .venv/bin/python -m pytest tests/ -q --ignore=tests/smoke` — все зелёные
- [ ] `curator demo --keep` — тур проходит, числа сходятся (7 принято / 3 отклонено → 5 verified / 2 deprecated). Этапы тура = готовые кадры для видео
- [ ] Включить VPN (нужен для xmemory)
- [ ] `export XMEMORY_API_KEY=...` и `export XMEMORY_INSTANCE_ID=...` (ключи у организаторов/у тебя)
- [ ] Почистить базу: `rm ~/.curator/knowledge.db ~/.curator/outbox.db` (начнём с нуля)
- [ ] Открыть в IDE 6 вкладок из `demo/project-map.md` (раздел 4)

## Сценарий записи (по шагам)

### 0. Установка одной командой (30 сек)
```bash
git clone https://github.com/podlodka-ai-club/refinement.git && cd refinement
./install.sh
```
«Одна команда, без вопросов: сам нашёл opencode, поставил команды,
скиллы, фоновый worker, правила памяти и плагин-реминдер.
База — по умолчанию ~/memory-curator.»

### 1. Ingest: .md → база (UC1, требование #1)
```bash
.venv/bin/python3 -c "from curator.demo import run_ingest_demo; run_ingest_demo()"
```
Показать: до индексации `curator get kotlin` → пусто, после → N фактов.

### 2. Сохранение из сессии: агент + candidates (UC2, требования #2, #5)
- В opencode открыть свежую сессию (любая реальная задача)
- Вызвать `/curator-save` — показать в терминале:
  - агент извлёк кандидатов и сделал self-review через `curator_query`
  - сервер вернул preview (тип/сводка/теги/доказательство, отклонённые с причинами)
  - после подтверждения: `Авто-сохранено: N фактов`
- `cat <база>/session/reference.md` — показать write-back в .md
- Подчеркнуть: **в бэкенде нет LLM-вызовов** — мгновенный ответ, никаких таймаутов

### 3. Query: переиспользование знаний (UC3, требование #5 хакатона)
- В новой сессии спросить агента «какие проверенные правила по JVM?» → агент вызывает `curator_query` → ответ со связями/статусами

### 3а. Память управляет поведением (30 сек, главный вопрос жюри «как опыт меняет поведение»)
- Открыть `~/.config/opencode/AGENTS.md` — инсталлер вписал правила памяти:
  база в контексте каждой сессии (сверяйся перед задачей, предлагай `/curator-save`)
- Спросить агента что-нибудь по сохранённой теме — агент вызывает `curator_query` **до ответа**,
  факт из базы цитируется в ответе
- «Обученный агент ведёт себя иначе, чем с пустой памятью: он сверяется с базой сам»

### 4. Improve loop: автономное улучшение (UC4, требования #3, #4)
```bash
curator improve
```
Показать: дубликаты найдены/объединены, stale помечены, **метрики «до → после»**,
eval gate применяет только улучшения. Открыть `~/.curator/improve_events.jsonl` — observability (доп. блок #5).
Затем `curator status` — «Последний improve: дубликатов/устаревших/противоречий» и
`~/.curator/usage.json` — телеметрия: факты, которые спрашивают → полезны,
не спрашивают → кандидаты на пересмотр (не приговор).

### 5. Противоречия: автоматическое разрешение (доп. блок #2)
```bash
.venv/bin/python3 -c "
from curator.improve_loop import ImproveLoop
i = ImproveLoop.__new__(ImproveLoop)
from curator.models import StructuredFact
f1 = StructuredFact(type='Reference', title='Использовать X', tags=['t'], status='verified', content_summary='x'*50)
f2 = StructuredFact(type='Reference', title='Не использовать X', tags=['t'], status='hypothesis', content_summary='x'*10)
w, l, r = i._pick_winner(f1, f2)
print(f'{w.title} ← {l.title} ({r})')"
```
«Verified бьёт hypothesis — противоречия разрешаются автоматически».

### 5а. Карта проекта: знания по вашей структуре (интеграция со скиллом Егора)
- Открыть в opencode проект с документацией, набрать `/curator-create-map`
- Скил построит карту (спросит границы и куда сохранить — указать `DOCUMENTATION-MAP.md` в базе)
- Сохранить ещё один факт → показать: лёг в файл по теме карты, режим записи темы соблюдается

### 6. xmemory durability (номинация xmemory)
```bash
MEMORY_BACKEND=xmemory .venv/bin/python3 -c "from curator.demo import run_durability_demo; run_durability_demo()"
```
«Записали в xmemory → перезапустили процесс → данные на месте».

### 7. Offline-fallback (UC6, отказоустойчивость)
- Выключить VPN
- Сохранить факт через `/curator-save` → «прошло мгновенно: ушли в локальную БД + outbox»
```bash
curator status   # факты на месте
curator get ...  # читается из локальной
```
- Включить VPN
```bash
curator sync    # пуш outbox в xmemory
```

### 8. Тесты + матрица требований (30 сек)
```bash
.venv/bin/python -m pytest tests/ -q --ignore=tests/smoke
```
«Надёжность: 290+ тестов, каждое требование хакатона закрыто тестом с ID».
Открыть `design/requirements.md` — матрица 6/6 + 5/5 + 4/4.

## Ответ на вопрос жюри про multi-user (выучить)

> «Файлы .md — Git-tracked, конфликты решает стандартный Git merge. Факты —
> natural key (title) + UPSERT, коллизия правок = last-write-wins по updated_at
> + provenance в observability-лог. Offline — outbox с идемпотентным повтором.
> Командная синхронизация через xmemory — в роадмапе (`curator pull`).»

## Грабли (если что-то падает)

- MCP-сервер не подхватился → перезапустить opencode (конфиг читается при старте)
- durability demo пустой → VPN выключен или ключи не заданы
- `/curator-save` ругается на candidates → агент передал старый формат (session_text больше нет) — перечитать команду в `~/.config/opencode/opencode.json`
- `/curator-create-map` нет в списке → не запускали `curator install` или не перезапустили opencode
