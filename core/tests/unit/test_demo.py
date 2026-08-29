"""Тесты demo.py: детерминированное keyword-извлечение и дельта «до/после».

Оставлены только тесты поведения; форматирование вывода и структура
dataclass-ов не тестируются (см. tests/requirements/ для требований).
"""

from curator.demo import (
    run_demo,
    run_time_lapse,
    _make_facts_from_session,
    TEST_SESSIONS,
)


class TestExtraction:
    def test_kotlin_session_yields_jvm_facts(self):
        facts = _make_facts_from_session(TEST_SESSIONS[0].text)
        assert len(facts) >= 2
        assert any("value class" in f.title.lower() for f in facts)

    def test_compose_session_yields_immutablelist_fact(self):
        facts = _make_facts_from_session(TEST_SESSIONS[1].text)
        assert any("immutablelist" in f.title.lower() for f in facts)

    def test_new_domain_creates_fact(self):
        facts = _make_facts_from_session(TEST_SESSIONS[3].text)
        assert any("mcp" in f.title.lower() for f in facts)

    def test_empty_session_yields_no_facts(self):
        assert _make_facts_from_session("hello world") == []

    def test_facts_have_required_fields(self):
        for session in TEST_SESSIONS:
            for fact in _make_facts_from_session(session.text):
                assert fact.type in ("Reference", "Style", "Tool", "Spec")
                assert fact.title
                assert fact.content_summary
                assert fact.tags


class TestDemoFlows:
    def test_clean_only_mode_processes_all_sessions(self):
        result = run_demo(backend_trained=None, verbose=False)
        assert len(result.comparisons) == len(TEST_SESSIONS)
        assert result.trained_facts_total == 0

    def test_time_lapse_shows_growth(self):
        result = run_time_lapse(verbose=False)
        totals = [s["total_after"] for s in result["snapshots"]]
        assert len(set(totals)) >= 2, f"дельта обязательна: {totals}"

    def test_verbose_does_not_crash(self):
        result = run_demo(backend_trained=None, verbose=True)
        assert len(result.comparisons) == len(TEST_SESSIONS)
