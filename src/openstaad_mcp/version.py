"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Version comparison utilities.

Public API
----------
``MINIMUM_SUPPORTED_VERSION``
    Lowest version fully supported without behavioral caveats.

``check_version_warning(version_str) -> str | None``
    Return a warning message if *version_str* is below the minimum, else ``None``.
"""

from __future__ import annotations

from packaging.version import InvalidVersion, Version

MINIMUM_SUPPORTED_VERSION = Version("25.0.1")


def check_version_warning(version_str: str) -> str | None:
    """Return a warning string if *version_str* is below the minimum, else ``None``."""
    try:
        v = Version(version_str)
    except InvalidVersion:
        return f"Unable to parse version '{version_str}'. Minimum supported is {MINIMUM_SUPPORTED_VERSION}."
    if v < MINIMUM_SUPPORTED_VERSION:
        return (
            f"Version {v} is below minimum supported {MINIMUM_SUPPORTED_VERSION}. "
            f"Some results may be inaccurate due to known bugs in older releases."
        )
    return None
