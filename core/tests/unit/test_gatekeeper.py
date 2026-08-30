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


class TestMarkdownInjection:
    """Регрессии код-ревью: вход приходит от LLM — title/summary без проверки
    ломали marker-логику .md и создавали фейковые секции при реингесте."""

    def test_rejects_multiline_title(self):
        result = Gatekeeper().filter([_fact(title="Правило про JVM\n### подделка секции")])
        assert len(result.rejected) == 1
        assert "одной строкой" in result.rejected[0][1]

    def test_rejects_carriage_return_title(self):
        result = Gatekeeper().filter([_fact(title="Правило про JVM\r\nс переносом")])
        assert len(result.rejected) == 1

    def test_rejects_hash_leading_title(self):
        result = Gatekeeper().filter([_fact(title="### Заголовок маскирующийся под секцию")])
        assert len(result.rejected) == 1
        assert "#" in result.rejected[0][1]

    def test_rejects_stale_marker_trailing_title(self):
        """Раунд-6: title с хвостовым [УСТАРЕЛО] неотличим от маркера
        деприкации при rebuild из .md — молчаливая потеря."""
        result = Gatekeeper().filter([_fact(title="Знание про пометки устаревших API [УСТАРЕЛО]")])
        assert len(result.rejected) == 1
        assert "УСТАРЕЛО" in result.rejected[0][1]

    def test_rejects_short_after_flattening(self):
        """Раунд-7: raw-длинный, но сплющенно-короткий summary (парсер .md
        склеивает строки) терялся при rebuild — валидируем сплющенную форму."""
        result = Gatekeeper().filter([_fact(summary="a\nb\nc\nd\ne\nf\ng\nh\ni\nj")])
        assert len(result.rejected) == 1
        assert "короткое" in result.rejected[0][1]

    def test_rejects_heading_inside_summary(self):
        result = Gatekeeper().filter([_fact(summary="Нормальное начало описания\n### Фейковая секция")])
        assert len(result.rejected) == 1
        assert "начинающиеся с #" in result.rejected[0][1]

    def test_rejects_overlong_summary(self):
        result = Gatekeeper().filter([_fact(summary="A" * 2001)])
        assert len(result.rejected) == 1
        assert "длинное" in result.rejected[0][1]

    def test_multiline_summary_without_headings_passes(self):
        result = Gatekeeper().filter([_fact(summary="Первая строка описания.\nВторая строка без заголовков.")])
        assert len(result.approved) == 1