"""Shared host-side COM calls, validation and query budgets."""

from typing import Annotated, Any

from pydantic import Field, TypeAdapter

from openstaad_mcp.sandbox.com_proxy import COMProxy

MAX_ROWS = 100_000
Id = Annotated[int, Field(strict=True, gt=0)]
Ids = Annotated[list[Id], Field(max_length=10_000)]
Tolerance = Annotated[float, Field(ge=0, allow_inf_nan=False)]
_IDS = TypeAdapter(Ids)
Name = Annotated[str, Field(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f]+$")]
Names = Annotated[list[Name], Field(max_length=10_000)]
End = Annotated[int, Field(strict=True, ge=0, le=1)]
Ends = Annotated[list[End], Field(min_length=1, max_length=2)]
Distances = Annotated[list[Tolerance], Field(max_length=1000)]
_FINITE = TypeAdapter(Annotated[float, Field(strict=True, allow_inf_nan=False)])


def values_record(names: tuple[str, ...], values: Any) -> dict[str, float]:
    """Map a fixed numeric API tuple without truncation or non-finite values."""
    return dict(zip(names, (_FINITE.validate_python(value) for value in values), strict=True))


def id_list(values: Any) -> list[int]:
    """Validate upstream IDs without interpreting API sentinel values as IDs."""
    return _IDS.validate_python(list(values), strict=True)


class QueryBase:
    def __init__(self, staad: Any) -> None:
        self._staad = COMProxy(staad)

    def _call(self, group: str | None, method: str, *args: Any) -> Any:
        try:
            target = self._staad if group is None else getattr(self._staad, group)
            return getattr(target, method)(*args)
        except Exception:
            # COM exceptions can include model paths or implementation details.
            raise ValueError(f"OpenSTAAD {group}.{method} failed; check model, IDs and API version") from None

    def _ids(self, requested: Ids | None, group: str, method: str) -> list[int]:
        values = requested if requested is not None else list(self._call(group, method))
        return list(dict.fromkeys(_IDS.validate_python(values, strict=True)))

    def _members(self, requested: Ids | None) -> list[int]:
        return self._ids(requested, "Geometry", "GetBeamList")

    def _require_results(self) -> None:
        if not self._call("Output", "AreResultsAvailable"):
            raise ValueError("Analysis results are unavailable; run analysis before querying results")


def _check_rows(count: int) -> None:
    if count > MAX_ROWS:
        raise ValueError("PTC result row limit exceeded; split IDs or load cases into smaller batches")
