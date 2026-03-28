from __future__ import annotations

import base64
import binascii
import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredObject:
    path: str
    md5: str
    size_bytes: int
    content_type: str


class ObjectStore(ABC):
    @abstractmethod
    def put_bytes(
        self,
        *,
        job_id: str,
        name: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
        expected_md5: str | None = None,
    ) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    def put_base64(
        self,
        *,
        job_id: str,
        name: str,
        base64_content: str,
        content_type: str = "application/octet-stream",
        expected_md5: str | None = None,
    ) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    def delete_path(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_download_url(self, path: str, expires_seconds: int = 900) -> str | None:
        raise NotImplementedError


class LocalObjectStore(ObjectStore):
    """Local S3/MinIO-compatible scaffold for Phase 1 development and testing."""

    def __init__(self, root_dir: str = "data/object_store") -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        *,
        job_id: str,
        name: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
        expected_md5: str | None = None,
    ) -> StoredObject:
        actual_md5 = hashlib.md5(payload).hexdigest()  # noqa: S324 - checksum for integrity, not crypto

        if expected_md5 and actual_md5.lower() != expected_md5.lower():
            raise ValueError(
                f"Checksum mismatch for '{name}': expected {expected_md5}, got {actual_md5}"
            )

        target = self.root / job_id / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

        return StoredObject(
            path=str(target),
            md5=actual_md5,
            size_bytes=len(payload),
            content_type=content_type,
        )

    def put_base64(
        self,
        *,
        job_id: str,
        name: str,
        base64_content: str,
        content_type: str = "application/octet-stream",
        expected_md5: str | None = None,
    ) -> StoredObject:
        try:
            payload = base64.b64decode(base64_content, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"Invalid base64 payload for '{name}'") from exc

        return self.put_bytes(
            job_id=job_id,
            name=name,
            payload=payload,
            content_type=content_type,
            expected_md5=expected_md5,
        )

    def delete_path(self, path: str) -> bool:
        target = Path(path)
        if not target.exists():
            return False
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()
        return True

    def get_download_url(self, path: str, expires_seconds: int = 900) -> str | None:
        return None


class MinioObjectStore(ObjectStore):
    """S3-compatible object store implementation for MinIO/AWS S3."""

    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        secure: bool = False,
    ) -> None:
        self.bucket = bucket
        scheme = "https" if secure else "http"
        if endpoint_url.startswith("http://") or endpoint_url.startswith("https://"):
            resolved_endpoint = endpoint_url
        else:
            resolved_endpoint = f"{scheme}://{endpoint_url}"

        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise RuntimeError(
                "boto3 is required for MinIO object storage. Install with: pip install boto3"
            ) from exc

        self._client_error = ClientError
        self._s3 = boto3.client(
            "s3",
            endpoint_url=resolved_endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        try:
            self._s3.head_bucket(Bucket=self.bucket)
        except self._client_error:
            self._s3.create_bucket(Bucket=self.bucket)

    def put_bytes(
        self,
        *,
        job_id: str,
        name: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
        expected_md5: str | None = None,
    ) -> StoredObject:
        actual_md5 = hashlib.md5(payload).hexdigest()  # noqa: S324 - checksum for integrity, not crypto

        if expected_md5 and actual_md5.lower() != expected_md5.lower():
            raise ValueError(
                f"Checksum mismatch for '{name}': expected {expected_md5}, got {actual_md5}"
            )

        object_key = f"{job_id}/{name}"
        self._s3.put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=payload,
            ContentType=content_type,
            Metadata={"md5": actual_md5},
        )

        return StoredObject(
            path=f"s3://{self.bucket}/{object_key}",
            md5=actual_md5,
            size_bytes=len(payload),
            content_type=content_type,
        )

    def put_base64(
        self,
        *,
        job_id: str,
        name: str,
        base64_content: str,
        content_type: str = "application/octet-stream",
        expected_md5: str | None = None,
    ) -> StoredObject:
        try:
            payload = base64.b64decode(base64_content, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"Invalid base64 payload for '{name}'") from exc

        return self.put_bytes(
            job_id=job_id,
            name=name,
            payload=payload,
            content_type=content_type,
            expected_md5=expected_md5,
        )

    def delete_path(self, path: str) -> bool:
        prefix = f"s3://{self.bucket}/"
        if not path.startswith(prefix):
            raise ValueError(f"Object path '{path}' does not belong to configured bucket '{self.bucket}'")

        object_key = path[len(prefix):]
        if not object_key:
            raise ValueError("Object path must include a key")

        self._s3.delete_object(Bucket=self.bucket, Key=object_key)
        return True

    def get_download_url(self, path: str, expires_seconds: int = 900) -> str | None:
        prefix = f"s3://{self.bucket}/"
        if not path.startswith(prefix):
            raise ValueError(f"Object path '{path}' does not belong to configured bucket '{self.bucket}'")

        object_key = path[len(prefix):]
        if not object_key:
            raise ValueError("Object path must include a key")

        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=expires_seconds,
        )


def get_object_store() -> ObjectStore:
    backend = os.getenv("NEOANTIGEN_OBJECT_STORE_BACKEND", "local").strip().lower()
    if backend == "local":
        return LocalObjectStore(root_dir=os.getenv("NEOANTIGEN_LOCAL_OBJECT_ROOT", "data/object_store"))

    if backend in {"minio", "s3"}:
        return MinioObjectStore(
            endpoint_url=os.getenv("MINIO_ENDPOINT", "minio:9000"),
            bucket=os.getenv("MINIO_BUCKET", "neoantigen-artifacts"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            region=os.getenv("MINIO_REGION", "us-east-1"),
            secure=os.getenv("MINIO_SECURE", "false").strip().lower() == "true",
        )

    raise ValueError(f"Unsupported object store backend '{backend}'")
