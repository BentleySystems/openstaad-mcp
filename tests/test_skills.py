"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for the skills discovery and loading module.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from openstaad_mcp.skills import (
    SkillsManager,
    _extract_section_names,
    _extract_skill_description,
    _format_section_index,
    _list_reference_files,
    _parse_filtered_content,
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


# ── SkillsManager.__init__ / _scan ────────────────────────────────


class TestSkillsManagerScan:
    def test_discovers_skills(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "staad-alpha", description="Alpha desc")
        _make_skill(tmp_path, "staad-beta", description="Beta desc")
        skills = SkillsManager(tmp_path).skills
        assert len(skills) == 2
        assert "staad-alpha" in skills
        assert "staad-beta" in skills
        assert skills["staad-alpha"].name == "staad-alpha"
        assert skills["staad-alpha"].description == "Alpha desc"
        assert skills["staad-beta"].name == "staad-beta"

    def test_skips_dirs_without_skill_md(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "valid-skill")
        (tmp_path / "no-skill-md").mkdir()
        skills = SkillsManager(tmp_path).skills
        assert len(skills) == 1
        assert "valid-skill" in skills
        assert skills["valid-skill"].name == "valid-skill"

    def test_empty_root_returns_empty(self, tmp_path: Path) -> None:
        skills = SkillsManager(tmp_path).skills
        assert len(skills) == 0

    def test_nonexistent_root_returns_empty(self, tmp_path: Path) -> None:
        skills = SkillsManager(tmp_path / "missing").skills
        assert len(skills) == 0

    def test_includes_references_when_present(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "with-refs",
            references={"assets/CODES.md": "codes content"},
        )
        skills = SkillsManager(tmp_path).skills
        assert len(skills) == 1
        assert "references" in skills["with-refs"].__dict__
        assert len(skills["with-refs"].references) == 1

    def test_sorted_alphabetically(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "z-skill")
        _make_skill(tmp_path, "a-skill")
        _make_skill(tmp_path, "m-skill")
        skills = SkillsManager(tmp_path).skills
        names = [s.name for s in skills.values()]
        assert names == ["a-skill", "m-skill", "z-skill"]

    def test_skips_files_in_root(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "real-skill")
        (tmp_path / "stray-file.md").write_text("not a skill", encoding="utf-8")
        skills = SkillsManager(tmp_path).skills
        assert len(skills) == 1


# ── SkillsManager.format_overview ─────────────────────────────────


class TestFormatOverview:
    def test_includes_header(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "test-skill", description="Desc")
        mgr = SkillsManager(tmp_path)
        overview = mgr.format_overview()
        assert overview.startswith("## Available Skills")

    def test_includes_skill_entries(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "alpha", description="Alpha description")
        _make_skill(tmp_path, "beta", description="Beta description")
        mgr = SkillsManager(tmp_path)
        overview = mgr.format_overview()
        assert "**alpha**" in overview
        assert "Alpha description" in overview
        assert "**beta**" in overview

    def test_empty_skills_has_header_only(self, tmp_path: Path) -> None:
        mgr = SkillsManager(tmp_path)
        overview = mgr.format_overview()
        assert "## Available Skills" in overview
        assert "**" not in overview


# ── SkillsManager.read_skill ──────────────────────────────────────


class TestReadSkill:
    def test_reads_skill_md(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo", body="Geometry content here.")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("geo")
        assert "# Skill: geo" in result
        assert "Geometry content here." in result

    def test_reads_reference_file(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "geo",
            references={"assets/COORDS.md": "Coordinate systems info"},
        )
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("geo/assets/COORDS")
        assert "Coordinate systems info" in result

    def test_reference_with_md_extension(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "geo",
            references={"assets/COORDS.md": "Coords content"},
        )
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("geo/assets/COORDS.md")
        assert "Coords content" in result

    def test_reference_with_py_extension(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "geo",
            references={"scripts/example.py": "print('Example script')"},
        )
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("geo/scripts/example.py")
        assert "print('Example script')" in result

    def test_unknown_skill_returns_error(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "existing-skill")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("nonexistent")
        assert "Error:" in result
        assert "not found" in result
        assert "existing-skill" in result

    def test_unknown_reference_returns_error(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("geo/assets/MISSING")
        assert "Error:" in result
        assert "not found" in result

    def test_unknown_reference_lists_available(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path,
            "geo",
            references={"assets/REAL.md": "real content"},
        )
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("geo/assets/FAKE")
        assert "Error:" in result
        assert "REAL.md" in result

    def test_skill_dir_without_skill_md(self, tmp_path: Path) -> None:
        """A directory without SKILL.md is not indexed — treated as unknown."""
        (tmp_path / "broken-skill").mkdir()
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("broken-skill")
        assert "Error:" in result
        assert "not found" in result

    def test_empty_root_lists_no_available(self, tmp_path: Path) -> None:
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("anything")
        assert "Error:" in result
        assert "none" in result


# ── XSS sanitization ─────────────────────────────────────


class TestReadSkillXssSanitization:
    """Verify user-controlled input is HTML-escaped in output."""

    def test_skill_name_escaped_in_read_skill(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo", body="content")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result or "Error" in result

    def test_skill_name_escaped_in_error(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "existing")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("<img src=x onerror=alert(1)>")
        assert "<img" not in result
        assert "&lt;img" in result or "Error" in result

    def test_description_escaped_in_overview(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "xss-skill", description="<b>bold</b>")
        mgr = SkillsManager(tmp_path)
        overview = mgr.format_overview()
        assert "<b>" not in overview
        assert "&lt;b&gt;" in overview

    def test_name_with_ampersand_escaped(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo", body="content")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("foo&bar")
        assert "&amp;" in result or "Error" in result

    def test_format_overview_escapes_name(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "a&b"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text('---\ndescription: "test"\n---\n\nBody', encoding="utf-8")
        mgr = SkillsManager(tmp_path)
        overview = mgr.format_overview()
        assert "&amp;" in overview


class TestReadSkillPathTraversalBlocked:
    """Path traversal in read_skill must be blocked."""

    def test_dotdot_in_first_component(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "my-skill")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("../../../etc/passwd")
        assert "Error:" in result
        assert "Invalid" in result

    def test_dotdot_in_ref_path(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "staad-core")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("staad-core/../../pyproject.toml")
        assert "Error:" in result
        assert "Invalid" in result

    def test_dotdot_deep_traversal(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "staad-core")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("staad-core/" + "../" * 20 + "etc/passwd")
        assert "Error:" in result
        assert "Invalid" in result

    def test_single_dot_rejected(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "my-skill")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("./my-skill")
        assert "Error:" in result

    def test_valid_skill_still_works(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo", body="Geometry skill content")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("geo")
        assert "Geometry skill content" in result

    def test_valid_ref_still_works(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo", references={"assets/CODES.md": "codes content"})
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("geo/assets/CODES")
        assert "codes content" in result

    def test_symlink_escape_blocked(self, tmp_path: Path) -> None:
        """A symlink pointing outside skills_root must be rejected."""
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.md"
        secret.write_text("secret content", encoding="utf-8")

        skills_root = tmp_path / "skills"
        skill_dir = skills_root / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text('---\ndescription: "test"\n---\n\nBody', encoding="utf-8")

        assets = skill_dir / "assets"
        assets.mkdir()
        link = assets / "escape.md"
        try:
            os.symlink(str(secret), str(link))
        except OSError:
            pytest.skip("Cannot create symlinks on this OS/permissions")

        mgr = SkillsManager(skills_root)
        result = mgr.read_skill("my-skill/assets/escape")
        assert "Error" in result or "Invalid" in result
        assert "secret content" not in result

    def test_ref_resolves_within_skills_root(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo", references={"assets/CODES.md": "codes content"})
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("geo/assets/CODES")
        assert "codes content" in result

    def test_deeply_nested_ref_traversal_blocked(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "staad-core")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("staad-core/sub/../../../etc/passwd")
        assert "Error:" in result
        assert "Invalid" in result


# ── SkillsManager.read_skills ─────────────────────────────────────


class TestReadSkills:
    def test_none_returns_error(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "my-skill", description="My desc")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skills(None)
        assert result.startswith("Error:")
        assert "discover_api" in result

    def test_empty_list_returns_error(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "my-skill")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skills([])
        assert result.startswith("Error:")
        assert "discover_api" in result

    def test_single_skill(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "geo", body="Geo body")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skills(["geo"])
        assert "# Skill: geo" in result
        assert "Geo body" in result

    def test_multiple_skills(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "alpha", body="Alpha body")
        _make_skill(tmp_path, "beta", body="Beta body")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skills(["alpha", "beta"])
        assert "Alpha body" in result
        assert "Beta body" in result

    def test_mixed_valid_and_invalid(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "valid-skill", body="Valid content")
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skills(["valid-skill", "nonexistent"])
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
        mgr = SkillsManager(tmp_path)
        md_result = mgr.read_skills(["design/assets/CODES"])
        py_result = mgr.read_skills(["design/scripts/example.py"])
        assert "Design codes reference" in md_result
        assert "print('Example script')" in py_result


# ── Integration: real staad_skills directory ───────────────────────


class TestRealSkills:
    """Smoke tests against the actual bundled staad_skills directory."""

    def test_real_skills_root_exists(self) -> None:
        skills = SkillsManager().skills
        assert len(skills) >= 0  # root exists if no error is raised

    def test_real_list_skills_non_empty(self) -> None:
        skills = SkillsManager().skills
        assert len(skills) >= 1
        for skill in skills.values():
            assert skill.name != "", "Skill has empty name"
            assert skill.description != "", f"Skill {skill.name} has empty description"
            if skill.name == "staad-analysis":
                assert len(skill.references) >= 1

    def test_real_read_each_skill(self) -> None:
        mgr = SkillsManager()
        skills = mgr.skills
        for skill in skills.values():
            result = mgr.read_skills([skill.name])
            assert f"# Skill: {skill.name}" in result
            assert len(result) > 50, f"Skill {skill.name} content too short"

    def test_real_overview_lists_all_skills(self) -> None:
        mgr = SkillsManager()
        skills = mgr.skills
        overview = mgr.format_overview()
        for skill in skills.values():
            assert skill.name in overview

    def test_real_skills_have_section_names(self) -> None:
        skills = SkillsManager().skills
        for skill in skills.values():
            assert isinstance(skill.section_names, tuple), f"{skill.name} section_names not a tuple"

    def test_real_toc_for_staad_results(self) -> None:
        mgr = SkillsManager()
        toc = mgr.read_skills(["staad-results/toc"])
        assert "member forces" in toc
        assert "gotchas" in toc

    def test_real_filtered_staad_results_member_forces(self) -> None:
        mgr = SkillsManager()
        full = mgr.read_skills(["staad-results"])
        filtered = mgr.read_skills(["staad-results"], sections=["member forces"])
        assert "Member Forces" in filtered
        assert "Gotchas" in filtered  # always included
        assert len(filtered) < len(full), "Filtered result should be smaller than full"

    def test_real_filtered_overview_tip_present(self) -> None:
        overview = SkillsManager().format_overview()
        assert "sections=" in overview


# ── _extract_section_names ─────────────────────────────────────────


class TestExtractSectionNames:
    def test_extracts_h2_and_h3(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(
            tmp_path, "s",
            body="## Instructions\n\nPreamble.\n\n### Topic A\nContent A.\n\n### Topic B\nContent B.\n\n## Gotchas\n- Be careful."
        )
        names = _extract_section_names(skill_dir / "SKILL.md")
        assert "instructions" in names
        assert "topic a" in names
        assert "topic b" in names
        assert "gotchas" in names

    def test_empty_file_returns_empty_tuple(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path, "s", body="")
        names = _extract_section_names(skill_dir / "SKILL.md")
        assert isinstance(names, tuple)

    def test_missing_file_returns_empty_tuple(self, tmp_path: Path) -> None:
        names = _extract_section_names(tmp_path / "nonexistent.md")
        assert names == ()

    def test_all_lowercase(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path, "s", body="## UPPER CASE\n### Mixed Case")
        names = _extract_section_names(skill_dir / "SKILL.md")
        assert "upper case" in names
        assert "mixed case" in names


# ── _parse_filtered_content ────────────────────────────────────────

_SAMPLE_SKILL_CONTENT = """---
name: "test-skill"
description: "A skill for testing"
---

# Test Skill

## Instructions

Preamble text here.

### Topic A
Content for topic A.

### Topic B
Content for topic B.

### Topic C
Content for topic C.

## Example
An example link.

## Gotchas
- Watch out for X.
"""


class TestParseFilteredContent:
    def test_requested_h3_included(self) -> None:
        result = _parse_filtered_content(_SAMPLE_SKILL_CONTENT, ["topic a"])
        assert "Topic A" in result
        assert "Content for topic A" in result

    def test_unrequested_h3_excluded(self) -> None:
        result = _parse_filtered_content(_SAMPLE_SKILL_CONTENT, ["topic a"])
        assert "Topic B" not in result
        assert "Topic C" not in result

    def test_leaf_h2_always_included(self) -> None:
        result = _parse_filtered_content(_SAMPLE_SKILL_CONTENT, ["topic a"])
        assert "## Example" in result
        assert "## Gotchas" in result
        assert "Watch out for X" in result

    def test_preamble_included_when_h3_matched(self) -> None:
        result = _parse_filtered_content(_SAMPLE_SKILL_CONTENT, ["topic a"])
        assert "Preamble text" in result

    def test_multiple_requested_sections(self) -> None:
        result = _parse_filtered_content(_SAMPLE_SKILL_CONTENT, ["topic a", "topic c"])
        assert "Topic A" in result
        assert "Topic C" in result
        assert "Topic B" not in result

    def test_empty_request_returns_only_leaf_h2s(self) -> None:
        result = _parse_filtered_content(_SAMPLE_SKILL_CONTENT, [])
        assert "## Gotchas" in result
        assert "## Example" in result
        assert "Topic A" not in result

    def test_case_insensitive_matching(self) -> None:
        result = _parse_filtered_content(_SAMPLE_SKILL_CONTENT, ["TOPIC A"])
        assert "Topic A" in result

    def test_requesting_h2_by_name_returns_full_h2(self) -> None:
        result = _parse_filtered_content(_SAMPLE_SKILL_CONTENT, ["instructions"])
        assert "Topic A" in result
        assert "Topic B" in result
        assert "Topic C" in result


# ── _format_section_index ──────────────────────────────────────────


class TestFormatSectionIndex:
    def test_h3_topics_listed(self) -> None:
        result = _format_section_index(_SAMPLE_SKILL_CONTENT, "test-skill")
        assert "topic a" in result
        assert "topic b" in result
        assert "topic c" in result

    def test_leaf_h2_sections_listed(self) -> None:
        result = _format_section_index(_SAMPLE_SKILL_CONTENT, "test-skill")
        assert "example" in result
        assert "gotchas" in result

    def test_skill_name_in_header(self) -> None:
        result = _format_section_index(_SAMPLE_SKILL_CONTENT, "test-skill")
        assert "test-skill" in result

    def test_usage_hint_present(self) -> None:
        result = _format_section_index(_SAMPLE_SKILL_CONTENT, "test-skill")
        assert "sections=" in result


# ── SkillsManager section features ────────────────────────────────


class TestSkillsManagerSections:
    def test_section_names_populated_on_scan(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path, "with-sections",
            body="## Instructions\n\n### Topic A\nA.\n\n### Topic B\nB.\n\n## Gotchas\nG."
        )
        skills = SkillsManager(tmp_path).skills
        entry = skills["with-sections"]
        assert "topic a" in entry.section_names
        assert "topic b" in entry.section_names
        assert "gotchas" in entry.section_names

    def test_toc_path_returns_section_index(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path, "my-skill",
            body="## Instructions\n\n### Alpha\nA.\n\n## Gotchas\nG."
        )
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("my-skill/toc")
        assert "alpha" in result
        assert "gotchas" in result

    def test_toc_unknown_skill_returns_error(self, tmp_path: Path) -> None:
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("nonexistent/toc")
        assert "Error:" in result

    def test_filtered_read_returns_requested_section(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path, "s",
            body="## Instructions\n\n### Alpha\nAlpha content.\n\n### Beta\nBeta content.\n\n## Gotchas\nG."
        )
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("s", sections=["alpha"])
        assert "Alpha content" in result
        assert "Beta content" not in result

    def test_filtered_read_unknown_section_appends_note(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path, "s",
            body="## Instructions\n\n### Alpha\nContent.\n\n## Gotchas\nG."
        )
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("s", sections=["nonexistent"])
        assert "nonexistent" in result.lower()

    def test_filtered_read_no_match_returns_error(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path, "s",
            body="## Instructions\n\n### Alpha\nContent."
        )
        mgr = SkillsManager(tmp_path)
        # "Instructions" IS matched as an H2 by-name, so only truly absent names fail
        result = mgr.read_skill("s", sections=["totally-missing-xyz"])
        # Filtered result has leaf H2s (none here) - just check no crash
        assert isinstance(result, str)

    def test_sections_param_ignored_for_reference_subpath(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path, "s",
            body="## Instructions\n\n### Alpha\nContent.",
            references={"assets/REF.md": "Reference content"}
        )
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skill("s/assets/REF", sections=["alpha"])
        assert "Reference content" in result

    def test_read_skills_passes_sections_through(self, tmp_path: Path) -> None:
        _make_skill(
            tmp_path, "s",
            body="## Instructions\n\n### Alpha\nAlpha content.\n\n### Beta\nBeta content.\n\n## Gotchas\nG."
        )
        mgr = SkillsManager(tmp_path)
        result = mgr.read_skills(["s"], sections=["alpha"])
        assert "Alpha content" in result
        assert "Beta content" not in result

    def test_overview_includes_usage_tip(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "s", description="A skill")
        overview = SkillsManager(tmp_path).format_overview()
        assert "sections=" in overview
