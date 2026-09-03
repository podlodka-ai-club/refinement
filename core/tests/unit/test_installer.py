"""Установщик: MCP+команды+скиллы мержатся не разрушая, идемпотентно,
база настраивается (вопрос/флаг/дефолт). Всё в песочнице (HOME → tmp)."""

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


@pytest.fixture(autouse=True)
def no_worker(monkeypatch):
    from curator import daemon
    monkeypatch.setattr(daemon, "ensure_worker", lambda: "Worker уже запущен (pid 1)")


class TestOpencodeInstall:
    def test_merge_preserves_existing_config(self, tmp_path):
        config = _config_path(tmp_path)
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({
            "model": "gpt-test",
            "mcp": {"other-server": {"command": "x"}},
            "command": {"my-command": {"description": "моя", "template": "т"}},
        }), encoding="utf-8")

        steps = installer.install_opencode(base_dir=str(tmp_path / "kb"))

        data = json.loads(config.read_text(encoding="utf-8"))
        assert data["model"] == "gpt-test", "чужие ключи не трогаем"
        assert data["mcp"]["other-server"] == {"command": "x"}
        assert data["command"]["my-command"]["description"] == "моя", "чужие команды не трогаем"
        entry = data["mcp"]["memory-curator"]
        assert entry["command"]
        assert entry["env"]["MEMORY_BACKEND"] == "local"
        assert entry["env"]["CURATOR_BASE_DIR"] == str(tmp_path / "kb")
        assert entry["env"]["ROUTER_CLASS"] == "curator.routing.map_router.MapRouter"
        assert any("MCP-сервер" in s for s in steps)

    def test_commands_installed_from_repo_source(self, tmp_path):
        """Команды /curator-* — часть продукта: приезжают с install,
        включая /curator-create-map (вызов скилла mapping-documentation)."""
        installer.install_opencode(base_dir=str(tmp_path / "kb"))

        data = json.loads(_config_path(tmp_path).read_text(encoding="utf-8"))
        commands = data["command"]
        assert "curator-save" in commands
        assert "curator-create-map" in commands
        assert "DOCUMENTATION-MAP.md" in commands["curator-create-map"]["template"]
        assert "mapping-documentation" in commands["curator-create-map"]["template"]

    def test_all_repo_skills_installed(self, tmp_path):
        """Оба скилла продукта: curator-save и mapping-documentation (Егора)."""
        installer.install_opencode(base_dir=str(tmp_path / "kb"))

        skills_dir = tmp_path / ".config" / "opencode" / "skills"
        installed = {p.name for p in skills_dir.iterdir()}
        assert "curator-save" in installed
        assert "mapping-documentation" in installed

    def test_idempotent_rerun(self, tmp_path):
        installer.install_opencode(base_dir=str(tmp_path / "kb"))
        first = _config_path(tmp_path).read_text(encoding="utf-8")
        installer.install_opencode(base_dir=str(tmp_path / "kb"))
        second = _config_path(tmp_path).read_text(encoding="utf-8")
        assert first == second, "повторная установка не меняет результат"

    def test_broken_existing_config_not_touched(self, tmp_path):
        config = _config_path(tmp_path)
        config.parent.mkdir(parents=True)
        config.write_text("{ это не json", encoding="utf-8")

        steps = installer.install_opencode(base_dir=str(tmp_path / "kb"))

        assert any("⛔" in s for s in steps)
        assert config.read_text(encoding="utf-8") == "{ это не json", \
            "битый конфиг пользователя нельзя перезаписывать"

    def test_default_base_dir_neutral(self):
        assert installer.default_base_dir().endswith("memory-curator")
        assert "Documents/AI" not in installer.default_base_dir(), \
            "личный путь автора не должен быть дефолтом продукта"


class TestClaudeInstall:
    def test_mcpjson_commands_and_skills(self, tmp_path, monkeypatch):
        project = tmp_path / "proj"
        project.mkdir()
        monkeypatch.chdir(project)

        steps = installer.install_claude(base_dir=str(tmp_path / "kb"))

        data = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
        assert "memory-curator" in data["mcpServers"]
        assert data["mcpServers"]["memory-curator"]["env"]["ROUTER_CLASS"] == \
            "curator.routing.map_router.MapRouter"

        commands_dir = tmp_path / ".claude" / "commands"
        assert (commands_dir / "curator-save.md").exists()
        assert (commands_dir / "curator-create-map.md").exists()
        body = (commands_dir / "curator-create-map.md").read_text(encoding="utf-8")
        assert "mapping-documentation" in body

        skills_dir = tmp_path / ".claude" / "skills"
        installed = {p.name for p in skills_dir.iterdir()}
        assert {"curator-save", "mapping-documentation"} <= installed
        assert any(".mcp.json" in s for s in steps)


class TestServerCommand:
    def test_returns_command_and_args(self):
        command, args = installer._server_command()
        assert Path(command).exists()
        assert isinstance(args, list)
