from dataclasses import dataclass, field
from typing import Literal

FactType = Literal["Reference", "Style", "Tool", "Spec"]
FactStatus = Literal["verified", "hypothesis", "deprecated"]

_FACT_TYPES = ("Reference", "Style", "Tool", "Spec")


def normalize_fact_type(raw: str) -> FactType:
    """Нормализовать тип факта от агента; неизвестное → Reference."""
    return raw if raw in _FACT_TYPES else "Reference"


@dataclass
class StructuredFact:
    """Валидированный факт, готовый к сохранению в память."""

    type: FactType
    title: str
    tags: list[str]
    status: FactStatus
    content_summary: str
    source_file: str | None = None
    source_session: str | None = None


@dataclass
class ProposedFact:
    """Факт до валидации — пришёл из сессии или .md парсинга."""

    type: FactType
    title: str
    content_summary: str
    tags: list[str] = field(default_factory=list)
    evidence: str = ""


@dataclass
class FactRef:
    """Ссылка на сохранённый факт."""

    id: str
    title: str


@dataclass
class FactQuery:
    """Параметры поиска фактов."""

    type: FactType | None = None
    tags: list[str] | None = None
    status: FactStatus | None = None
    search: str | None = None


@dataclass
class Relation:
    """Связь между двумя фактами."""

    source_id: str
    target_id: str
    kind: Literal["related_to", "contradicts"]


@dataclass
class GraphData:
    """Граф знаний: узлы и рёбра."""

    nodes: list[StructuredFact]
    edges: list[Relation]