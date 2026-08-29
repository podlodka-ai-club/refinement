"""Тесты ImproveLoop: similarity, contradictions, краевые случаи."""

from curator.improve_loop import ImproveLoop, ImproveReport
from curator.models import StructuredFact


def _ref(title, tags=None, status="verified"):
    return StructuredFact(
        type="Reference", title=title,
        tags=tags or ["test"], status=status,
        content_summary=f"Summary for {title}" * 2,
    )


class TestTitleSimilarity:
    def setup_method(self):
        self.loop = ImproveLoop.__new__(ImproveLoop)

    def test_identical(self):
        assert self.loop._title_similarity("Правило про JVM", "Правило про JVM") == 1.0

    def test_completely_different(self):
        sim = self.loop._title_similarity("Правило про JVM", "Стиль коммитов")
        assert sim < 0.3

    def test_partial_overlap(self):
        sim = self.loop._title_similarity("Правило про JVM inline классы", "Правило про JVM бокс")
        assert sim > 0.3

    def test_different_case(self):
        sim = self.loop._title_similarity("ПРАВИЛО ПРО JVM", "правило про jvm")
        assert sim == 1.0

    def test_empty_strings(self):
        assert self.loop._title_similarity("", "") == 0.0


class TestFindDuplicates:
    def test_no_duplicates_unique(self):
        loop = ImproveLoop.__new__(ImproveLoop)
        facts = [_ref("Kotlin rules"), _ref("Python rules")]
        assert loop._find_duplicates(facts) == []

    def test_duplicates_same_type_similar_title(self):
        loop = ImproveLoop.__new__(ImproveLoop)
        f1 = _ref("Правило про JVM inline классы sealed interface бокс")
        f2 = _ref("Правило про JVM inline классы sealed interface")
        dups = loop._find_duplicates([f1, f2])
        assert len(dups) == 1

    def test_different_types_not_duplicates(self):
        loop = ImproveLoop.__new__(ImproveLoop)
        f1 = StructuredFact(type="Reference", title="Same title", tags=["test"], status="verified", content_summary="x" * 20)
        f2 = StructuredFact(type="Style", title="Same title", tags=["test"], status="verified", content_summary="x" * 20)
        assert loop._find_duplicates([f1, f2]) == []


class TestFindStale:
    def test_finds_hypothesis(self):
        loop = ImproveLoop.__new__(ImproveLoop)
        facts = [_ref("A", status="hypothesis"), _ref("B")]
        assert len(loop._find_stale(facts)) == 1

    def test_finds_deprecated(self):
        loop = ImproveLoop.__new__(ImproveLoop)
        facts = [_ref("A", status="deprecated"), _ref("B")]
        assert len(loop._find_stale(facts)) == 1

    def test_no_stale(self):
        loop = ImproveLoop.__new__(ImproveLoop)
        facts = [_ref("A"), _ref("B")]
        assert loop._find_stale(facts) == []


class TestContradictions:
    def setup_method(self):
        self.loop = ImproveLoop.__new__(ImproveLoop)

    def test_no_contradictions_same_sentiment(self):
        f1 = _ref("Использовать ImmutableList для больших списков", ["compose", "performance"])
        f2 = _ref("ImmutableList рекомендуется для MVI", ["compose", "architecture"])
        assert self.loop._find_contradictions([f1, f2]) == []

    def test_detects_opposing_views(self):
        f1 = _ref("Использовать ImmutableList для списков в Compose", ["compose"])
        f2 = _ref("Не использовать ImmutableList в Compose", ["compose"])
        result = self.loop._find_contradictions([f1, f2])
        assert len(result) == 1

    def test_oppose_only_same_domain(self):
        f1 = _ref("Использовать data class в sealed interface", ["kotlin", "jvm"])
        f2 = _ref("Не использовать data class для Compose State", ["compose"])
        assert self.loop._find_contradictions([f1, f2]) == []

    def test_contradictions_require_reference_type(self):
        f1 = StructuredFact(type="Style", title="Использовать X", tags=["test"], status="verified", content_summary="x" * 20)
        f2 = StructuredFact(type="Style", title="Не использовать X", tags=["test"], status="verified", content_summary="x" * 20)
        assert self.loop._find_contradictions([f1, f2]) == []

    def test_share_tags_detection(self):
        f1 = _ref("A", ["kotlin", "jvm"])
        f2 = _ref("B", ["kotlin", "jvm"])
        assert self.loop._share_tags(f1, f2)

        f3 = _ref("A", ["kotlin"])
        f4 = _ref("B", ["python"])
        assert not self.loop._share_tags(f3, f4)


class TestImproveReport:
    def test_empty_report(self):
        r = ImproveReport()
        assert r.stats == {}
        assert r.duplicates == []
        assert r.stale == []
        assert r.contradictions == []

    def test_with_stats(self):
        r = ImproveReport(stats={"total": 10})
        assert r.stats["total"] == 10

    def test_with_contradictions(self):
        r = ImproveReport(contradictions=[(None, None)])
        assert len(r.contradictions) == 1


class TestResolution:
    def setup_method(self):
        self.loop = ImproveLoop.__new__(ImproveLoop)

    def test_verified_beats_hypothesis(self):
        f1 = _ref("Использовать X", status="verified")
        f2 = _ref("Не использовать X", status="hypothesis")
        winner, loser, reason = self.loop._pick_winner(f1, f2)
        assert winner.status == "verified"
        assert "verified" in reason

    def test_more_tags_beats_fewer(self):
        f1 = _ref("Использовать X", tags=["compose", "android"], status="verified")
        f2 = _ref("Не использовать X", tags=["compose"], status="verified")
        winner, loser, reason = self.loop._pick_winner(f1, f2)
        assert len(winner.tags) > len(loser.tags)

    def test_more_summary_beats_shorter(self):
        f1 = _ref("Использовать X", status="verified")
        f2 = _ref("Не использовать X", status="verified")
        f1.content_summary = "x" * 100
        f2.content_summary = "x" * 20
        winner, loser, reason = self.loop._pick_winner(f1, f2)
        assert winner == f1

    def test_resolve_multiple_pairs(self):
        f1 = _ref("Использовать Y", status="verified")
        f2 = _ref("Не использовать Y", status="hypothesis")
        f3 = _ref("Делать Z", status="verified")
        f4 = _ref("Не делать Z", status="deprecated")
        resolutions = self.loop._resolve_contradictions([(f1, f2), (f3, f4)])
        assert len(resolutions) == 2
        assert all(r.winner.status == "verified" for r in resolutions)