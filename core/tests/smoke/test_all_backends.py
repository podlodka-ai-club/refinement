"""Smoke tests: все бэкенды живы."""

import os
import pytest
from curator.backend.interface import MemoryBackend
from curator.backend.local import LocalBackend
from curator.backend.xmemory import XMemoryBackend


class TestAllBackendsHealth:
    def test_local_healthy(self):
        be = LocalBackend(":memory:")
        assert be.health_check()

    def test_xmemory_fallback_healthy(self):
        be = XMemoryBackend(api_key="", instance_id=None)
        assert be.health_check()

    def test_xmemory_live(self):
        key = os.environ.get("XMEMORY_API_KEY", "")
        inst = os.environ.get("XMEMORY_INSTANCE_ID", "")
        if not key:
            pytest.skip("XMEMORY_API_KEY not set")
        be = XMemoryBackend(api_key=key, instance_id=inst)
        assert be.health_check()

    def test_protocol_compliance_local(self):
        be = LocalBackend(":memory:")
        assert isinstance(be, MemoryBackend)

    def test_protocol_compliance_xmemory(self):
        be = XMemoryBackend(api_key="", instance_id=None)
        assert isinstance(be, MemoryBackend)