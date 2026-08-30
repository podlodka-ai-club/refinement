"""Интеграционные тесты LocalBackend: SQLite, persistence, краевые случаи."""

import pytest
from curator.backend.local import LocalBackend
from curator.models import StructuredFact, FactQuery, FactRef


class TestLocalBackendCRUD:
    def test_store_and_retrieve(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        f = StructuredFact(type="Reference", title="Test", tags=["t"], status="verified", content_summary="x" * 20)
        ref = be.store_fact(f)
        assert isinstance(ref, FactRef)
        assert ref.id

        results = be.query_facts(FactQuery())
        assert len(results) == 1
        assert results[0].title == f.title

    def test_query_by_type(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="R1", tags=["t"], status="verified", content_summary="x" * 20))
        be.store_fact(StructuredFact(type="Style", title="S1", tags=["t"], status="verified", content_summary="x" * 20))
        assert len(be.query_facts(FactQuery(type="Reference"))) == 1
        assert len(be.query_facts(FactQuery(type="Style"))) == 1

    def test_query_by_tags(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="A", tags=["jvm"], status="verified", content_summary="x" * 20))
        be.store_fact(StructuredFact(type="Reference", title="B", tags=["compose"], status="verified", content_summary="x" * 20))
        assert len(be.query_facts(FactQuery(tags=["jvm"]))) == 1
        assert len(be.query_facts(FactQuery(tags=["jvm", "compose"]))) == 2

    def test_query_by_status(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="V", tags=["t"], status="verified", content_summary="x" * 20))
        be.store_fact(StructuredFact(type="Reference", title="H", tags=["t"], status="hypothesis", content_summary="x" * 20))
        assert len(be.query_facts(FactQuery(status="verified"))) == 1

    def test_query_by_search(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="Unique XYZ", tags=["t"], status="verified", content_summary="x" * 20))
        be.store_fact(StructuredFact(type="Reference", title="Other", tags=["t"], status="verified", content_summary="has XYZ"))
        assert len(be.query_facts(FactQuery(search="XYZ"))) == 2

    def test_empty_db(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        assert be.query_facts(FactQuery()) == []

    def test_query_nonexistent_tag(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="T", tags=["a"], status="verified", content_summary="x" * 20))
        assert be.query_facts(FactQuery(tags=["nonexistent"])) == []


class TestPersistence:
    def test_survives_reconnect(self, tmpdir):
        db_path = str(tmpdir / "persist.db")
        be1 = LocalBackend(db_path)
        be1.store_fact(StructuredFact(type="Reference", title="Persistent", tags=["t"], status="verified", content_summary="x" * 20))

        be2 = LocalBackend(db_path)
        results = be2.query_facts(FactQuery())
        assert len(results) == 1
        assert results[0].title == "Persistent"

    def test_multiple_writes(self, tmpdir):
        db_path = str(tmpdir / "multi.db")
        be = LocalBackend(db_path)
        for i in range(10):
            be.store_fact(StructuredFact(type="Reference", title=f"Fact {i}", tags=["t"], status="verified", content_summary="x" * 20))
        assert len(be.query_facts(FactQuery())) == 10


class TestRelations:
    def test_add_and_get(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.add_relation("1", "2", "related_to")
        be.add_relation("1", "3", "contradicts")
        assert len(be.get_relations("1")) == 2

    def test_no_duplicates(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.add_relation("1", "2", "related_to")
        be.add_relation("1", "2", "related_to")
        assert len(be.get_relations("1")) == 1

    def test_empty_relations(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        assert be.get_relations("nonexistent") == []


class TestHealthCheck:
    def test_new_db_healthy(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        assert be.health_check()

    def test_broken_db_path_fails(self):
        with pytest.raises((FileNotFoundError, OSError)):
            LocalBackend("/dev/null/test.db")


class TestFindSimilar:
    def test_finds_by_tags(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(type="Reference", title="Правило JVM inline классы", tags=["jvm"], status="verified", content_summary="x" * 20))
        be.store_fact(StructuredFact(type="Reference", title="Compose text style", tags=["compose"], status="verified", content_summary="x" * 20))
        similar = be.find_similar(StructuredFact(type="Reference", title="Правило JVM", tags=["jvm"], status="verified", content_summary="x" * 20), threshold=0.2)
        assert len(similar) >= 1
        assert "Compose" not in [s.title for s in similar]

    def test_no_self_match(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        f = StructuredFact(type="Reference", title="Unique", tags=["u"], status="verified", content_summary="x" * 20)
        be.store_fact(f)
        similar = be.find_similar(f, threshold=0.5)
        assert "Unique" not in [s.title for s in similar]