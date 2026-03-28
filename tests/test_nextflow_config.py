from __future__ import annotations

from pathlib import Path

from services.worker import cohort_analysis


def test_workflow_file_exists():
    assert Path("workflows/neoantigen.nf").exists()


def test_nextflow_config_exists():
    assert Path("workflows/nextflow.config").exists()


def test_conda_env_exists():
    assert Path("envs/neoantigen.yml").exists()


def test_cohort_analysis_cli_entrypoint():
    assert hasattr(cohort_analysis, "main")
    assert callable(cohort_analysis.main)


def test_nf_file_has_required_processes():
    workflow_text = Path("workflows/neoantigen.nf").read_text(encoding="utf-8")
    assert "process HLA_TYPING" in workflow_text
    assert "process PHASE2_PREDICT" in workflow_text
    assert "process REPORT" in workflow_text
