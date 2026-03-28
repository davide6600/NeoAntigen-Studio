from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from pathlib import Path


SAFETY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    capabilities: list[str]
    input_types: list[str]
    priority: int
    safety_level: str


class SkillRegistry:
    def __init__(self) -> None:
        self._skills = self._autoload_skills()
        self._dag = {
            "pipeline_orchestrator": ["ml_trainer"],
            "label_ingest": ["ml_trainer", "acquisition_ranker"],
            "acquisition_ranker": ["mrna_designer"],
            "ml_trainer": ["sequence_safety", "mrna_designer"],
            "sequence_safety": ["mrna_designer"],
            "mrna_designer": ["human_approval"],
            "human_approval": [],
        }

    def _autoload_skills(self) -> dict[str, SkillMetadata]:
        skills: dict[str, SkillMetadata] = {}
        package_name = "agent.skills"
        package_path = [str(Path(__file__).parent)]

        for module_info in pkgutil.iter_modules(package_path):
            if module_info.name in {"__init__", "skill_registry"}:
                continue
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            metadata = getattr(module, "SKILL_METADATA", None)
            if not metadata:
                continue
            record = SkillMetadata(**metadata)
            skills[record.name] = record
        return skills

    def list_skills(self) -> list[SkillMetadata]:
        return sorted(
            self._skills.values(),
            key=lambda s: (-s.priority, SAFETY_ORDER.get(s.safety_level, 99), s.name),
        )

    def _matching_skills(self, request: dict) -> tuple[list[str], dict[str, str]]:
        request_inputs = set(request.get("input_types", []))
        rationale: dict[str, str] = {}
        selected: list[str] = []

        for skill in self.list_skills():
            overlap = sorted(request_inputs.intersection(skill.input_types))
            if overlap:
                selected.append(skill.name)
                rationale[skill.name] = (
                    f"Matched input_types {overlap}; priority={skill.priority}; "
                    f"safety_level={skill.safety_level}"
                )
            else:
                rationale[skill.name] = "Skipped: no matching input_types"

        return selected, rationale

    def _expand_with_dag(self, selected: list[str]) -> list[str]:
        result = set(selected)

        for skill in list(selected):
            for downstream in self._dag.get(skill, []):
                if downstream == "human_approval":
                    result.add("human_approval")

        ordered = [
            "pipeline_orchestrator",
            "label_ingest",
            "acquisition_ranker",
            "ml_trainer",
            "sequence_safety",
            "mrna_designer",
            "human_approval",
        ]
        return [name for name in ordered if name in result]

    def select_skills(self, request: dict) -> dict:
        selected, rationale = self._matching_skills(request)
        ordered = self._expand_with_dag(selected)
        return {
            "selected_skills": ordered,
            "rationale": rationale,
            "request": request,
        }
