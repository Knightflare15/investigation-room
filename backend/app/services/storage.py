from __future__ import annotations

from pathlib import Path

from ..config import Settings


class AssetStorage:
    def __init__(self, settings: Settings, cases_root: Path) -> None:
        self.settings = settings
        self.cases_root = cases_root

    @property
    def uses_r2(self) -> bool:
        return bool(
            self.settings.r2_endpoint_url
            and self.settings.r2_access_key_id
            and self.settings.r2_secret_access_key
            and self.settings.r2_bucket
            and self.settings.r2_public_base_url
        )

    def put(self, case_id: str, relative_path: Path, content: bytes, content_type: str) -> str:
        key = f"{case_id}/assets/{relative_path.as_posix()}"
        if self.uses_r2:
            client = self._r2_client()
            client.put_object(
                Bucket=self.settings.r2_bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )
            return f"{self.settings.r2_public_base_url.rstrip('/')}/{key}"

        target = self.cases_root / case_id / "assets" / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return f"/case-assets/{case_id}/assets/{relative_path.as_posix()}"

    def delete_case_assets(self, case_id: str) -> None:
        if not self.uses_r2:
            return
        client = self._r2_client()
        paginator = client.get_paginator("list_objects_v2")
        prefix = f"{case_id}/assets/"
        for page in paginator.paginate(Bucket=self.settings.r2_bucket, Prefix=prefix):
            objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if objects:
                client.delete_objects(Bucket=self.settings.r2_bucket, Delete={"Objects": objects, "Quiet": True})

    def _r2_client(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("R2 storage requires boto3") from exc
        return boto3.client(
            "s3",
            endpoint_url=self.settings.r2_endpoint_url,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            region_name="auto",
        )
