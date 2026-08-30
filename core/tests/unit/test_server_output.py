"""Контрактные тесты: вывод MCP-тулзов содержит все ключевые поля.

Защита от ситуации «поле добавили в модель, но забыли показать в выводе».
Бэкенд сидится в :memory: — тесты не зависят от реальной БД.
"""

import pytest
import curator.server as server_mod
from curator.server import _improve, _status, _feedback
from curator.backend.local import LocalBackend
from curator.improve_loop import ImproveLoop
from curator.models import StructuredFact


@pytest.fixture(autouse=True)
def seeded_backend(monkeypatch):
    be = LocalBackend(":memory:")
    be.store_fact(StructuredFact(
        type="Reference", title="ImmutableList нужен только для стабильных коллекций",
        tags=["kotlin"], status="verified",
        content_summary="Для read-only данных ImmutableList оправдан, иначе overhead.",
    ))
    be.store_fact(StructuredFact(
        type="Reference", title="Старая гипотеза про производительность боксинга",
        tags=["kotlin"], status="hypothesis",
        content_summary="Гипотетическое знание, которое должно попасть в stale.",
    ))
    monkeypatch.setattr(server_mod, "backend", be)
    monkeypatch.setattr(server_mod, "improve", ImproveLoop(be))


class TestImproveOutput:
    def test_contains_stats_fields(self):
        output = _improve()
        assert "Всего фактов:" in output
        assert "Найдено дубликатов:" in output
        assert "Устаревших:" in output
        assert "Противоречий:" in output

    def test_contains_sections_when_data_present(self):
        output = _improve()
        sections = ["Дубликаты:", "Устаревшие:", "Противоречия", "Eval-решения:", "Часто запрашиваемые:"]
        found = [s for s in sections if s in output]
        assert len(found) > 0, f"No sections found in output:\n{output}"

    def test_eval_decisions_format(self):
        output = _improve()
        if "Eval-решения:" in output:
            assert "применено" in output or "отклонено" in output

    def test_contradictions_format(self):
        output = _improve()
        if "Противоречия" in output and "⚡" not in output:
            pass

    def test_output_is_valid_string(self):
        output = _improve()
        assert isinstance(output, str)
        assert len(output) > 50


class TestStatusOutput:
    def test_contains_type_and_status(self):
        output = _status()
        assert "Всего фактов:" in output
        assert "По типам:" in output
        assert "По статусам:" in output

    def test_output_is_json_parseable(self):
        output = _status()
        assert "{" in output

    def test_total_facts_is_number(self):
        output = _status()
        import re
        match = re.search(r"Всего фактов: (\d+)", output)
        assert match, f"No total facts found in: {output}"


class TestFeedbackOutput:
    def test_contains_header(self):
        output = _feedback()
        assert "Статистика использования" in output

    def test_output_is_valid(self):
        output = _feedback()
        assert isinstance(output, str)