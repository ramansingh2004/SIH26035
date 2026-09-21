"""Create a NEW private versioned development bucket. Never changes an existing bucket."""

import asyncio

from app.core.config import Settings
from app.storage.objects import create_storage


async def main():
    settings = Settings()
    if (
        settings.environment != "development"
        or not settings.storage_bucket
        or not settings.storage_bucket.endswith("-dev")
    ):
        raise RuntimeError("Use development settings and a fresh bucket ending in -dev")
    storage = create_storage(settings)
    # list_buckets also refuses accidental reconfiguration of existing evidence storage.
    existing = await storage.call("list_buckets")
    if any(item["Name"] == storage.bucket for item in existing.get("Buckets", [])):
        raise RuntimeError("Bucket already exists; choose a new disposable development bucket")
    params = {"Bucket": storage.bucket}
    if settings.storage_provider == "s3" and settings.storage_region != "us-east-1":
        params["CreateBucketConfiguration"] = {"LocationConstraint": settings.storage_region}
    await storage.call("create_bucket", **params)
    if settings.storage_provider == "s3":
        await storage.call(
            "put_public_access_block",
            Bucket=storage.bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
    await storage.call(
        "put_bucket_versioning",
        Bucket=storage.bucket,
        VersioningConfiguration={"Status": "Enabled"},
    )
    await storage.ready()
    print("New private versioned development bucket configured")


if __name__ == "__main__":
    asyncio.run(main())
