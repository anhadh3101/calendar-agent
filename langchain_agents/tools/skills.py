import re
from pathlib import Path

import yaml
from langchain_core.tools import tool

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split YAML frontmatter from markdown body."""
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", content, re.DOTALL)
    if not match:
        return {}, content.strip()
    meta = yaml.safe_load(match.group(1)) or {}
    body = content[match.end() :].strip()
    return meta, body


def discover_skills() -> list[dict]:
    """Scan skills/ for SKILL.md files; return name + description only."""
    catalog: list[dict] = []
    if not SKILLS_DIR.is_dir():
        return catalog
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta, _ = _parse_frontmatter(skill_md.read_text())
        name = meta.get("name") or skill_dir.name
        catalog.append(
            {
                "name": name,
                "description": meta.get("description", ""),
            }
        )
    return catalog


def build_skills_catalog_prompt(skills: list[dict]) -> str:
    if not skills:
        return ""
    lines = "\n".join(f'- {s["name"]}: {s["description"]}' for s in skills)
    return (
        "Available skills (call load_skill with the skill name before following it):\n"
        f"{lines}"
    )


def load_skill_body(name: str) -> str | None:
    """Return the markdown body for a skill by name, or None if not found."""
    target = name.strip().lower()
    for skill_dir in SKILLS_DIR.iterdir():
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta, body = _parse_frontmatter(skill_md.read_text())
        skill_name = (meta.get("name") or skill_dir.name).lower()
        if skill_name == target or skill_dir.name.lower() == target:
            return body
    return None


def make_load_skill_tool():
    @tool
    def load_skill(name: str) -> str:
        """Load full instructions for a skill by name.

        Call this when a user request matches one of the available skills
        listed in your system prompt. Returns the skill's step-by-step playbook.
        """
        body = load_skill_body(name)
        if body is not None:
            return body
        return (
            f"Skill '{name}' not found. "
            "Available skills are listed in your system prompt."
        )

    return load_skill
