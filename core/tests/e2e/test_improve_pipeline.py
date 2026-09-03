"""E2E: improve на граничащих случаях."""

from curator.backend.local import LocalBackend
from curator.improve_loop import ImproveLoop


class TestImprovePipeline:
    def test_empty_store(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        improve = ImproveLoop(be)
        report = improve.run()

        assert report.stats["total_facts"] == 0
        assert report.stats["duplicates_found"] == 0
