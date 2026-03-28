from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from services.api.object_store import LocalObjectStore, MinioObjectStore, get_object_store


def test_get_object_store_defaults_to_local(monkeypatch):
    monkeypatch.delenv("NEOANTIGEN_OBJECT_STORE_BACKEND", raising=False)
    store = get_object_store()
    assert isinstance(store, LocalObjectStore)


def test_get_object_store_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("NEOANTIGEN_OBJECT_STORE_BACKEND", "unsupported")
    with pytest.raises(ValueError, match="Unsupported object store backend"):
        get_object_store()


def test_local_object_store_put_base64(tmp_path, monkeypatch):
    monkeypatch.setenv("NEOANTIGEN_OBJECT_STORE_BACKEND", "local")
    monkeypatch.setenv("NEOANTIGEN_LOCAL_OBJECT_ROOT", str(tmp_path / "objects"))

    store = get_object_store()
    saved = store.put_base64(
        job_id="job-1",
        name="file.txt",
        base64_content="QUJDRA==",
        content_type="text/plain",
        expected_md5="cb08ca4a7bb5f9683c19133a84872ca7",
    )

    assert saved.size_bytes == 4
    assert saved.content_type == "text/plain"
    assert Path(saved.path).name == "file.txt"
    assert Path(saved.path).parent.name == "job-1"


def test_local_object_store_delete_path(tmp_path):
    store = LocalObjectStore(root_dir=str(tmp_path / "objects"))
    saved = store.put_base64(
        job_id="job-1",
        name="file.txt",
        base64_content="QUJDRA==",
        content_type="text/plain",
    )

    assert Path(saved.path).exists()
    assert store.delete_path(saved.path) is True
    assert not Path(saved.path).exists()
    assert store.delete_path(saved.path) is False


def test_minio_object_store_delete_path_calls_delete_object(monkeypatch):
    calls: dict[str, str] = {}

    class FakeS3Client:
        def head_bucket(self, Bucket):
            return None

        def delete_object(self, Bucket, Key):
            calls["Bucket"] = Bucket
            calls["Key"] = Key

        def generate_presigned_url(self, operation, Params, ExpiresIn):
            calls["operation"] = operation
            calls["presign_bucket"] = Params["Bucket"]
            calls["presign_key"] = Params["Key"]
            calls["expires"] = str(ExpiresIn)
            return f"https://signed.example/{Params['Key']}?ttl={ExpiresIn}"

    fake_boto3 = types.SimpleNamespace()
    fake_boto3.client = lambda *args, **kwargs: FakeS3Client()

    fake_botocore_exceptions = types.SimpleNamespace()
    fake_botocore_exceptions.ClientError = RuntimeError

    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore_exceptions)

    store = MinioObjectStore(
        endpoint_url="minio:9000",
        bucket="neoantigen-artifacts",
        access_key="minioadmin",
        secret_key="minioadmin",
    )

    deleted = store.delete_path("s3://neoantigen-artifacts/job-1/file.txt")

    assert deleted is True
    assert calls == {"Bucket": "neoantigen-artifacts", "Key": "job-1/file.txt"}


def test_minio_object_store_generates_presigned_download_url(monkeypatch):
    calls: dict[str, str] = {}

    class FakeS3Client:
        def head_bucket(self, Bucket):
            return None

        def generate_presigned_url(self, operation, Params, ExpiresIn):
            calls["operation"] = operation
            calls["bucket"] = Params["Bucket"]
            calls["key"] = Params["Key"]
            calls["expires"] = str(ExpiresIn)
            return f"https://signed.example/{Params['Key']}?ttl={ExpiresIn}"

    fake_boto3 = types.SimpleNamespace()
    fake_boto3.client = lambda *args, **kwargs: FakeS3Client()

    fake_botocore_exceptions = types.SimpleNamespace()
    fake_botocore_exceptions.ClientError = RuntimeError

    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore_exceptions)

    store = MinioObjectStore(
        endpoint_url="minio:9000",
        bucket="neoantigen-artifacts",
        access_key="minioadmin",
        secret_key="minioadmin",
    )

    signed = store.get_download_url("s3://neoantigen-artifacts/job-1/file.txt", expires_seconds=600)

    assert signed == "https://signed.example/job-1/file.txt?ttl=600"
    assert calls == {
        "operation": "get_object",
        "bucket": "neoantigen-artifacts",
        "key": "job-1/file.txt",
        "expires": "600",
    }


def test_minio_object_store_delete_path_rejects_wrong_bucket(monkeypatch):
    class FakeS3Client:
        def head_bucket(self, Bucket):
            return None

    fake_boto3 = types.SimpleNamespace()
    fake_boto3.client = lambda *args, **kwargs: FakeS3Client()

    fake_botocore_exceptions = types.SimpleNamespace()
    fake_botocore_exceptions.ClientError = RuntimeError

    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore_exceptions)

    store = MinioObjectStore(
        endpoint_url="minio:9000",
        bucket="neoantigen-artifacts",
        access_key="minioadmin",
        secret_key="minioadmin",
    )

    with pytest.raises(ValueError, match="does not belong to configured bucket"):
        store.delete_path("s3://other-bucket/job-1/file.txt")
