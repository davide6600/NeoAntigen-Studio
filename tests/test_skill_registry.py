from agent.skills.skill_registry import SkillRegistry


def test_select_skills_orders_by_dag_and_matches_inputs() -> None:
    registry = SkillRegistry()
    result = registry.select_skills({"input_types": ["VCF", "HLA", "LABEL", "PEPTIDE", "DESIGN_POLICY"]})

    # PEPTIDE matches sequence_safety; LABEL matches ml_trainer; VCF+HLA matches pipeline_orchestrator
    # acquisition_ranker needs PEPTIDE_FEATURES which is NOT in this request
    assert result["selected_skills"] == [
        "pipeline_orchestrator",
        "label_ingest",
        "ml_trainer",
        "sequence_safety",
        "mrna_designer",
        "human_approval",
    ]
    assert "Matched input_types" in result["rationale"]["pipeline_orchestrator"]


def test_select_skills_with_peptide_features_adds_acquisition_ranker() -> None:
    registry = SkillRegistry()
    result = registry.select_skills({"input_types": ["PEPTIDE_FEATURES", "METRICS"]})
    assert "acquisition_ranker" in result["selected_skills"]
    assert "ml_trainer" in result["selected_skills"]
