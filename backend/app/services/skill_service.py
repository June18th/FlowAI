from __future__ import annotations

import re
import yaml
from pathlib import Path

from app.config import settings
from app.schemas.skills import SkillDetail, SkillSummary


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, SkillDetail] = {}
        self._reference_cache: dict[str, dict[str, str]] = {}  # skill_name -> {ref_name: content}
        self._loaded = False

    def _get_skills_dir(self) -> Path:
        path = Path(settings.skills_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path

    def _load_skill(self, skill_dir: Path) -> SkillDetail | None:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        content = skill_md.read_text(encoding="utf-8")

        name = skill_dir.name
        description = ""
        body = content

        # Parse YAML frontmatter
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if frontmatter_match:
            try:
                fm = yaml.safe_load(frontmatter_match.group(1))
                if isinstance(fm, dict):
                    name = fm.get("name", name)
                    description = fm.get("description", "")
            except yaml.YAMLError:
                pass
            body = content[frontmatter_match.end():]

        # Find references
        references: list[str] = []
        ref_dir = skill_dir / "reference"
        if ref_dir.exists():
            for ref_file in ref_dir.glob("*.md"):
                ref_name = ref_file.stem
                if re.match(r"^[a-zA-Z0-9._-]+$", ref_name):
                    references.append(ref_name)
                    ref_content = ref_file.read_text(encoding="utf-8")
                    self._reference_cache.setdefault(name, {})[ref_name] = ref_content

        return SkillDetail(
            name=name,
            description=description,
            content=body.strip(),
            references=references,
        )

    def _ensure_loaded(self):
        if self._loaded:
            return
        skills_dir = self._get_skills_dir()
        if skills_dir.exists():
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir() and not d.name.startswith("."):
                    skill = self._load_skill(d)
                    if skill:
                        self._skills[skill.name] = skill
        self._loaded = True

    def get_all_summaries(self) -> list[SkillSummary]:
        self._ensure_loaded()
        return sorted(
            [SkillSummary(name=s.name, description=s.description) for s in self._skills.values()],
            key=lambda x: x.name,
        )

    def get_skill(self, name: str) -> SkillDetail | None:
        self._ensure_loaded()
        return self._skills.get(name)

    def get_reference(self, skill_name: str, reference_name: str) -> str | None:
        self._ensure_loaded()
        refs = self._reference_cache.get(skill_name, {})
        return refs.get(reference_name)

    def load_all_references(self, skill_name: str) -> dict[str, str]:
        self._ensure_loaded()
        return self._reference_cache.get(skill_name, {})


skill_registry = SkillRegistry()
