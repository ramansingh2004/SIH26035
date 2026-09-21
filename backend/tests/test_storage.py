"""Isolated adapter/content tests, not a MinIO/S3 integration acceptance claim."""

import hashlib
import io
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.foundations import EquipmentData, EquipmentView, UploadRequest
from app.services.equipment import calibration_snapshot
from app.storage.objects import (
    MinioStorage,
    S3Storage,
    StoredObject,
    create_storage,
    safe_key,
    verify_content,
)

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"


def test_content_hash_and_size():
    digest = hashlib.sha256(PDF).hexdigest()
    assert (
        verify_content(
            StoredObject(PDF, "application/pdf", "v1"), len(PDF), "application/pdf", digest
        )
        == digest
    )


@pytest.mark.parametrize("kind", ["size", "mime", "signature", "hash"])
def test_content_mismatch(kind):
    obj = StoredObject(
        PDF if kind != "signature" else b"x" * len(PDF),
        "text/plain" if kind == "mime" else "application/pdf",
        "v1",
    )
    with pytest.raises(AppError) as error:
        verify_content(
            obj,
            len(PDF) + (kind == "size"),
            "application/pdf",
            "0" * 64 if kind == "hash" else hashlib.sha256(PDF).hexdigest(),
        )
    assert error.value.status == 422


@pytest.mark.parametrize(
    "key", ["../secret", "staged/other", "https://bucket/object", "/evidence/x", "evidence/%2e%2e"]
)
def test_storage_keys_are_server_shapes(key):
    with pytest.raises(AppError):
        safe_key(key)


@pytest.mark.parametrize("name", ["../x.pdf", "x\\y.png", "x\r\n.pdf", ".."])
def test_unsafe_filename(name):
    with pytest.raises(ValidationError):
        UploadRequest(
            entity_type="test_equipment",
            entity_id=uuid4(),
            purpose="certificate",
            laboratory_id=uuid4(),
            file_name=name,
            content_type="application/pdf",
            file_size=10,
            sha256="0" * 64,
        )


def test_client_cannot_claim_a_storage_key():
    with pytest.raises(ValidationError):
        UploadRequest(
            entity_type="test_equipment",
            entity_id=uuid4(),
            purpose="certificate",
            laboratory_id=uuid4(),
            file_name="x.pdf",
            content_type="application/pdf",
            file_size=10,
            sha256="0" * 64,
            storage_key="stolen",
        )


def test_equipment_snapshot_preserves_exact_facts_and_is_frozen():
    now = datetime.now(UTC)
    equipment = EquipmentView(
        id=uuid4(),
        laboratory_id=uuid4(),
        created_by=uuid4(),
        created_at=now,
        updated_at=now,
        lock_version=3,
        is_active=True,
        category="Mass",
        metadata_json={"nominal_mass_g": "1000.000001"},
    )
    snapshot = calibration_snapshot(equipment, now)
    assert snapshot.nominal_mass_g == Decimal("1000.000001")
    assert snapshot.model_dump(mode="json")["nominal_mass_g"] == "1000.000001"
    assert snapshot.equipment_version == 3
    assert snapshot.regulatory_validation_status == "TODO_REGULATORY_VALIDATION"
    with pytest.raises(ValidationError):
        snapshot.equipment_version = 4
    with pytest.raises(ValidationError):
        EquipmentData(
            category="Mass", calibration_date="2026-06-01", calibration_due_date="2026-01-01"
        )


def test_storage_configuration_closed_and_private(
    monkeypatch: pytest.MonkeyPatch,
):
    for variable in (
        "STORAGE_PROVIDER",
        "STORAGE_ENDPOINT",
        "STORAGE_BUCKET",
        "STORAGE_ACCESS_KEY",
        "STORAGE_SECRET_KEY",
        "STORAGE_REGION",
    ):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings(_env_file=None)

    with pytest.raises(AppError, match="Configure"):
        create_storage(settings)


def adapter(kind=S3Storage):
    result = object.__new__(kind)
    result.bucket = "private"
    result.client = MagicMock()
    return result


@pytest.mark.asyncio
async def test_s3_requires_private_versioned_bucket():
    storage = adapter()
    storage.client.get_bucket_versioning.return_value = {"Status": "Suspended"}
    with pytest.raises(AppError):
        await storage.ready()
    storage.client.get_bucket_versioning.return_value = {"Status": "Enabled"}
    storage.client.get_public_access_block.return_value = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
    }
    await storage.ready()
    storage.client.get_public_access_block.return_value = {}
    with pytest.raises(AppError):
        await storage.ready()


@pytest.mark.asyncio
async def test_minio_rejects_bucket_policy():
    storage = adapter(MinioStorage)
    storage.client.get_bucket_versioning.return_value = {"Status": "Enabled"}
    with pytest.raises(AppError):
        await storage.ready()
    storage.client.get_bucket_policy.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucketPolicy"}}, "GetBucketPolicy"
    )
    await storage.ready()


@pytest.mark.asyncio
async def test_read_pins_versions_closes_stream_and_download_is_private():
    storage = adapter()
    key = f"evidence/{uuid4()}/{uuid4()}/{uuid4().hex}"
    body = io.BytesIO(PDF)
    storage.client.get_object.return_value = {
        "Body": body,
        "ContentLength": len(PDF),
        "ContentType": "application/pdf",
        "VersionId": "v1",
    }
    result = await storage.read(key, "v1")
    assert result.body == PDF and body.closed
    assert storage.client.get_object.call_args.kwargs["VersionId"] == "v1"
    await storage.presign_download(key, "v1", 60)
    params = storage.client.generate_presigned_url.call_args.kwargs
    assert params["Params"]["VersionId"] == "v1"
    assert params["ExpiresIn"] == 60
    assert params["Params"]["ResponseContentDisposition"] == "attachment"
