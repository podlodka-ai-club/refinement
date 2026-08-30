"""Тесты routing: Router Protocol, DefaultRouter, get_router."""

from curator.routing.interface import Router
from curator.routing.default import DefaultRouter
from curator.routing import get_router
from curator.models import ProposedFact


def _fact(type="Reference", title="Test", tags=None):
    return ProposedFact(type=type, title=title, content_summary="x" * 20, tags=tags or ["test"])


class TestDefaultRouter:
    def test_route_reference(self):
        r = DefaultRouter()
        path = r.route_fact(_fact("Reference"))
        assert path == "session/reference.md"

    def test_route_style(self):
        r = DefaultRouter()
        path = r.route_fact(_fact("Style"))
        assert path == "session/style.md"

    def test_list_routes(self):
        r = DefaultRouter()
        routes = r.list_routes()
        assert len(routes) == 1
        assert routes[0]["path"] == "session/"

    def test_reload_noop(self):
        r = DefaultRouter()
        r.reload()


class TestRouterProtocol:
    def test_default_is_protocol(self):
        r = DefaultRouter()
        assert isinstance(r, Router)

    def test_has_required_methods(self):
        r = DefaultRouter()
        assert hasattr(r, "route_fact")
        assert callable(r.route_fact)
        assert hasattr(r, "list_routes")
        assert callable(r.list_routes)


class TestGetRouter:
    def test_returns_default_when_no_env(self):
        import os
        old = os.environ.pop("ROUTER_CLASS", None)
        try:
            r = get_router()
            assert isinstance(r, DefaultRouter)
        finally:
            if old:
                os.environ["ROUTER_CLASS"] = old

    def test_returns_default_when_invalid_class(self):
        import os
        os.environ["ROUTER_CLASS"] = "nonexistent.module.NoSuchClass"
        r = get_router()
        assert isinstance(r, DefaultRouter)
        del os.environ["ROUTER_CLASS"]