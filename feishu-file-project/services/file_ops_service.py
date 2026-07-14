from __future__ import annotations

import os

from services.drive_service import DriveService
from services.permission_service import PermissionService


class FileOpsService:
    """Orchestrates file operations: validates local files, uploads/downloads, sets permissions."""

    CHUNK_THRESHOLD = 20 * 1024 * 1024  # 20MB

    def __init__(
        self,
        drive_service: DriveService,
        permission_service: PermissionService,
    ) -> None:
        self._drive = drive_service
        self._permission = permission_service

    async def upload_local_file(
        self,
        local_path: str,
        parent_token: str | None = None,
    ) -> dict:
        """Upload a local file to Feishu Drive with org-readable permission."""
        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")

        file_name = os.path.basename(local_path)
        with open(local_path, "rb") as f:
            file_data = f.read()

        result = await self._drive.upload_file(
            file_name=file_name,
            file_data=file_data,
            parent_token=parent_token,
        )

        # Set organization-readable permission
        await self._permission.set_org_readable(result.file_token)

        return {
            "file_token": result.file_token,
            "file_name": result.file_name,
            "type": result.type,
        }

    async def download_to_bytes(self, file_token: str) -> bytes:
        """Download file from Feishu Drive to memory."""
        return await self._drive.download_file(file_token)

    async def update_local_file(
        self,
        file_token: str,
        local_path: str,
    ) -> dict:
        """Overwrite a drive file with local file content."""
        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")

        file_name = os.path.basename(local_path)
        with open(local_path, "rb") as f:
            file_data = f.read()

        result = await self._drive.update_file(
            file_token=file_token,
            new_file_data=file_data,
            new_file_name=file_name,
        )

        return {
            "file_token": result.file_token,
            "file_name": result.file_name,
            "type": result.type,
        }
