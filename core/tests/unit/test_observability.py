"""Тесты observability.py."""

import json
import tempfile
from pathlib import Path
from curator.observability import Observability, ObserveEvent


class TestObserveEvent:
    def test_creates_with_defaults(self):
        e = ObserveEvent(action="consolidate", applied=True)
        assert e.action == "consolidate"
        assert e.ts
        assert "T" in e.ts
        assert e.facts == []


class TestObservability:
    def test_log_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            o = Observability(f"{tmp}/events.jsonl")
            o.log(ObserveEvent(action="consolidate", applied=True, facts=["A ↔ B"]))
            o.log(ObserveEvent(action="deprecate", applied=False, facts=["C"]))

            recent = o.recent(10)
            assert len(recent) == 2
            assert recent[0]["action"] == "consolidate"
            assert recent[1]["action"] == "deprecate"

    def test_stats_computation(self):
        with tempfile.TemporaryDirectory() as tmp:
            o = Observability(f"{tmp}/events.jsonl")
            o.log(ObserveEvent(action="consolidate", applied=True, facts=["A"]))
            o.log(ObserveEvent(action="deprecate", applied=False, facts=["B"]))
            o.log(ObserveEvent(action="consolidate", applied=True, facts=["C"]))

            s = o.stats()
            assert s["total_events"] == 3
            assert s["applied"] == 2
            assert s["skipped"] == 1
            assert s["by_action"]["consolidate"] == 2
            assert s["by_action"]["deprecate"] == 1

    def test_empty_log_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            o = Observability(f"{tmp}/nonexistent.jsonl")
            s = o.stats()
            assert s["total_events"] == 0

    def test_empty_log_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            o = Observability(f"{tmp}/nonexistent.jsonl")
            assert o.recent(10) == []

    def test_persistence_between_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/events.jsonl"
            o1 = Observability(path)
            o1.log(ObserveEvent(action="consolidate", applied=True, facts=["A"]))

            o2 = Observability(path)
            assert len(o2.recent(5)) == 1

    def test_recent_tolerates_broken_line(self):
        """Регрессия ревью: битая строка JSONL валила improve.run() после
        применения действий — теперь пропускается."""
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/events.jsonl"
            with open(path, "w") as f:
                f.write(json.dumps({"action": "ok", "applied": True}) + "\n")
                f.write("{broken json\n")
                f.write(json.dumps({"action": "ok2", "applied": False}) + "\n")
            o = Observability(path)
            assert len(o.recent(10)) == 2

    def test_stats_tolerates_broken_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/events.jsonl"
            with open(path, "w") as f:
                f.write(json.dumps({"action": "ok", "applied": True}) + "\n")
                f.write("{broken json\n")
            o = Observability(path)
            s = o.stats()
            assert s["total_events"] == 1
            assert s["applied"] == 1

    def test_log_contains_json_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/events.jsonl"
            o = Observability(path)
            o.log(ObserveEvent(
                action="consolidate", applied=True,
                facts=["A ↔ B"], eval_before=0.8, eval_after=0.9,
            ))
            text = Path(path).read_text()
            d = json.loads(text)
            assert "ts" in d
            assert "action" in d
            assert "applied" in d
            assert "facts" in d