import io
from datetime import timedelta
from functools import lru_cache
from typing import Optional

from minio import Minio

from src.common.config import settings


@lru_cache
def get_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket() -> None:
    client = get_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def upload_file(local_path: str, key: str, content_type: Optional[str] = None) -> None:
    get_client().fput_object(
        settings.minio_bucket,
        key,
        local_path,
        content_type=content_type or "application/octet-stream",
    )


def upload_bytes(data: bytes, key: str, content_type: str) -> None:
    get_client().put_object(
        settings.minio_bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def download_file(key: str, local_path: str) -> None:
    get_client().fget_object(settings.minio_bucket, key, local_path)


def presigned_get(key: str, expires: Optional[int] = None) -> str:
    return get_client().presigned_get_object(
        settings.minio_bucket,
        key,
        expires=timedelta(seconds=expires or settings.signed_url_expire),
    )


def delete_object(key: str) -> None:
    try:
        get_client().remove_object(settings.minio_bucket, key)
    except Exception:
        pass
