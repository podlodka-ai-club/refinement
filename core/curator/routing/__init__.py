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
    import sys
    import importlib
    cls_path = os.getenv("ROUTER_CLASS", "")
    if cls_path and "." in cls_path:
        try:
            mod_name, cls_name = cls_path.rsplit(".", 1)
            mod = importlib.import_module(mod_name)
            router_cls = getattr(mod, cls_name)
            return router_cls()
        except Exception as e:
            # Откат на DefaultRouter допустим, но деградация обязана быть видимой:
            # иначе опечатка в ROUTER_CLASS молча перенаправляет все факты в session/
            print(f"[curator] ROUTER_CLASS '{cls_path}' не загрузился: {e} — использую DefaultRouter",
                  file=sys.stderr)
    return DefaultRouter()


def route_fact_safe(router: Router, fact) -> str:
    """route_fact с изоляцией сбоя стороннего роутера: исключение роутера
    отправляет факт на дефолтный маршрут вместо обрушения батча сохранения."""
    try:
        return router.route_fact(fact)
    except Exception as e:
        import sys
        print(f"[curator] router упал на '{getattr(fact, 'title', '?')}': {e} — маршрут DefaultRouter",
              file=sys.stderr)
        return DefaultRouter().route_fact(fact)