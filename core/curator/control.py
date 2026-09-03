"""curator CLI — универсальный интерфейс к Memory Curator.

Использование:
    curator save               — сохранить кандидатов знаний (JSON из stdin, извлекает агент)
    curator get "kotlin"       — поиск фактов
    curator start              — запустить worker daemon в фоне
    curator stop               — остановить worker
    curator status              — worker жив? последний improve? фактов в базе?
    curator report             — сводка: сегодня / 3 дня / неделя
    curator improve            — ручной запуск improve цикла
    curator routes             — текущие правила маршрутизации

Конфигурация:
    MEMORY_BACKEND: "local" | "xmemory"
    IMPROVE_INTERVAL_MINUTES: интервал daemon (default: 1440 = сутки)
    XMEMORY_API_KEY / XMEMORY_INSTANCE_ID
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

REPORT_DIR = Path.home() / ".curator" / "reports"
IMPROVE_LOG = Path.home() / ".curator" / "improve_events.jsonl"
USAGE_JSON = Path.home() / ".curator" / "usage.json"


def _header(title: str):
    try:
        from rich.console import Console
        from rich.panel import Panel
        Console().print(Panel(title, style="bold cyan", expand=False))
    except ImportError:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")


def _table(headers: list[str], rows: list[list], title: str = ""):
    try:
        from rich.table import Table
        from rich.console import Console
        c = Console()
        t = Table(title=title)
        for h in headers:
            t.add_column(h)
        for row in rows:
            t.add_row(*[str(c) for c in row])
        c.print(t)
    except ImportError:
        if title:
            print(f"\n  {title}")
        for row in rows:
            print(f"  {' | '.join(str(c) for c in row)}")


def cmd_status():
    _header("Curator Status")

    from curator.daemon import read_pid, is_running, pid_is_curator_worker
    pid = read_pid()
    if pid and is_running(pid) and pid_is_curator_worker(pid):
        print(f"  Worker: ✅ запущен (pid {pid})")
    else:
        print("  Worker: ⛔ остановлен")

    backend = _make_backend()
    try:
        from curator.models import FactQuery
        facts = backend.query_facts(FactQuery())
        by_type = {}
        by_status = {}
        for f in facts:
            by_type[f.type] = by_type.get(f.type, 0) + 1
            by_status[f.status] = by_status.get(f.status, 0) + 1
        print(f"\n  Фактов: {len(facts)}")
        print(f"  По типам: {json.dumps(by_type, ensure_ascii=False)}")
        print(f"  По статусам: {json.dumps(by_status, ensure_ascii=False)}")
    except Exception as e:
        print(f"  Ошибка чтения фактов: {e}")

    last_report = _last_report_time()
    if last_report:
        print(f"\n  Последний improve: {last_report}")

    if IMPROVE_LOG.exists():
        events = _read_events()
        today = [e for e in events if _is_today(e.get("ts", ""))]
        applied = sum(1 for e in today if e.get("applied"))
        skipped = sum(1 for e in today if not e.get("applied"))
        print(f"  Событий сегодня: {len(today)} (применено: {applied}, отклонено: {skipped})")

    interval = os.getenv("IMPROVE_INTERVAL_MINUTES", "1440")
    print(f"\n  Интервал improve: {interval} мин ({_human_interval(int(interval))})")


def cmd_report(days: int = 0):
    period = "за всё время" if days == 0 else f"за {days} дн."
    _header(f"Curator Report — {period}")

    cutoff = None
    if days > 0:
        cutoff = datetime.now() - timedelta(days=days)

    _section_usage(cutoff)
    _section_improve_log(cutoff)


def _section_usage(cutoff):
    if not USAGE_JSON.exists():
        print("  Нет данных об использовании.")
        return

    try:
        data = json.loads(USAGE_JSON.read_text())
    except Exception:
        return

    sorted_items = sorted(data.items(), key=lambda x: x[1].get("count", 0), reverse=True)
    active = [(t, d["count"], d.get("last_access", 0)) for t, d in sorted_items[:10] if d.get("count", 0) > 0]
    if active:
        rows = []
        for i, (title, count, last) in enumerate(active[:10], 1):
            last_str = datetime.fromtimestamp(last).strftime("%d.%m %H:%M") if last else "—"
            rows.append([str(i), title[:60], str(count), last_str])
        _table(["#", "Факт", "Запросов", "Последний доступ"], rows, "Топ запросов")

    now = time.time()
    unused_30 = [t for t, d in sorted_items if d.get("last_access", 0) < now - 30 * 86400]
    unused_90 = [t for t, d in sorted_items if d.get("last_access", 0) < now - 90 * 86400]
    if unused_30 or unused_90:
        print(f"\n  Забытые: >30д: {len(unused_30)}, >90д: {len(unused_90)}")


def _section_improve_log(cutoff):
    events = _read_events()
    if not events:
        print("  Нет данных improve-лога.")
        return

    if cutoff:
        events = [e for e in events if e.get("ts", "") >= cutoff.isoformat()[:10]]

    applied = sum(1 for e in events if e.get("applied"))
    skipped = sum(1 for e in events if not e.get("applied"))
    by_action = {}
    for e in events:
        a = e.get("action", "unknown")
        by_action[a] = by_action.get(a, 0) + 1

    print(f"\n  Всего событий: {len(events)} (✅ {applied}, ⛔ {skipped})")
    for action, count in sorted(by_action.items()):
        print(f"    {action}: {count}")

    recent = events[-5:]
    if recent:
        rows = []
        for e in recent:
            ts = e.get("ts", "")[:16].replace("T", " ")
            applied_str = "✅" if e.get("applied") else "⛔"
            before = e.get("eval_before")
            after = e.get("eval_after")
            eval_str = f"{before:.0%}→{after:.0%}" if isinstance(before, (int, float)) and isinstance(after, (int, float)) else "—"
            facts = e.get("facts", [])
            detail = facts[0][:60] if facts else "—"
            rows.append([ts, e.get("action", "?"), applied_str, eval_str, detail])
        _table(["Время", "Действие", "", "Eval", "Детали"], rows, "Последние события")


def cmd_save(auto_yes: bool = False):
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not raw.strip():
        print("Ошибка: нет данных. Используйте: curator save < candidates.json")
        print('  Формат: [{"type": "Reference", "title": "...", "content_summary": "...", "tags": ["..."], "evidence": "..."}]')
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Ошибка: stdin не является валидным JSON ({e})")
        return

    if isinstance(data, dict):
        data = data.get("candidates") or data.get("facts") or []
    if not isinstance(data, list) or not data:
        print('Ошибка: ожидается непустой массив кандидатов (или {"candidates": [...]})')
        return

    _header("Curator Save — кандидаты от агента")

    from curator.models import ProposedFact, StructuredFact, parse_tags, resolve_fact_type
    proposed = []
    for i, c in enumerate(data, 1):
        title = str(c.get("title", "")).strip() if isinstance(c, dict) else ""
        summary = str(c.get("content_summary", "")).strip() if isinstance(c, dict) else ""
        if not title or not summary:
            print(f"  ⚠ Кандидат #{i} некорректен (нет title/content_summary) — пропущен")
            continue
        fact_type, type_error = resolve_fact_type(
            str(c.get("type", "Reference")).strip(),
            new_type=str(c.get("new_type", "")).lower() in ("true", "1", "yes"),
            type_description=str(c.get("type_description", "") or ""),
        )
        if fact_type is None:
            print(f"  ⚠ Кандидат #{i}: {type_error}")
            continue
        proposed.append(ProposedFact(
            type=fact_type,
            title=title,
            content_summary=summary,
            tags=parse_tags(c.get("tags")),
            evidence=str(c.get("evidence", "") or ""),
            source_file=str(c.get("source_file", "") or "").strip() or None,
        ))

    if not proposed:
        print("  Валидных кандидатов нет.")
        return

    backend = _make_backend()
    from curator.gatekeeper import Gatekeeper
    gk = Gatekeeper(backend)
    result = gk.filter(proposed)

    print(f"\n  Получено: {len(proposed)}")
    print(f"  Одобрено: {len(result.approved)}")
    print(f"  Отклонено: {len(result.rejected)}")

    if result.rejected:
        print("\n  Отклонённые:")
        for fact, reason in result.rejected:
            print(f"    ⛔ {fact.title[:70]} — {reason}")

    if result.approved:
        print("\n  Одобренные:")
        for fact in result.approved:
            print(f"    ✅ {fact.title[:70]}")
            print(f"       {fact.type} | {', '.join(fact.tags[:5])}")

        if auto_yes:
            answer = "y"
        else:
            print(f"\n  Сохранить {len(result.approved)} фактов? [y/N]: ", end="")
            answer = input().strip().lower()
        if answer == "y":
            from curator.routing import get_router, route_fact_safe
            from curator.sync_engine import SyncEngine
            from curator.retrieval_feedback import RetrievalFeedback
            router = get_router()
            base_dir = Path(os.getenv("CURATOR_BASE_DIR", os.path.expanduser("~/Documents/AI/personal/learnings")))
            sync = SyncEngine(backend, base_dir)
            fb = RetrievalFeedback()
            saved = 0
            for fact in result.approved:
                structured = StructuredFact(
                    type=fact.type, title=fact.title, tags=fact.tags,
                    status="verified", content_summary=fact.content_summary,
                    source_file=route_fact_safe(router, fact),
                )
                backend.store_fact(structured)
                try:
                    sync.write_fact_to_md(structured)
                except Exception as e:
                    # Факт в DB, но в .md его нет — молчать нельзя
                    print(f"    ⚠ write-back в .md не удался для '{fact.title[:50]}': {e}")
                fb.record_save(fact.title)
                saved += 1
            print(f"  ✅ Сохранено: {saved} фактов")
        else:
            print("  Сохранение отменено.")


def cmd_get(query: str = ""):
    if not query:
        print("Использование: curator get 'kotlin'")
        return

    _header(f"Curator Get — поиск: '{query}'")
    backend = _make_backend()
    from curator.models import FactQuery
    facts = backend.query_facts(FactQuery(search=query))
    if not facts:
        print("  Ничего не найдено.")
        return

    print(f"  Найдено: {len(facts)}")
    rows = []
    for f in facts:
        rows.append([f.title[:60], f.type, f.status, ", ".join(f.tags[:4])])
    _table(["Факт", "Тип", "Статус", "Теги"], rows)


def cmd_start():
    from curator.daemon import ensure_worker
    print(ensure_worker())


def cmd_stop():
    from curator.daemon import stop_worker
    print(stop_worker())


def cmd_demo():
    args = sys.argv[2:]
    keep = "--keep" in args
    backend = "local"
    if "--backend" in args:
        idx = args.index("--backend")
        if idx + 1 < len(args):
            backend = args[idx + 1]
    from curator.tour import run_tour
    run_tour(backend=backend, keep=keep)


def cmd_install():
    """Установить Memory Curator: opencode или Claude Code (MCP + команды + скиллы + worker)."""
    _header("Curator Install")
    from curator import installer

    args = sys.argv[2:]
    if "--opencode" in args:
        target = "opencode"
    elif "--claude" in args:
        target = "claude"
    else:
        print("  Куда ставим?")
        print("  1) opencode")
        print("  2) Claude Code")
        answer = input("  Выбор [1/2]: ").strip()
        target = "claude" if answer == "2" else "opencode"

    base_dir = None
    if "--base-dir" in args:
        idx = args.index("--base-dir")
        if idx + 1 < len(args):
            base_dir = args[idx + 1]
    if base_dir is None:
        # Единственный вопрос установки: база может лежать где угодно —
        # это просто папка с .md (можно внутри репо проекта, чтобы жила в гите)
        print("\n  Куда класть базу знаний? Может быть любой путь —")
        print("  факты и .md лягут туда (папка создастся при первом сохранении).")
        answer = input(f"  Путь [{installer.default_base_dir()}]: ").strip()
        base_dir = answer or installer.default_base_dir()

    print()
    if target == "opencode":
        steps = installer.install_opencode(base_dir=base_dir)
    else:
        steps = installer.install_claude(base_dir=base_dir)
    for step in steps:
        print(f"  {step}")


def cmd_sync():
    _header("Curator Sync — пуш outbox в xmemory")

    key = os.getenv("XMEMORY_API_KEY", "")
    inst = os.getenv("XMEMORY_INSTANCE_ID", "")
    if not key or not inst:
        print("  ⚠ Нет XMEMORY_API_KEY / XMEMORY_INSTANCE_ID — синк невозможен.")
        return

    from curator.outbox import Outbox
    from curator.backend.xmemory import XMemoryBackend
    ob = Outbox()
    pending = ob.pending()
    if not pending:
        print("  Outbox пуст — нечего синхронизировать.")
        return

    print(f"  В очереди: {len(pending)} фактов")
    xmem = XMemoryBackend(api_key=key, instance_id=inst)
    pushed = 0
    failed = 0
    for row_id, fact in pending:
        try:
            xmem.push_direct(fact)
            ob.mark_synced(row_id)
            pushed += 1
        except Exception as e:
            ob.fail(row_id)
            failed += 1
            print(f"    ⛔ {fact.title[:60]} — {str(e)[:80]}")
    print(f"  ✅ Отправлено: {pushed}, ⛔ Не удалось: {failed}")


def cmd_improve():
    _header("Curator Improve")
    backend = _make_backend()
    from curator.improve_loop import ImproveLoop
    loop = ImproveLoop(backend)
    report = loop.run()

    # Жизненный цикл в .md: задеприкейтнутые → маркер [УСТАРЕЛО]
    base_dir = Path(os.getenv("CURATOR_BASE_DIR", os.path.expanduser("~/Documents/AI/personal/learnings")))
    from curator.sync_engine import SyncEngine
    sync = SyncEngine(backend, base_dir)
    for f in report.deprecated:
        try:
            sync.rewrite_status(f)
        except Exception as e:
            print(f"  ⚠ write-back в .md не удался для '{f.title[:50]}': {e}")

    print(f"  Фактов: {report.stats['total_facts']}")
    print(f"  Дубликатов: {report.stats['duplicates_found']}")
    print(f"  Устаревших: {report.stats['stale_found']}")
    print(f"  Противоречий: {report.stats['contradictions_found']}")
    if report.metrics_before and report.metrics_after:
        b, a = report.metrics_before, report.metrics_after
        print(f"\n  Метрики (до → после): coverage {b.query_coverage:.0%} → {a.query_coverage:.0%}, "
              f"факты {b.total_facts} → {a.total_facts}")
    if report.duplicates:
        print(f"\n  Дубликаты ({len(report.duplicates)}):")
        for f1, f2 in report.duplicates[:5]:
            print(f"    '{f1.title[:50]}' ↔ '{f2.title[:50]}'")
    if report.contradictions:
        print(f"\n  Противоречия ({len(report.contradictions)}):")
        for f1, f2 in report.contradictions[:5]:
            print(f"    ⚡ '{f1.title[:50]}' ↔ '{f2.title[:50]}'")
    if getattr(report, "resolutions", None):
        print(f"\n  Разрешено ({len(report.resolutions)}):")
        for r in report.resolutions[:5]:
            print(f"    ✅ {r.winner.title[:50]} ← {r.loser.title[:50]}")
            print(f"       {r.reason}")
    if report.events:
        print("\n  Eval-решения:")
        for e in report.events[-5:]:
            status = "✅" if e.get("applied") else "⛔"
            print(f"    {e['action']}: {status}")


def cmd_routes():
    _header("Curator Routes")
    from curator.routing import get_router
    router = get_router()
    routes = router.list_routes()
    rows = []
    for r in routes:
        path = r.get("path", "?")
        desc = r.get("description", "")
        rules = r.get("rules", "")
        if isinstance(rules, list):
            rules = ", ".join(str(rule) for rule in rules)
        rows.append([path, desc, str(rules)[:60]])
    _table(["Путь", "Описание", "Правила"], rows)


def _make_backend():
    backend_type = os.getenv("MEMORY_BACKEND", "local")
    if backend_type == "xmemory":
        from curator.backend.xmemory import XMemoryBackend
        return XMemoryBackend(
            api_key=os.getenv("XMEMORY_API_KEY", ""),
            instance_id=os.getenv("XMEMORY_INSTANCE_ID", ""),
        )
    else:
        from curator.backend.local import LocalBackend
        return LocalBackend(os.path.expanduser("~/.curator/knowledge.db"))


def _read_events():
    if not IMPROVE_LOG.exists():
        return []
    events = []
    with open(IMPROVE_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


def _is_today(ts: str) -> bool:
    return ts[:10] == datetime.now().isoformat()[:10]


def _last_report_time():
    if not REPORT_DIR.exists():
        return None
    reports = sorted(REPORT_DIR.glob("improve_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        return None
    return datetime.fromtimestamp(reports[0].stat().st_mtime).strftime("%d.%m.%Y %H:%M")


def _human_interval(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ч"
    days = hours // 24
    return f"{days} д"


def main():
    if len(sys.argv) < 2:
        print("curator — Memory Curator CLI")
        print("Использование:")
        print("  curator save              — сохранить кандидатов (JSON из stdin, извлекает агент)")
        print("  curator get <query>       — поиск фактов")
        print("  curator start             — запустить worker daemon")
        print("  curator stop              — остановить worker")
        print("  curator status            — worker + факты + последний improve")
        print("  curator report [-d N]    — сводка (за N дней или всё время)")
        print("  curator improve           — ручной improve цикл")
        print("  curator routes            — правила маршрутизации")
        print("  curator sync              — пуш offline-outbox в xmemory")
        print("  curator install [--opencode|--claude] — установить в opencode / Claude Code (MCP + скилл + worker)")
        print("  curator demo [--keep] [--backend xmemory] — тур: полный цикл жизни знания")
        print()
        print("Конфигурация: MEMORY_BACKEND, IMPROVE_INTERVAL_MINUTES, XMEMORY_API_KEY")
        return

    cmd = sys.argv[1].lower()
    if cmd == "status":
        cmd_status()
    elif cmd == "report":
        days = 0
        if len(sys.argv) >= 4 and sys.argv[2] == "-d":
            days = int(sys.argv[3])
        cmd_report(days=days)
    elif cmd == "save":
        auto_yes = any(a in ("-y", "--yes") for a in sys.argv[2:])
        cmd_save(auto_yes=auto_yes)
    elif cmd == "get":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        cmd_get(query)
    elif cmd == "start":
        cmd_start()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "improve":
        cmd_improve()
    elif cmd == "routes":
        cmd_routes()
    elif cmd == "sync":
        cmd_sync()
    elif cmd == "install":
        cmd_install()
    elif cmd == "demo":
        cmd_demo()
    else:
        print(f"Неизвестная команда: {cmd}")
        print("Доступные: save, get, start, stop, status, report, improve, routes, sync, demo")


if __name__ == "__main__":
    main()