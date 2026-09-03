"""Routing module — контракт и default-реализация.

Кастомный роутер подключается через ROUTER_CLASS (см. interface.py —
контракт Router). Встроенный MapRouter читает карту документации
(см. map_router.py); без карты молча ведёт себя как DefaultRouter.
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