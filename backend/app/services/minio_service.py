from __future__ import annotations

import io
from urllib.parse import urljoin

import boto3
import httpx
from botocore.config import Config as BotoConfig

from app.config import settings


class MinioService:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.minio_endpoint,
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                config=BotoConfig(signature_version="s3v4"),
                region_name="us-east-1",
            )
            self._ensure_bucket()
        return self._client

    def _ensure_bucket(self):
        try:
            self._client.head_bucket(Bucket=settings.minio_bucket_name)
        except Exception:
            self._client.create_bucket(Bucket=settings.minio_bucket_name)

    async def upload_from_bytes(self, data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
        client = self._get_client()
        client.put_object(
            Bucket=settings.minio_bucket_name,
            Key=object_name,
            Body=io.BytesIO(data),
            ContentType=content_type,
        )
        return self.get_public_url(object_name)

    async def upload_from_url(self, file_url: str, object_name: str, content_type: str = "application/octet-stream") -> str:
        async with httpx.AsyncClient(timeout=60) as http_client:
            resp = await http_client.get(file_url)
            resp.raise_for_status()
            return await self.upload_from_bytes(resp.content, object_name, content_type)

    def get_public_url(self, object_name: str) -> str:
        base = settings.minio_public_url.rstrip("/")
        return f"{base}/{settings.minio_bucket_name}/{object_name}"


minio_service = MinioService()
