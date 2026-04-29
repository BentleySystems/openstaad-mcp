"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for the skills discovery and loading module.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from openstaad_mcp.skills import (
    _extract_skill_description,
    _list_reference_files,
    _read_skill,
    discover_api_impl,
    format_skills_overview,
    list_skills,
    read_skills_impl,
)

# ── Helpers ────────────────────────────────────────────────────────


def _make_skill(
    tmp_path: Path,
    name: str,
    description: str = "A test skill",
    body: str = "Skill body content.",
    *,
    bom: bool = False,
    references: dict[str, str] | None = None,
) -> Path:
    """Create a minimal skill directory with SKILL.md and optional references."""
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    prefix = "\ufeff" if bom else ""
    content = f'{prefix}---\nname: "{name}"\ndescription: "{description}"\n---\n\n{body}'
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    if references:
        for ref_path, ref_content in references.items():
            ref_file = skill_dir / ref_path
            ref_file.parent.mkdir(parents=True, exist_ok=True)
            ref_file.write_text(ref_content, encoding="utf-8")
    return skill_dir


# ── _extract_skill_description ─────────────────────────────────────


class TestExtractSkillDescription:
    def test_basic_frontmatter(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path, "my-skill", description="Hello world")
        assert _extract_skill_description(skill_dir / "SKILL.md") == "Hello world"

    def test_quoted_description(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path, "my-skill", description="Quoted desc")
        assert _extract_skill_description(skill_dir / "SKILL.md") == "Quoted desc"

    def test_single_quoted_description(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "sq-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: 'Single quoted'\n---\n\nBody", encoding="utf-8")
        assert _extract_skill_description(skill_dir / "SKILL.md") == "Single quoted"

    def test_unquoted_description(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "uq-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: No quotes here\n---\n\nBody", encoding="utf-8")
        assert _extract_skill_description(skill_dir / "SKILL.md") == "No quotes here"

    def test_bom_prefix_stripped(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path, "bom-skill", description="With BOM", bom=True)
        assert _extract_skill_description(skill_dir / "SKILL.md") == "With BOM"

    def test_no_frontmatter_returns_empty(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "no-fm"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Just a heading\n\nNo frontmatter.", encoding="utf-8")
        assert _extract_skill_description(skill_dir / "SKILL.md") == ""

    def test_no_description_key_returns_empty(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "no-desc"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ntitle: Something\n---\n\nBody", encoding="utf-8")
        assert _extract_skill_description(skill_dir / "SKILL.md") == ""

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert _extract_skill_description(tmp_path / "nonexistent" / "SKILL.md") == ""

    def test_incomplete_frontmatter_returns_empty(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "incomplete"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: Oops", encoding="utf-8")
        assert _extract_skill_description(skill_dir / "SKILL.md") == ""


# ── _list_reference_files ──────────────────────────────────────────


class TestListReferenceFiles:
    def test_empty_skill_dir(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path, "empty-refs")
        assert _list_reference_files(skill_dir) == []

    def test_finds_assets(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(
            tmp_path,
            "with-refs",
            references={"assets/REF_A.md": "ref a", "assets/REF_B.md": "ref b"},
        )
        refs = _list_reference_files(skill_dir)
        names = [str(r) for r in refs]
        assert "assets\\REF_A.md" in names or "assets/REF_A.md" in names
        assert "assets\\REF_B.md" in names or "assets/REF_B.md" in names

    def test_excludes_skill_md(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path, "excl-skill")
        refs = _list_reference_files(skill_dir)
        assert all(r != Path("SKILL.md") for r in refs)

    def test_finds_nested_references(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(
            tmp_path,
            "nested-refs",
            references={"assets/sub/DEEP.md": "deep content"},
        )
        refs = _list_reference_files(skill_dir)
        assert len(refs) == 1
        assert refs[0].parts[-1] == "DEEP.md"

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path, "non-md")
        (skill_dir / "readme.txt").write_text("not markdown", encoding="utf-8")
        (skill_dir / "script.py").write_text("print('hi')", encoding="utf-8")
        refs = _list_reference_files(skill_dir)
        assert len(refs) == 0


# ── list_skills ────────────────────────────────────────────────────


class TestListSkills:
    def test_discovers_skills(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "staad-alpha", description="Alpha desc")
        _make_skill(tmp_path, "staad-beta", description="Beta desc")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            skills = list_skills()
        assert len(skills) == 2
        assert skills[0]["name"] == "staad-alpha"
        assert skills[0]["description"] == "Alpha desc"
        assert skills[1]["name"] == "staad-beta"

    def test_skips_dirs_without_skill_md(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "valid-skill")
        (tmp_path / "no-skill-md").mkdir()
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            skills = list_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "valid-skill"

    def test_empty_root_returns_empty(self, tmp_path: Path) -> None:
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            skills = list_skills()
        assert skills == []

    def test_nonexistent_root_returns_empty(self, tmp_path: Path) -> None:
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path / "missing"):
            skills = list_skills()
        assert skills == []

    def test_includes_references_when_present(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "with-refs",
            references={"assets/CODES.md": "codes content"},
        )
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            skills = list_skills()
        assert len(skills) == 1
        assert "references" in skills[0]
        assert len(skills[0]["references"]) == 1

    def test_omits_references_key_when_none(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "no-refs")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            skills = list_skills()
        assert "references" not in skills[0]

    def test_sorted_alphabetically(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "z-skill")
        _make_skill(tmp_path, "a-skill")
        _make_skill(tmp_path, "m-skill")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            skills = list_skills()
        names = [s["name"] for s in skills]
        assert names == ["a-skill", "m-skill", "z-skill"]

    def test_skips_files_in_root(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "real-skill")
        (tmp_path / "stray-file.md").write_text("not a skill", encoding="utf-8")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            skills = list_skills()
        assert len(skills) == 1


# ── format_skills_overview ─────────────────────────────────────────


class TestFormatSkillsOverview:
    def test_includes_header(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "test-skill", description="Desc")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            overview = format_skills_overview()
        assert overview.startswith("## Available Skills")

    def test_includes_skill_entries(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "alpha", description="Alpha description")
        _make_skill(tmp_path, "beta", description="Beta description")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            overview = format_skills_overview()
        assert "**alpha**" in overview
        assert "Alpha description" in overview
        assert "**beta**" in overview

    def test_empty_skills_has_header_only(self, tmp_path: Path) -> None:
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            overview = format_skills_overview()
        assert "## Available Skills" in overview
        assert "**" not in overview


# ── _read_skill ────────────────────────────────────────────────────


class TestReadSkill:
    def test_reads_skill_md(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo", body="Geometry content here.")
        result = _read_skill("geo", tmp_path)
        assert "# Skill: geo" in result
        assert "Geometry content here." in result

    def test_reads_reference_file(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "geo",
            references={"assets/COORDS.md": "Coordinate systems info"},
        )
        result = _read_skill("geo/assets/COORDS", tmp_path)
        assert "Coordinate systems info" in result

    def test_reference_with_md_extension(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "geo",
            references={"assets/COORDS.md": "Coords content"},
        )
        result = _read_skill("geo/assets/COORDS.md", tmp_path)
        assert "Coords content" in result

    def test_reference_with_py_extension(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "geo",
            references={"scripts/example.py": "print('Example script')"},
        )
        result = _read_skill("geo/scripts/example.py", tmp_path)
        assert "print('Example script')" in result

    def test_unknown_skill_returns_error(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "existing-skill")
        result = _read_skill("nonexistent", tmp_path)
        assert "Error:" in result
        assert "not found" in result
        assert "existing-skill" in result

    def test_unknown_reference_returns_error(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo")
        result = _read_skill("geo/assets/MISSING", tmp_path)
        assert "Error:" in result
        assert "not found" in result

    def test_unknown_reference_lists_available(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "geo",
            references={"assets/REAL.md": "real content"},
        )
        result = _read_skill("geo/assets/FAKE", tmp_path)
        assert "Error:" in result
        assert "REAL.md" in result

    def test_skill_dir_without_skill_md(self, tmp_path: Path) -> None:
        (tmp_path / "broken-skill").mkdir()
        result = _read_skill("broken-skill", tmp_path)
        assert "Error:" in result
        assert "no SKILL.md" in result

    def test_empty_root_lists_no_available(self, tmp_path: Path) -> None:
        result = _read_skill("anything", tmp_path)
        assert "Error:" in result
        assert "none" in result


# ── read_skills_impl ───────────────────────────────────────────────


class TestReadSkillsImpl:
    def test_none_returns_error(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "my-skill", description="My desc")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            result = read_skills_impl(None)
        assert result.startswith("Error:")
        assert "discover_api" in result

    def test_empty_list_returns_error(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "my-skill")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            result = read_skills_impl([])
        assert result.startswith("Error:")
        assert "discover_api" in result

    def test_single_skill(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo", body="Geo body")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            result = read_skills_impl(["geo"])
        assert "# Skill: geo" in result
        assert "Geo body" in result

    def test_multiple_skills(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "alpha", body="Alpha body")
        _make_skill(tmp_path, "beta", body="Beta body")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            result = read_skills_impl(["alpha", "beta"])
        assert "Alpha body" in result
        assert "Beta body" in result

    def test_mixed_valid_and_invalid(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "valid-skill", body="Valid content")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            result = read_skills_impl(["valid-skill", "nonexistent"])
        assert "Valid content" in result
        assert "Error:" in result

    def test_reference_subpath(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "design",
            references={
                "assets/CODES.md": "Design codes reference",
                "scripts/example.py": "print('Example script')",
            },
        )
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            md_result = read_skills_impl(["design/assets/CODES"])
            py_result = read_skills_impl(["design/scripts/example.py"])
        assert "Design codes reference" in md_result
        assert "print('Example script')" in py_result


# ── Integration: real staad_skills directory ───────────────────────


class TestRealSkills:
    """Smoke tests against the actual bundled staad_skills directory."""

    def test_real_skills_root_exists(self) -> None:
        from openstaad_mcp.skills import _skills_root

        root = _skills_root()
        assert root.is_dir(), f"staad_skills root not found at {root}"

    def test_real_list_skills_non_empty(self) -> None:
        skills = list_skills()
        assert len(skills) >= 1
        for skill in skills:
            assert "name" in skill
            assert "description" in skill
            assert skill["description"] != "", f"Skill {skill['name']} has empty description"

    def test_real_read_each_skill(self) -> None:
        skills = list_skills()
        for skill in skills:
            result = read_skills_impl([skill["name"]])
            assert f"# Skill: {skill['name']}" in result
            assert len(result) > 50, f"Skill {skill['name']} content too short"

    def test_real_overview_lists_all_skills(self) -> None:
        skills = list_skills()
        overview = format_skills_overview()
        for skill in skills:
            assert skill["name"] in overview


class TestDiscoverApiImpl:
    def test_returns_skills_overview(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "staad-demo", description="Demo description")
        with patch("openstaad_mcp.skills._skills_root", return_value=tmp_path):
            result = discover_api_impl()
        assert "## Available Skills" in result
        assert "staad-demo" in result
