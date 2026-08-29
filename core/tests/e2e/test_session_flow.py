"""E2E: сессия → gatekeeper → store → query."""

from curator.backend.local import LocalBackend
from curator.gatekeeper import Gatekeeper
from curator.models import ProposedFact, StructuredFact, FactQuery


class TestSessionFlow:
    def test_full_flow(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        gk = Gatekeeper(be, check_duplicates=True)

        proposed = [
            ProposedFact(type="Reference", title="Правило про strong skipping в Compose",
                         content_summary="Strong skipping работает только со stable типами. Нестабильные вызывают рекомпозицию.",
                         tags=["compose", "performance"]),
            ProposedFact(type="Reference", title="Кноп", content_summary="Слишком короткий заголовок", tags=["ui"]),
            ProposedFact(type="Reference", title="Поменять цвет кнопки", content_summary="Нужно поменять цвет в форме логина на синий", tags=["ui"]),
            ProposedFact(type="Style", title="Conventional Commits с модулем и Jira ключом",
                         content_summary="type[module]: AAA-000 описание на русском. Без AI attribution.",
                         tags=["git", "workflow"]),
        ]

        result = gk.filter(proposed)
        assert len(result.approved) == 2
        assert len(result.rejected) == 2

        rejected_titles = [f.title for f, _ in result.rejected]
        assert "Кноп" in rejected_titles
        assert "Поменять цвет кнопки" in rejected_titles

        for fact in result.approved:
            structured = StructuredFact(
                type=fact.type, title=fact.title, tags=fact.tags,
                status="verified", content_summary=fact.content_summary,
                source_file="session/test.md",
            )
            be.store_fact(structured)

        all_stored = be.query_facts(FactQuery())
        assert len(all_stored) == 2

        compose_facts = be.query_facts(FactQuery(search="strong skipping"))
        assert len(compose_facts) == 1

        style_facts = be.query_facts(FactQuery(type="Style"))
        assert len(style_facts) == 1
        assert "Conventional Commits" in style_facts[0].title

    def test_dedup_on_second_run(self, tmpdir):
        be = LocalBackend(str(tmpdir / "test.db"))
        be.store_fact(StructuredFact(
            type="Reference", title="Правило про JVM inline классы",
            tags=["jvm"], status="verified", content_summary="JvmInline внутри sealed interface вызывает бокс.",
        ))
        gk = Gatekeeper(be, check_duplicates=True)

        fact = ProposedFact(
            type="Reference",
            title="Правило про JVM inline классы sealed interface",
            content_summary="Это почти то же самое правило про JVM и sealed interface но с дополнением",
            tags=["jvm"],
        )
        result = gk.filter([fact])
        assert len(result.rejected) == 1