"""Almacenamiento de objetos en MinIO."""

import io
import logging
from functools import lru_cache

from minio import Minio

from app.core.config import get_settings

log = logging.getLogger("papasana")


class StorageService:
    def __init__(self, client: Minio):
        self.client = client

    def ensure_bucket(self, bucket: str) -> None:
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)

    def put_bytes(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self.ensure_bucket(bucket)
        self.client.put_object(bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)

    def get_bytes(self, bucket: str, key: str) -> bytes:
        resp = self.client.get_object(bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def remove(self, bucket: str, key: str) -> None:
        try:
            self.client.remove_object(bucket, key)
        except Exception:
            log.warning("No se pudo eliminar %s/%s", bucket, key)


@lru_cache
def _client() -> Minio:
    s = get_settings()
    return Minio(s.minio_endpoint, access_key=s.minio_access_key, secret_key=s.minio_secret_key,
                 secure=s.minio_secure)


def get_storage() -> StorageService:
    return StorageService(_client())
