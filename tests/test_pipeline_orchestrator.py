from agent.skills.pipeline_orchestrator import build_plan, minimal_smoke_command


def test_build_plan_nextflow_dry_run() -> None:
    plan = build_plan("nextflow", "pipelines/nextflow/main.nf", {"hla": "HLA-A*02:01"}, dry_run=True)
    assert plan.engine == "nextflow"
    assert plan.command[:3] == ["nextflow", "run", "pipelines/nextflow/main.nf"]
    assert plan.dry_run is True
    assert plan.requires_human_approval is False


def test_minimal_smoke_command() -> None:
    assert minimal_smoke_command() == ["nextflow", "run", "pipelines/nextflow/smoke_test/main.nf"]
