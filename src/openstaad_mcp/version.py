"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Version comparison utilities.

Public API
----------
``Version``
    Comparable semantic version parsed from a dotted string.

``parse_version(raw) -> Version``
    Parse a raw version string (e.g. "26.00.01.05") into a ``Version``.

``MINIMUM_SUPPORTED_VERSION``
    Lowest version fully supported without behavioral caveats.

``check_version_warning(version_str) -> str | None``
    Return a warning message if *version_str* is below the minimum, else ``None``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Version class
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?")
_BRACKETED_RE = re.compile(r"\[v?(\d+(?:\.\d+)*)\]", re.IGNORECASE)


@dataclass(frozen=True, order=True)
class Version:
    """A comparable semantic version with up to four segments.

    Comparison uses tuple ordering: (major, minor, patch, build).
    Missing segments default to 0.
    """

    major: int = 0
    minor: int = 0
    patch: int = 0
    build: int = 0

    def __str__(self) -> str:
        if self.build:
            return f"{self.major}.{self.minor}.{self.patch}.{self.build}"
        return f"{self.major}.{self.minor}.{self.patch}"


def parse_version(raw: str) -> Version:
    """Parse a dotted version string into a :class:`Version`.

    Handles formats like:
    - ``"26.00.01.05"``
    - ``"26.0.1"``
    - ``"30"``
    - ``"STAAD.Pro 2024 [v30.00.01.01]"`` — bracketed version preferred

    Leading zeros are stripped (``"01"`` → 1).  If a bracketed version
    (e.g. ``[v30.00.01.01]``) is present, it takes priority over any
    preceding numbers.
    """
    # Prefer bracketed version like [v30.00.01.01]
    bm = _BRACKETED_RE.search(raw)
    if bm:
        raw = bm.group(1)
    m = _VERSION_RE.search(raw)
    if not m:
        raise ValueError(f"Cannot parse version from: {raw!r}")
    parts = [int(g) if g else 0 for g in m.groups()]
    return Version(*parts)


# ---------------------------------------------------------------------------
# Minimum supported version
# ---------------------------------------------------------------------------

MINIMUM_SUPPORTED_VERSION = Version(25, 0, 1)


def check_version_warning(version_str: str) -> str | None:
    """Return a warning string if *version_str* is below the minimum, else ``None``."""
    try:
        v = parse_version(version_str)
    except ValueError:
        return f"Unable to parse version '{version_str}'. Minimum supported is {MINIMUM_SUPPORTED_VERSION}."
    if v < MINIMUM_SUPPORTED_VERSION:
        return (
            f"Version {v} is below minimum supported {MINIMUM_SUPPORTED_VERSION}. "
            f"Some results may be inaccurate due to known bugs in older releases."
        )
    return None
