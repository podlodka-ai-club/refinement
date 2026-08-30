"""E2E: полный ingest пайплайн .md → backend → query."""

from pathlib import Path
from curator.analyzers.ingest import ingest_directory
from curator.backend.local import LocalBackend
from curator.gatekeeper import Gatekeeper
from curator.models import FactQuery


class TestFullIngestPipeline:
    def test_md_to_backend_roundtrip(self, tmpdir):
        md_dir = tmpdir / "learnings/reference"
        md_dir.mkdir(parents=True)
        content = (
            "---\n"
            "type: Reference\n"
            "tags: [test]\n"
            "description: Test\n"
            "---\n\n"
            "### Important Rule About Testing\n"
            "This is a very important rule about testing pipelines.\n\n"
            "### Another Important Rule\n"
            "This is another rule that should be ingested.\n"
        )
        (md_dir / "test.md").write_text(content, encoding="utf-8")

        be = LocalBackend(str(tmpdir / "test.db"))
        gk = Gatekeeper(be, check_duplicates=False)
        saved = ingest_directory(Path(md_dir), be, gk)

        assert saved >= 1
        all_facts = be.query_facts(FactQuery())
        titles = {f.title for f in all_facts}
        assert "Important Rule About Testing" in titles

    def test_ingest_is_idempotent(self, tmpdir):
        md_dir = tmpdir / "learnings"
        md_dir.mkdir()
        content = (
            "---\n"
            "type: Reference\n"
            "tags: [x]\n"
            "description: X\n"
            "---\n\n"
            "### Rule Number One Long\n"
            "Long enough content here for the summary check.\n"
        )
        (md_dir / "test.md").write_text(content, encoding="utf-8")

        be = LocalBackend(str(tmpdir / "test.db"))
        gk = Gatekeeper(be, check_duplicates=False)
        first = ingest_directory(Path(md_dir), be, gk)
        second = ingest_directory(Path(md_dir), be, gk)

        assert first >= 1
        assert second == 0

    def test_multiple_files_ingest(self, tmpdir):
        md_dir = tmpdir / "learnings"
        md_dir.mkdir()
        (md_dir / "a.md").write_text(
            "---\ntype: Reference\ntags: [a]\ndescription: A\n---\n\n"
            "### Rule About Reference\n"
            "Long enough content here.\n",
            encoding="utf-8",
        )
        (md_dir / "b.md").write_text(
            "---\ntype: Style\ntags: [b]\ndescription: B\n---\n\n"
            "### Rule About Styling\n"
            "Long enough content here.\n",
            encoding="utf-8",
        )

        be = LocalBackend(str(tmpdir / "test.db"))
        gk = Gatekeeper(be, check_duplicates=False)
        saved = ingest_directory(Path(md_dir), be, gk)

        assert saved == 2
        refs = be.query_facts(FactQuery(type="Reference"))
        styles = be.query_facts(FactQuery(type="Style"))
        assert len(refs) == 1
        assert len(styles) == 1