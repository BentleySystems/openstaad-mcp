"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Unit tests for server-level helpers: _poll_hint, _JobStore, _classify_mode.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from openstaad_mcp.server import (
    _classify_mode,
    _Job,
    _JobStore,
    _poll_hint,
)


def _make_job(created_ago: float, last_progress_ago: float | None = None) -> _Job:
    """Return a _Job whose timestamps are offset into the past by the given seconds."""
    now = time.monotonic()
    lpt = now - (last_progress_ago if last_progress_ago is not None else created_ago)
    return _Job(future=MagicMock(), created=now - created_ago, last_progress_time=lpt)


class TestPollHint:
    def test_early_job_returns_5s_wait(self):
        job = _make_job(created_ago=5.0)
        strategy, wait = _poll_hint(job)
        assert strategy == "poll"
        assert wait == 5

    def test_active_phase_returns_10s(self):
        # 60 s old - in the 10s-2min tier
        job = _make_job(created_ago=60.0, last_progress_ago=3.0)
        strategy, wait = _poll_hint(job)
        assert strategy == "poll"
        assert wait == 10

    def test_active_phase_no_progress_still_10s(self):
        # 60 s old, no progress → still 10s tier
        job = _make_job(created_ago=60.0, last_progress_ago=60.0)
        strategy, wait = _poll_hint(job)
        assert strategy == "poll"
        assert wait == 10

    def test_slow_phase_returns_20s_wait(self):
        # 2-10 min range
        job = _make_job(created_ago=300.0)
        strategy, wait = _poll_hint(job)
        assert strategy == "poll"
        assert wait == 20

    def test_intermediate_phase_returns_30s_wait(self):
        # 10-20 min range
        job = _make_job(created_ago=700.0)
        strategy, wait = _poll_hint(job)
        assert strategy == "poll"
        assert wait == 30

    def test_long_job_triggers_await_user(self):
        # > 20 min → stop autonomous polling
        job = _make_job(created_ago=1300.0)
        strategy, wait = _poll_hint(job)
        assert strategy == "await_user_trigger"
        assert wait == 0

    def test_boundary_just_before_slow_phase(self):
        # 119 s — still in active phase
        job = _make_job(created_ago=119.0)
        strategy, wait = _poll_hint(job)
        assert strategy == "poll"
        assert wait == 10

    def test_boundary_just_into_slow_phase(self):
        # 121 s — just entered 2-min tier
        job = _make_job(created_ago=121.0)
        strategy, wait = _poll_hint(job)
        assert strategy == "poll"
        assert wait == 20


class TestJobStore:
    def test_create_and_get(self):
        future = MagicMock()
        store = _JobStore()
        job_id = store.create(future)
        job = store.get(job_id)
        assert job is not None
        assert job.future is future

    def test_last_progress_time_initialized_to_created(self):
        future = MagicMock()
        store = _JobStore()
        before = time.monotonic()
        job_id = store.create(future)
        after = time.monotonic()
        job = store.get(job_id)
        assert job is not None
        assert before <= job.last_progress_time <= after
        assert job.last_progress_time == job.created

    def test_pop_removes_job(self):
        future = MagicMock()
        store = _JobStore()
        job_id = store.create(future)
        assert store.pop(job_id) is not None
        assert store.get(job_id) is None

    def test_ttl_eviction(self):
        future = MagicMock()
        store = _JobStore(ttl_seconds=0.01)
        job_id = store.create(future)
        time.sleep(0.05)  # generous margin for Windows timer resolution
        assert store.get(job_id) is None  # evicted on next access


class TestClassifyMode:
    """Tests for _classify_mode — simple keyword-based timeout/mode heuristic."""

    def test_trivial_code_returns_sync_120(self):
        timeout, mode = _classify_mode("count = staad.Geometry.GetNodeCount()")
        assert timeout == 120.0
        assert mode == "sync"

    def test_analysis_keyword_returns_async_3600(self):
        timeout, mode = _classify_mode("staad.AnalyzeEx(1, 0, 1)")
        assert timeout == 3600.0
        assert mode == "async"

    def test_analyzemodel_returns_async_3600(self):
        timeout, mode = _classify_mode("staad.AnalyzeModel()")
        assert timeout == 3600.0
        assert mode == "async"

    def test_design_keyword_returns_async_3600(self):
        timeout, mode = _classify_mode("design.PerformSteelDesign()")
        assert timeout == 3600.0
        assert mode == "async"

    def test_loop_returns_async_600(self):
        code = "for nid in node_ids:\n    x, y, z = geo.GetNodeCoordinates(nid)"
        timeout, mode = _classify_mode(code)
        assert timeout == 600.0
        assert mode == "async"

    def test_while_loop_returns_async_600(self):
        code = "while i < n:\n    out.GetSupportReaction(nid, lc)"
        timeout, mode = _classify_mode(code)
        assert timeout == 600.0
        assert mode == "async"

    def test_analysis_takes_priority_over_loop(self):
        code = "for lc in cases:\n    staad.AnalyzeEx(1, 0, 1)"
        timeout, mode = _classify_mode(code)
        assert timeout == 3600.0
        assert mode == "async"

    def test_design_takes_priority_over_loop(self):
        code = "for member in members:\n    design.PerformDesign()"
        timeout, mode = _classify_mode(code)
        assert timeout == 3600.0
        assert mode == "async"

    def test_keywords_are_case_insensitive(self):
        timeout, mode = _classify_mode("staad.ANALYZEEX(1, 0, 1)")
        assert timeout == 3600.0
        assert mode == "async"
