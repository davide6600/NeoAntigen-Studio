import pytest
from unittest.mock import patch, MagicMock

from services.worker.tasks import execute_job
from agent.learnings.store import LearningStore

@pytest.fixture
def job_store(tmp_path):
    from services.api.job_store import get_job_store
    db = str(tmp_path / "test.db")
    return get_job_store(db_path_override=db)

@pytest.fixture
def base_metadata():
    return {
        "patient_id": "TEST-001",
        "hla_alleles": ["HLA-A*02:01"],
        "peptides": ["SIINFEKL"],
        "pipeline_engine": "dry_run",
        "model_version": "bootstrap-v0.1"
    }

def test_execute_job_dry_run_success(job_store, base_metadata, tmp_path):
    db_path = str(tmp_path / "test.db")
    job_id = job_store.create_job(
        run_mode="dry_run",
        requested_by="test",
        metadata=base_metadata,
        message="dry run test"
    )
    
    result = execute_job(job_id=job_id, db_path=db_path)
    
    assert result["status"] == "completed"
    assert result["run_mode"] == "dry_run"
    
    job = job_store.get_job(job_id)
    assert job["status"] == "completed"
    
    events = job_store.list_job_audit_events(job_id)
    steps = [e["step"] for e in events]
    assert steps == ["acquisition", "pipeline_plan", "pipeline_run", "mrna_design", "safety_scan", "safe_export"]
    
    export_event = next(e for e in events if e["step"] == "safe_export")
    assert export_event["status"] == "skipped"

@patch("services.worker.tasks.run_plan")
def test_execute_job_full_mode_awaiting_approval(mock_run_plan, job_store, base_metadata, tmp_path):
    mock_rec = MagicMock()
    mock_rec.exit_code = 0
    mock_run_plan.return_value = mock_rec
    
    db_path = str(tmp_path / "test.db")
    job_id = job_store.create_job(
        run_mode="full",
        requested_by="test",
        metadata=base_metadata,
        message="full mode test"
    )
    
    result = execute_job(job_id=job_id, db_path=db_path)
    
    assert result["status"] == "awaiting_approval"
    assert result["run_mode"] == "full"
    
    job = job_store.get_job(job_id)
    assert job["status"] == "awaiting_approval"
    
    learnings = LearningStore(db_path=db_path)
    approvals = learnings.get_pending_approvals()
    assert any(a["proposal_id"] == f"synthesize-{job_id}" for a in approvals)
    
    events = job_store.list_job_audit_events(job_id)
    export_event = next(e for e in events if e["step"] == "safe_export")
    assert export_event["status"] == "blocked"

@patch("services.worker.tasks.design_sequence")
def test_execute_job_homopolymer_fails(mock_design, job_store, base_metadata, tmp_path):
    db_path = str(tmp_path / "test.db")
    job_id = job_store.create_job(
        run_mode="dry_run",
        requested_by="test",
        metadata=base_metadata,
        message="homopolymer test"
    )
    
    mock_design.return_value = {"rna_sequence": "AAAAAAAAAAAAAAAAAAAA", "vienna_mfe": -10.0}
    
    with pytest.raises(ValueError, match="Unsafe sequence detected"):
        execute_job(job_id=job_id, db_path=db_path)
        
    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    
    events = job_store.list_job_audit_events(job_id)
    assert any(e["step"] == "safety_scan" and e["status"] == "failed" for e in events)


def test_execute_job_empty_peptides_fails(job_store, base_metadata, tmp_path):
    db_path = str(tmp_path / "test.db")
    empty_metadata = base_metadata.copy()
    empty_metadata["peptides"] = []
    
    job_id = job_store.create_job(
        run_mode="dry_run",
        requested_by="test",
        metadata=empty_metadata,
        message="empty peptides test"
    )
    
    with pytest.raises(ValueError):
        execute_job(job_id=job_id, db_path=db_path)
        
    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    
    events = job_store.list_job_audit_events(job_id)
    assert any(e["step"] == "mrna_design" and e["status"] == "failed" for e in events)
