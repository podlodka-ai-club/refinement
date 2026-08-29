"""Лог сервера: JSONL в ~/.curator/server.log.

Каждая строка — один вызов/этап:
  {"ts": "2026-08-25T10:00:00", "event": "session_capture", "stage": "analyze",
   "model": "...", "duration_ms": 1234, "num_facts": 3, "error": ""}

Зачем: диагностика таймаутов и ошибок MCP-сервера без правки вслепую.
"""

import json
import os
import time
from pathlib import Path


def _path() -> Path:
    base = os.getenv("CURATOR_LOG_PATH", "~/.curator/server.log")
    return Path(base).expanduser()


def log(event: str, **fields):
    try:
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "event": event,
        }
        rec.update(fields)
        with open(p, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
