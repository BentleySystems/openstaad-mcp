"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Security tests for ``_read_skill`` — path traversal prevention.

The skill reader must not read files outside the bundled ``staad_skills``
tree no matter what the user types as the skill name.
"""

from __future__ import annotations

from pathlib import Path

from openstaad_mcp.skills import _read_skill


def _setup_skill(tmp_path: Path, name: str = "alpha") -> Path:
    """Create a minimal skill directory; return the tmp_path root."""
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(f"---\ndescription: {name}\n---\n\nbody", encoding="utf-8")
    # A sub-script that is legitimately addressable via 'alpha/scripts/example.js'
    scripts = skill_dir / "scripts"
    scripts.mkdir()
    (scripts / "example.js").write_text("console.log('ok');", encoding="utf-8")
    return tmp_path


class TestPositive:
    """Legitimate paths still work after hardening."""

    def test_bare_skill_name(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        r = _read_skill("alpha", root)
        assert "# Skill: alpha" in r
        assert "Error:" not in r

    def test_reference_md_auto_suffix(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        (root / "alpha" / "assets").mkdir()
        (root / "alpha" / "assets" / "CODES.md").write_text("code table", encoding="utf-8")
        r = _read_skill("alpha/assets/CODES", root)
        assert "code table" in r
        assert "Error:" not in r

    def test_reference_js_with_extension(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        r = _read_skill("alpha/scripts/example.js", root)
        assert "console.log('ok')" in r
        assert "Error:" not in r


class TestTraversalAttacks:
    """Path traversal attack vectors for skill name input."""

    def test_parent_dir_escape(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        # Create a sensitive file outside the skills root.
        secret = tmp_path.parent / "etc-passwd-lookalike.txt"
        secret.write_text("secret", encoding="utf-8")
        try:
            r = _read_skill("../../../etc/passwd", root)
            assert "Error:" in r
            assert "secret" not in r
        finally:
            secret.unlink(missing_ok=True)

    def test_absolute_posix_path(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        r = _read_skill("/etc/passwd", root)
        assert "Error:" in r

    def test_escape_via_skill_prefix(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        r = _read_skill("alpha/../../../etc/passwd", root)
        assert "Error:" in r

    def test_backslash_traversal(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        r = _read_skill("..\\..\\windows\\win.ini", root)
        assert "Error:" in r

    def test_absolute_windows_drive(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        r = _read_skill("C:/Windows/win.ini", root)
        assert "Error:" in r

    def test_empty_name(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        r = _read_skill("", root)
        assert "Error:" in r

    def test_nul_byte_in_name(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        r = _read_skill("alpha\x00/../etc", root)
        assert "Error:" in r

    def test_just_dot_dot(self, tmp_path: Path) -> None:
        root = _setup_skill(tmp_path)
        r = _read_skill("..", root)
        assert "Error:" in r

    def test_trailing_traversal_after_suffix_fix(self, tmp_path: Path) -> None:
        """Sub-path containment must hold after the `.md` auto-suffix."""
        root = _setup_skill(tmp_path)
        outside = tmp_path.parent / "outside.md"
        outside.write_text("gotcha", encoding="utf-8")
        try:
            r = _read_skill("alpha/../../outside", root)
            assert "Error:" in r
            assert "gotcha" not in r
        finally:
            outside.unlink(missing_ok=True)
