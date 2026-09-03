"""Управление фоновым worker-демоном (improve loop).

pid-файл и лог живут в ~/.curator/. Инвариант: worker жив, пока жив
MCP-сервер — server.main() зовёт ensure_worker(). `curator start` —
тот же ensure (идемпотентный): живой наш worker → ничего не делает,
мёртвый/чужой/отсутствующий pid → подчистка pid-файла и запуск.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _pid_file() -> Path:
    # Path.home() читает HOME при каждом вызове — тесты изолируются через env
    return Path.home() / ".curator" / "worker.pid"


def _worker_log() -> Path:
    return Path.home() / ".curator" / "worker.log"


def read_pid() -> int | None:
    pid_file = _pid_file()
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def pid_is_curator_worker(pid: int) -> bool:
    """Верификация перед kill: pid-файл мог протухнуть, ОС переиспользовала pid.

    Матчим точные токены командной строки: `python -m curator.worker`
    (как запускает start_worker) и entrypoint `curator-worker`. Подстрочные
    совпадения (`rg curator.worker`, `tail -f curator.worker.log`) — нет.
    """
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return False
    tokens = out.stdout.split()
    for i, tok in enumerate(tokens):
        if tok == "-m" and i + 1 < len(tokens) and tokens[i + 1] == "curator.worker":
            return True
        if tok == "curator-worker" or tok.endswith("/curator-worker"):
            return True
    return False


def start_worker() -> str:
    """Запустить worker-демон, вернуть человекочитаемый статус."""
    pid_file = _pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    interval = os.getenv("IMPROVE_INTERVAL_MINUTES", "1440")
    backend = os.getenv("MEMORY_BACKEND", "local")

    worker_cmd = [sys.executable, "-m", "curator.worker", "--daemon"]
    env = os.environ.copy()
    env["MEMORY_BACKEND"] = backend
    env["IMPROVE_INTERVAL_MINUTES"] = interval

    log_file = _worker_log()
    from datetime import datetime
    with open(log_file, "a") as log:
        log.write(f"\n[{datetime.now().isoformat()}] Starting worker...\n")
        proc = subprocess.Popen(
            worker_cmd, env=env,
            stdout=log, stderr=log,
            start_new_session=True,
        )
        pid_file.write_text(str(proc.pid))

    time.sleep(0.5)
    if is_running(proc.pid):
        return f"✅ Worker запущен (pid {proc.pid}, интервал {interval} мин, бэкенд {backend}, лог {log_file})"
    return f"❌ Worker не запустился. Проверьте лог: {log_file}"


def ensure_worker(spawn=None) -> str:
    """Инвариант «worker жив»: идемпотентный запуск.

    Живой наш worker → ничего не делает. Мёртвый или чужой (pid
    переиспользован ОС) pid-файл → подчистка + запуск. `spawn` — точка
    подмены для тестов.
    """
    spawn = spawn or start_worker
    pid_file = _pid_file()
    pid = read_pid()
    if pid and is_running(pid) and pid_is_curator_worker(pid):
        return f"Worker уже запущен (pid {pid})"
    if pid:
        pid_file.unlink(missing_ok=True)
    return spawn()


def stop_worker() -> str:
    pid_file = _pid_file()
    pid = read_pid()
    if not pid:
        return "Worker не запущен."
    if not is_running(pid):
        pid_file.unlink(missing_ok=True)
        return f"Процесс {pid} не существует. Удаляю pid-файл."
    if not pid_is_curator_worker(pid):
        pid_file.unlink(missing_ok=True)
        return (f"Процесс {pid} не похож на curator-worker (pid переиспользован ОС?) "
                f"— не убиваю, удаляю pid-файл.")
    os.kill(pid, signal.SIGTERM)
    time.sleep(0.5)
    if is_running(pid):
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.3)
    pid_file.unlink(missing_ok=True)
    return f"✅ Worker остановлен (pid {pid})"
