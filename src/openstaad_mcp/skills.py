"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Skills discovery and loading helpers for the MCP server.
"""

from __future__ import annotations

import html
import importlib.resources
from dataclasses import dataclass
from pathlib import Path


def _default_skills_root() -> Path:
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
    """List reference files for a skill (all files except ``SKILL.md``)."""
    return sorted(
        p.relative_to(skill_dir)
        for p in skill_dir.rglob("*")
        if p.is_file() and p.relative_to(skill_dir) != Path("SKILL.md")
    )


@dataclass(frozen=True)
class _SkillEntry:
    """Pre-scanned metadata for a single skill."""

    name: str
    description: str
    path: Path
    references: tuple[Path, ...] = ()


class SkillsManager:
    """Manages skill discovery, validation, and loading.

    All filesystem scanning happens at construction time.  Subsequent
    read operations validate against the pre-scanned index so that only
    known skill folders are accessed.
    """

    def __init__(self, skills_root: Path | None = None) -> None:
        self._root = skills_root or _default_skills_root()
        self._skills: dict[str, _SkillEntry] = {}
        self._scan()

    @property
    def skills(self) -> dict[str, _SkillEntry]:
        return self._skills

    # ── startup scan ──────────────────────────────────────────────

    def _scan(self) -> None:
        """Walk *skills_root* once and index every valid skill folder."""
        if not self._root.is_dir():
            return
        for child in sorted(self._root.iterdir()):
            skill_file = child / "SKILL.md"
            if child.is_dir() and skill_file.is_file():
                desc = _extract_skill_description(skill_file)
                refs = tuple(_list_reference_files(child))
                self._skills[child.name] = _SkillEntry(
                    name=child.name,
                    description=desc,
                    path=child,
                    references=refs,
                )

    # ── validation ────────────────────────────────────────────────

    def _validate_skill_name(self, name: str) -> Path:
        """Resolve *name* to a file path, checking against the pre-scanned index."""
        parts = name.split("/")

        # Reject path-traversal components
        if any(p in (".", "..") for p in parts):
            raise ValueError("Error: Invalid skill path.")

        skill_name = parts[0]
        if skill_name not in self._skills:
            available = sorted(self._skills.keys())
            raise ValueError(
                f"Error: Skill '{html.escape(skill_name)}' not found.\n"
                f"Available skills: {', '.join(available) if available else 'none'}"
            )

        entry = self._skills[skill_name]
        skill_dir = entry.path

        if len(parts) == 1:
            return skill_dir / "SKILL.md"

        # Reference sub-path
        ref_path = Path("/".join(parts[1:]))
        if not ref_path.suffix:
            ref_path = ref_path.with_suffix(".md")
        ref_file = skill_dir / ref_path

        # Verify ref_file stays within skills_root
        try:
            ref_file.resolve().relative_to(self._root.resolve())
        except ValueError as e:
            raise ValueError("Error: Invalid skill path.") from e

        if not ref_file.is_file():
            raise ValueError(
                f"Error: Reference '{html.escape(str(ref_path))}' not found in skill '{html.escape(skill_name)}'.\n"
                f"Available references: {', '.join(str(p) for p in entry.references) if entry.references else 'none'}"
            )
        return ref_file

    # ── public API ────────────────────────────────────────────────

    def format_overview(self) -> str:
        """Return a formatted overview of available skills."""
        lines = ["## Available Skills", ""]
        for entry in self._skills.values():
            lines.append(f"- **{html.escape(entry.name)}**: {html.escape(entry.description)}")
        return "\n".join(lines)

    def read_skill(self, name: str) -> str:
        """Read a single skill or skill reference and return its content."""
        try:
            skill_file = self._validate_skill_name(name)
        except ValueError as e:
            return html.escape(str(e))
        return f"# Skill: {html.escape(name)}\n\n{skill_file.read_text(encoding='utf-8')}"

    def discover_api(self) -> str:
        """Return the API/skills overview used by the ``discover_api`` tool."""
        return self.format_overview()

    def read_skills(self, skills: list[str] | None = None) -> str:
        """Read the content of one or more skills or skill references."""
        if not skills:
            return "Error: No skills requested. Call discover_api first, then pass skill names to read_skills."
        results = [self.read_skill(name) for name in skills]
        return "\n\n".join(results)
