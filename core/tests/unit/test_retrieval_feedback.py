"""Тесты RetrievalFeedback."""

import json
import time
import tempfile
from pathlib import Path
from curator.retrieval_feedback import RetrievalFeedback


class TestRetrievalFeedback:
    def test_records_and_retrieves(self):
        with tempfile.TemporaryDirectory() as tmp:
            rf = RetrievalFeedback(f"{tmp}/usage.json")
            rf.record_query(3, ["Fact A", "Fact B", "Fact A"])
            rf.record_query(1, ["Fact A"])

            stats = rf.get_stats(10)
            assert len(stats) >= 1
            titles = {s["title"]: s["count"] for s in stats}
            assert titles.get("Fact A", 0) >= 2
            assert titles.get("Fact B", 0) == 1

    def test_get_unused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/usage.json"
            rf = RetrievalFeedback(path)
            rf.record_query(1, ["Recent Fact"])
            # Устаревший факт пишем в файл напрямую — get_unused читает с диска
            data = json.loads(Path(path).read_text())
            data["Old Fact"] = {"count": 1, "last_access": time.time() - (91 * 86400)}
            Path(path).write_text(json.dumps(data))

            unused = rf.get_unused(90)
            assert "Old Fact" in unused
            assert "Recent Fact" not in unused

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/usage.json"
            rf1 = RetrievalFeedback(path)
            rf1.record_query(1, ["Test"])

            rf2 = RetrievalFeedback(path)
            stats = rf2.get_stats(10)
            assert len(stats) == 1
            assert stats[0]["title"] == "Test"

    def test_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            rf = RetrievalFeedback(f"{tmp}/usage.json")
            assert rf.get_stats(10) == []
            assert rf.get_unused(90) == []

    def test_parallel_instances_no_lost_update(self):
        """Регрессия ревью: два процесса (MCP-сервер и CLI) писали usage.json —
        запись второго затирала счётчики первого."""
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/usage.json"
            rf1 = RetrievalFeedback(path)
            rf2 = RetrievalFeedback(path)
            rf1.record_query(1, ["Fact A"])
            rf2.record_query(1, ["Fact B"])

            data = json.loads(Path(path).read_text())
            assert data["Fact A"]["count"] == 1
            assert data["Fact B"]["count"] == 1, "запись второго процесса не должна затирать первую"

    def test_write_is_atomic(self):
        """Регрессия ревью: write_text без tmp+rename оставлял читателю полуфайл."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(f"{tmp}/usage.json")
            rf = RetrievalFeedback(str(path))
            rf.record_query(1, ["Fact A"])

            assert not list(path.parent.glob("*.tmp")), "tmp-файл обязан быть переименован, не оставлен"