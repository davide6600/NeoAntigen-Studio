from unittest.mock import patch, MagicMock
import pytest

@pytest.fixture
def job_store(tmp_path):
    from services.api.job_store import get_job_store
    db = str(tmp_path / "test.db")
    return get_job_store(db_path_override=db)

@pytest.fixture
def sample_job(job_store):
    job_id = job_store.create_job(
        run_mode="dry_run",
        requested_by="test",
        metadata={
            "patient_id": "TEST-001",
            "hla_alleles": ["HLA-A*02:01"],
            "peptides": ["SIINFEKL"],
            "pipeline_engine": "dry_run",
            "model_version": "bootstrap-v0.1"
        },
        message="Test job"
    )
    return job_id


@patch("services.worker.queue.execute_job")
def test_enqueue_job_local_fallback(mock_execute, job_store, sample_job, monkeypatch):
    """Test local fallback mode (no broker URL)."""
    monkeypatch.setenv("CELERY_BROKER_URL", "")
    mock_execute.return_value = {"status": "completed"}
    
    from services.worker.queue import enqueue_job
    
    result = enqueue_job(sample_job, db_path="dummy.db")
    
    mock_execute.assert_called_once_with(job_id=sample_job, db_path="dummy.db")
    assert result["job_id"] == sample_job
    assert result["status"] == "started_locally"
    assert result["queue_mode"] == "local_fallback"


@patch("services.worker.queue.execute_job")
@patch("celery.Celery")
def test_enqueue_job_falls_back_when_celery_raises(mock_celery_cls, mock_execute, job_store, sample_job, monkeypatch):
    """Test fallback when Celery broker is unreachable."""
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:9999/0")
    
    import socket
    mock_app = MagicMock()
    mock_celery_cls.return_value = mock_app
    mock_app.send_task.side_effect = socket.error("connection refused")
    mock_execute.return_value = {"status": "completed"}
    
    from services.worker.queue import enqueue_job
    
    result = enqueue_job(sample_job, db_path="dummy.db")
    
    mock_app.send_task.assert_called_once()
    mock_execute.assert_called_once_with(job_id=sample_job, db_path="dummy.db")
    assert result["job_id"] == sample_job
    assert result["status"] == "started_locally"
    assert result["queue_mode"] == "local_fallback"


@patch("celery.Celery")
def test_enqueue_job_uses_celery_when_reachable(mock_celery_cls, job_store, sample_job, monkeypatch):
    """Test proper queue dispatch when Celery broker is reachable."""
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:9999/0")
    
    mock_app = MagicMock()
    mock_celery_cls.return_value = mock_app
    
    from services.worker.queue import enqueue_job
    
    result = enqueue_job(sample_job, db_path="dummy.db")
    
    mock_app.send_task.assert_called_once_with("services.worker.tasks.execute_job_task", args=[sample_job, "dummy.db"])
    assert result["job_id"] == sample_job
    assert result["status"] == "queued"
    assert result["queue_mode"] == "celery"
