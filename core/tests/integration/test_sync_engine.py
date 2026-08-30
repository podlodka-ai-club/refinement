"""Интеграционные тесты Sync Engine: .md ↔ backend."""

import pytest
from curator.sync_engine import SyncEngine
from curator.backend.local import LocalBackend
from curator.models import StructuredFact


class TestWrite:
    def test_new_fact_creates_md(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        engine = SyncEngine(be, tmpdir)
        fact = StructuredFact(type="Reference", title="Test Rule", tags=["test"], status="verified", content_summary="Test content.", source_file="reference/test.md")
        path = engine.write_fact_to_md(fact)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Test Rule" in content
        assert "Test content" in content

    def test_upsert_updates_existing(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        engine = SyncEngine(be, tmpdir)
        md_path = tmpdir / "reference/test.md"
        md_path.parent.mkdir(parents=True)
        md_path.write_text("### Old Rule\n\nOld text.\n\n*Тип:* Reference | *Статус:* Подтверждено | *Теги:* old\n*Файл:* reference/test.md\n", encoding="utf-8")

        fact = StructuredFact(type="Reference", title="Old Rule", tags=["updated"], status="verified", content_summary="Updated text.", source_file="reference/test.md")
        engine.write_fact_to_md(fact)
        content = md_path.read_text(encoding="utf-8")
        assert "Updated text" in content
        assert "Old text" not in content

    def test_append_to_existing_file(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        engine = SyncEngine(be, tmpdir)
        md_path = tmpdir / "reference/test.md"
        md_path.parent.mkdir(parents=True)
        md_path.write_text("### Existing Rule\n\nContent.\n\n", encoding="utf-8")

        fact = StructuredFact(type="Reference", title="New Rule", tags=["new"], status="verified", content_summary="New content.", source_file="reference/test.md")
        engine.write_fact_to_md(fact)
        content = md_path.read_text(encoding="utf-8")
        assert "Existing Rule" in content
        assert "New Rule" in content


class TestRemove:
    def test_marks_deprecated(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        engine = SyncEngine(be, tmpdir)
        md_path = tmpdir / "reference/test.md"
        md_path.parent.mkdir(parents=True)
        md_path.write_text("### Old Rule\n\nText.\n\n*Тип:* Reference\n", encoding="utf-8")

        fact = StructuredFact(type="Reference", title="Old Rule", tags=["t"], status="deprecated", content_summary="Text.", source_file="reference/test.md")
        path = engine.remove_fact_from_md(fact)
        assert path is not None
        content = path.read_text(encoding="utf-8")
        assert "[УСТАРЕЛО]" in content

    def test_nonexistent_fact_no_error(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        engine = SyncEngine(be, tmpdir)
        md_path = tmpdir / "reference/test.md"
        md_path.parent.mkdir(parents=True)
        md_path.write_text("### Existing\n\nText.\n", encoding="utf-8")

        fact = StructuredFact(type="Reference", title="Missing Rule", tags=["t"], status="deprecated", content_summary=".", source_file="reference/test.md")
        assert engine.remove_fact_from_md(fact) is None

    def test_nonexistent_file_no_error(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        engine = SyncEngine(be, tmpdir)
        fact = StructuredFact(type="Reference", title="Test", tags=["t"], status="deprecated", content_summary=".", source_file="reference/missing.md")
        assert engine.remove_fact_from_md(fact) is None


class TestErrors:
    def test_no_source_file_raises(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        engine = SyncEngine(be, tmpdir)
        fact = StructuredFact(type="Reference", title="Test", tags=["t"], status="verified", content_summary="x" * 20)
        with pytest.raises(ValueError):
            engine.write_fact_to_md(fact)

    def test_update_no_source_file_raises(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        engine = SyncEngine(be, tmpdir)
        fact = StructuredFact(type="Reference", title="Test", tags=["t"], status="verified", content_summary="x" * 20)
        with pytest.raises(ValueError):
            engine.update_fact_in_md(fact)


class TestMultipleFacts:
    def test_multiple_facts_one_file(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        engine = SyncEngine(be, tmpdir)
        f1 = StructuredFact(type="Reference", title="Rule 1", tags=["a"], status="verified", content_summary="Content 1.", source_file="ref/all.md")
        f2 = StructuredFact(type="Reference", title="Rule 2", tags=["b"], status="verified", content_summary="Content 2.", source_file="ref/all.md")

        engine.write_fact_to_md(f1)
        engine.write_fact_to_md(f2)

        content = (tmpdir / "ref/all.md").read_text(encoding="utf-8")
        assert "Rule 1" in content
        assert "Rule 2" in content