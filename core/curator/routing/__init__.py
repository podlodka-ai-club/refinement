"""Routing module — контракт и default-реализация.

TODO(participant-1): реализовать RoutingRouter с чтением routing.yaml.
  См. curator/routing/interface.py — контракт Router.
  Подключение: ROUTER_CLASS=your.module.YourRouter curator-mcp-server
  Пример routing.yaml:
      routes:
        - path: "reference/kotlin/"
          rules:
            - tags_contains: ["kotlin", "jvm"]
        - path: "style/"
          rules:
            - type: "Style"
      default: "general/"
"""

from curator.routing.interface import Router
from curator.routing.default import DefaultRouter


def get_router() -> Router:
    import os
    import importlib
    cls_path = os.getenv("ROUTER_CLASS", "")
    if cls_path and "." in cls_path:
        try:
            mod_name, cls_name = cls_path.rsplit(".", 1)
            mod = importlib.import_module(mod_name)
            router_cls = getattr(mod, cls_name)
            return router_cls()
        except Exception:
            pass
    return DefaultRouter()