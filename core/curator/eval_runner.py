"""Eval-фреймворк: проверяет улучшения перед применением.

Перед тем как изменить память (mark stale, consolidate), прогоняет
тестовые запросы на текущем и предлагаемом состояниях, сравнивает метрики.

Метрики:
- query_coverage: % тестовых запросов которые возвращают результаты
- duplicate_count: сколько дубликатов в базе
- stale_percent: доля устаревших/неподтверждённых фактов
- freshness: доля verified фактов

Gate: изменение применяется только если метрики улучшились (или не ухудшились).
"""

from dataclasses import dataclass, field
from curator.models import StructuredFact, FactQuery


@dataclass
class EvalMetrics:
    query_coverage: float
    total_facts: int
    verified_percent: float
    stale_percent: float
    duplicate_count: int
    details: dict = field(default_factory=dict)


@dataclass
class EvalAction:
    description: str
    before_metrics: EvalMetrics
    after_metrics: EvalMetrics

    @property
    def improved(self) -> bool:
        if self.before_metrics.total_facts == 0 and self.after_metrics.total_facts == 0:
            return False
        if self.after_metrics.query_coverage < self.before_metrics.query_coverage:
            return False
        if self.after_metrics.stale_percent > self.before_metrics.stale_percent:
            return False
        if self.after_metrics.total_facts < self.before_metrics.total_facts * 0.5:
            return False
        if self.before_metrics == self.after_metrics:
            return False
        return True

    @property
    def delta(self) -> dict:
        return {
            "query_coverage": self.after_metrics.query_coverage - self.before_metrics.query_coverage,
            "verified_percent": self.after_metrics.verified_percent - self.before_metrics.verified_percent,
            "stale_percent": self.after_metrics.stale_percent - self.before_metrics.stale_percent,
            "total_facts": self.after_metrics.total_facts - self.before_metrics.total_facts,
        }


TEST_QUERIES = [
    FactQuery(search="kotlin"),
    FactQuery(search="compose"),
    FactQuery(search="git"),
    FactQuery(search="architecture"),
    FactQuery(type="Style"),
]


class EvalRunner:
    def __init__(self, test_queries: list[FactQuery] | None = None):
        self.queries = test_queries or TEST_QUERIES

    def measure(self, facts: list[StructuredFact]) -> EvalMetrics:
        total = len(facts)
        if total == 0:
            return EvalMetrics(
                query_coverage=0.0,
                total_facts=0,
                verified_percent=0.0,
                stale_percent=0.0,
                duplicate_count=0,
            )

        verified = sum(1 for f in facts if f.status == "verified")
        stale = sum(1 for f in facts if f.status in ("hypothesis", "deprecated"))

        covered = 0
        for q in self.queries:
            q_result = self._search(facts, q)
            if q_result:
                covered += 1

        coverage = covered / len(self.queries) if self.queries else 0.0

        return EvalMetrics(
            query_coverage=coverage,
            total_facts=total,
            verified_percent=verified / total,
            stale_percent=stale / total,
            duplicate_count=0,
            details={
                "verified": verified,
                "stale": stale,
                "queries_covered": covered,
            },
        )

    def _search(self, facts: list[StructuredFact], query: FactQuery) -> list[StructuredFact]:
        result = []
        for f in facts:
            match = True
            if query.type and f.type != query.type:
                match = False
            if query.status and f.status != query.status:
                match = False
            if query.search and query.search.lower() not in f.title.lower():
                match = False
            if match:
                result.append(f)
        return result

    def evaluate_consolidation(
        self,
        before_facts: list[StructuredFact],
        duplicates_to_consolidate: list[tuple[StructuredFact, StructuredFact]],
    ) -> EvalAction:
        before = self.measure(before_facts)
        after_facts = self._simulate_consolidation(before_facts, duplicates_to_consolidate)
        after = self.measure(after_facts)
        return EvalAction(
            description=f"Консолидация {len(duplicates_to_consolidate)} пар дубликатов",
            before_metrics=before,
            after_metrics=after,
        )

    def evaluate_deprecation(
        self,
        before_facts: list[StructuredFact],
        facts_to_deprecate: list[StructuredFact],
    ) -> EvalAction:
        before = self.measure(before_facts)
        after_facts = self._simulate_deprecation(before_facts, facts_to_deprecate)
        after = self.measure(after_facts)
        return EvalAction(
            description=f"Deprecation {len(facts_to_deprecate)} устаревших фактов",
            before_metrics=before,
            after_metrics=after,
        )

    def _simulate_consolidation(
        self,
        facts: list[StructuredFact],
        dups: list[tuple[StructuredFact, StructuredFact]],
    ) -> list[StructuredFact]:
        """Симуляция: проигравшие дубликаты становятся deprecated и покидают
        активный набор (ImproveLoop фильтрует deprecated) — в симуляции это
        эквивалентно удалению из измеряемого списка."""
        to_remove = set()
        for _, f2 in dups:
            to_remove.add(f2.title)
        return [f for f in facts if f.title not in to_remove]

    def _simulate_deprecation(
        self,
        facts: list[StructuredFact],
        stale: list[StructuredFact],
    ) -> list[StructuredFact]:
        """Симуляция: устаревшие факты становятся deprecated и покидают
        активный набор (ImproveLoop фильтрует deprecated) — в симуляции это
        эквивалентно удалению из измеряемого списка."""
        stale_titles = {f.title for f in stale}
        return [f for f in facts if f.title not in stale_titles]