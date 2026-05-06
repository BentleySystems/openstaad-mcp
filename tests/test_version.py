"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for version comparison utilities.
"""

from __future__ import annotations

from openstaad_mcp.version import check_version_warning


class TestCheckVersionWarning:
    def test_below_minimum_returns_warning(self) -> None:
        warning = check_version_warning("25.0.0")
        assert warning is not None
        assert "below minimum" in warning
        assert "25.0.0" in warning

    def test_above_minimum_returns_none(self) -> None:
        assert check_version_warning("26.0.1") is None

    def test_well_above_minimum_returns_none(self) -> None:
        assert check_version_warning("30.0.0") is None

    def test_four_segment_staad_format(self) -> None:
        # STAAD reports versions like "26.00.01.05"; packaging normalizes leading zeros.
        assert check_version_warning("26.00.01.05") is None

    def test_unparseable_returns_warning(self) -> None:
        warning = check_version_warning("unknown")
        assert warning is not None
        assert "Unable to parse" in warning
