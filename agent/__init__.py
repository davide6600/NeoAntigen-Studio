from agent.skills.skill_registry import SkillRegistry
from agent.learnings.store import LearningStore


_registry = SkillRegistry()
_store = LearningStore()


def select_skills(request: dict) -> dict:
    return _registry.select_skills(request)


def suggest_retrain() -> dict:
    return _store.suggest_retrain()


def model_summary() -> dict:
    return _store.model_summary()
