"""Helper: regenerate tests/test_integration.py atomically.

Kept in scripts/ so we avoid shell-quoting landmines when the test file
contains JS backticks, template literals, or triple-quoted Python strings.
"""

from __future__ import annotations

from pathlib import Path

CONTENT = '''"""Integration tests - require running STAAD.Pro instance."""
from __future__ import annotations

import time

import pytest

from openstaad_mcp.connection import InstanceRegistry, connect_and_run
from openstaad_mcp.sandbox import WasmExecutor

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def staad_instance():
    registry = InstanceRegistry()
    instances = registry.get_active_instances()
    if not instances:
        pytest.skip("No STAAD.Pro instances found")
    return instances[0]


@pytest.fixture
def executor() -> WasmExecutor:
    return WasmExecutor()


class TestReadOnly:
    def test_get_node_count(self, staad_instance):
        count = connect_and_run(lambda s: s.Geometry.GetNodeCount(), staad_instance.file_path)
        assert isinstance(count, int) and count >= 0

    def test_get_beam_count(self, staad_instance):
        count = connect_and_run(lambda s: s.Geometry.GetMemberCount(), staad_instance.file_path)
        assert isinstance(count, int) and count >= 0

    def test_execute_javascript_via_executor(self, staad_instance, executor):
        def _run(staad):
            return executor.execute("staad.Geometry.GetNodeCount()", staad).to_dict()

        result = connect_and_run(_run, staad_instance.file_path)
        assert result["success"], result.get("error")
        assert isinstance(result["result"], int)
        assert result["result"] >= 0

    def test_base_unit_and_zup(self, staad_instance, executor):
        def _run(staad):
            code = (
                "const baseUnit = staad.GetBaseUnit();"
                " const zUp = staad.Geometry.IsZUp();"
                " return [baseUnit, zUp];"
            )
            return executor.execute(code, staad).to_dict()

        result = connect_and_run(_run, staad_instance.file_path)
        assert result["success"], result.get("error")
        assert isinstance(result["result"], list) and len(result["result"]) == 2
        assert isinstance(result["result"][1], bool)

    def test_console_log_captured(self, staad_instance, executor):
        def _run(staad):
            code = (
                "const n = staad.Geometry.GetNodeCount();"
                " console.log('nodes=' + n);"
                " return n;"
            )
            return executor.execute(code, staad).to_dict()

        result = connect_and_run(_run, staad_instance.file_path)
        assert result["success"], result.get("error")
        assert "nodes=" in result["stdout"]
        assert isinstance(result["result"], int)


class TestWriteAndMath:
    """Exercise the full write path: AddNode / AddBeam / read-back / math.

    This proves the sandbox can mutate the live STAAD model via host
    functions and that COM return values round-trip through JSON into JS
    numerics without loss of precision.
    """

    def test_add_nodes_and_beam_roundtrip(self, staad_instance, executor):
        """Add two nodes + a beam, read them back, assert geometry matches."""

        def _run(staad):
            code = (
                "const geo = staad.Geometry;"
                " const nBefore = geo.GetNodeCount();"
                " const mBefore = geo.GetMemberCount();"
                " const n1 = geo.AddNode(1000.0, 0.0, 0.0);"
                " const n2 = geo.AddNode(1000.0, 300.0, 400.0);"
                " const b = geo.AddBeam(n1, n2);"
                " const p1 = geo.GetNodeCoordinates(n1);"
                " const p2 = geo.GetNodeCoordinates(n2);"
                " const inc = geo.GetMemberIncidence(b);"
                " return {"
                "   nBefore, mBefore,"
                "   nAfter: geo.GetNodeCount(),"
                "   mAfter: geo.GetMemberCount(),"
                "   n1, n2, b, p1, p2, inc"
                " };"
            )
            return executor.execute(code, staad).to_dict()

        result = connect_and_run(_run, staad_instance.file_path)
        assert result["success"], result.get("error")
        r = result["result"]

        # STAAD deduplicates nodes at identical coordinates, so re-running
        # this test may return existing node IDs rather than creating new
        # ones. The real invariant is that the coords + incidence match
        # what we wrote, and that counts did not *decrease*.
        assert r["nAfter"] >= r["nBefore"]
        assert r["mAfter"] >= r["mBefore"]
        assert r["n1"] > 0 and r["n2"] > 0 and r["b"] > 0

        # Coordinates came back exactly as written (IEEE 754 doubles round-trip).
        assert r["p1"] == [1000.0, 0.0, 0.0]
        assert r["p2"] == [1000.0, 300.0, 400.0]

        # Incidence points at the nodes we just created / found.
        assert r["inc"] == [r["n1"], r["n2"]]

    def test_js_math_on_com_values(self, staad_instance, executor):
        """Pure-JS math on COM return values must match a Python-side baseline.

        We're not testing STAAD's math here - we're testing that JSON
        serialisation across the WASM boundary preserves IEEE 754 doubles.
        The test picks two points with an exact-representable 3-4-5
        Pythagorean-like distance so floating-point noise is ruled out:
        sqrt(300^2 + 400^2) = 500.0 exactly.
        """

        def _run(staad):
            code = (
                "const geo = staad.Geometry;"
                " const n1 = geo.AddNode(2000.0, 0.0, 0.0);"
                " const n2 = geo.AddNode(2000.0, 300.0, 400.0);"
                " const p1 = geo.GetNodeCoordinates(n1);"
                " const p2 = geo.GetNodeCoordinates(n2);"
                " const dx = p2[0] - p1[0];"
                " const dy = p2[1] - p1[1];"
                " const dz = p2[2] - p1[2];"
                " const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);"
                " return { p1, p2, dist };"
            )
            return executor.execute(code, staad).to_dict()

        result = connect_and_run(_run, staad_instance.file_path)
        assert result["success"], result.get("error")
        r = result["result"]
        assert r["dist"] == 500.0, f"expected 500.0, got {r['dist']!r}"


class TestPerformance:
    """Minimal perf sanity checks. Single-user workloads only.

    These exist to catch catastrophic regressions (e.g. 10x slower than
    baseline). They do not enforce tight latency budgets - hardware varies
    too much. Bounds are generous on purpose.
    """

    def test_host_call_latency(self, staad_instance, executor):
        """100 sequential GetNodeCount() calls should complete quickly."""

        def _run(staad):
            code = (
                "const geo = staad.Geometry;"
                " const iters = 100;"
                " let sum = 0;"
                " for (let i = 0; i < iters; i++) { sum += geo.GetNodeCount(); }"
                " return sum;"
            )
            t0 = time.perf_counter()
            out = executor.execute(code, staad).to_dict()
            elapsed = time.perf_counter() - t0
            out["_elapsed"] = elapsed
            return out

        result = connect_and_run(_run, staad_instance.file_path)
        assert result["success"], result.get("error")
        elapsed = result["_elapsed"]
        # Budget: 100 host calls + plugin spin-up should fit in 2s on any
        # reasonable dev box. Phase 0 saw ~180 us / call, so ~18 ms of
        # actual host-call time; the rest is plugin instantiation.
        assert elapsed < 2.0, f"100 GetNodeCount() calls took {elapsed:.3f}s (budget 2.0s)"
        print(f"\\n[perf] 100 host calls + plugin spin-up: {elapsed*1000:.1f} ms")

    def test_sequential_execute_code_calls(self, staad_instance, executor):
        """10 back-to-back execute_code calls should complete quickly.

        Each execute_code call instantiates a fresh extism.Plugin. This
        stresses plugin-creation cost, which is the dominant overhead
        for small scripts.
        """

        def _run(staad):
            t0 = time.perf_counter()
            for _ in range(10):
                out = executor.execute("staad.Geometry.GetNodeCount()", staad).to_dict()
                if not out["success"]:
                    return {"success": False, "error": out.get("error")}
            return {"success": True, "elapsed": time.perf_counter() - t0}

        result = connect_and_run(_run, staad_instance.file_path)
        assert result["success"], result.get("error")
        elapsed = result["elapsed"]
        # Budget: 10 plugin instantiations + trivial scripts within 5s.
        assert elapsed < 5.0, f"10 execute_code calls took {elapsed:.3f}s (budget 5.0s)"
        print(f"\\n[perf] 10 execute_code calls: {elapsed*1000:.1f} ms "
              f"(~{elapsed*100:.1f} ms per call)")

    def test_large_stdout_within_cap(self, staad_instance, executor):
        """Write a meaningful chunk of stdout. Must not exceed 256 KiB cap."""

        def _run(staad):
            code = (
                "for (let i = 0; i < 1000; i++) {"
                "   console.log('line ' + i + ' pad pad pad pad pad pad pad pad');"
                " }"
                " return 1000;"
            )
            return executor.execute(code, staad).to_dict()

        result = connect_and_run(_run, staad_instance.file_path)
        assert result["success"], result.get("error")
        assert result["result"] == 1000
        assert len(result["stdout"]) <= 256 * 1024
        assert "line 0 " in result["stdout"]
'''


def main() -> None:
    target = Path(__file__).resolve().parent.parent / "tests" / "test_integration.py"
    target.write_text(CONTENT, encoding="utf-8")
    print(f"wrote {len(CONTENT)} bytes -> {target}")


if __name__ == "__main__":
    main()
