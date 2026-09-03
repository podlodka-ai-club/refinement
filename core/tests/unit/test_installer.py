"""Установщик: MCP-конфиг мержится не разрушая, скилл копируется,
идемпотентно. Всё в песочнице (HOME → tmp)."""

import json
from pathlib import Path

import pytest

from curator import installer


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _config_path(home):
    return home / ".config" / "opencode" / "opencode.json"


class TestOpencodeInstall:
    def test_merge_preserves_existing_config(self, tmp_path, monkeypatch):
        config = _config_path(tmp_path)
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({
            "model": "gpt-test",
            "mcp": {"other-server": {"command": "x"}},
        }), encoding="utf-8")
        monkeypatch.setattr(installer, "_install_skill", lambda dest: dest / "curator-save")
        from curator import daemon
        monkeypatch.setattr(daemon, "ensure_worker", lambda: "Worker уже запущен (pid 1)")

        steps = installer.install_opencode()

        data = json.loads(config.read_text(encoding="utf-8"))
        assert data["model"] == "gpt-test", "чужие ключи не трогаем"
        assert data["mcp"]["other-server"] == {"command": "x"}
        entry = data["mcp"]["memory-curator"]
        assert entry["command"]
        assert entry["env"]["MEMORY_BACKEND"] == "local"
        assert "CURATOR_BASE_DIR" in entry["env"]
        assert any("MCP-сервер" in s for s in steps)

    def test_idempotent_rerun(self, tmp_path, monkeypatch):
        from curator import daemon
        monkeypatch.setattr(daemon, "ensure_worker", lambda: "ok")
        monkeypatch.setattr(installer, "_install_skill", lambda dest: dest / "curator-save")

        installer.install_opencode()
        first = _config_path(tmp_path).read_text(encoding="utf-8")
        installer.install_opencode()
        second = _config_path(tmp_path).read_text(encoding="utf-8")

        assert first == second, "повторная установка не меняет результат"

    def test_broken_existing_config_not_touched(self, tmp_path, monkeypatch):
        config = _config_path(tmp_path)
        config.parent.mkdir(parents=True)
        config.write_text("{ это не json", encoding="utf-8")
        from curator import daemon
        monkeypatch.setattr(daemon, "ensure_worker", lambda: "ok")

        steps = installer.install_opencode()

        assert any("⛔" in s for s in steps)
        assert config.read_text(encoding="utf-8") == "{ это не json", \
            "битый конфиг пользователя нельзя перезаписывать"

    def test_no_config_creates_fresh(self, tmp_path, monkeypatch):
        from curator import daemon
        monkeypatch.setattr(daemon, "ensure_worker", lambda: "ok")
        monkeypatch.setattr(installer, "_install_skill", lambda dest: dest / "curator-save")

        installer.install_opencode()

        data = json.loads(_config_path(tmp_path).read_text(encoding="utf-8"))
        assert data["mcp"]["memory-curator"]["env"]["MEMORY_BACKEND"] == "local"


class TestClaudeInstall:
    def test_mcpjson_in_project_and_skill(self, tmp_path, monkeypatch, tmp_path_factory):
        project = tmp_path / "proj"
        project.mkdir()
        monkeypatch.chdir(project)

        steps = installer.install_claude()

        data = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
        assert "memory-curator" in data["mcpServers"]
        assert any(".mcp.json" in s for s in steps)


class TestSkillInstall:
    def test_real_skill_copied(self, tmp_path):
        # скилл реально лежит в репо (editable-установка)
        dest = installer._install_skill(tmp_path / "skills")
        if dest is None:
            pytest.skip("wheel-окружение без репо-скилла")
        assert (dest / "SKILL.md").exists()

    def test_skill_overwrite_is_clean(self, tmp_path):
        dest = installer._install_skill(tmp_path / "skills")
        if dest is None:
            pytest.skip("wheel-окружение без репо-скилла")
        (dest / "SKILL.md").write_text("испорчен", encoding="utf-8")
        dest2 = installer._install_skill(tmp_path / "skills")
        assert "испорчен" not in dest2.joinpath("SKILL.md").read_text(encoding="utf-8")


class TestServerCommand:
    def test_returns_command_and_args(self):
        command, args = installer._server_command()
        assert Path(command).exists()
        assert isinstance(args, list)
