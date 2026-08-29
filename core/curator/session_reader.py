"""Читатель реальных сессий OpenCode из opencode.db.

Извлекает диалоги для демо на реальных данных: 386 сессий, 16K сообщений.
Использование:
    from curator.session_reader import extract_opencode_sessions
    sessions = extract_opencode_sessions(n=5)  # → list[DemoSession]
"""

import sqlite3
import json
from pathlib import Path
from dataclasses import dataclass


@dataclass
class OpenCodeSession:
    name: str
    text: str
    messages: int
    tokens: int


def extract_opencode_sessions(
    db_path: str = "~/.local/share/opencode/opencode.db",
    n: int = 5,
) -> list[OpenCodeSession]:
    db = Path(db_path).expanduser()
    if not db.exists():
        return []

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    # Берём N самых насыщенных неархивированных сессий
    rows = conn.execute("""
        SELECT s.id, s.slug, s.title, COUNT(m.id) as msg_count,
               s.tokens_input, s.tokens_output
        FROM session s
        JOIN message m ON m.session_id = s.id
        WHERE s.time_archived IS NULL
        GROUP BY s.id
        HAVING msg_count >= 5
        ORDER BY msg_count DESC
        LIMIT ?
    """, [n]).fetchall()

    sessions = []
    for row in rows:
        messages = conn.execute("""
            SELECT m.id, m.data, p.data as part_data
            FROM message m
            JOIN part p ON p.message_id = m.id
            WHERE m.session_id = ?
            ORDER BY m.time_created, p.time_created
            LIMIT 100
        """, [row["id"]]).fetchall()

        lines = []
        for msg in messages:
            try:
                pdata = json.loads(msg["part_data"])
                if pdata.get("type") == "text" and pdata.get("text"):
                    role = _extract_role(msg)
                    text = pdata["text"].strip()
                    if text and len(text) > 10:
                        prefix = "пользователь:" if role == "user" else "агент:"
                        lines.append(f"{prefix} {text[:300]}")
            except (json.JSONDecodeError, KeyError):
                continue

        if len(lines) >= 5:
            sessions.append(OpenCodeSession(
                name=row["title"] or row["slug"],
                text="\n".join(lines[:30]),
                messages=row["msg_count"],
                tokens=(row["tokens_input"] or 0) + (row["tokens_output"] or 0),
            ))

    conn.close()
    return sessions


def _extract_role(msg) -> str:
    try:
        data = json.loads(msg["data"])
        role = data.get("role", "")
        if role:
            return role
    except (json.JSONDecodeError, KeyError):
        pass
    try:
        pdata = json.loads(msg["part_data"])
        role = pdata.get("role", "")
        if role:
            return role
    except (json.JSONDecodeError, KeyError):
        pass
    return "agent"