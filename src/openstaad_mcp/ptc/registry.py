"""Explicit tool registration, discovery and per-execution dispatch."""

import inspect
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints

from pydantic import ConfigDict, ValidationError, create_model

from openstaad_mcp.ptc.namespace import ToolCallable, ToolNamespace

MAX_TOOL_CALLS = 1000


@dataclass
class CallBudget:
    limit: int = MAX_TOOL_CALLS
    calls: int = 0
    counts: dict[str, int] = field(default_factory=dict)

    def consume(self, name: str) -> None:
        if self.calls >= self.limit:
            raise ValueError("PTC tool call limit reached; split the request into smaller batches")
        self.calls += 1
        self.counts[name] = self.counts.get(name, 0) + 1


class ToolRegistry:
    """Host-only registry. Only an opaque namespace crosses into the sandbox."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple] = {}

    def register(self, name: str, function: Callable[..., Any]) -> None:
        if not re.fullmatch(r"[a-z][a-z_]*\.[a-z][a-z_]*", name) or name in self._tools:
            raise ValueError(f"Invalid or duplicate PTC tool name: {name}")
        signature = inspect.signature(function)
        hints = get_type_hints(function, include_extras=True)
        fields = {
            key: (hints[key], ... if parameter.default is inspect.Parameter.empty else parameter.default)
            for key, parameter in signature.parameters.items()
        }
        model = create_model(name, __config__=ConfigDict(strict=True, extra="forbid"), **fields)
        self._tools[name] = (function, signature, model)

    def discover(self, namespace: str | None = None) -> list[dict[str, Any]]:
        names = {name.split(".")[0] for name in self._tools}
        if namespace is not None and namespace not in names:
            raise ValueError(f"Unknown PTC namespace; choose from {sorted(names)}")
        return [
            {
                "name": f"tools.{name}",
                "description": inspect.getdoc(function) or "",
                "input_schema": model.model_json_schema(),
                "read_only": True,
            }
            for name, (function, _, model) in self._tools.items()
            if namespace is None or name.split(".")[0] == namespace
        ]

    def bind(self, budget: CallBudget) -> ToolNamespace:
        groups: dict[str, dict[str, ToolCallable]] = {}
        for name in self._tools:
            group, method = name.split(".")
            groups.setdefault(group, {})[method] = ToolCallable(self._dispatcher(name, budget))
        return ToolNamespace({name: ToolNamespace(methods) for name, methods in groups.items()})

    def _dispatcher(self, name: str, budget: CallBudget) -> Callable[..., Any]:
        function, signature, model = self._tools[name]

        def invoke(*args: Any, **kwargs: Any) -> Any:
            budget.consume(name)
            try:
                bound = signature.bind(*args, **kwargs)
                validated = model.model_validate(bound.arguments)
            except (TypeError, ValidationError):
                raise ValueError(f"Invalid arguments for tools.{name}; see discover_ptc input_schema") from None
            # JSON round-trip ensures only fresh native data leaves an adapter,
            # never a COM wrapper, a bound method or a mutable shared object.
            return json.loads(json.dumps(function(**validated.model_dump()), allow_nan=False))

        return invoke
