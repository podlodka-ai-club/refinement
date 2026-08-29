"""Интеграционные тесты offline-fallback (UC6): сетевые ошибки → локальная БД + outbox."""

import httpx
import pytest
from curator.backend.xmemory import XMemoryBackend
from curator.backend.local import LocalBackend
from curator.outbox import Outbox
from curator.models import StructuredFact, FactQuery, FactRef

FACT = StructuredFact(
    type="Reference",
    title="Data class предпочтительнее value class в sealed иерархии",
    tags=["kotlin"],
    status="verified",
    content_summary="JvmInline в sealed interface даёт неизбежный бокс — использовать data class.",
)


class FailingClient:
    def __init__(self, exc):
        self._exc = exc

    def post(self, *args, **kwargs):
        raise self._exc

    def get(self, *args, **kwargs):
        raise self._exc


def _connect_error():
    return httpx.ConnectError("connection refused")


def _status_error(code: int):
    req = httpx.Request("POST", "https://api.xmemory.ai/x")
    resp = httpx.Response(code, request=req)
    return httpx.HTTPStatusError(f"HTTP {code}", request=req, response=resp)


def _backend(tmp_path, exc) -> XMemoryBackend:
    be = XMemoryBackend(
        api_key="key", instance_id="inst",
        local_path=str(tmp_path / "local.db"),
        outbox_path=str(tmp_path / "outbox.db"),
    )
    be._client = FailingClient(exc)
    return be


class TestStoreFailover:
    def test_connect_error_goes_local_and_outbox(self, tmp_path):
        be = _backend(tmp_path, _connect_error())
        ref = be.store_fact(FACT)
        assert ref.title == FACT.title

        assert Outbox(str(tmp_path / "outbox.db")).count() == 1
        local = LocalBackend(str(tmp_path / "local.db"))
        assert len(local.query_facts(FactQuery(search="value class"))) == 1

    def test_504_goes_local(self, tmp_path):
        be = _backend(tmp_path, _status_error(504))
        be.store_fact(FACT)
        assert Outbox(str(tmp_path / "outbox.db")).count() == 1

    def test_4xx_raises_no_failover(self, tmp_path):
        be = _backend(tmp_path, _status_error(400))
        with pytest.raises(httpx.HTTPStatusError):
            be.store_fact(FACT)
        assert Outbox(str(tmp_path / "outbox.db")).count() == 0

    def test_outbox_upsert_by_title(self, tmp_path):
        be = _backend(tmp_path, _connect_error())
        be.store_fact(FACT)
        be.store_fact(FACT)
        assert Outbox(str(tmp_path / "outbox.db")).count() == 1


class TestQueryFailover:
    def test_query_degrades_to_local(self, tmp_path):
        be = _backend(tmp_path, _connect_error())
        be.store_fact(FACT)
        facts = be.query_facts(FactQuery(search="value class"))
        assert len(facts) == 1
        assert facts[0].title == FACT.title


class TestSyncFlow:
    def test_push_direct_success_and_mark_synced(self, tmp_path):
        be = _backend(tmp_path, _connect_error())
        be.store_fact(FACT)

        ob = Outbox(str(tmp_path / "outbox.db"))
        assert ob.count() == 1

        class OkClient:
            def post(self, *args, **kwargs):
                class R:
                    def raise_for_status(self):
                        pass

                    def json(self):
                        return {"items": [{"write_id": "w1"}]}
                return R()

        be._client = OkClient()
        pending = ob.pending()
        assert len(pending) == 1
        row_id, fact = pending[0]
        ref = be.push_direct(fact)
        assert isinstance(ref, FactRef)
        ob.mark_synced(row_id)
        assert ob.count() == 0
