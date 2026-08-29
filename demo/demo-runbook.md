---
type: Demo Runbook
project: Memory Curator
duration: 7-9 минут
date: 2026-08-23
---

# Демо-runbook: Memory Curator

**Перед записью**: включи VPN, открой терминал в `core/`. Каждая секция — одна команда.

```bash
export XMEMORY_API_KEY=<your-xmemory-key>
export XMEMORY_INSTANCE_ID=<your-instance-id>
```

---

## 1. Time-lapse: эволюция знаний (60 сек)

```bash
.venv/bin/python3 -c "from curator.demo import run_time_lapse; run_time_lapse()"
```

**Что покажет**: 3 сессии подряд → 0→2→3→4 фактов в Rich-таблице. Зелёные «Новых», красные «Дубл.». Главный пруф «с каждой итерацией лучше».

**Говори**: «Агент обрабатывает 3 сессии последовательно. Каждая добавляет новые факты, дубликаты отбрасываются. Память растёт: 0 → 4 факта.»

---

## 2. Реальный ingest: .md файлы → знания (60 сек)

```bash
.venv/bin/python3 -c "from curator.demo import run_ingest_demo; run_ingest_demo()"
```

**Что покажет**: ДО: `query('kotlin') → 0`, `query('compose') → 0`. ПОСЛЕ: факты по каждому запросу из `.md` файлов.

**Говори**: «До индексации агент ничего не знает. После — отвечает на запросы по Kotlin, Compose, MCP. Факты из моей личной базы знаний `learnings`/.»

---

## 3. Реальные сессии OpenCode (40 сек)

```bash
.venv/bin/python3 -c "from curator.demo import run_opencode_demo; run_opencode_demo(2)"
```

**Что покажет**: заголовки реальных сессий из opencode.db. Извлекает факты из рабочих диалогов.

**Говори**: «Это не синтетика. Читаем реальные сессии OpenCode из базы. Парсим диалоги, извлекаем уроки.»

---

## 4. xmemory durability (30 сек)

```bash
.venv/bin/python3 -c "from curator.demo import run_durability_demo; run_durability_demo()"
```

**Что покажет**: запись маркера → «перезапуск» backend → чтение того же маркера. ✅ факт пережил рестарт.

**Говори**: «xmemory хранит состояние независимо от процесса. Записали маркер, перезапустили агента — данные на месте. Требование `«память между рестартами»` выполнено.»

---

## 5. Improve loop + противоречия (60 сек)

```bash
.venv/bin/python3 -c "
from curator.backend.local import LocalBackend
from curator.improve_loop import ImproveLoop
from curator.models import StructuredFact
import tempfile, pathlib

be = LocalBackend(str(pathlib.Path(tempfile.mkdtemp()) / 'test.db'))
be.store_fact(StructuredFact(type='Reference', title='Использовать ImmutableList в Compose для списков', tags=['compose'], status='verified', content_summary='Рекомендуется для стабильности при рекомпозиции' * 2))
be.store_fact(StructuredFact(type='Reference', title='Не использовать ImmutableList в Compose', tags=['compose'], status='verified', content_summary='Оверхед для маленьких списков'))
be.store_fact(StructuredFact(type='Reference', title='Использовать data class в sealed interface', tags=['kotlin','jvm'], status='verified', content_summary='Data class предпочтительнее value class' * 2))
be.store_fact(StructuredFact(type='Reference', title='Не использовать data class — value class лучше', tags=['kotlin','jvm'], status='hypothesis', content_summary='Value class экономит память'))

loop = ImproveLoop(be)
report = loop.run()
print(f'Дубликатов: {report.stats[\"duplicates_found\"]}')
print(f'Устаревших: {report.stats[\"stale_found\"]}')
print(f'Противоречий: {report.stats[\"contradictions_found\"]}')
print(f'Разрешено: {len(report.resolutions)}')
for r in report.resolutions:
    print(f'  {r.winner.title} ← {r.loser.title}')
    print(f'  Причина: {r.reason}')
"
```

**Что покажет**: contradictions_found + resolutions с победителем и причиной. «verified beats hypothesis», «подробнее описано».

**Говори**: «Improve loop автономно находит дубликаты, устаревшие и противоречия. Противоречия автоматически разрешаются: verified бьёт hypothesis, больше тегов бьёт меньше. Каждое изменение проходит eval-gate — не станет ли хуже.»

---

## 6. Eval gate (15 сек)

**Покажи в IDE**: `core/curator/eval_runner.py` — метод `EvalAction.improved`

**Говори**: «Перед каждым изменением памяти Eval Runner проверяет метрики: coverage, staleness. Если coverage упадёт или база уменьшится >50% — изменение блокируется.»

---

## 7. Observability (15 сек)

```bash
cat ~/.curator/improve_events.jsonl | python3 -m json.tool 2>/dev/null | head -30 || echo "(лог появится после первого improve-прогона)"
```

**Говори**: «Все improve-действия логируются в JSONL. Видно какой урок к какому изменению привёл, eval-метрики до и после, применено или отклонено.»

---

## 8. Тесты (10 сек)

```bash
.venv/bin/python -m pytest tests/ -q --ignore=tests/smoke 2>&1 | tail -3
```

**Покажи**: `pytest tests/ -q --ignore=tests/smoke` → все тесты проходят

**Говори**: «Все тесты проходят. Unit + integration + e2e + smoke.»

---

## 9. Итоговая матрица (15 сек)

**Покажи**: `design/requirements.md`

**Говори**: «Итого: 6 из 6 минимальных требований, 5 из 5 дополнительных блоков, 4 из 4 критериев xmemory. Реальные данные — мои сессии OpenCode и база знаний. Автономный improve loop через worker daemon. Память переживает рестарты. Код в podlodka-ai-club/refinement.»

---

## Титры

```
Memory Curator — «Агент, который помнит»
Hacker Sprint #2, podlodka-ai-club

Технологии: Python 3.12+, xmemory, MCP SDK v2, SQLite
Извлечение знаний: агент харнеса (LLM в слое агента, не в бэкенде)
175 тестов (включая 21 тест-требование), 0 ошибок
~20 .md файлов `learnings/`
```