"""Тесты парсера .md файлов: frontmatter, ### секции, краевые случаи."""

import tempfile
from pathlib import Path
from curator.analyzers.ingest import parse_md_file, _parse_yaml_frontmatter


class TestFrontmatterParsing:
    def test_extracts_type_and_tags(self):
        content = "---\ntype: Reference\ntags: [kotlin, jvm, performance]\ndescription: Some desc with: colon and stuff\n---\n\n# Title\nsome text"
        result = _parse_yaml_frontmatter(content)
        assert result["type"] == "Reference"
        assert result["tags"] == ["kotlin", "jvm", "performance"]

    def test_colon_in_description_does_not_break(self):
        content = "---\ntype: Style\ntags: [git, workflow]\ndescription: Правила: как коммитить, что писать\n---\n\n# Title"
        result = _parse_yaml_frontmatter(content)
        assert result["type"] == "Style"
        assert result["tags"] == ["git", "workflow"]

    def test_no_frontmatter(self):
        content = "# Title\n\nSome text"
        result = _parse_yaml_frontmatter(content)
        assert result == {}

    def test_missing_tags(self):
        content = "---\ntype: Reference\ndescription: No tags here\n---\n\n# Title"
        result = _parse_yaml_frontmatter(content)
        assert result["type"] == "Reference"
        assert result["tags"] == []

    def test_missing_type(self):
        content = "---\ntags: [a, b]\n---\n\n# Title"
        result = _parse_yaml_frontmatter(content)
        assert result["type"] is None
        assert result["tags"] == ["a", "b"]

    def test_any_valid_type_name_accepted(self):
        """Контракт реестра типов: словарь расширяем, .md — доверенный
        локальный источник, тип принимается как записан (round-trip
        кастомных типов)."""
        content = "---\ntype: Note\ntags: [a]\n---\n\n# Title"
        result = _parse_yaml_frontmatter(content)
        assert result["type"] == "Note"

    def test_malformed_type_name_rejected(self):
        """Кривое имя типа (небезопасно для имён файлов/regex) → None."""
        for bad in ("1bad", "не латиница", "note/type", ""):
            content = f"---\ntype: {bad}\ntags: [a]\n---\n\n# Title"
            result = _parse_yaml_frontmatter(content)
            assert result["type"] is None, bad

    def test_empty_file(self):
        result = _parse_yaml_frontmatter("")
        assert result == {}


class TestMdParsing:
    def test_parses_sections_with_frontmatter(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", encoding="utf-8", delete=False) as f:
            f.write("---\ntype: Reference\ntags: [kotlin, jvm]\ndescription: Test\n---\n\n# Title\n\n### First Rule\nContent of first rule.\n\n### Second Rule\nContent of second rule.\n")
            f.flush()
            facts = parse_md_file(Path(f.name))
            assert len(facts) == 2
            assert facts[0].type == "Reference"
            assert facts[0].tags == ["kotlin", "jvm"]
            assert facts[0].title == "First Rule"

    def test_skips_short_titles(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", encoding="utf-8", delete=False) as f:
            f.write("---\ntype: Reference\ntags: [test]\ndescription: Test\n---\n\n### AB\nShort\n\n### Long Enough Title Here\nGood content here.\n")
            f.flush()
            facts = parse_md_file(Path(f.name))
            assert len(facts) == 1
            assert "Long Enough" in facts[0].title

    def test_skips_deprecated(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", encoding="utf-8", delete=False) as f:
            f.write("---\ntype: Reference\ntags: [test]\ndescription: Test\n---\n\n### Good Long Rule\nContent is here.\n\n### Old Rule [УСТАРЕЛО]\nOld content.\n")
            f.flush()
            facts = parse_md_file(Path(f.name))
            assert len(facts) == 1
            assert "Good" in facts[0].title

    def test_no_frontmatter_no_tags(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", encoding="utf-8", delete=False) as f:
            f.write("# Title\n\n### Some Section\nContent here without tags.\n")
            f.flush()
            facts = parse_md_file(Path(f.name))
            assert facts[0].tags == []

    def test_file_with_no_sections(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", encoding="utf-8", delete=False) as f:
            f.write("Just text\nNo sections here\n")
            f.flush()
            facts = parse_md_file(Path(f.name))
            assert facts == []