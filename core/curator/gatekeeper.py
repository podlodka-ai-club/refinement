from dataclasses import dataclass, field
from curator.models import ProposedFact, StructuredFact, META_LINE_PREFIXES
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
    MAX_SUMMARY_LENGTH = 2000

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
        # Многострочный title или # в его начале ломают маркер `### {title}`
        # в .md (upsert/remove) — вход приходит от LLM, проверяем жёстко
        if "\n" in fact.title or "\r" in fact.title:
            return "Заголовок должен быть одной строкой"
        if fact.title.lstrip().startswith("#"):
            return "Заголовок не может начинаться с #"
        # Рендер деприкации пишет `### {title} [УСТАРЕЛО]` — title с таким
        # хвостом неотличим от маркера и терялся бы при rebuild из .md
        if fact.title.rstrip().endswith("[УСТАРЕЛО]"):
            return "Заголовок не может заканчиваться на [УСТАРЕЛО]"
        # Длина меряется по СПЛЮЩЕННОЙ форме: парсер .md склеивает строки
        # summary в одну — raw-длинный, но сплющенно-короткий факт прошёл бы
        # capture и молча терялся при rebuild из .md
        flattened = " ".join(line.strip() for line in fact.content_summary.splitlines() if line.strip())
        if len(flattened) < self.MIN_SUMMARY_LENGTH:
            return "Слишком короткое описание"
        if len(fact.content_summary) > self.MAX_SUMMARY_LENGTH:
            return "Слишком длинное описание"
        # Одиночный \r читается как перевод строки (universal newlines) —
        # нормализация .md молча мутировала бы описание
        if "\r" in fact.content_summary:
            return "Описание не может содержать \\r"
        # Инвариант формата .md: рендер факта (SyncEngine) никогда не содержит
        # строк, начинающихся с # — иначе поиск секции при следующем апдейте
        # обрежется на собственном контенте факта и апдейт превратится в дубль.
        # Код в summary — только инлайн (`#include <vector>`) или с отступом
        # (парсер и граница секции смотрят строго на начало строки)
        if any(line.startswith("#") for line in fact.content_summary.splitlines()):
            return "Описание не может содержать строки, начинающиеся с # (заголовок .md): код — только в инлайн-кавычках"
        # Служебные мета-строки рендера подменяют тип/теги при реингесте .md
        if any(line.startswith(META_LINE_PREFIXES) for line in fact.content_summary.splitlines()):
            return "Описание не может содержать служебные строки (*Тип:*, *Теги:* и т.п.)"

        title_lower = fact.title.lower()
        for pattern in self.NOISE_PATTERNS:
            if pattern in title_lower:
                return "Похоже на фичевую деталь, не абстрактное знание"

        if not fact.tags:
            return "Нет тегов — знание невозможно категоризировать"

        # Теги попадают в мета-строку рендера `*Теги:* a, b` и парсятся
        # обратно по запятой/до '|': перевод строки ломал бы формат .md,
        # '|' и ',' — раунд-трип тегов
        for tag in fact.tags:
            if any(ch in tag for ch in ("\n", "\r", "|", ",")):
                return "Тег не может содержать перевод строки, '|' или запятую"

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