from __future__ import annotations

import httpx

from config.settings import Settings
from core.token_manager import TokenManager
from models import DriveCreateResponse, DriveFileListResponse, FileListItem


_API_BASE = "https://open.feishu.cn/open-apis"
_UPLOAD_THRESHOLD = 20 * 1024 * 1024  # 20MB


class DriveService:
    """Direct HTTP calls to Feishu Drive official REST APIs."""

    def __init__(self, settings: Settings, token_mgr: TokenManager) -> None:
        self._settings = settings
        self._token_mgr = token_mgr

    async def _get_token(self) -> str:
        return await self._token_mgr.get_tenant_access_token()

    def _root_token(self) -> str:
        return self._settings.default_root_folder_token or "root"

    async def create_folder(
        self, name: str, parent_token: str | None = None
    ) -> DriveCreateResponse:
        token = await self._get_token()
        parent_ref = parent_token or self._root_token()
        url = f"{_API_BASE}/drive/v1/files/create_folder"

        data = {"name": name, "folder_token": parent_ref}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=data, headers={"Authorization": f"Bearer {token}"})

        result = resp.json()
        if resp.status_code != 200 or result.get("code", 0) != 0:
            raise RuntimeError(f"Failed to create folder '{name}': {result.get('msg', resp.text)}")

        fi = result["data"]
        return DriveCreateResponse(
            file_token=fi.get("token", ""),
            file_name=fi.get("name", name),
            type="folder",
        )

    async def list_folder(
        self, parent_token: str | None = None, page_token: str | None = None
    ) -> DriveFileListResponse:
        token = await self._get_token()
        ref = parent_token or self._root_token()
        url = f"{_API_BASE}/drive/v1/files"

        params = {"parent_node": ref}
        if page_token:
            params["page_token"] = page_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})

        result = resp.json()
        if resp.status_code != 200 or result.get("code", 0) != 0:
            raise RuntimeError(f"Failed to list folder '{ref}': {result.get('msg', resp.text)}")

        items = [
            FileListItem(
                file_token=f.get("file_token", ""),
                file_name=f.get("file_name", ""),
                type=f.get("type", "file"),
                size=f.get("size", 0),
                last_modified_time=f.get("last_modified_time", ""),
            )
            for f in result["data"].get("files", [])
        ]

        return DriveFileListResponse(
            items=items,
            has_more=result["data"].get("has_more", False),
            page_token=result["data"].get("page_token"),
        )

    async def upload_file(
        self, file_name: str, file_data: bytes, parent_token: str | None = None
    ) -> DriveCreateResponse:
        """Upload file. Uses simple multipart for ≤20MB, chunked upload otherwise."""
        token = await self._get_token()
        parent_ref = parent_token or self._root_token()

        if len(file_data) <= _UPLOAD_THRESHOLD:
            return await self._upload_simple(token, file_name, file_data, parent_ref)

        return await self._upload_chunked(token, file_name, file_data, parent_ref)

    async def _upload_simple(
        self, token: str, file_name: str, file_data: bytes, parent_ref: str
    ) -> DriveCreateResponse:
        """Simple multipart upload for files ≤20MB."""
        url = f"{_API_BASE}/drive/v1/files"

        # Initialize upload session
        init_resp = await self._post_init(url, token, {"parent_node": parent_ref, "file_name": file_name})
        upload_id = init_resp["data"]["upload_id"]

        # Upload single chunk
        total_size = len(file_data)
        range_header = f"bytes 0-{total_size - 1}/{total_size}"

        async with httpx.AsyncClient(timeout=60) as client:
            chunk_resp = await client.post(
                f"{url}/{upload_id}/chunks",
                content=file_data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/octet-stream",
                    "Content-Range": range_header,
                },
            )
        chunk_result = chunk_resp.json()
        if chunk_resp.status_code != 200 or chunk_result.get("code", 0) != 0:
            raise RuntimeError(f"Failed to upload chunk: {chunk_result.get('msg', chunk_resp.text)}")

        # Complete
        complete_resp = await client.post(
            f"{url}/{upload_id}/complete",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        complete_result = complete_resp.json()
        if complete_resp.status_code != 200 or complete_result.get("code", 0) != 0:
            raise RuntimeError(f"Failed to complete upload: {complete_result.get('msg', complete_resp.text)}")

        fi = complete_result["data"]
        return DriveCreateResponse(
            file_token=fi.get("file_token", ""),
            file_name=fi.get("file_name", file_name),
            type="file",
        )

    async def _upload_chunked(
        self, token: str, file_name: str, file_data: bytes, parent_ref: str
    ) -> DriveCreateResponse:
        """Chunked upload for files >20MB."""
        url = f"{_API_BASE}/drive/v1/files"
        CHUNK_SIZE = 4 * 1024 * 1024  # 4MB per chunk

        init_resp = await self._post_init(url, token, {"parent_node": parent_ref, "file_name": file_name})
        upload_id = init_resp["data"]["upload_id"]
        total_size = len(file_data)

        async with httpx.AsyncClient(timeout=120) as client:
            offset = 0
            while offset < total_size:
                chunk = file_data[offset:offset + CHUNK_SIZE]
                chunk_end = min(offset + len(chunk), total_size) - 1
                range_header = f"bytes {offset}-{chunk_end}/{total_size}"

                chunk_resp = await client.post(
                    f"{url}/{upload_id}/chunks",
                    content=chunk,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/octet-stream",
                        "Content-Range": range_header,
                    },
                )
                chunk_result = chunk_resp.json()
                if chunk_resp.status_code != 200 or chunk_result.get("code", 0) != 0:
                    raise RuntimeError(f"Failed to upload chunk: {chunk_result.get('msg', chunk_resp.text)}")
                offset += len(chunk)

            complete_resp = await client.post(
                f"{url}/{upload_id}/complete",
                json={},
                headers={"Authorization": f"Bearer {token}"},
            )
            complete_result = complete_resp.json()
            if complete_resp.status_code != 200 or complete_result.get("code", 0) != 0:
                raise RuntimeError(f"Failed to complete upload: {complete_result.get('msg', complete_resp.text)}")

        fi = complete_result["data"]
        return DriveCreateResponse(
            file_token=fi.get("file_token", ""),
            file_name=fi.get("file_name", file_name),
            type="file",
        )

    async def _post_init(self, url: str, token: str, data: dict) -> dict:
        """Initialize an upload session and return parsed response."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={**data, "type": "file"},
                                     headers={"Authorization": f"Bearer {token}"})
        result = resp.json()
        if resp.status_code != 200 or result.get("code", 0) != 0:
            raise RuntimeError(f"Failed to init upload: {result.get('msg', resp.text)}")
        return result

    async def download_file(self, file_token: str) -> bytes:
        token = await self._get_token()
        url = f"{_API_BASE}/drive/v1/files/{file_token}/download"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

        if resp.status_code != 200:
            result = resp.json()
            raise RuntimeError(f"Failed to download file '{file_token}': {result.get('msg', resp.text)}")

        return resp.content

    async def update_file(
        self, file_token: str, new_file_data: bytes, new_file_name: str | None = None
    ) -> DriveCreateResponse:
        """Overwrite file content using chunked upload API."""
        token = await self._get_token()
        url = f"{_API_BASE}/drive/v1/files"
        CHUNK_SIZE = 4 * 1024 * 1024

        # Initialize with file_token to target existing file
        init_data = {"type": "file"}
        if new_file_name:
            init_data["file_name"] = new_file_name

        init_resp = await self._post_init_with_token(url, token, file_token, init_data)
        upload_id = init_resp["data"]["upload_id"]
        total_size = len(new_file_data)

        async with httpx.AsyncClient(timeout=120) as client:
            offset = 0
            while offset < total_size:
                chunk = new_file_data[offset:offset + CHUNK_SIZE]
                chunk_end = min(offset + len(chunk), total_size) - 1
                range_header = f"bytes {offset}-{chunk_end}/{total_size}"

                chunk_resp = await client.post(
                    f"{url}/{upload_id}/chunks",
                    content=chunk,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/octet-stream",
                        "Content-Range": range_header,
                    },
                )
                chunk_result = chunk_resp.json()
                if chunk_resp.status_code != 200 or chunk_result.get("code", 0) != 0:
                    raise RuntimeError(f"Failed to upload chunk: {chunk_result.get('msg', chunk_resp.text)}")
                offset += len(chunk)

            complete_resp = await client.post(
                f"{url}/{upload_id}/complete",
                json={},
                headers={"Authorization": f"Bearer {token}"},
            )
            complete_result = complete_resp.json()
            if complete_resp.status_code != 200 or complete_result.get("code", 0) != 0:
                raise RuntimeError(f"Failed to complete update: {complete_result.get('msg', complete_resp.text)}")

        fi = complete_result["data"]
        return DriveCreateResponse(
            file_token=fi.get("file_token", file_token),
            file_name=fi.get("file_name", new_file_name or ""),
            type="file",
        )

    async def _post_init_with_token(
        self, url: str, token: str, file_token: str, data: dict
    ) -> dict:
        """Initialize upload targeting a specific file_token."""
        init_url = f"{url}?file_token={file_token}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(init_url, json={**data, "type": "file"},
                                     headers={"Authorization": f"Bearer {token}"})
        result = resp.json()
        if resp.status_code != 200 or result.get("code", 0) != 0:
            raise RuntimeError(f"Failed to init upload for token '{file_token}': {result.get('msg', resp.text)}")
        return result
