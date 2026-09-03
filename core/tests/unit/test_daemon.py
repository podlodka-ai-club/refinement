"""Юнит-тесты daemon: инвариант «worker жив, пока жив MCP-сервер».

ensure_worker идемпотентен: живой наш worker → ничего; мёртвый/чужой/
отсутствующий pid → подчистка + запуск. start_worker не запускает
реальных процессов (subprocess.Popen подменён)."""

from curator import daemon


class TestEnsureWorker:
    def test_no_pid_file_starts_worker(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        calls = []

        def fake_spawn():
            calls.append("spawn")
            return "запущен"

        result = daemon.ensure_worker(spawn=fake_spawn)
        assert calls == ["spawn"]
        assert result == "запущен"

    def test_live_own_worker_no_spawn(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        pid_file = tmp_path / ".curator" / "worker.pid"
        pid_file.parent.mkdir(parents=True)
        pid_file.write_text("42")

        monkeypatch.setattr(daemon, "read_pid", lambda: 42)
        monkeypatch.setattr(daemon, "is_running", lambda pid: True)
        monkeypatch.setattr(daemon, "pid_is_curator_worker", lambda pid: True)
        calls = []

        result = daemon.ensure_worker(spawn=lambda: calls.append("spawn"))

        assert "запущен" in result and "42" in result
        assert calls == [], "живой наш worker не должен запускаться повторно"

    def test_dead_pid_cleaned_and_spawned(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        pid_file = tmp_path / ".curator" / "worker.pid"
        pid_file.parent.mkdir(parents=True)
        pid_file.write_text("42")

        monkeypatch.setattr(daemon, "read_pid", lambda: 42)
        monkeypatch.setattr(daemon, "is_running", lambda pid: False)
        calls = []

        daemon.ensure_worker(spawn=lambda: calls.append("spawn") or "запущен")

        assert calls == ["spawn"]
        assert not pid_file.exists(), "мёртвый pid-файл обязан быть подчипчен"

    def test_foreign_live_pid_cleaned_and_spawned(self, tmp_path, monkeypatch):
        """pid жив, но это чужой процесс (ОС переиспользовала pid) —
        pid-файлу верить нельзя: подчистка + запуск своего."""
        monkeypatch.setenv("HOME", str(tmp_path))
        pid_file = tmp_path / ".curator" / "worker.pid"
        pid_file.parent.mkdir(parents=True)
        pid_file.write_text("1")  # launchd

        monkeypatch.setattr(daemon, "read_pid", lambda: 1)
        monkeypatch.setattr(daemon, "is_running", lambda pid: True)
        monkeypatch.setattr(daemon, "pid_is_curator_worker", lambda pid: False)
        calls = []

        daemon.ensure_worker(spawn=lambda: calls.append("spawn") or "запущен")

        assert calls == ["spawn"]
        assert not pid_file.exists()


class TestStartWorker:
    def test_start_writes_pid_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))

        class FakeProc:
            pid = 12345

        monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **kw: FakeProc())
        monkeypatch.setattr(daemon, "is_running", lambda pid: True)

        result = daemon.start_worker()

        assert "запущен" in result and "12345" in result
        pid_file = tmp_path / ".curator" / "worker.pid"
        assert pid_file.read_text().strip() == "12345"

    def test_start_failure_reports_log(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))

        class FakeProc:
            pid = 999

        monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **kw: FakeProc())
        monkeypatch.setattr(daemon, "is_running", lambda pid: False)

        result = daemon.start_worker()

        assert "не запустился" in result


class TestStopWorker:
    def test_no_pid(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert "не запущен" in daemon.stop_worker()

    def test_dead_pid_removed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        pid_file = tmp_path / ".curator" / "worker.pid"
        pid_file.parent.mkdir(parents=True)
        pid_file.write_text("42")

        monkeypatch.setattr(daemon, "read_pid", lambda: 42)
        monkeypatch.setattr(daemon, "is_running", lambda pid: False)

        result = daemon.stop_worker()
        assert "не существует" in result
        assert not pid_file.exists()

    def test_foreign_pid_not_killed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        pid_file = tmp_path / ".curator" / "worker.pid"
        pid_file.parent.mkdir(parents=True)
        pid_file.write_text("1")

        monkeypatch.setattr(daemon, "read_pid", lambda: 1)
        monkeypatch.setattr(daemon, "is_running", lambda pid: True)
        monkeypatch.setattr(daemon, "pid_is_curator_worker", lambda pid: False)
        killed = []
        monkeypatch.setattr(daemon.os, "kill", lambda pid, sig: killed.append((pid, sig)))

        result = daemon.stop_worker()
        assert "не похож" in result
        assert killed == [], "чужой процесс нельзя трогать"
        assert not pid_file.exists()


class TestPidFilesRespectHome:
    def test_pid_file_path_reads_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert daemon._pid_file() == tmp_path / ".curator" / "worker.pid"
