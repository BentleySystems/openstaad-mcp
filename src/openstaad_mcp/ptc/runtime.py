"""One execution, one capability namespace, no persistent model data."""

import json
from typing import Any

from openstaad_mcp.ptc.adapter import build_registry
from openstaad_mcp.ptc.registry import CallBudget
from openstaad_mcp.sandbox.executor import Executor

MAX_INLINE_BYTES = 65_536


class PTCRuntime:
    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    def execute(self, code: str, staad: Any, *, input_data: Any = None, export: bool = False) -> dict[str, Any]:
        budget = CallBudget()
        tools = build_registry(staad).bind(budget)
        response = self._executor.execute(code, None, input_data=input_data, ptc_tools=tools).to_dict()
        response["ptc"] = {"tool_calls": budget.calls, "calls_by_tool": dict(budget.counts)}
        if response["success"] and not export:
            size = len(json.dumps(response["result"], ensure_ascii=False).encode("utf-8"))
            if size > MAX_INLINE_BYTES:
                response.update(
                    success=False,
                    result=None,
                    error="PTC result exceeds 65536 bytes; aggregate the final result or use output_data_path",
                )
        return response
