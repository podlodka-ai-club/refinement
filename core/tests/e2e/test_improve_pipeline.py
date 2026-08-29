"""E2E: store дубликатов → improve → consolidate."""

from curator.backend.local import LocalBackend
from curator.models import StructuredFact
from curator.improve_loop import ImproveLoop


class TestImprovePipeline:
    def test_find_duplicates(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="Правило про JVM inline классы и sealed interface", tags=["jvm"], status="verified", content_summary="JvmInline value class внутри sealed interface бесполезен."))
        be.store_fact(StructuredFact(type="Reference", title="Правило про JVM inline классы и sealed interface бокс", tags=["jvm"], status="verified", content_summary="Бокс неизбежен при использовании внутри sealed interface."))
        be.store_fact(StructuredFact(type="Reference", title="Совсем другая тема про Compose", tags=["compose"], status="verified", content_summary="Совсем не про JVM и не про бокс."))

        improve = ImproveLoop(be)
        report = improve.run()

        assert report.stats["total_facts"] == 3
        assert report.stats["duplicates_found"] == 1
        assert report.stats["stale_found"] == 0

    def test_empty_store(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        improve = ImproveLoop(be)
        report = improve.run()

        assert report.stats["total_facts"] == 0
        assert report.stats["duplicates_found"] == 0

    def test_find_stale(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="Verified fact", tags=["t"], status="verified", content_summary="x" * 20))
        be.store_fact(StructuredFact(type="Reference", title="Stale hypothesis", tags=["t"], status="hypothesis", content_summary="x" * 20))
        be.store_fact(StructuredFact(type="Reference", title="Deprecated", tags=["t"], status="deprecated", content_summary="x" * 20))

        improve = ImproveLoop(be)
        report = improve.run()

        assert report.stats["stale_found"] == 2

    def test_all_duplicates(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="Одно и то же правило про JVM классы", tags=["jvm"], status="verified", content_summary="x" * 20))
        be.store_fact(StructuredFact(type="Reference", title="Одно и то же правило про JVM классы копия", tags=["jvm"], status="verified", content_summary="x" * 20))

        improve = ImproveLoop(be)
        report = improve.run()
        assert report.stats["duplicates_found"] == 1

    def test_all_unique(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        for i, topic in enumerate(["JVM", "Compose", "Git", "API", "Security"]):
            be.store_fact(StructuredFact(type="Reference", title=f"Уникальное правило про {topic}", tags=[topic.lower()], status="verified", content_summary=f"Content about {topic}"))
        improve = ImproveLoop(be)
        report = improve.run()
        assert report.stats["duplicates_found"] == 0