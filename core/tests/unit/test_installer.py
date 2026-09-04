"""Установщик без вопросов: автодетект харнесов, молчаливый дефолт базы,
идемпотентность. Всё в песочнице (HOME → tmp)."""

import json
from pathlib import Path

import pytest

from curator import installer


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CURATOR_BASE_DIR", raising=False)
    return tmp_path


@pytest.fixture(autouse=True)
def no_worker(monkeypatch):
    from curator import daemon
    monkeypatch.setattr(daemon, "ensure_worker", lambda: "Worker уже запущен (pid 1)")


def _opencode_dir(home):
    d = home / ".config" / "opencode"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _claude_dir(home):
    d = home / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    return d


class TestAutoDetect:
    def test_opencode_only(self, tmp_path):
        _opencode_dir(tmp_path)
        steps = installer.install_all()
        assert any("opencode: MCP" in s for s in steps)
        assert not any("Claude Code: MCP" in s for s in steps)
        config = json.loads((tmp_path / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8"))
        assert config["mcp"]["memory-curator"]["env"]["ROUTER_CLASS"] == "curator.routing.map_router.MapRouter"

    def test_claude_only(self, tmp_path, monkeypatch):
        _claude_dir(tmp_path)
        project = tmp_path / "proj"
        project.mkdir()
        monkeypatch.chdir(project)

        steps = installer.install_all()

        assert any("Claude Code: MCP" in s for s in steps)
        assert not (tmp_path / ".config" / "opencode" / "opencode.json").exists(), \
            "opencode не найден — его конфиг не создаём"
        assert (project / ".mcp.json").exists()
        assert (tmp_path / ".claude" / "commands" / "curator-create-map.md").exists()

    def test_both_detected_installed_both(self, tmp_path, monkeypatch):
        _opencode_dir(tmp_path)
        _claude_dir(tmp_path)
        project = tmp_path / "proj"
        project.mkdir()
        monkeypatch.chdir(project)

        installer.install_all()

        assert (tmp_path / ".config" / "opencode" / "opencode.json").exists()
        assert (project / ".mcp.json").exists()

    def test_nothing_detected_opencode_layout_with_hint(self, tmp_path):
        steps = installer.install_all()
        assert any("не обнаружены" in s for s in steps), \
            "без находок — честная подсказка, а не молчаливая установка"
        assert (tmp_path / ".config" / "opencode" / "opencode.json").exists()

    def test_target_override_claude(self, tmp_path, monkeypatch):
        project = tmp_path / "proj"
        project.mkdir()
        monkeypatch.chdir(project)

        installer.install_all(target="claude")

        assert (project / ".mcp.json").exists()
        assert not (tmp_path / ".config" / "opencode").exists()


class TestZeroQuestions:
    def test_footer_tells_how_to_change_base(self, tmp_path):
        steps = installer.install_all()
        text = "\n".join(steps)
        assert "База знаний:" in text and "curator status" in text, \
            "где база и как сменить — обязаны быть в выводе, не вопросом"
        assert "попроси агента" in text

    def test_base_dir_flag_silent_override(self, tmp_path):
        _opencode_dir(tmp_path)
        installer.install_all(base_dir=str(tmp_path / "custom-kb"))
        config = json.loads((tmp_path / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8"))
        assert config["mcp"]["memory-curator"]["env"]["CURATOR_BASE_DIR"] == str(tmp_path / "custom-kb")

    def test_default_base_neutral(self):
        assert installer.default_base_dir().endswith("memory-curator")
        assert "Documents/AI" not in installer.default_base_dir()


class TestIdempotencyAndSafety:
    def test_merge_preserves_existing(self, tmp_path):
        config_path = _opencode_dir(tmp_path) / "opencode.json"
        config_path.write_text(json.dumps({
            "model": "gpt-test",
            "mcp": {"other": {"command": "x"}},
            "command": {"my-command": {"description": "моя", "template": "т"}},
        }), encoding="utf-8")

        installer.install_all()

        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["model"] == "gpt-test"
        assert data["mcp"]["other"] == {"command": "x"}
        assert data["command"]["my-command"]["description"] == "моя"
        assert "curator-create-map" in data["command"]

    def test_idempotent_rerun(self, tmp_path):
        _opencode_dir(tmp_path)
        installer.install_all()
        first = (tmp_path / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8")
        installer.install_all()
        second = (tmp_path / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8")
        assert first == second

    def test_broken_existing_config_not_touched(self, tmp_path):
        config_path = _opencode_dir(tmp_path) / "opencode.json"
        config_path.write_text("{ это не json", encoding="utf-8")

        steps = installer.install_all()

        assert any("⛔" in s for s in steps)
        assert config_path.read_text(encoding="utf-8") == "{ это не json"

    def test_all_repo_skills_installed(self, tmp_path):
        _opencode_dir(tmp_path)
        installer.install_all()
        skills = {p.name for p in (tmp_path / ".config" / "opencode" / "skills").iterdir()}
        assert {"curator-save", "mapping-documentation"} <= skills


class TestConfiguredBaseDir:
    def test_cli_status_reads_installed_config(self, tmp_path, capsys):
        from curator import control
        _opencode_dir(tmp_path)
        installer.install_all(base_dir=str(tmp_path / "kb"))

        control.cmd_status()

        out = capsys.readouterr().out
        assert str(tmp_path / "kb") in out, "curator status показывает, где лежит база"

    def test_server_status_shows_base(self, tmp_path):
        import curator.server as server_mod
        from curator.backend.local import LocalBackend
        from curator.improve_loop import ImproveLoop
        server_mod.backend = LocalBackend(":memory:")
        server_mod.improve = ImproveLoop(server_mod.backend)
        out = server_mod._status()
        assert "База знаний:" in out


class TestServerCommand:
    def test_returns_command_and_args(self):
        command, args = installer._server_command()
        assert Path(command).exists()
        assert isinstance(args, list)
