"""Тесты Gatekeeper с реальным backend (dedup check)."""

from curator.gatekeeper import Gatekeeper
from curator.models import ProposedFact, StructuredFact
from curator.backend.local import LocalBackend


class TestDedupCheck:
    def test_detects_duplicate(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="Правило про JVM inline классы", tags=["jvm"], status="verified", content_summary="x" * 20))
        gk = Gatekeeper(be, check_duplicates=True)

        fact = ProposedFact(type="Reference", title="Правило про JVM inline классы sealed", content_summary="Очень похожее описание но чуть длиннее для проверки", tags=["jvm"])
        result = gk.filter([fact])
        assert len(result.rejected) == 1
        assert "дубликат" in result.rejected[0][1].lower()

    def test_no_duplicate_when_chec_off(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="Правило про JVM inline классы", tags=["jvm"], status="verified", content_summary="x" * 20))
        gk = Gatekeeper(be, check_duplicates=False)

        fact = ProposedFact(type="Reference", title="Правило про JVM inline классы и sealed", content_summary="Очень похожее описание но чуть длиннее для проверки", tags=["jvm"])
        result = gk.filter([fact])
        assert len(result.approved) == 1

    def test_different_topic_passes(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="Правило про JVM классы", tags=["jvm"], status="verified", content_summary="x" * 20))
        gk = Gatekeeper(be, check_duplicates=True)

        fact = ProposedFact(type="Reference", title="Совсем другой топик про Compose", content_summary="Абсолютно разные вещи обсуждаются здесь длинно", tags=["compose"])
        result = gk.filter([fact])
        assert len(result.approved) == 1