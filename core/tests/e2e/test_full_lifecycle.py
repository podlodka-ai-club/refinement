"""E2E: полный жизненный цикл знания — всё заявленное, один связный сценарий.

Сценарий = скрипт демо: capture (валидные + мусор) → query → improve
(дубликаты + противоречия + eval-гейт) → жизненный цикл отражается в .md →
rebuild из .md не воскрешает устаревшее. Отдельно: decay по usage и
offline-fallback xmemory → outbox → sync (реальный HTTP, не моки путей).

Изоляция: HOME → tmp. Все ~/.curator/... пути (usage, outbox, логи) и базы
живут в песочнице — реальное окружение пользователя не затрагивается.
"""

import json
import time
from pathlib import Path

import pytest

from curator.backend.local import LocalBackend
from curator.gatekeeper import Gatekeeper
from curator.improve_loop import ImproveLoop
from curator.models import FactQuery, StructuredFact
from curator.sync_engine import SyncEngine
from curator.retrieval_feedback import RetrievalFeedback

A_TITLE = "Правило про kotlin inline классы и sealed interface"
B_TITLE = A_TITLE + " бокс"  # near-дубликат A, similarity > 0.8
WINNER_TITLE = "Никогда не используй rxjava в новых модулях"
LOSER_TITLE = "Всегда используй rxjava в новых модулях"
STYLE_TITLE = "Стиль git коммитов в рабочих проектах"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _wire_server(monkeypatch, be: LocalBackend, md_dir: Path, usage_path: Path):
    """Подменить глобальные зависимости MCP-сервера на песочницу."""
    import curator.server as server_mod

    monkeypatch.setattr(server_mod, "backend", be)
    monkeypatch.setattr(server_mod, "improve", ImproveLoop(be))
    monkeypatch.setattr(server_mod, "gatekeeper", Gatekeeper(be))
    monkeypatch.setattr(server_mod, "base_dir", md_dir)
    monkeypatch.setattr(server_mod, "feedback", RetrievalFeedback(str(usage_path)))
    return server_mod


class TestDeclaredLifecycle:
    """Один сценарий — вся заявка: capture, query, improve, write-back,
    rebuild из .md. Каждый шаг идёт через продакшен-путь (server-хендлеры)."""

    def test_full_story(self, tmp_path, monkeypatch):
        home = tmp_path
        md_dir = home / "learnings"
        be = LocalBackend(str(home / "db" / "knowledge.db"))
        usage_path = home / "usage.json"
        server_mod = _wire_server(monkeypatch, be, md_dir, usage_path)

        # ---- Шаг 1: агент сохраняет кандидатов: 5 валидных + 2 мусорных.
        # Near-дубликаты A/B проходят одним батчем (gatekeeper смотрит базу,
        # не батч) — их консолидирует improve loop, это заявленный кейс.
        candidates = [
            {"type": "Reference", "title": A_TITLE,
             "content_summary": "JvmInline value class внутри sealed interface боксируется. Проверено исходниками.",
             "tags": ["kotlin"], "evidence": "сессия"},
            {"type": "Reference", "title": B_TITLE,
             "content_summary": "Бокс при использовании value class внутри sealed interface неизбежен.",
             "tags": ["kotlin"]},
            {"type": "Style", "title": STYLE_TITLE,
             "content_summary": "Коммит содержит модуль и Jira-ключ: type[module]: AAA-000.",
             "tags": ["git"]},
            # противоречивая пара: победителя выбирает improve (длиннее сводка)
            {"type": "Reference", "title": LOSER_TITLE,
             "content_summary": "Короткая сводка про rxjava.",
             "tags": ["rx", "java"]},
            {"type": "Reference", "title": WINNER_TITLE,
             "content_summary": "Подробная сводка: rxjava запрещена в новых модулях, только coroutines flow.",
             "tags": ["rx", "java"]},
            # мусор: слишком короткий title и мета-строка в summary
            {"type": "Reference", "title": "Коротко",
             "content_summary": "сводка нормальной длины", "tags": ["x"]},
            {"type": "Reference", "title": "Заголовок достаточно длинный",
             "content_summary": "*Тип:* Reference подделка", "tags": ["x"]},
        ]
        out = server_mod._session_capture({"candidates": candidates, "auto_approve": True})

        assert "Отклонено: 2" in out, f"мусор обязан отклоняться gatekeeper'ом:\n{out}"
        assert "Авто-сохранено: 5 фактов" in out
        assert "Слишком короткий заголовок" in out

        # upsert-инвариант: 5 фактов в базе, а не 10 — повторный вызов того
        # же батча не плодит строки (title = natural key)
        server_mod._session_capture({"candidates": candidates[:5], "auto_approve": True})
        assert len(be.query_facts(FactQuery())) == 5

        # write-back: факты легли в .md через роутинг session/{type}.md
        reference_md = (md_dir / "session" / "reference.md").read_text(encoding="utf-8")
        style_md = (md_dir / "session" / "style.md").read_text(encoding="utf-8")
        assert f"### {A_TITLE}" in reference_md
        assert f"### {B_TITLE}" in reference_md
        assert f"### {STYLE_TITLE}" in style_md

        # ---- Шаг 2: query находит, usage-телеметрия пишется
        out = server_mod._query({"search": "kotlin"})
        assert "Найдено: 2" in out and A_TITLE in out
        stats = RetrievalFeedback(str(usage_path)).get_stats(10)
        assert {s["title"] for s in stats} == {A_TITLE, B_TITLE}
        assert all(s["count"] == 1 for s in stats)

        # ---- Шаг 2а: наблюдаемость (сохранённое видно через тулзы)
        out = server_mod._status()
        assert "Всего фактов: 5" in out, "status отражает то, что сохранили"
        assert "Типы (словарь для агента):" in out
        assert "Reference —" in out, "описания типов — контракт для агента"
        out = server_mod._feedback()
        assert "kotlin" in out or A_TITLE in out, "телеметрия запросов живая"

        # ---- Шаг 3: improve — дубликат консолидирован (eval-гейт одобрил:
        # покрытие запросов не упало), противоречие разрешено, .md отражает
        out = server_mod._improve()
        assert "Найдено дубликатов: 1" in out
        assert "Противоречия" in out
        assert WINNER_TITLE in out
        assert "Метрики (до → после)" in out, "замер пользы обязана быть в отчёте"

        by_title = {f.title: f for f in be.query_facts(FactQuery())}
        assert by_title[B_TITLE].status == "deprecated", "dup-проигравший устаревает"
        assert by_title[A_TITLE].status == "verified"
        assert by_title[LOSER_TITLE].status == "deprecated", "проигравший противоречия устаревает"
        assert by_title[WINNER_TITLE].status == "verified"

        # жизненный цикл отражён в .md: устаревшие помечены, rebuild из .md
        # их не воскрешает
        reference_md = (md_dir / "session" / "reference.md").read_text(encoding="utf-8")
        assert f"### {B_TITLE} [УСТАРЕЛО]" in reference_md
        assert f"### {LOSER_TITLE} [УСТАРЕЛО]" in reference_md
        # A_TITLE — префикс B_TITLE: считаем точные строки-заголовки, не подстроки
        a_headers = [line for line in reference_md.splitlines() if line == f"### {A_TITLE}"]
        assert len(a_headers) == 1, "секция A не должна дублироваться"

        # ---- Шаг 4: rebuild из .md в чистую базу — раунд-трип заявки
        be2 = LocalBackend(str(home / "db2" / "knowledge.db"))
        from curator.analyzers.ingest import ingest_directory
        saved = ingest_directory(md_dir, be2, Gatekeeper(be2, check_duplicates=False))

        assert saved == 3, "A, winner и Style; устаревшие секции ingest пропускает"
        rebuilt = {f.title: f for f in be2.query_facts(FactQuery())}
        assert set(rebuilt) == {A_TITLE, WINNER_TITLE, STYLE_TITLE}
        assert rebuilt[A_TITLE].type == "Reference"
        assert rebuilt[A_TITLE].tags == ["kotlin"]
        assert rebuilt[STYLE_TITLE].type == "Style"

        # ---- Шаг 5: навигация: автогенерируемый index.md отражает живое
        index = (md_dir / "index.md").read_text(encoding="utf-8")
        assert SyncEngine.INDEX_MARKER in index
        assert f"- [{A_TITLE}](session/reference.md)" in index
        assert f"- [{WINNER_TITLE}](session/reference.md)" in index
        assert f"- [{STYLE_TITLE}](session/style.md)" in index
        assert B_TITLE not in index, "устаревшие не попадают в навигацию"


class TestDecayByUsage:
    """Заявка «устаревание по использованию»: 30д без запросов →
    verified→hypothesis, 90д → hypothesis→deprecated (worker-цикл)."""

    def test_decay(self, tmp_path, monkeypatch):
        home = tmp_path
        md_dir = home / "learnings"
        md_dir.mkdir()
        be = LocalBackend(str(home / "db" / "knowledge.db"))

        fact_recent = StructuredFact(type="Reference", title="Проверенное правило про compose рекомпозицию",
                                     tags=["compose"], status="verified",
                                     content_summary="Рекомпозиция в compose управляется stability входов.",
                                     source_file="session/reference.md")
        # title содержит латинское "architecture": факт уникально покрывает
        # тестовый запрос eval-гейта → improve НЕ деприкейтит его (coverage
        # упал бы), устаревание делает decay-цикл по usage — ровно заявка
        fact_old_hyp = StructuredFact(type="Reference", title="Старая гипотеза про architecture модулей",
                                      tags=["architecture"], status="hypothesis",
                                      content_summary="Гипотеза: слои обязаны делиться по модулям.",
                                      source_file="session/reference.md")
        for f in (fact_recent, fact_old_hyp):
            be.store_fact(f)
            SyncEngine(be, md_dir).write_fact_to_md(f)

        # usage-сид: fresh не запрашивали 40 дней, old — 100 дней
        usage_path = home / ".curator" / "usage.json"
        usage_path.parent.mkdir(parents=True)
        now = time.time()
        usage_path.write_text(json.dumps({
            fact_recent.title: {"count": 1, "last_access": now - 40 * 86400},
            fact_old_hyp.title: {"count": 0, "last_access": now - 100 * 86400},
        }))

        from curator import worker
        data = worker.run_improve_cycle(be, home / "reports", base_dir=md_dir)

        by_title = {f.title: f for f in be.query_facts(FactQuery())}
        assert by_title[fact_recent.title].status == "hypothesis", "unused > 30д деградирует"
        assert by_title[fact_old_hyp.title].status == "deprecated", "unused > 90д уходит"

        decay_titles = {e["title"]: e for e in data["auto_decay"]}
        assert decay_titles[fact_recent.title]["reason"] == "unused > 30d"
        assert decay_titles[fact_old_hyp.title]["reason"] == "unused > 90d"
        assert list((home / "reports").glob("improve_*.json")), "отчёт цикла обязан писаться"

        # жизненный цикл в .md: deprecated → [УСТАРЕЛО], hypothesis → Гипотеза
        md_text = (md_dir / "session" / "reference.md").read_text(encoding="utf-8")
        assert f"### {fact_old_hyp.title} [УСТАРЕЛО]" in md_text
        assert "*Статус:* Гипотеза" in md_text


class TestOfflineOutbox:
    """Заявка UC6: xmemory недоступен → факт не теряется (локальная БД +
    outbox), восстановление → sync пушит. Реальная сеть: мёртвый порт,
    затем живой локальный HTTP-сервер."""

    def test_offline_fallback_and_sync(self, tmp_path, monkeypatch):
        from curator.backend.xmemory import XMemoryBackend
        from curator.outbox import Outbox

        fact = StructuredFact(type="Reference",
                               title="Факт переживший недоступность xmemory",
                               tags=["offline"], status="verified",
                               content_summary="Сеть лежала, но знание дошло через outbox.")
        local_db = str(tmp_path / "knowledge.db")
        outbox_db = str(tmp_path / "outbox.db")

        # порт 1: bind требует root → ConnectError гарантирован, без внешней сети
        monkeypatch.setattr(XMemoryBackend, "BASE_URL", "http://127.0.0.1:1")
        xmem = XMemoryBackend(api_key="test-key", instance_id="inst-42",
                              local_path=local_db, outbox_path=outbox_db)

        ref = xmem.store_fact(fact)
        assert ref.title == fact.title
        assert len(xmem.query_facts(FactQuery(search="недоступность"))) == 1, \
            "чтение деградирует на локальную БД, знание доступно офлайн"

        ob = Outbox(outbox_db)
        assert ob.count() == 1, "запись обязана встать в очередь"

        # восстановление: живой локальный HTTP-сервер
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Handler(BaseHTTPRequestHandler):
            received = []

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                Handler.received.append({
                    "path": self.path,
                    "auth": self.headers.get("Authorization"),
                    "body": body,
                })
                payload = json.dumps({"items": [{"write_id": f"write-{len(Handler.received)}"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        import threading
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            monkeypatch.setattr(XMemoryBackend, "BASE_URL", f"http://127.0.0.1:{httpd.server_port}")

            # `curator sync` — свежий процесс с новым клиентом (кэш httpx.Client
            # старого инстанса держит мёртвый base_url — как в реальном CLI)
            xmem2 = XMemoryBackend(api_key="test-key", instance_id="inst-42",
                                   local_path=local_db, outbox_path=outbox_db)
            pushed = 0
            for row_id, pending_fact in ob.pending():
                xmem2.push_direct(pending_fact)
                ob.mark_synced(row_id)
                pushed += 1
        finally:
            httpd.shutdown()

        assert pushed == 1
        assert ob.count() == 0, "очередь после sync пуста"
        assert len(Handler.received) == 1
        assert Handler.received[0]["path"] == "/instances/inst-42/write"
        assert Handler.received[0]["auth"] == "Bearer test-key"
        assert "Факт переживший недоступность xmemory" in Handler.received[0]["body"]["text"]


class TestMapRoutingE2E:
    """Сквозная интеграция с картой участника 1: capture → MapRouter →
    таргеты карты, mode в write-back (readonly — честный ⚠), routes
    показывает темы, OKF-тип факта не мутируется маршрутизацией."""

    def test_capture_routes_via_map(self, tmp_path, monkeypatch):
        home = tmp_path
        md_dir = home / "learnings"
        md_dir.mkdir()
        (md_dir / "DOCUMENTATION-MAP.md").write_text(
            "---\n"
            "status: draft\n"
            "categories: [knowledge, rules, records]\n"
            "modes: [update, append, readonly]\n"
            "on_unmatched: report\n"
            "topics:\n"
            "  - name: kotlin\n"
            "    watch_for: знания о kotlin\n"
            "    targets:\n"
            "      - path: docs/kotlin.md\n"
            "        captures: [knowledge]\n"
            "        mode: update\n"
            "  - name: journal\n"
            "    watch_for: исторические записи\n"
            "    targets:\n"
            "      - path: docs/journal.md\n"
            "        captures: [records]\n"
            "        mode: append\n"
            "  - name: context\n"
            "    watch_for: только контекст\n"
            "    targets:\n"
            "      - path: docs/context.md\n"
            "        captures: [knowledge]\n"
            "        mode: readonly\n"
            "---\n",
            encoding="utf-8",
        )

        be = LocalBackend(str(home / "db" / "knowledge.db"))
        server_mod = _wire_server(monkeypatch, be, md_dir, home / "usage.json")
        from curator.routing.map_router import MapRouter
        monkeypatch.setattr(server_mod, "router", MapRouter(md_dir / "DOCUMENTATION-MAP.md"))

        candidates = [
            {"type": "Reference", "title": "Правило про kotlin inline классы и sealed",
             "content_summary": "JvmInline внутри sealed interface боксируется всегда.",
             "tags": ["kotlin"]},
            {"type": "Spec", "title": "Решение журнала про стек тестирования",
             "content_summary": "Историческое решение: выбираем junit5 для новых модулей.",
             "tags": ["journal"]},
            {"type": "Reference", "title": "Контекстный факт readonly таргета",
             "content_summary": "Этот факт попадает в readonly таргет и не пишется в .md.",
             "tags": ["context"]},
        ]
        out = server_mod._session_capture({"candidates": candidates, "auto_approve": True})

        assert "Авто-сохранено: 3" in out
        assert "readonly" in out, "readonly — видимый отказ записи в .md, не молчание"

        by_title = {f.title: f for f in be.query_facts(FactQuery())}
        assert by_title["Правило про kotlin inline классы и sealed"].source_file == "docs/kotlin.md"
        assert by_title["Решение журнала про стек тестирования"].source_file == "docs/journal.md"
        # OKF-инвариант: карта решает только путь, тип факта не мутируется
        assert by_title["Правило про kotlin inline классы и sealed"].type == "Reference"
        assert by_title["Решение журнала про стек тестирования"].type == "Spec"

        assert (md_dir / "docs" / "kotlin.md").exists()
        assert (md_dir / "docs" / "journal.md").exists()
        assert not (md_dir / "docs" / "context.md").exists(), "readonly не пишет .md"

        # routes: темы карты с mode видны до сохранения
        out = server_mod._routes()
        assert "docs/kotlin.md (mode: update)" in out
        assert "docs/journal.md (mode: append)" in out
        assert "kotlin" in out
