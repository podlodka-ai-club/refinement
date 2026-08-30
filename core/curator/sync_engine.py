from pathlib import Path
from curator.models import StructuredFact, META_TYPE_PREFIX
from curator.backend.interface import MemoryBackend


class SyncEngine:
    """Двусторонняя синхронизация: .md ↔ memory backend."""

    def __init__(self, backend: MemoryBackend, base_dir: Path):
        self.backend = backend
        self.base_dir = base_dir

    def write_fact_to_md(self, fact: StructuredFact) -> Path:
        if not fact.source_file:
            raise ValueError("Fact has no source_file")
        md_path = self._resolve_md_path(fact.source_file)
        md_path.parent.mkdir(parents=True, exist_ok=True)

        if not md_path.exists():
            md_path.write_text(self._render_fact(fact), encoding="utf-8")
        else:
            self._upsert_fact_in_md(md_path, fact)

        return md_path

    def update_fact_in_md(self, fact: StructuredFact) -> Path:
        if not fact.source_file:
            raise ValueError("Fact has no source_file")
        md_path = self._resolve_md_path(fact.source_file)
        self._upsert_fact_in_md(md_path, fact)
        return md_path

    def remove_fact_from_md(self, fact: StructuredFact) -> Path | None:
        if not fact.source_file:
            return None
        md_path = self._resolve_md_path(fact.source_file)
        if not md_path.exists():
            return None

        content = md_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        idx = self._find_fact_section(lines, fact.title)
        if idx is None:
            return None

        lines[idx:self._content_end(lines, idx)] = [
            f"### {fact.title} [УСТАРЕЛО]",
            "",
            "*Это знание помечено как устаревшее.*",
        ]
        self._write_lines(md_path, lines)
        return md_path

    def _render_fact(self, fact: StructuredFact) -> str:
        status_labels = {"verified": "Подтверждено", "hypothesis": "Гипотеза", "deprecated": "Устарело"}
        tags = ", ".join(fact.tags)
        return (
            f"### {fact.title}\n\n"
            f"{fact.content_summary}\n\n"
            f"*Тип:* {fact.type} | *Статус:* {status_labels.get(fact.status, fact.status)} | *Теги:* {tags}\n"
            f"*Файл:* {fact.source_file}\n"
        )

    def _upsert_fact_in_md(self, md_path: Path, fact: StructuredFact) -> None:
        content = md_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        idx = self._find_fact_section(lines, fact.title)

        if idx is not None:
            rendered = self._render_fact(fact).rstrip("\n").split("\n")
            lines[idx:self._content_end(lines, idx)] = rendered
            self._write_lines(md_path, lines)
        else:
            md_path.write_text(content + f"\n\n---\n\n{self._render_fact(fact)}", encoding="utf-8")

    def _write_lines(self, md_path: Path, lines: list[str]) -> None:
        """Единая точка записи .md: гарантирует финальный перевод строки
        (POSIX), чтобы инвариант не зависел от формы слайса."""
        text = "\n".join(lines)
        if text and not text.endswith("\n"):
            text += "\n"
        md_path.write_text(text, encoding="utf-8")

    def _resolve_md_path(self, source_file: str) -> Path:
        """Путь .md строго внутри base_dir — source_file не может выйти за
        sandbox и не может содержать перевод строки (сломал бы формат .md)."""
        if "\n" in source_file or "\r" in source_file:
            raise ValueError(f"source_file содержит перевод строки: {source_file!r}")
        md_path = (self.base_dir / source_file).resolve()
        if not md_path.is_relative_to(self.base_dir.resolve()):
            raise ValueError(f"source_file вне base_dir: {source_file}")
        return md_path

    def _find_fact_section(self, lines: list[str], title: str) -> int | None:
        """Индекс строки-заголовка нашей секции факта или None.

        Совпадение строго по целой строке `### {title}` (не подстрокой) и только
        для секций в нашем формате рендера (`*Тип:*`): чужая одноимённая секция
        пользователя не считается нашей и не затирается.
        """
        marker = f"### {title}".strip()
        for i, line in enumerate(lines):
            if line.strip() != marker:
                continue
            for j in range(i + 1, self._section_end(lines, i)):
                if lines[j].startswith(META_TYPE_PREFIX):
                    return i
        return None

    def _section_end(self, lines: list[str], idx: int) -> int:
        """Конец секции: первая строка-заголовок ЛЮБОГО уровня (`#`, `##`,
        `###`...) после idx — или конец файла. Заголовок чужой ## главы не
        принадлежит нашей секции и не может быть съеден."""
        for j in range(idx + 1, len(lines)):
            if lines[j].startswith("#"):
                return j
        return len(lines)

    def _content_end(self, lines: list[str], idx: int) -> int:
        """Конец ЗАМЕНЯЕМОГО диапазона: как _section_end, но не захватывает
        хвостовые пустые строки и `---`-разделители перед следующей секцией —
        они сохраняются на месте."""
        end = self._section_end(lines, idx)
        while end > idx + 1 and lines[end - 1].strip() in ("", "---"):
            end -= 1
        return end