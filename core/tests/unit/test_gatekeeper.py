"""Тесты Gatekeeper: фильтры, краевые случаи, dedup."""

from curator.gatekeeper import Gatekeeper, GatekeeperResult
from curator.models import ProposedFact


def _fact(type="Reference", title="Long enough valid title", summary="Very long summary that is more than twenty characters", tags=None):
    _tags = ["test"] if tags is None else tags
    return ProposedFact(type=type, title=title, content_summary=summary, tags=_tags)


class TestBasicFiltering:
    def test_approves_valid(self):
        result = Gatekeeper().filter([_fact()])
        assert len(result.approved) == 1

    def test_rejects_short_title(self):
        result = Gatekeeper().filter([_fact(title="Kotlin")])
        assert len(result.rejected) == 1
        assert "короткий" in result.rejected[0][1]

    def test_rejects_long_title(self):
        title = "A" * 201
        result = Gatekeeper().filter([_fact(title=title)])
        assert len(result.rejected) == 1

    def test_rejects_no_tags(self):
        result = Gatekeeper().filter([_fact(tags=[])])
        assert len(result.rejected) == 1

    def test_rejects_short_summary(self):
        result = Gatekeeper().filter([_fact(summary="Short")])
        assert len(result.rejected) == 1

    def test_rejects_noise_pattern(self):
        title = "Поменять цвет кнопки на синий"
        result = Gatekeeper().filter([_fact(title=title, tags=["ui"])])
        assert len(result.rejected) == 1
        assert "фичевую" in result.rejected[0][1]


class TestBoundaryValues:
    def test_title_at_min(self):
        result = Gatekeeper().filter([_fact(title="Long enough")])
        assert len(result.approved) == 1

    def test_title_at_max(self):
        result = Gatekeeper().filter([_fact(title="A" * 200)])
        assert len(result.approved) == 1

    def test_summary_at_min(self):
        result = Gatekeeper().filter([_fact(summary="A" * 20)])
        assert len(result.approved) == 1

    def test_tags_with_spaces(self):
        result = Gatekeeper().filter([_fact(tags=["  kotlin  ", " jvm "])])
        assert len(result.approved) == 1


class TestMultipleFacts:
    def test_mixed_approvals(self):
        facts = [
            _fact(),
            _fact(title="Bad"),
        ]
        result = Gatekeeper().filter(facts)
        assert len(result.approved) == 1
        assert len(result.rejected) == 1

    def test_all_rejected(self):
        result = Gatekeeper().filter([_fact(title="A"), _fact(title="B")])
        assert len(result.rejected) == 2

    def test_empty_input(self):
        result = Gatekeeper().filter([])
        assert result.approved == []
        assert result.rejected == []


class TestGatekeeperResult:
    def test_defaults(self):
        r = GatekeeperResult()
        assert r.approved == []
        assert r.rejected == []

    def test_rejected_tuple_structure(self):
        gk = Gatekeeper()
        result = gk.filter([_fact(title="Bad")])
        fact, reason = result.rejected[0]
        assert isinstance(fact, ProposedFact)
        assert isinstance(reason, str)