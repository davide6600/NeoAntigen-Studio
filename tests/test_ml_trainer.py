from unittest.mock import patch, MagicMock
import pytest
import os
import shutil

from agent.skills.ml_trainer import predict_immunogenicity
from services.worker.tasks import execute_job
from agent.learnings.store import LearningStore
from services.api.job_store import get_job_store


@patch("shutil.which")
def test_predict_immunogenicity_sklearn_fallback(mock_which):
    mock_which.return_value = None
    peptides = ["SIINFEKL", "AAAA"]
    hlas = ["HLA-A*02:01"]
    
    results, method = predict_immunogenicity(peptides, hlas)
    
    assert method == "sklearn"
    
    assert len(results) == 2
    for r in results:
        assert "peptide" in r
        assert "hla" in r
        assert "rank_score" in r
        assert "strong_binder" in r
        assert "weak_binder" in r
        
    assert results[0]["strong_binder"] is True  # SIINFEKL is known strong
    assert results[1]["strong_binder"] is False # AAAA should be negative

@patch("shutil.which")
def test_predict_immunogenicity_filters_nonbinders(mock_which):
    mock_which.return_value = None
    # Known negative using only non-binders. We need one binder so fallback doesn't trigger
    peptides = ["SIINFEKL", "QQQQQQQQQ", "RRRRRRRRR"]
    hlas = ["HLA-A*02:01"]
    
    results, method = predict_immunogenicity(peptides, hlas)
    non_binders = [r for r in results if not r["strong_binder"] and not r["weak_binder"]]
    
    # QQQQQQQQQ and RRRRRRRRR should be strictly non-binders in sklearn model
    assert len(non_binders) >= 2
    assert any(r["peptide"] == "QQQQQQQQQ" for r in non_binders)

@patch("shutil.which")
def test_predict_immunogenicity_safety_fallback(mock_which):
    mock_which.return_value = None
    # Provide only negative peptides to trigger the safety fallback
    peptides = ["QQQQQQQQQ", "RRRRRRRRR"]
    hlas = ["HLA-A*02:01"]
    
    results, method = predict_immunogenicity(peptides, hlas)
    
    
    # Verify all peptides are returned with weak_binder=True due to fallback
    assert all(r["weak_binder"] is True for r in results)
    assert len(results) == 2

@patch("services.worker.tasks.run_acquisition")
@patch("services.worker.tasks.build_plan")
@patch("services.worker.tasks.run_plan")
@patch("services.worker.tasks.design_sequence")
@patch("services.worker.tasks.run_safety_scan")
@patch("agent.skills.ml_trainer.predict_immunogenicity")
def test_predict_immunogenicity_integration(
    mock_predict, mock_scan, mock_design, mock_run, mock_build, mock_acq, tmp_path
):
    # Setup job store mocking manually or via standard test db
    db_path = str(tmp_path / "test.db")
    store = get_job_store(db_path_override=db_path)
    
    metadata = {
        "patient_id": "PT-001",
        "peptides": ["SIINFEKL", "NLVPMVATV"],
        "hla_alleles": ["HLA-A*02:01"]
    }
    # Create job as an e2e run, so the audit logging isn't skipped
    job_id = store.create_job("dry_run", "e2e", metadata)
    
    mock_acq.return_value = {"peptides_generated": 0, "peptides": [], "variants_found": 0}
    
    mock_predict.return_value = ([{"peptide": "SIINFEKL", "hla": "HLA-A*02:01", "rank_score": 0.9, "strong_binder": True, "weak_binder": False}], "sklearn")
    mock_design.return_value = {"rna_sequence": "AUG"}
    mock_plan = MagicMock()
    mock_plan.command = "dummy"
    mock_build.return_value = mock_plan
    
    mock_plan_res = MagicMock()
    mock_plan_res.exit_code = 0
    mock_run.return_value = mock_plan_res
    
    mock_scan_res = MagicMock()
    mock_scan_res.is_safe = True
    mock_scan_res.findings = []
    mock_scan.return_value = mock_scan_res
    
    # Execute job with requested_by NOT equals "test" so audit gets written
    store.update_job_status(job_id, "running")
    
    try:
        execute_job(job_id, db_path=db_path)
    except Exception as e:
        pass # Handle Missing artifacts errors or others, we just want to check audit
        
    audit_trail = store.list_job_audit_events(job_id)
    steps = [s["step"] for s in audit_trail]
    
    # Verify audit event is logged with correct step name
    assert "immunogenicity_prediction" in steps
    
    pred_step = next(s for s in audit_trail if s["step"] == "immunogenicity_prediction")
    assert pred_step["status"] == "completed"
    assert "total" in pred_step["details"]
    assert "immunogenic" in pred_step["details"]
    assert "predictions" in pred_step["details"]

@patch("subprocess.run")
@patch("shutil.which")
def test_predictor_selection_explicit(mock_which, mock_subprocess):
    # 1. method="sklearn" does not call which or subprocess
    peptides = ["SIINFEKL"]
    hlas = ["HLA-A*02:01"]
    
    res, method = predict_immunogenicity(peptides, hlas, method="sklearn")
    assert method == "sklearn"
    mock_which.assert_not_called()
    mock_subprocess.assert_not_called()
    
    # 2. method="netmhcpan" with NO netMHCpan available falls back to sklearn
    mock_which.return_value = None
    res, method = predict_immunogenicity(peptides, hlas, method="netmhcpan")
    assert method == "sklearn"
    mock_which.assert_called_with("netMHCpan")
    mock_subprocess.assert_not_called()
