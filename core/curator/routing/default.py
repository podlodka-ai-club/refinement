from curator.models import ProposedFact


class DefaultRouter:
    """Дефолт: всё в session/{type}.md. Не требует конфига.

    Путь, предложенный агентом/скиллом (fact.source_file), уважается:
    sandbox-безопасность (traversal, symlink) проверяет SyncEngine.
    """

    def route_fact(self, fact: ProposedFact) -> str:
        if fact.source_file:
            return fact.source_file
        return f"session/{fact.type.lower()}.md"

    def list_routes(self) -> list[dict]:
        return [{"path": "session/", "type": "all", "description": "Default — всё в одну папку"}]

    def reload(self):
        pass