import re
from pathlib import Path
from curator.models import (
    ProposedFact, StructuredFact, FactQuery,
    META_LINE_PREFIXES, META_TYPE_PREFIX, META_TAGS_PREFIX,
)
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

    # Тип: любое валидное имя (словарь расширяем через реестр/регистрацию),
    # обязательная форма ^[A-Za-z][A-Za-z0-9_-]*$ — безопасно для имён файлов
    m = re.search(r'^type:\s*([A-Za-z][A-Za-z0-9_-]*)\s*$', fm_text, re.MULTILINE)
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
        # .md — доверенный локальный источник (его пишет ядро или человек):
        # тип принимается как записан, без сверки с реестром машины
        if not re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", file_type):
            file_type = "Reference"
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

        lines = section.split("\n")
        title_line = lines[0]
        # Маркер устаревшего знания пишется только в заголовок секции
        # (`### {title} [УСТАРЕЛО]`) — контент факта с этой подстрокой
        # в тегах/описании легитимен и не должен дропать секцию
        if title_line.endswith("[УСТАРЕЛО]"):
            continue

        # removeprefix (не replace): title может содержать '### ' внутри
        title = title_line.removeprefix("### ").strip()

        body_lines = []
        for line in lines[1:]:
            if line.startswith(META_LINE_PREFIXES):
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
    # Сортировка = детерминированный порядок rebuild'а базы из .md
    for md_file in sorted(dir_path.rglob("*.md")):
        try:
            facts = parse_md_file(md_file)
        except (OSError, UnicodeDecodeError) as e:
            # Один битый файл (не-UTF8, права) не должен валить
            # индексацию всей директории
            print(f"  ⚠ пропущен {md_file.name}: {e}")
            continue
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
    """Теги из метаданных секции — только строка-начала `*Тип:*` (рендер) или
    собственная строка `*Теги:*` (рукописный формат). Mid-line вхождения в
    теле секции игнорируются — это контент, не метаданные."""
    for line in section.splitlines():
        if line.startswith(META_TYPE_PREFIX):
            m = re.search(r"\*Теги:\*\s*([^|]+)", line)
            if m:
                return [t.strip() for t in m.group(1).split(",") if t.strip()]
        elif line.startswith(META_TAGS_PREFIX):
            m = re.match(r"\*Теги:\*\s*(.+)", line)
            if m:
                return [t.strip() for t in m.group(1).split(",") if t.strip()]
    return []


def _extract_type(section: str) -> str | None:
    """Тип факта из строки-меты. Рендер пишет `*Тип:* Tool | *Статус:* ...` —
    берём только точное значение до разделителя, не всю строку. Имя — любой
    валидный идентификатор (словарь типов расширяем)."""
    for line in section.splitlines():
        if line.startswith(META_TYPE_PREFIX):
            m = re.match(r"\*Тип:\*\s*([A-Za-z][A-Za-z0-9_-]*)", line)
            if m:
                return m.group(1)
            return None
    return None