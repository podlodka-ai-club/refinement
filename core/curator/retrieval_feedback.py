"""Обратная связь по использованию: отслеживает какие факты запрашиваются."""

import time
import json
from pathlib import Path
from collections import defaultdict


class RetrievalFeedback:
    """Отслеживает usage фактов через query-запросы."""

    def __init__(self, storage_path: str = "~/.curator/usage.json"):
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "last_access": 0.0})
        self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                self._counts = defaultdict(
                    lambda: {"count": 0, "last_access": 0.0},
                    json.loads(self.storage_path.read_text()),
                )
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        self.storage_path.write_text(json.dumps(dict(self._counts), indent=2))

    def record_query(self, query_result_count: int, accessed_titles: list[str]):
        """Записать что N фактов были возвращены в ответ на запрос."""
        for title in accessed_titles:
            self._counts[title]["count"] += 1
            self._counts[title]["last_access"] = time.time()
        self._save()

    def record_save(self, title: str):
        """Записать сохранение нового факта."""
        if title not in self._counts:
            self._counts[title] = {"count": 0, "last_access": time.time()}
        self._save()

    def get_stats(self, top_n: int = 10) -> list[dict]:
        """Топ-N самых используемых фактов."""
        sorted_items = sorted(
            self._counts.items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        )
        return [
            {"title": title, "count": data["count"], "last_access": data["last_access"]}
            for title, data in sorted_items[:top_n]
            if data["count"] > 0
        ]

    def get_unused(self, min_days: int = 90) -> list[str]:
        """Факты к которым не обращались > N дней (кандидаты на deprecation)."""
        cutoff = time.time() - (min_days * 86400)
        return [
            title
            for title, data in self._counts.items()
            if data["last_access"] < cutoff
        ]