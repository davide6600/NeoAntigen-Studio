"""Tests for consent-aware retention and deletion workflows."""
from __future__ import annotations

import json
import sqlite3

import pytest

from agent.privacy.retention import check_consent, schedule_deletion, execute_deletion
from agent.learnings.store import LearningStore
from services.api.object_store import LocalObjectStore


@pytest.fixture()
def tmp_store(tmp_path):
    db = tmp_path / "test.db"
    return LearningStore(db_path=str(db))


class TestCheckConsent:
    def test_no_consent_record_denies(self, tmp_store):
        assert check_consent("patient-X", "training", tmp_store) is False

    def test_explicit_consent_passes(self, tmp_store):
        tmp_store.record_consent("patient-Y", "consented", ["training", "reporting"])
        assert check_consent("patient-Y", "training", tmp_store) is True

    def test_consent_for_wrong_use_denies(self, tmp_store):
        tmp_store.record_consent("patient-Z", "consented", ["reporting"])
        assert check_consent("patient-Z", "training", tmp_store) is False

    def test_soft_deleted_consent_denies(self, tmp_store):
        tmp_store.record_consent("patient-W", "consented", ["training"])
        tmp_store.soft_delete_consent("patient-W")
        assert check_consent("patient-W", "training", tmp_store) is False


class TestDeletionWorkflow:
    def test_schedule_deletion_returns_request_id(self, tmp_store):
        tmp_store.record_consent("patient-A", "consented", ["training"])
        req_id = schedule_deletion("patient-A", "patient request", "admin", tmp_store)
        assert req_id.startswith("del-")

    def test_execute_deletion_marks_consent_soft_deleted(self, tmp_store):
        tmp_store.record_consent("patient-B", "consented", ["training"])
        req_id = schedule_deletion("patient-B", "gdpr", "tester", tmp_store)
        execute_deletion(req_id, "approval-officer", tmp_store)
        # After execution the consent record should be soft-deleted
        assert tmp_store.get_consent_record("patient-B") is None

    def test_execute_deletion_marks_request_executed(self, tmp_store):
        tmp_store.record_consent("patient-C", "consented", ["training"])
        req_id = schedule_deletion("patient-C", "gdpr", "tester", tmp_store)
        execute_deletion(req_id, "approval-officer", tmp_store)
        record = tmp_store.get_deletion_request(req_id)
        assert record["status"] == "executed"

    def test_execute_unknown_request_raises(self, tmp_store):
        with pytest.raises(ValueError):
            execute_deletion("del-99999", "admin", tmp_store)

    def test_execute_deletion_removes_approved_object_store_paths(self, tmp_path, tmp_store):
        tmp_store.record_consent("patient-D", "consented", ["training"])
        req_id = schedule_deletion("patient-D", "gdpr", "tester", tmp_store)

        object_store = LocalObjectStore(root_dir=str(tmp_path / "objects"))
        saved = object_store.put_base64(
            job_id="job-1",
            name="tumor.fastq",
            base64_content="QUJDRA==",
            content_type="text/plain",
        )

        result = execute_deletion(
            req_id,
            "approval-officer",
            tmp_store,
            object_store=object_store,
            object_paths=[saved.path],
        )

        assert result["deleted_object_paths"] == [saved.path]
        assert not tmp_path.joinpath("objects", "job-1", "tumor.fastq").exists()

        with sqlite3.connect(tmp_store.db_path) as conn:
            row = conn.execute(
                """
                SELECT details_json
                FROM audit_log
                WHERE action = 'data_deletion'
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        assert row is not None
        details = json.loads(row[0])
        assert details["deleted_object_paths"] == [saved.path]

    def test_execute_deletion_requires_object_store_when_paths_provided(self, tmp_store):
        tmp_store.record_consent("patient-E", "consented", ["training"])
        req_id = schedule_deletion("patient-E", "gdpr", "tester", tmp_store)

        with pytest.raises(ValueError, match="object_store is required"):
            execute_deletion(req_id, "approval-officer", tmp_store, object_paths=["data/object_store/file.txt"])

    def test_execute_deletion_rejects_unknown_object_path_without_mutating_request(self, tmp_path, tmp_store):
        tmp_store.record_consent("patient-F", "consented", ["training"])
        req_id = schedule_deletion("patient-F", "gdpr", "tester", tmp_store)
        object_store = LocalObjectStore(root_dir=str(tmp_path / "objects"))

        with pytest.raises(ValueError, match="was not found or could not be deleted"):
            execute_deletion(
                req_id,
                "approval-officer",
                tmp_store,
                object_store=object_store,
                object_paths=[str(tmp_path / "objects" / "missing.fastq")],
            )

        record = tmp_store.get_deletion_request(req_id)
        assert record is not None
        assert record["status"] == "pending"
        assert tmp_store.get_consent_record("patient-F") is not None
