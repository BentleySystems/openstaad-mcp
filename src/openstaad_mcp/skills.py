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
from dataclasses import dataclass, field
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


def _extract_section_names(skill_file: Path) -> tuple[str, ...]:
    """Extract all H2 and H3 heading names (lowercase) from a SKILL.md file.

    Stored on ``_SkillEntry`` at startup so ``/toc`` and error messages can
    list valid section names without re-parsing the file on every call.
    """
    try:
        content = skill_file.read_text(encoding="utf-8")
    except OSError:
        return ()
    body = content.lstrip("\ufeff")
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]
    names = []
    for line in body.splitlines():
        if line.startswith("## "):
            names.append(line[3:].strip().lower())
        elif line.startswith("### "):
            names.append(line[4:].strip().lower())
    return tuple(names)


def _parse_filtered_content(content: str, requested: list[str]) -> str:
    """Return SKILL.md body filtered to the requested H2/H3 section names.

    Rules:
    - H2 sections that have no H3 children (leaf H2s like Gotchas, Examples) are
      always included \u2014 they are small and contain high-value reference material.
    - For H2 sections that *do* have H3 children (like Instructions), only H3s
      whose lowercase names appear in *requested* are included, along with the
      H2 heading and any preamble text that precedes the first H3.
    - H2 sections whose names appear directly in *requested* are always included
      in full (useful for skills like staad-errors that have no H3 sections).
    """
    body = content.lstrip("\ufeff")
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    requested_lower = {r.lower() for r in requested}

    # \u2500\u2500 Parse into H2 blocks \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    # Each block: {heading, heading_lower, preamble, h3s: [{heading, heading_lower, content}]}
    h2_blocks: list[dict] = []
    cur_h2: dict | None = None
    preamble_lines: list[str] = []
    cur_h3: str | None = None
    cur_h3_lines: list[str] = []

    def _flush_h3() -> None:
        if cur_h3 is not None and cur_h2 is not None:
            cur_h2["h3s"].append({
                "heading": cur_h3,
                "heading_lower": cur_h3.lower(),
                "content": "\n".join(cur_h3_lines),
            })

    for line in body.splitlines():
        if line.startswith("## "):
            _flush_h3()
            cur_h3, cur_h3_lines = None, []
            if cur_h2 is not None:
                if not cur_h2["h3s"]:
                    cur_h2["preamble"] = "\n".join(preamble_lines).strip()
                h2_blocks.append(cur_h2)
            preamble_lines = []
            heading = line[3:].strip()
            cur_h2 = {"heading": heading, "heading_lower": heading.lower(), "preamble": "", "h3s": []}
        elif line.startswith("### ") and cur_h2 is not None:
            _flush_h3()
            cur_h3_lines = []
            if not cur_h2["h3s"]:
                cur_h2["preamble"] = "\n".join(preamble_lines).strip()
                preamble_lines = []
            cur_h3 = line[4:].strip()
            cur_h3_lines = [line]
        elif cur_h3 is not None:
            cur_h3_lines.append(line)
        elif cur_h2 is not None:
            preamble_lines.append(line)

    _flush_h3()
    if cur_h2 is not None:
        if not cur_h2["h3s"]:
            cur_h2["preamble"] = "\n".join(preamble_lines).strip()
        h2_blocks.append(cur_h2)

    # \u2500\u2500 Render filtered output \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    output: list[str] = []
    for blk in h2_blocks:
        if not blk["h3s"]:
            # Leaf H2 (Gotchas, Examples, etc.) \u2014 always include
            output.append(f"## {blk['heading']}")
            if blk["preamble"]:
                output.append(blk["preamble"])
        else:
            matching = [h for h in blk["h3s"] if h["heading_lower"] in requested_lower]
            # Also fully include this H2 if its own name was requested
            if blk["heading_lower"] in requested_lower:
                output.append(f"## {blk['heading']}")
                if blk["preamble"]:
                    output.append(blk["preamble"])
                for h3 in blk["h3s"]:
                    output.append(h3["content"])
            elif matching:
                output.append(f"## {blk['heading']}")
                if blk["preamble"]:
                    output.append(blk["preamble"])
                for h3 in matching:
                    output.append(h3["content"])

    return "\n\n".join(output)


def _format_section_index(content: str, skill_name: str) -> str:
    """Generate a compact section index (TOC) for a SKILL.md file.

    Returned by the ``skill/toc`` virtual path so an agent can discover
    available section names before deciding what to load.
    """
    body = content.lstrip("\ufeff")
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    h2_topics: list[str] = []
    h3_topics: list[str] = []
    cur_h2_has_h3 = False
    cur_h2_name = ""

    for line in body.splitlines():
        if line.startswith("## "):
            cur_h2_name = line[3:].strip().lower()
            cur_h2_has_h3 = False
            h2_topics.append(cur_h2_name)
        elif line.startswith("### "):
            cur_h2_has_h3 = True
            h3_topics.append(line[4:].strip().lower())

    lines = [f"# Skill: {html.escape(skill_name)} \u2014 Section Index", ""]

    if h3_topics:
        lines.append("## H3 Topics  (filterable via `sections=[...]`)")
        for t in h3_topics:
            lines.append(f"- {html.escape(t)}")
        lines.append("")

    leaf_h2 = [n for n in h2_topics if n not in {t.lower() for t in h3_topics}]
    if leaf_h2:
        lines.append("## H2 Sections  (always included in filtered results)")
        for n in leaf_h2:
            lines.append(f"- {html.escape(n)}")
        lines.append("")

    lines.append("Usage: `read_skills([\"skill-name\"], sections=[\"topic\", ...])`")
    return "\n".join(lines)


@dataclass(frozen=True)
class _SkillEntry:
    """Pre-scanned metadata for a single skill."""

    name: str
    description: str
    path: Path
    references: tuple[Path, ...] = ()
    section_names: tuple[str, ...] = ()


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
                sec_names = _extract_section_names(skill_file)
                self._skills[child.name] = _SkillEntry(
                    name=child.name,
                    description=desc,
                    path=child,
                    references=refs,
                    section_names=sec_names,
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
        lines.extend([
            "",
            "## Token-Efficient Loading",
            "",
            "1. Load only the sections you need: `read_skills([\"staad-results\"], sections=[\"member forces\"])`",
            "2. Discover available sections first: `read_skills([\"staad-results/toc\"])`",
            "3. Full load (default): `read_skills([\"staad-results\"])`",
        ])
        return "\n".join(lines)

    def read_skill(self, name: str, sections: list[str] | None = None) -> str:
        """Read a single skill or skill reference and return its content.

        If *name* ends with ``/toc``, returns the section index for that skill
        without loading the full content.  Pass *sections* to filter SKILL.md
        content to specific H2/H3 headings; only valid when reading a SKILL.md
        (not a reference sub-path).
        """
        # Handle virtual /toc path before disk-based validation
        if name.endswith("/toc"):
            skill_name = name[: -len("/toc")]
            if skill_name not in self._skills:
                available = sorted(self._skills.keys())
                return html.escape(
                    f"Error: Skill '{skill_name}' not found.\n"
                    f"Available skills: {', '.join(available) if available else 'none'}"
                )
            skill_file = self._skills[skill_name].path / "SKILL.md"
            return _format_section_index(skill_file.read_text(encoding="utf-8"), skill_name)

        try:
            skill_file = self._validate_skill_name(name)
        except ValueError as e:
            return html.escape(str(e))

        raw = skill_file.read_text(encoding="utf-8")

        if sections and skill_file.name == "SKILL.md":
            # Validate requested names against the pre-scanned index
            skill_name = name.split("/")[0]
            entry = self._skills.get(skill_name)
            known = set(entry.section_names) if entry else set()
            unknown = [s for s in sections if s.lower() not in known]

            filtered = _parse_filtered_content(raw, sections)
            if not filtered.strip():
                available = ", ".join(entry.section_names) if entry and entry.section_names else "none"
                return (
                    f"Error: None of the requested sections {sections!r} were found in "
                    f"'{html.escape(skill_name)}'. Available: {available}\n"
                    f"Tip: use read_skills([\"{skill_name}/toc\"]) to browse sections."
                )

            header = f"# Skill: {html.escape(name)} (sections: {', '.join(s.lower() for s in sections)})"
            result = f"{header}\n\n{filtered}"
            if unknown:
                available = ", ".join(entry.section_names) if entry and entry.section_names else "none"
                result += (
                    f"\n\nNote: section(s) not found: {unknown!r}. "
                    f"Available: {available}"
                )
            return result

        return f"# Skill: {html.escape(name)}\n\n{raw}"

    def discover_api(self) -> str:
        """Return the API/skills overview used by the ``discover_api`` tool."""
        return self.format_overview()

    def read_skills(self, skills: list[str] | None = None, sections: list[str] | None = None) -> str:
        """Read the content of one or more skills or skill references."""
        if not skills:
            return "Error: No skills requested. Call discover_api first, then pass skill names to read_skills."
        results = [self.read_skill(name, sections=sections) for name in skills]
        return "\n\n".join(results)
