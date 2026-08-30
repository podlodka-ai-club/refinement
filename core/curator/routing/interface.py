from typing import Protocol, runtime_checkable
from curator.models import ProposedFact


@runtime_checkable
class Router(Protocol):
    """Определяет куда сохранять факт.

    Участник 1 (Блок 1) реализует свой RoutingRouter с чтением routing.yaml.
    Подключение: ROUTER_CLASS=your.module.YourRouter curator-mcp-server
    """

    def route_fact(self, fact: ProposedFact) -> str:
        """Возвращает source_file для факта.

        Например: 'reference/kotlin/data.md' или 'style/commits.md'.
        """
        ...

    def list_routes(self) -> list[dict]:
        """Возвращает текущие маршруты для MCP-тулза curator_routes."""
        ...