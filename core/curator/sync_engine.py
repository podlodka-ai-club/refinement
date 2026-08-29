from pathlib import Path
from curator.models import StructuredFact
from curator.backend.interface import MemoryBackend


class SyncEngine:
    """Двусторонняя синхронизация: .md ↔ memory backend."""

    def __init__(self, backend: MemoryBackend, base_dir: Path):
        self.backend = backend
        self.base_dir = base_dir

    def write_fact_to_md(self, fact: StructuredFact) -> Path:
        if not fact.source_file:
            raise ValueError("Fact has no source_file")
        md_path = self.base_dir / fact.source_file
        md_path.parent.mkdir(parents=True, exist_ok=True)

        if not md_path.exists():
            md_path.write_text(self._render_fact(fact), encoding="utf-8")
        else:
            self._upsert_fact_in_md(md_path, fact)

        return md_path

    def update_fact_in_md(self, fact: StructuredFact) -> Path:
        if not fact.source_file:
            raise ValueError("Fact has no source_file")
        md_path = self.base_dir / fact.source_file
        self._upsert_fact_in_md(md_path, fact)
        return md_path

    def remove_fact_from_md(self, fact: StructuredFact) -> Path | None:
        if not fact.source_file:
            return None
        md_path = self.base_dir / fact.source_file
        if not md_path.exists():
            return None

        content = md_path.read_text(encoding="utf-8")
        marker = f"### {fact.title}"
        if marker not in content:
            return None

        lines = content.split("\n")
        new_lines = []
        skip = False

        for line in lines:
            if line.strip() == marker.strip():
                new_lines.append(f"### {fact.title} [УСТАРЕЛО]")
                new_lines.append("")
                new_lines.append(f"*Это знание помечено как устаревшее.*")
                skip = True
                continue
            if skip and line.startswith("### "):
                skip = False
            if not skip:
                new_lines.append(line)

        md_path.write_text("\n".join(new_lines), encoding="utf-8")
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
        marker = f"### {fact.title}"

        if marker in content:
            lines = content.split("\n")
            new_lines = []
            skip = False

            for line in lines:
                if line.strip() == marker.strip():
                    skip = True
                    new_lines.append(self._render_fact(fact))
                    continue
                if skip and line.startswith("### "):
                    skip = False
                if not skip:
                    new_lines.append(line)

            md_path.write_text("\n".join(new_lines), encoding="utf-8")
        else:
            md_path.write_text(content + f"\n\n---\n\n{self._render_fact(fact)}", encoding="utf-8")