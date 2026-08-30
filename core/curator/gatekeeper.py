from dataclasses import dataclass, field
from curator.models import ProposedFact, StructuredFact
from curator.backend.interface import MemoryBackend


@dataclass
class GatekeeperResult:
    approved: list[ProposedFact] = field(default_factory=list)
    rejected: list[tuple[ProposedFact, str]] = field(default_factory=list)


class Gatekeeper:
    """Фильтрует факты перед сохранением."""

    MIN_TITLE_LENGTH = 10
    MAX_TITLE_LENGTH = 200
    MIN_SUMMARY_LENGTH = 20

    NOISE_PATTERNS = [
        "поменять цвет", "сдвинуть на 2px", "добавить отступ",
        "поменять шрифт", "изменить размер", "поправить верстку",
    ]

    def __init__(self, backend: MemoryBackend | None = None, check_duplicates: bool = True):
        self.backend = backend
        self.check_duplicates = check_duplicates

    def filter(self, facts: list[ProposedFact]) -> GatekeeperResult:
        result = GatekeeperResult()
        for fact in facts:
            rejection = self._check(fact)
            if rejection:
                result.rejected.append((fact, rejection))
            else:
                result.approved.append(fact)
        return result

    def _check(self, fact: ProposedFact) -> str | None:
        if len(fact.title) < self.MIN_TITLE_LENGTH:
            return "Слишком короткий заголовок"
        if len(fact.title) > self.MAX_TITLE_LENGTH:
            return "Слишком длинный заголовок"
        if len(fact.content_summary) < self.MIN_SUMMARY_LENGTH:
            return "Слишком короткое описание"

        title_lower = fact.title.lower()
        for pattern in self.NOISE_PATTERNS:
            if pattern in title_lower:
                return "Похоже на фичевую деталь, не абстрактное знание"

        if not fact.tags:
            return "Нет тегов — знание невозможно категоризировать"

        if self.check_duplicates and self.backend:
            similar = self.backend.find_similar(
                StructuredFact(type=fact.type, title=fact.title, tags=fact.tags, status="verified", content_summary=fact.content_summary),
                threshold=0.6
            )
            for e in similar:
                if self._is_similar(fact.title, e.title):
                    return f"Вероятный дубликат: уже есть '{e.title}'"

        return None

    def _is_similar(self, a: str, b: str) -> bool:
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a:
            return False
        overlap = len(words_a & words_b)
        return overlap / len(words_a) > 0.6