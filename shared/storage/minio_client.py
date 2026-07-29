"""
shared/storage/minio_client.py — MinIO (S3-compatible) client wrapper.
"""

import logging
import os
from io import BytesIO

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.environ.get("MINIO_SECRET_KEY", "minio_secret"),
            secure=os.environ.get("MINIO_USE_SSL", "false").lower() == "true",
        )
        logger.info(
            "MinIO client created — endpoint=%s", os.environ.get("MINIO_ENDPOINT")
        )
    return _client


def ensure_bucket(bucket: str) -> None:
    """Create bucket if it doesn't exist."""
    client = get_minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("MinIO bucket created: %s", bucket)


def upload_file(
    bucket: str,
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload bytes to MinIO. Returns the object URL."""
    client = get_minio_client()
    ensure_bucket(bucket)
    client.put_object(
        bucket,
        object_name,
        data=BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    return f"http://{endpoint}/{bucket}/{object_name}"


def get_presigned_url(bucket: str, object_name: str, expires_hours: int = 1) -> str:
    """Generate a pre-signed URL for temporary access."""
    from datetime import timedelta

    client = get_minio_client()
    return client.presigned_get_object(
        bucket, object_name, expires=timedelta(hours=expires_hours)
    )


def delete_file(bucket: str, object_name: str) -> None:
    client = get_minio_client()
    try:
        client.remove_object(bucket, object_name)
    except S3Error as exc:
        logger.warning(
            "MinIO delete failed: bucket=%s object=%s error=%s",
            bucket,
            object_name,
            exc,
        )
