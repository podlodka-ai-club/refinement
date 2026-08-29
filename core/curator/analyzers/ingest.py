import re
from pathlib import Path
from curator.models import ProposedFact, StructuredFact, FactQuery
from curator.backend.interface import MemoryBackend
from curator.gatekeeper import Gatekeeper


def _parse_yaml_frontmatter(content: str) -> dict:
    """Извлечь type и tags из YAML frontmatter .md файла (ручной парсер, yaml-safe-load ломается на двоеточиях в description)."""
    if not content.startswith("---\n"):
        return {}
    end = content.find("\n---\n", 4)
    if end == -1:
        end = content.find("\n---", 4)
    if end == -1:
        return {}
    fm_text = content[4:end]

    result = {"type": None, "tags": []}

    # Extract type: Reference|Style|Tool|Spec
    m = re.search(r'^type:\s*(Reference|Style|Tool|Spec)\s*$', fm_text, re.MULTILINE)
    if m:
        result["type"] = m.group(1)

    # Extract tags: [tag1, tag2, ...]
    m = re.search(r'^tags:\s*\[(.+?)\]\s*$', fm_text, re.MULTILINE)
    if m:
        result["tags"] = [t.strip().strip('"').strip("'") for t in m.group(1).split(",")]

    return result


def parse_md_file(filepath: Path) -> list[ProposedFact]:
    """Извлечь факты из .md файла.

    Поддерживает два формата:
    1. YAML frontmatter с type/tags на уровне файла + ### секции как факты
    2. ### секции с инлайн-метаданными (*Тип:*, *Теги:*)
    """
    content = filepath.read_text(encoding="utf-8")

    frontmatter = _parse_yaml_frontmatter(content)
    file_type = frontmatter.get("type", "Reference")
    if isinstance(file_type, str):
        file_type = file_type if file_type in ("Reference", "Style", "Tool", "Spec") else "Reference"
    file_tags = frontmatter.get("tags", [])
    if isinstance(file_tags, str):
        file_tags = [t.strip() for t in file_tags.split(",")]

    body = content
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            body = content[end + 5:]
        else:
            end = content.find("\n---", 4)
            if end != -1:
                body = content[end + 4:]

    facts = []

    sections = re.split(r'\n(?=### )', body)
    for section in sections:
        section = section.strip()
        if not section.startswith("### "):
            continue
        if "[УСТАРЕЛО]" in section:
            continue

        lines = section.split("\n")
        title = lines[0].replace("### ", "").strip()

        body_lines = []
        for line in lines[1:]:
            if line.startswith("*Тип:") or line.startswith("*Статус:") or line.startswith("*Теги:") or line.startswith("*Файл:"):
                break
            if line.startswith("#"):
                break
            line = line.strip()
            if line:
                body_lines.append(line)

        summary = " ".join(body_lines)

        tags = _extract_tags(section)
        if not tags:
            tags = list(file_tags)

        fact_type = _extract_type(section) or file_type

        source = str(_relative_to(filepath))

        if len(title) >= 10:
            facts.append(ProposedFact(
                type=fact_type,
                title=title,
                content_summary=summary or title,
                tags=tags,
            ))

    return facts


def ingest_directory(dir_path: Path, backend: MemoryBackend, gatekeeper: Gatekeeper) -> int:
    """Проиндексировать все .md файлы в директории. Возвращает количество сохранённых фактов."""
    existing_titles = {f.title for f in backend.query_facts(FactQuery())}

    saved = 0
    for md_file in dir_path.rglob("*.md"):
        facts = parse_md_file(md_file)
        if not facts:
            continue
        result = gatekeeper.filter(facts)

        for fact in result.approved:
            if fact.title in existing_titles:
                continue

            structured = StructuredFact(
                type=fact.type,
                title=fact.title,
                tags=fact.tags,
                status="verified",
                content_summary=fact.content_summary,
                source_file=str(md_file.relative_to(dir_path)),
            )
            backend.store_fact(structured)
            existing_titles.add(fact.title)
            saved += 1

    return saved


def _extract_tags(section: str) -> list[str]:
    match = re.search(r'\*Теги:\*\s*(.+)', section)
    return [t.strip() for t in match.group(1).split(",")] if match else []


def _extract_type(section: str) -> str | None:
    match = re.search(r'\*Тип:\*\s*(.+)', section)
    if match:
        raw = match.group(1).strip()
        if raw in ("Reference", "Style", "Tool", "Spec"):
            return raw
    return None


def _relative_to(filepath: Path) -> Path:
    parts = filepath.parts
    if len(parts) >= 2:
        return Path(*parts[-2:])
    return filepath