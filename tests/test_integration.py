"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Integration tests — require a running STAAD.Pro instance on Windows.

These tests verify the full pipeline: MCP server → executor → COM bridge
→ STAAD.Pro.  They should only be run on a Windows machine with
STAAD.Pro open and a model loaded.

Run with::

    pytest tests/test_integration.py -v -m integration
"""

import pytest

from openstaad_mcp.connection import InstanceRegistry, connect_and_run
from openstaad_mcp.sandbox.executor import Executor

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def staad_instance():
    """Return the first running STAAD.Pro instance from the ROT."""
    registry = InstanceRegistry()
    instances = registry.get_active_instances()
    if not instances:
        pytest.skip("No STAAD.Pro instances found — start STAAD and open a model")
    return instances[0]


@pytest.fixture
def executor():
    return Executor()


class TestIntegration:
    def test_get_node_count(self, staad_instance):
        count = connect_and_run(
            lambda s: s.Geometry.GetNodeCount(),
            staad_instance.file_path,
        )
        assert isinstance(count, int)
        assert count > 0

    def test_get_beam_count(self, staad_instance):
        count = connect_and_run(
            lambda s: s.Geometry.GetMemberCount(),
            staad_instance.file_path,
        )
        assert isinstance(count, int)
        assert count >= 0

    def test_execute_code_via_executor(self, staad_instance, executor):
        def _run(staad):
            return executor.execute("result = staad.Geometry.GetNodeCount()", staad).to_dict()

        result = connect_and_run(_run, staad_instance.file_path)
        assert result["success"]
        assert isinstance(result["result"], int)
