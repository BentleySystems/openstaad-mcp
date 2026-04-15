from types import ModuleType
from typing import Any


class ModuleProxy:
    """Read-only proxy exposing only whitelisted attributes of a module.

    Prevents sandbox code from traversing the internal module graph
    (e.g. ``json.codecs.builtins``) to reach unrestricted Python internals.
    """

    __slots__ = ("_proxy_allowed", "_proxy_module", "_proxy_name")

    def __init__(self, module: ModuleType, allowed: frozenset[str]) -> None:
        object.__setattr__(self, "_proxy_module", module)
        object.__setattr__(self, "_proxy_allowed", allowed)
        object.__setattr__(self, "_proxy_name", module.__name__)

    def __getattribute__(self, name: str) -> Any:
        if name in {"_proxy_allowed", "_proxy_module", "_proxy_name"}:
            pname = object.__getattribute__(self, "_proxy_name")
            raise AttributeError(f"attribute '{name}' is not available on '{pname}' in the sandbox")

        if name in {"__class__", "__repr__", "__setattr__", "__delattr__"}:
            return object.__getattribute__(self, name)

        allowed = object.__getattribute__(self, "_proxy_allowed")
        if name in allowed:
            mod = object.__getattribute__(self, "_proxy_module")
            return getattr(mod, name)
        pname = object.__getattribute__(self, "_proxy_name")
        raise AttributeError(f"attribute '{name}' is not available on '{pname}' in the sandbox")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("cannot set attributes on sandbox modules")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("cannot delete attributes on sandbox modules")

    def __repr__(self) -> str:
        pname = object.__getattribute__(self, "_proxy_name")
        return f"<sandbox module '{pname}'>"
