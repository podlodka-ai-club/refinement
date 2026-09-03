# Тесты требований — трассировочная матрица

> Каждый тест = одно требование из `design/requirements.md`. Запуск:
> ```bash
> .venv/bin/python -m pytest tests/requirements/ -v
> ```
> Названия тестов = ID требований. Только публичные API (ingest, MCP-функции,
> backend Protocol, CLI-функции) — внутренние рефакторинги не могут «обнулить» тест.

## MUST HAVE (6/6)

| ID | Требование | Тест | Статус |
|----|-----------|------|--------|
| R1 | Поток задач из источника (.md → факты) | `test_hackathon_must.py::test_R1_поток_задач_из_источника_ingest` | ✅ |
| R2 | Цикл «выполнил → оценил → извлёк урок» (candidates → gatekeeper → store) | `test_R2_цикл_выполнил_оценил_извлёк_урок` | ✅ |
| R3 | Менять поведение на основе опыта (improve консолидирует дубликаты) | `test_R3_поведение_меняется_на_основе_опыта` | ✅ |
| R4 | Память между рестартами (персистентный файл, не :memory:) | `test_R4_память_между_рестартами` | ✅ |
| R5 | Реальные данные (фикстуры = структура learnings) | `test_R5_реальные_данные_структуры_learnings` | ✅ |
| R6 | Дельта «до/после» (clean принимает / trained отклоняет дубли) | `test_R6_дельта_до_и_после` | ✅ |

## NICE TO HAVE (5/5)

| ID | Требование | Тест | Статус |
|----|-----------|------|--------|
| N1 | Забывание: семантическое устаревание (hypothesis → deprecated по eval-гейту), таймерного decay нет — телеметрия = observability | `test_nice_to_have.py::test_N1_забывание_семантическое` | ✅ |
| N2 | Противоречия: verified побеждает hypothesis | `test_N2_противоречия_разрешаются` | ✅ |
| N3 | Eval gate: блокирует ухудшение метрик, разрешает чистку | `test_N3_eval_блокирует_ухудшение` | ✅ |
| N4 | Human-in-the-loop: без approve база не меняется | `test_N4_human_in_the_loop` | ✅ |
| N5 | Observability: JSONL-лог всех improve-действий | `test_N5_observability_логирует_улучшения` | ✅ |

## xmemory номинация (4/4)

| ID | Требование | Тест | Статус |
|----|-----------|------|--------|
| X1 | Durability write→read (smoke — VPN + ключи) | `test_xmemory_criteria.py::test_X1_durability_write_read` | smoke |
| X2 | XMD-схема: required поля, enum, primary_key | `test_X2_схема_под_задачу` | ✅ |
| X3 | xmemory primary при MEMORY_BACKEND=xmemory | `test_X3_xmemory_primary_backend` | ✅ |
| X4 | Наглядность: curator_status со счётчиками | `test_X4_наглядность_статуса` | ✅ |

## Spec UC (spec.md)

| ID | Требование | Тест | Статус |
|----|-----------|------|--------|
| UC2 | Write-back: approve → факт в .md | `unit/test_session_capture.py::test_auto_approve_writes_md` | ✅ |
| UC6 | Fallback: сеть падает → локальная БД + outbox → sync | `test_uc_fallback.py` (6 тестов: store/query/4xx/upsert/sync) | ✅ |

## Регрессии, пойманные этим подходом

- **R4**: fallback в `:memory:` терял данные при «рестарте» — зелёные юнит-тесты
  это не ловили (проверяли код, а не требование). Requirement-тест упал бы сразу.
- **UC6**: fallback срабатывал только при пустых ключах, а не при сетевой ошибке
  (наш реальный баг, починен 29.08).
