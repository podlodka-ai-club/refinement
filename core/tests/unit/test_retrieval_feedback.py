"""Тесты RetrievalFeedback."""

import time
import tempfile
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
            rf = RetrievalFeedback(f"{tmp}/usage.json")
            rf.record_query(1, ["Recent Fact"])
            # Искусственно устариваем
            rf._counts["Old Fact"] = {"count": 1, "last_access": time.time() - (91 * 86400)}

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