"""Тесты eval_runner.py."""

import pytest
from curator.eval_runner import (
    EvalRunner, EvalMetrics, EvalAction, TEST_QUERIES,
)
from curator.models import StructuredFact


def _fact(title, status="verified", type="Reference"):
    return StructuredFact(
        type=type, title=title, tags=["test"],
        status=status, content_summary=f"Summary for {title}" * 2,
    )


class TestEvalAction:
    def test_improved_when_coverage_up(self):
        before = EvalMetrics(query_coverage=0.5, total_facts=10, verified_percent=0.9, stale_percent=0.1, duplicate_count=2)
        after = EvalMetrics(query_coverage=0.8, total_facts=10, verified_percent=0.9, stale_percent=0.1, duplicate_count=0)
        action = EvalAction(description="test", before_metrics=before, after_metrics=after)
        assert action.improved
        assert action.delta["query_coverage"] == pytest.approx(0.3)

    def test_not_improved_when_coverage_down(self):
        before = EvalMetrics(query_coverage=0.8, total_facts=10, verified_percent=0.9, stale_percent=0.1, duplicate_count=0)
        after = EvalMetrics(query_coverage=0.5, total_facts=10, verified_percent=0.9, stale_percent=0.1, duplicate_count=2)
        action = EvalAction(description="test", before_metrics=before, after_metrics=after)
        assert not action.improved

    def test_not_improved_when_facts_halved(self):
        before = EvalMetrics(query_coverage=0.9, total_facts=10, verified_percent=0.9, stale_percent=0.1, duplicate_count=0)
        after = EvalMetrics(query_coverage=0.9, total_facts=4, verified_percent=0.9, stale_percent=0.0, duplicate_count=0)
        action = EvalAction(description="test", before_metrics=before, after_metrics=after)
        assert not action.improved


class TestEvalRunner:
    def test_measure_empty(self):
        runner = EvalRunner()
        m = runner.measure([])
        assert m.total_facts == 0
        assert m.query_coverage == 0.0

    def test_measure_with_facts(self):
        runner = EvalRunner()
        facts = [_fact("Kotlin JVM boxing rules"), _fact("Compose stability tips"), _fact("Python MCP setup")]
        m = runner.measure(facts)
        assert m.total_facts == 3
        assert m.verified_percent == 1.0
        assert m.stale_percent == 0.0
        assert m.query_coverage > 0.0

    def test_measure_with_stale(self):
        runner = EvalRunner()
        facts = [
            _fact("A", "verified"),
            _fact("B", "deprecated"),
            _fact("C", "hypothesis"),
        ]
        m = runner.measure(facts)
        assert m.verified_percent == 1 / 3
        assert m.stale_percent == 2 / 3

    def test_consolidation_improves_coverage(self):
        runner = EvalRunner()
        dup1 = _fact("Kotlin JVM boxing rule version A")
        dup2 = _fact("Kotlin JVM boxing rule version B")
        facts = [dup1, dup2, _fact("Compose stability")]
        action = runner.evaluate_consolidation(facts, [(dup1, dup2)])
        assert action.improved
        assert action.after_metrics.total_facts < action.before_metrics.total_facts

    def test_deprecation_improves_stale(self):
        runner = EvalRunner()
        deprecated_fact = _fact("Old deprecated", "deprecated")
        facts = [deprecated_fact, _fact("Verified fact")]
        action = runner.evaluate_deprecation(facts, [deprecated_fact])
        assert action.after_metrics.stale_percent <= action.before_metrics.stale_percent

    def test_deprecation_empty_facts(self):
        runner = EvalRunner()
        action = runner.evaluate_deprecation([], [])
        assert not action.improved

    def test_test_queries_defined(self):
        assert len(TEST_QUERIES) >= 3
        assert all(q.search or q.type for q in TEST_QUERIES)