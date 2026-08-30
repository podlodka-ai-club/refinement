from curator.models import ProposedFact


class DefaultRouter:
    """Падает всё в session/{type}.md. Не требует конфига."""

    def route_fact(self, fact: ProposedFact) -> str:
        return f"session/{fact.type.lower()}.md"

    def list_routes(self) -> list[dict]:
        return [{"path": "session/", "type": "all", "description": "Default — всё в одну папку"}]

    def reload(self):
        pass