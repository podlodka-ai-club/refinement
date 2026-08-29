"""Тесты нового контракта curator_session_capture: candidates на входе.

Извлечение делает агент — сервер валидирует, фильтрует и сохраняет.
"""

import pytest
import curator.server as server_mod
from curator.backend.local import LocalBackend
from curator.gatekeeper import Gatekeeper
from curator.retrieval_feedback import RetrievalFeedback
from curator.models import FactQuery

VALID_FACT = {
    "type": "Reference",
    "title": "JvmInline value class внутри sealed interface бесполезен",
    "content_summary": "Бокс неизбежен, data class предпочтительнее для доменных типов-обёрток.",
    "tags": ["kotlin", "jvm"],
    "evidence": "агент: бокс неизбежен в sealed иерархии",
}

VALID_FACT_2 = {
    "type": "Style",
    "title": "Коммиты только по явной просьбе пользователя",
    "content_summary": "Никогда не коммитить автоматически после изменений, только по /commit.",
    "tags": ["workflow", "git"],
}


@pytest.fixture
def memory_server(monkeypatch, tmp_path):
    be = LocalBackend(":memory:")
    monkeypatch.setattr(server_mod, "backend", be)
    monkeypatch.setattr(server_mod, "gatekeeper", Gatekeeper(be))
    monkeypatch.setattr(server_mod, "feedback", RetrievalFeedback())
    monkeypatch.setattr(server_mod, "base_dir", tmp_path)
    monkeypatch.delenv("AUTO_MODE", raising=False)
    return be


class TestCandidatesIntake:
    def test_valid_candidates_preview(self, memory_server):
        out = server_mod._session_capture({"candidates": [VALID_FACT, VALID_FACT_2]})
        assert "Получено кандидатов: 2" in out
        assert VALID_FACT["title"] in out
        assert VALID_FACT_2["title"] in out
        assert "Авто-сохранено" not in out

    def test_empty_candidates_error(self, memory_server):
        out = server_mod._session_capture({"candidates": []})
        assert "Ошибка" in out

    def test_missing_title_reported(self, memory_server):
        broken = dict(VALID_FACT)
        broken["title"] = ""
        out = server_mod._session_capture({"candidates": [broken]})
        assert "нет title" in out

    def test_missing_summary_reported(self, memory_server):
        broken = dict(VALID_FACT)
        broken["content_summary"] = ""
        out = server_mod._session_capture({"candidates": [broken]})
        assert "нет content_summary" in out

    def test_candidates_as_json_string(self, memory_server):
        import json
        out = server_mod._session_capture({"candidates": json.dumps([VALID_FACT])})
        assert "Получено кандидатов: 1" in out

    def test_invalid_json_string(self, memory_server):
        out = server_mod._session_capture({"candidates": "{not json"})
        assert "Ошибка" in out


class TestCandidatesSave:
    def test_auto_approve_saves_to_backend(self, memory_server, tmp_path):
        out = server_mod._session_capture({"candidates": [VALID_FACT], "auto_approve": True})
        assert "Авто-сохранено: 1" in out
        facts = memory_server.query_facts(FactQuery(search="JvmInline"))
        assert len(facts) == 1

    def test_auto_approve_writes_md(self, memory_server, tmp_path):
        server_mod._session_capture({"candidates": [VALID_FACT], "auto_approve": True})
        md = tmp_path / "session" / "reference.md"
        assert md.exists()
        content = md.read_text(encoding="utf-8")
        assert "### " + VALID_FACT["title"] in content

    def test_no_autosave_without_flag(self, memory_server, tmp_path):
        server_mod._session_capture({"candidates": [VALID_FACT]})
        assert not (tmp_path / "session").exists()


class TestCandidatesGatekeeper:
    def test_noise_rejected(self, memory_server):
        noisy = dict(VALID_FACT)
        noisy["title"] = "Поправить верстку кнопки на экране входа"
        out = server_mod._session_capture({"candidates": [noisy, VALID_FACT_2]})
        assert "Отклонено: 1" in out
        assert "фичевую" in out

    def test_duplicate_rejected(self, memory_server):
        server_mod._session_capture({"candidates": [VALID_FACT], "auto_approve": True})
        similar = dict(VALID_FACT)
        similar["title"] = "JvmInline value class внутри sealed interface вызывает бокс"
        out = server_mod._session_capture({"candidates": [similar]})
        assert "дубликат" in out.lower()
