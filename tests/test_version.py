"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for version comparison utilities.
"""

from __future__ import annotations

import pytest

from openstaad_mcp.version import (
    Version,
    check_version_warning,
    parse_version,
)

# ---------------------------------------------------------------------------
# Version parsing
# ---------------------------------------------------------------------------


class TestParseVersion:
    def test_simple_three_part(self) -> None:
        assert parse_version("26.0.1") == Version(26, 0, 1)

    def test_four_part(self) -> None:
        assert parse_version("30.00.01.05") == Version(30, 0, 1, 5)

    def test_two_part(self) -> None:
        assert parse_version("26.1") == Version(26, 1, 0)

    def test_single_number(self) -> None:
        assert parse_version("30") == Version(30, 0, 0)

    def test_leading_zeros_stripped(self) -> None:
        assert parse_version("026.001.007") == Version(26, 1, 7)

    def test_embedded_in_text(self) -> None:
        # Handles formats like "STAAD.Pro 2024 [v30.00.01.01]"
        assert parse_version("STAAD.Pro 2024 [v30.00.01.01]") == Version(30, 0, 1, 1)

    def test_no_match_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse version"):
            parse_version("no-version-here")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse version"):
            parse_version("")


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------


class TestVersionComparison:
    def test_equal(self) -> None:
        assert Version(26, 0, 1) == Version(26, 0, 1)

    def test_less_than_major(self) -> None:
        assert Version(25, 9, 9) < Version(26, 0, 0)

    def test_less_than_minor(self) -> None:
        assert Version(26, 0, 1) < Version(26, 1, 0)

    def test_less_than_patch(self) -> None:
        assert Version(26, 0, 0) < Version(26, 0, 1)

    def test_less_than_build(self) -> None:
        assert Version(26, 0, 1, 0) < Version(26, 0, 1, 1)

    def test_greater_than(self) -> None:
        assert Version(27, 0, 0) > Version(26, 9, 9)

    def test_greater_equal(self) -> None:
        assert Version(26, 0, 1) >= Version(26, 0, 1)
        assert Version(26, 0, 2) >= Version(26, 0, 1)


# ---------------------------------------------------------------------------
# Version string representation
# ---------------------------------------------------------------------------


class TestVersionStr:
    def test_no_build(self) -> None:
        assert str(Version(26, 0, 1)) == "26.0.1"

    def test_with_build(self) -> None:
        assert str(Version(26, 0, 1, 5)) == "26.0.1.5"


# ---------------------------------------------------------------------------
# check_version_warning
# ---------------------------------------------------------------------------


class TestCheckVersionWarning:
    def test_below_minimum_returns_warning(self) -> None:
        warning = check_version_warning("25.0.0")
        assert warning is not None
        assert "below minimum" in warning
        assert "25.0.0" in warning

    def test_at_minimum_returns_none(self) -> None:
        assert check_version_warning("26.0.1") is None

    def test_above_minimum_returns_none(self) -> None:
        assert check_version_warning("30.0.0") is None

    def test_unparseable_returns_warning(self) -> None:
        warning = check_version_warning("unknown")
        assert warning is not None
        assert "Unable to parse" in warning
