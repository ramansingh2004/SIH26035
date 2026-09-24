"""Private version-pinned storage adapters. SDK I/O stays off the event loop."""

import asyncio
import hashlib
import io
import re
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.errors import AppError

KEY = re.compile(
    r"^(staged|evidence|reports|previews)/"
    r"[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f]{32}$"
)
MAX_SIZE = 25 * 1024 * 1024


def safe_key(key):
    if not KEY.fullmatch(key):
        raise AppError(422, "INVALID_STORAGE_KEY", "Invalid server storage key")
    return key


@dataclass(frozen=True)
class StoredObject:
    body: bytes
    content_type: str
    version: str


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _valid_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            return {
                "[Content_Types].xml",
                "_rels/.rels",
                "word/document.xml",
            } <= names
    except (zipfile.BadZipFile, OSError):
        return False


def verify_content(obj: StoredObject, size: int, content_type: str, sha256: str):
    if len(obj.body) != size or size > MAX_SIZE:
        raise AppError(422, "ATTACHMENT_SIZE_MISMATCH", "Stored size differs from declared size")
    signatures = {
        "application/pdf": obj.body.startswith(b"%PDF-") and b"%%EOF" in obj.body[-1024:],
        "image/png": obj.body.startswith(b"\x89PNG\r\n\x1a\n")
        and obj.body.endswith(b"IEND\xaeB`\x82"),
        "image/jpeg": obj.body.startswith(b"\xff\xd8\xff") and obj.body.endswith(b"\xff\xd9"),
        DOCX_MIME: _valid_docx(obj.body),
    }
    if obj.content_type != content_type or not signatures.get(content_type, False):
        raise AppError(422, "ATTACHMENT_TYPE_MISMATCH", "Declared and stored media types differ")
    actual = hashlib.sha256(obj.body).hexdigest()
    if actual != sha256:
        raise AppError(422, "ATTACHMENT_HASH_MISMATCH", "Stored content digest differs")
    return actual


class ObjectStorage(ABC):
    provider: str

    @abstractmethod
    async def ready(self): ...

    @abstractmethod
    async def presign_upload(self, key, content_type, size, seconds): ...

    @abstractmethod
    async def read(self, key, version=None) -> StoredObject: ...

    @abstractmethod
    async def publish(self, key, obj: StoredObject) -> str: ...

    @abstractmethod
    async def presign_download(self, key, version, seconds): ...

    async def delete_staged(self, key):
        raise NotImplementedError


class S3Storage(ObjectStorage):
    provider = "s3"

    def __init__(self, settings):
        self.bucket = settings.storage_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint,
            region_name=settings.storage_region,
            aws_access_key_id=settings.storage_access_key.get_secret_value(),
            aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=15,
                retries={"max_attempts": 2},
                s3={"addressing_style": "path"},
            ),
        )

    async def call(self, method, **kwargs):
        try:
            return await asyncio.to_thread(getattr(self.client, method), **kwargs)
        except (BotoCoreError, ClientError):
            # SDK exceptions may include URLs/keys; never forward them to API/audit.
            raise AppError(
                503, "STORAGE_UNAVAILABLE", "Private object storage operation failed"
            ) from None

    async def ready(self):
        versioning = await self.call("get_bucket_versioning", Bucket=self.bucket)
        if versioning.get("Status") != "Enabled":
            raise AppError(503, "STORAGE_NOT_PRIVATE", "Versioned private bucket required")
        await self._privacy()

    async def _privacy(self):
        settings = await self.call("get_public_access_block", Bucket=self.bucket)
        block = settings.get("PublicAccessBlockConfiguration", {})
        if not all(
            block.get(k) is True
            for k in (
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            )
        ):
            raise AppError(503, "STORAGE_NOT_PRIVATE", "All public-access blocks must be enabled")

    async def presign_upload(self, key, content_type, size, seconds):
        return await self.call(
            "generate_presigned_url",
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket,
                "Key": safe_key(key),
                "ContentType": content_type,
                "ContentLength": size,
            },
            ExpiresIn=seconds,
            HttpMethod="PUT",
        )

    async def read(self, key, version=None):
        args = {"Bucket": self.bucket, "Key": safe_key(key)}
        if version:
            args["VersionId"] = version
        result = await self.call("get_object", **args)
        body = result["Body"]
        try:
            if result["ContentLength"] > MAX_SIZE:
                raise AppError(422, "ATTACHMENT_SIZE_MISMATCH", "Stored object exceeds size limit")
            data = await asyncio.to_thread(body.read, MAX_SIZE + 1)
        except BotoCoreError:
            raise AppError(503, "STORAGE_UNAVAILABLE", "Object stream failed") from None
        finally:
            await asyncio.to_thread(body.close)
        version_id = result.get("VersionId")
        if not version_id or version_id == "null":
            raise AppError(503, "STORAGE_VERSION_REQUIRED", "Immutable object version required")
        return StoredObject(data, result.get("ContentType", ""), version_id)

    async def publish(self, key, obj):
        key = safe_key(key)
        if not key.startswith(("evidence/", "reports/", "previews/")):
            raise AppError(422, "INVALID_STORAGE_KEY", "Published prefix required")
        result = await self.call(
            "put_object", Bucket=self.bucket, Key=key, Body=obj.body, ContentType=obj.content_type
        )
        version = result.get("VersionId")
        if not version or version == "null":
            raise AppError(503, "STORAGE_VERSION_REQUIRED", "Immutable object version required")
        # Verify published bytes too, before any database attachment becomes visible.
        stored = await self.read(key, version)
        if stored.body != obj.body or stored.content_type != obj.content_type:
            raise AppError(503, "STORAGE_INTEGRITY_FAILED", "Published object verification failed")
        return version

    async def presign_download(self, key, version, seconds):
        return await self.call(
            "generate_presigned_url",
            ClientMethod="get_object",
            Params={
                "Bucket": self.bucket,
                "Key": safe_key(key),
                "VersionId": version,
                "ResponseContentDisposition": "attachment",
                "ResponseCacheControl": "no-store",
            },
            ExpiresIn=seconds,
            HttpMethod="GET",
        )

    async def delete_staged(self, key):
        key = safe_key(key)
        if not key.startswith("staged/"):
            raise AppError(
                422,
                "INVALID_STORAGE_KEY",
                "Cleanup is restricted to staged upload objects",
            )
        result = await self.call(
            "list_object_versions",
            Bucket=self.bucket,
            Prefix=key,
        )
        if result.get("IsTruncated"):
            raise AppError(
                503,
                "STORAGE_UNAVAILABLE",
                "Staged object version listing was truncated",
            )

        matches = [
            item
            for collection in (
                result.get("Versions", ()),
                result.get("DeleteMarkers", ()),
            )
            for item in collection
            if item.get("Key") == key and item.get("VersionId")
        ]
        for item in matches:
            await self.call(
                "delete_object",
                Bucket=self.bucket,
                Key=key,
                VersionId=item["VersionId"],
            )
        return len(matches)


class MinioStorage(S3Storage):
    provider = "minio"

    async def _privacy(self):
        # MinIO is private by default and does not implement AWS public-access blocks.
        # Reject every bucket policy: this deployment foundation permits IAM-only access.
        try:
            await asyncio.to_thread(self.client.get_bucket_policy, Bucket=self.bucket)
        except ClientError as error:
            if error.response["Error"]["Code"] == "NoSuchBucketPolicy":
                return
        except BotoCoreError:
            pass
        raise AppError(
            503, "STORAGE_NOT_PRIVATE", "MinIO bucket must have no anonymous bucket policy"
        )


def create_storage(settings):
    if not all((settings.storage_bucket, settings.storage_access_key, settings.storage_secret_key)):
        raise AppError(503, "STORAGE_NOT_CONFIGURED", "Configure private object storage")
    if settings.storage_provider == "minio" and not settings.storage_endpoint:
        raise AppError(503, "STORAGE_NOT_CONFIGURED", "MinIO endpoint required")
    return (MinioStorage if settings.storage_provider == "minio" else S3Storage)(settings)
