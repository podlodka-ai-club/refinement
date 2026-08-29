"""Тесты fallback: переключение XMEMORY ↔ LOCAL."""

from curator.backend.interface import MemoryBackend
from curator.backend.local import LocalBackend
from curator.backend.xmemory import XMemoryBackend
from curator.models import StructuredFact, FactQuery


class TestFallback:
    def test_local_backend_healthy(self):
        be = LocalBackend(":memory:")
        assert be.health_check()

    def test_xmemory_with_empty_key_falls_back(self):
        be = XMemoryBackend(api_key="", instance_id=None)
        assert isinstance(be, MemoryBackend)
        ref = be.store_fact(StructuredFact(type="Reference", title="Fallback test", tags=["t"], status="verified", content_summary="x" * 20))
        assert ref.title == "Fallback test"
        assert len(be.query_facts(FactQuery())) == 1

    def test_xmemory_with_key_but_no_instance_also_falls_back(self):
        be = XMemoryBackend(api_key="some_key", instance_id=None)
        ref = be.store_fact(StructuredFact(type="Reference", title="No instance", tags=["t"], status="verified", content_summary="x" * 20))
        assert ref.title == "No instance"

    def test_switching_backends_independence(self):
        local = LocalBackend(":memory:")
        xmem = XMemoryBackend(api_key="", instance_id=None)

        local.store_fact(StructuredFact(type="Reference", title="Local only", tags=["t"], status="verified", content_summary="x" * 20))
        xmem.store_fact(StructuredFact(type="Reference", title="XMem fallback", tags=["t"], status="verified", content_summary="x" * 20))

        assert len(local.query_facts(FactQuery())) >= 1
        assert len(xmem.query_facts(FactQuery())) >= 1