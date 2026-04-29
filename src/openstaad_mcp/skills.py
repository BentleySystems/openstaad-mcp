"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Skills discovery and loading helpers for the MCP server.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any


def _skills_root() -> Path:
    """Return the resolved path to bundled ``openstaad_mcp.staad_skills``."""
    ref = importlib.resources.files("openstaad_mcp").joinpath("staad_skills")
    return Path(str(ref))


def _extract_skill_description(skill_file: Path) -> str:
    """Extract the description from YAML front-matter in a SKILL.md file."""
    try:
        content = skill_file.read_text(encoding="utf-8")
    except OSError:
        return ""
    content = content.lstrip("\ufeff")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                line = line.strip()
                if line.startswith("description:"):
                    desc = line[len("description:") :].strip().strip('"').strip("'")
                    return desc
    return ""


def _list_reference_files(skill_dir: Path) -> list[Path]:
    """List reference files for a skill (all ``.md`` files except ``SKILL.md``)."""
    return sorted(
        p.relative_to(skill_dir)
        for p in skill_dir.rglob("*.md")
        if p.is_file() and p.relative_to(skill_dir) != Path("SKILL.md")
    )


def list_skills() -> list[dict[str, Any]]:
    """Return a list of ``{"name": ..., "description": ...}`` for each skill."""
    root = _skills_root()
    if not root.is_dir():
        return []
    skills: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        skill_file = child / "SKILL.md"
        if child.is_dir() and skill_file.is_file():
            description = _extract_skill_description(skill_file)
            references = _list_reference_files(child)
            entry: dict[str, Any] = {"name": child.name, "description": description}
            if references:
                entry["references"] = [str(r) for r in references]
            skills.append(entry)
    return skills


def format_skills_overview() -> str:
    """Return a formatted overview of available skills."""
    skills = list_skills()
    lines = ["## Available Skills", ""]
    for skill in skills:
        lines.append(f"- **{skill['name']}**: {skill['description']}")
    return "\n".join(lines)


def _read_skill(name: str, skills_root: Path) -> str:
    """Read a single skill or skill reference and return its content.

    Hardens against path-traversal attacks: ``name`` may contain ``/`` as
    a sub-path separator inside one skill, but may not escape
    ``skills_root``. We resolve the candidate path and require that it is
    contained within the resolved ``skills_root``; this single check
    handles ``..``, absolute paths, Windows backslashes, drive letters,
    and symlinks pointing outside the tree.
    """
    if not name or not isinstance(name, str):
        return "Error: Skill name must be a non-empty string."

    try:
        root = skills_root.resolve(strict=False)
    except (OSError, RuntimeError):
        return "Error: Unable to resolve skills root."

    # Resolve the candidate and enforce containment. ``resolve()`` collapses
    # ``..``, normalises separators, and follows symlinks. ``is_relative_to``
    # then rejects anything outside the tree, including the root itself.
    try:
        candidate = (root / name).resolve(strict=False)
    except (OSError, ValueError):
        return f"Error: Invalid skill path: {name!r}"

    if candidate == root or not candidate.is_relative_to(root):
        return f"Error: Invalid skill path: {name!r}"

    # The first path segment (after containment) identifies the skill.
    try:
        rel_parts = candidate.relative_to(root).parts
    except ValueError:
        return f"Error: Invalid skill path: {name!r}"
    if not rel_parts:
        return f"Error: Invalid skill path: {name!r}"

    skill_name = rel_parts[0]
    skill_dir = root / skill_name

    if not skill_dir.is_dir():
        available = [d.name for d in sorted(root.iterdir()) if d.is_dir() and (d / "SKILL.md").is_file()]
        return (
            f"Error: Skill '{skill_name}' not found.\n"
            f"Available skills: {', '.join(available) if available else 'none'}"
        )

    if len(rel_parts) == 1:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            return f"Error: Skill '{skill_name}' has no SKILL.md."
        return f"# Skill: {skill_name}\n\n{skill_file.read_text(encoding='utf-8')}"

    # Sub-path into the skill. Default to .md when no suffix is given.
    ref_parts = rel_parts[1:]
    ref_rel = Path(*ref_parts)
    if not ref_rel.suffix:
        ref_rel = ref_rel.with_suffix(".md")

    try:
        ref_file = (skill_dir / ref_rel).resolve(strict=False)
    except (OSError, ValueError):
        return f"Error: Invalid skill path: {name!r}"

    # Re-check containment after the suffix extension in case of trickery.
    if not ref_file.is_relative_to(skill_dir.resolve(strict=False)):
        return f"Error: Invalid skill path: {name!r}"

    if ref_file.is_file():
        return f"# Skill: {skill_name}/{ref_rel.as_posix()}\n\n{ref_file.read_text(encoding='utf-8')}"

    available_refs = _list_reference_files(skill_dir)
    return (
        f"Error: Reference '{ref_rel.as_posix()}' not found in skill '{skill_name}'.\n"
        f"Available references: {', '.join(p.as_posix() for p in available_refs) if available_refs else 'none'}"
    )


def discover_api_impl() -> str:
    """Return the API/skills overview used by ``discover_api``."""
    return format_skills_overview()


def read_skills_impl(skills: list[str] | None = None) -> str:
    """Read the content of one or more skills or skill references."""
    if not skills:
        return "Error: No skills requested. Call discover_api first, then pass skill names to read_skills."
    root = _skills_root()
    results = [_read_skill(name, root) for name in skills]
    return "\n\n".join(results)
