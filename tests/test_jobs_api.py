from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import sys
import types

from fastapi.testclient import TestClient

from agent.learnings.store import LearningStore
from services.api.main import app


def _payload_bytes() -> bytes:
    return b"ACGTACGTACGT"


def _sample_job_request() -> dict:
    payload = _payload_bytes()
    return {
        "requested_by": "tester",
        "run_mode": "dry_run",
        "metadata": {"sample_id": "S-001", "patient_id": "P-001", "hla_alleles": ["A*02:01", "B*07:02"], "peptides": ["SIINFEKL"]},
        "inputs": [
            {
                "name": "tumor.fastq",
                "base64_content": base64.b64encode(payload).decode("ascii"),
                "content_type": "text/plain",
                "expected_md5": hashlib.md5(payload).hexdigest(),  # noqa: S324
            }
        ],
    }


class TestJobsApi:
    def test_create_job_missing_requested_by_returns_422(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        body = _sample_job_request()
        del body["requested_by"]

        resp = client.post("/jobs", json=body)
        assert resp.status_code == 422

    def test_create_job_with_non_list_inputs_returns_422(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        body = _sample_job_request()
        body["inputs"] = {"name": "tumor.fastq"}

        resp = client.post("/jobs", json=body)
        assert resp.status_code == 422

    def test_create_job_and_fetch_status(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        create_resp = client.post("/jobs", json=_sample_job_request())
        assert create_resp.status_code == 200
        job_id = create_resp.json()["job_id"]

        job_resp = client.get(f"/jobs/{job_id}")
        assert job_resp.status_code == 200
        assert job_resp.json()["status"] == "completed"

    def test_results_include_artifacts(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        create_resp = client.post("/jobs", json=_sample_job_request())
        job_id = create_resp.json()["job_id"]

        results_resp = client.get(f"/jobs/{job_id}/results")
        assert results_resp.status_code == 200
        data = results_resp.json()
        assert data["job_id"] == job_id
        assert isinstance(data["artifacts"], list)
        assert any(item["artifact_type"].startswith("report_") for item in data["artifacts"])
        assert any(item["artifact_type"] == "provenance_json" for item in data["artifacts"])
        assert data["provenance"]["pipeline_version"] == "phase3-v0.1"
        assert data["provenance"]["model_version"] == "production-model-latest"

    def test_results_include_persisted_provenance_from_job_metadata(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        monkeypatch.setenv("NEOANTIGEN_IMAGE_DIGEST", "sha256:test-image")
        client = TestClient(app)

        body = _sample_job_request()
        body["metadata"]["model_version"] = "seq2neo-v1-staging"

        create_resp = client.post("/jobs", json=body)
        job_id = create_resp.json()["job_id"]

        results_resp = client.get(f"/jobs/{job_id}/results")
        assert results_resp.status_code == 200
        provenance = results_resp.json()["provenance"]

        assert provenance["pipeline_version"] == "phase3-v0.1"
        assert provenance["model_version"] == "seq2neo-v1-staging"
        assert provenance["image_digest"] == "sha256:test-image"
        assert provenance["parameters"]["run_mode"] == "dry_run"
        assert provenance["parameters"]["job_metadata"]["patient_id"] == "P-001"

    def test_report_download(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        create_resp = client.post("/jobs", json=_sample_job_request())
        job_id = create_resp.json()["job_id"]

        report_resp = client.get(f"/jobs/{job_id}/report.md")
        assert report_resp.status_code == 200
        assert report_resp.headers["content-type"].startswith("text/markdown")

    def test_report_endpoint_returns_404_when_report_artifact_absent(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
        client = TestClient(app)

        store = LearningStore(db_path=str(db_path))
        job_id = store.create_job(run_mode="dry_run", requested_by="tester", metadata={"sample_id": "S-001"})

        resp = client.get(f"/jobs/{job_id}/report.md")
        assert resp.status_code == 404
        assert "No report found" in resp.json()["detail"]

    def test_report_endpoint_returns_404_when_report_file_missing(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
        client = TestClient(app)

        store = LearningStore(db_path=str(db_path))
        job_id = store.create_job(run_mode="dry_run", requested_by="tester", metadata={"sample_id": "S-001"})
        store.add_job_artifact(
            job_id=job_id,
            artifact_type="report_markdown",
            path=str(tmp_path / "missing-report.md"),
            size_bytes=0,
            content_type="text/markdown",
        )

        resp = client.get(f"/jobs/{job_id}/report.md")
        assert resp.status_code == 404
        assert "Report path missing" in resp.json()["detail"]

    def test_results_include_presigned_download_url_for_remote_artifacts(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
        monkeypatch.setenv("NEOANTIGEN_OBJECT_STORE_BACKEND", "minio")
        monkeypatch.setenv("NEOANTIGEN_SIGNED_URL_TTL_SECONDS", "600")

        class FakeS3Client:
            def head_bucket(self, Bucket):
                return None

            def generate_presigned_url(self, operation, Params, ExpiresIn):
                return f"https://signed.example/{Params['Key']}?ttl={ExpiresIn}"

        fake_boto3 = types.SimpleNamespace()
        fake_boto3.client = lambda *args, **kwargs: FakeS3Client()

        fake_botocore_exceptions = types.SimpleNamespace()
        fake_botocore_exceptions.ClientError = RuntimeError

        monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
        monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore_exceptions)

        from services.api.config import get_settings
        get_settings.cache_clear()

        client = TestClient(app)
        store = LearningStore(db_path=str(db_path))
        job_id = store.create_job(run_mode="phase2_real", requested_by="tester", metadata={"sample_id": "S-001"})
        store.add_job_artifact(
            job_id=job_id,
            artifact_type="ranked_peptides_json_object_ref",
            path="s3://neoantigen-artifacts/job-1/phase2/ranked_peptides.json",
            size_bytes=123,
            content_type="application/json",
        )

        resp = client.get(f"/jobs/{job_id}/results")
        assert resp.status_code == 200
        artifact = resp.json()["artifacts"][0]
        assert artifact["download_url"] == "https://signed.example/job-1/phase2/ranked_peptides.json?ttl=600"
        assert artifact["download_expires_in_seconds"] == 600

    def test_report_endpoint_redirects_to_presigned_url_for_remote_report(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
        monkeypatch.setenv("NEOANTIGEN_OBJECT_STORE_BACKEND", "minio")
        monkeypatch.setenv("NEOANTIGEN_SIGNED_URL_TTL_SECONDS", "300")

        class FakeS3Client:
            def head_bucket(self, Bucket):
                return None

            def generate_presigned_url(self, operation, Params, ExpiresIn):
                return f"https://signed.example/{Params['Key']}?ttl={ExpiresIn}"

        fake_boto3 = types.SimpleNamespace()
        fake_boto3.client = lambda *args, **kwargs: FakeS3Client()

        fake_botocore_exceptions = types.SimpleNamespace()
        fake_botocore_exceptions.ClientError = RuntimeError

        monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
        monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore_exceptions)
        
        from services.api.config import get_settings
        get_settings.cache_clear()

        client = TestClient(app)
        store = LearningStore(db_path=str(db_path))
        job_id = store.create_job(run_mode="phase2_real", requested_by="tester", metadata={"sample_id": "S-001"})
        store.add_job_artifact(
            job_id=job_id,
            artifact_type="report_markdown",
            path="s3://neoantigen-artifacts/job-1/report.md",
            size_bytes=321,
            content_type="text/markdown",
        )

        resp = client.get(f"/jobs/{job_id}/report.md", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"] == "https://signed.example/job-1/report.md?ttl=300"

    def test_get_unknown_job_returns_404(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        resp = client.get("/jobs/job-does-not-exist")
        assert resp.status_code == 404
        assert "Unknown job_id" in resp.json()["detail"]

    def test_get_unknown_job_results_returns_404(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        resp = client.get("/jobs/job-does-not-exist/results")
        assert resp.status_code == 404
        assert "Unknown job_id" in resp.json()["detail"]

    def test_get_unknown_job_report_returns_404(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        resp = client.get("/jobs/job-does-not-exist/report.md")
        assert resp.status_code == 404
        assert "Unknown job_id" in resp.json()["detail"]

    def test_create_job_with_checksum_mismatch_returns_400(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        body = _sample_job_request()
        body["inputs"][0]["expected_md5"] = "00000000000000000000000000000000"

        resp = client.post("/jobs", json=body)
        assert resp.status_code == 400
        assert "Checksum mismatch" in resp.json()["detail"]

    def test_checksum_mismatch_persists_failed_job_and_audit(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        client = TestClient(app)

        body = _sample_job_request()
        body["inputs"][0]["expected_md5"] = "ffffffffffffffffffffffffffffffff"

        resp = client.post("/jobs", json=body)
        assert resp.status_code == 400

        with sqlite3.connect(db_path) as conn:
            job_rows = conn.execute(
                """
                SELECT job_id, status, message
                FROM jobs
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchall()
            audit_rows = conn.execute(
                """
                SELECT status, details_json
                FROM audit_log
                WHERE action = 'job_status_transition'
                ORDER BY id ASC
                """
            ).fetchall()

        assert len(job_rows) == 1
        failed_job_id, failed_status, failed_message = job_rows[0]
        assert failed_status == "failed"
        assert "Checksum mismatch" in (failed_message or "")

        statuses = [row[0] for row in audit_rows]
        assert statuses == ["queued", "failed"]

        details = [json.loads(row[1]) for row in audit_rows]
        assert details[0].get("job_id") == failed_job_id
        assert details[1].get("job_id") == failed_job_id

    def test_invalid_base64_persists_failed_job_and_audit(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        client = TestClient(app)

        body = _sample_job_request()
        body["inputs"][0]["base64_content"] = "not-valid-base64***"

        resp = client.post("/jobs", json=body)
        assert resp.status_code == 400
        assert "Invalid base64 payload" in resp.json()["detail"]

        with sqlite3.connect(db_path) as conn:
            job_rows = conn.execute(
                """
                SELECT job_id, status, message
                FROM jobs
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchall()
            audit_rows = conn.execute(
                """
                SELECT status, details_json
                FROM audit_log
                WHERE action = 'job_status_transition'
                ORDER BY id ASC
                """
            ).fetchall()

        assert len(job_rows) == 1
        failed_job_id, failed_status, failed_message = job_rows[0]
        assert failed_status == "failed"
        assert "Invalid base64 payload" in (failed_message or "")

        statuses = [row[0] for row in audit_rows]
        assert statuses == ["queued", "failed"]

        details = [json.loads(row[1]) for row in audit_rows]
        assert details[0].get("job_id") == failed_job_id
        assert details[1].get("job_id") == failed_job_id

    def test_create_job_writes_lifecycle_audit_events(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        client = TestClient(app)

        create_resp = client.post("/jobs", json=_sample_job_request())
        assert create_resp.status_code == 200
        job_id = create_resp.json()["job_id"]

        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT status, details_json
                FROM audit_log
                WHERE action = 'job_status_transition'
                ORDER BY id ASC
                """
            ).fetchall()

        statuses = [row[0] for row in rows]
        assert "queued" in statuses
        assert "completed" in statuses

        audited_job_ids = [json.loads(row[1]).get("job_id") for row in rows]
        assert all(id == job_id for id in audited_job_ids)

class TestJobLogsEndpoint:
    def test_get_job_logs_returns_audit_events(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        client = TestClient(app)

        create_resp = client.post("/jobs", json=_sample_job_request())
        assert create_resp.status_code == 200
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/jobs/{job_id}/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        logs = data["logs"]
        assert len(logs) >= 3
        statuses = [log["status"] for log in logs]
        assert "queued" in statuses
        assert "completed" in statuses

    def test_get_job_logs_unknown_job_returns_404(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "jobs.db"))
        client = TestClient(app)

        resp = client.get("/jobs/job-does-not-exist/logs")
        assert resp.status_code == 404
        assert "Unknown job_id" in resp.json()["detail"]

    def test_get_job_logs_text_format_returns_plain_text(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(db_path))
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        client = TestClient(app)

        create_resp = client.post("/jobs", json=_sample_job_request())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/jobs/{job_id}/logs?format=text")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert f'filename="{job_id}-logs.txt"' in resp.headers["content-disposition"]
        content = resp.text
        assert "job_status_transition - queued" in content
        assert "job_status_transition - completed" in content


class TestLabelIngestEndpoint:
    def test_ingest_labels_missing_labels_returns_422(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "labels.db"))
        client = TestClient(app)

        resp = client.post("/ingest-labels", json={"enforce_schema": True})
        assert resp.status_code == 422

    def test_ingest_labels_endpoint(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOANTIGEN_LEARNINGS_DB", str(tmp_path / "labels.db"))
        client = TestClient(app)

        body = {
            "labels": [
                {
                    "label_id": "lbl-0001",
                    "peptide_id": "pep-0001",
                    "assay_type": "MS",
                    "assay_id": "assay-001",
                    "result": "positive",
                    "score": 0.91,
                    "qc_metrics": {"psm_count": 4, "fdr": 0.005},
                    "uploaded_by": "tester",
                    "timestamp": "2026-03-15T12:00:00Z",
                    "uncertainty": 0.2,
                }
            ]
        }
        resp = client.post("/ingest-labels", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["accepted"] == 1
