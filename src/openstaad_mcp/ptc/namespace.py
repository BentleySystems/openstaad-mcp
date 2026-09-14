"""Opaque, immutable capabilities exposed to sandbox code.

Unlike ordinary Python adapter objects, these objects never expose their
implementation attributes (including through single-underscore names).
"""

from collections.abc import Callable, Mapping
from typing import Any


class ToolNamespace:
    __slots__ = ("_members",)

    def __init__(self, members: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_members", dict(members))

    def __getattribute__(self, name: str) -> Any:
        members = object.__getattribute__(self, "_members")
        if not name.startswith("_") and name in members:
            return members[name]
        raise AttributeError(f"PTC tool or namespace '{name}' is not registered")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("PTC namespaces are read-only")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("PTC namespaces are read-only")

    def __repr__(self) -> str:
        return "<PTC namespace>"


class ToolCallable:
    __slots__ = ("_invoke",)

    def __init__(self, invoke: Callable[..., Any]) -> None:
        object.__setattr__(self, "_invoke", invoke)

    def __getattribute__(self, name: str) -> Any:
        raise AttributeError("PTC callable internals are not accessible")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return object.__getattribute__(self, "_invoke")(*args, **kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("PTC callables are read-only")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("PTC callables are read-only")

    def __repr__(self) -> str:
        return "<PTC tool>"
