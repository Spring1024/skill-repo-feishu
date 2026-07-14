from __future__ import annotations

import httpx

from core.token_manager import TokenManager


_API_BASE = "https://open.feishu.cn/open-apis"


class PermissionService:
    """Manages file/folder permissions via Feishu Drive permission APIs."""

    def __init__(self, token_mgr: TokenManager) -> None:
        self._token_mgr = token_mgr

    async def _get_token(self) -> str:
        return await self._token_mgr.get_tenant_access_token()

    async def set_org_readable(self, file_token: str) -> dict:
        """Set file/folder permission: organization-wide readable.

        Uses POST /open-apis/drive/v1/permissions/{file_token}/share_link
        to create a sharing link with visibility=tenant_read_all.

        This makes the file accessible to everyone in the organization.
        """
        token = await self._get_token()
        url = f"{_API_BASE}/drive/v1/permissions/{file_token}/share_link"

        body = {
            "external_access_entity": False,
            "is_external": False,
            "link_entity": {
                "status": 1,
                "visibility": "tenant_read_all",
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})

        result = resp.json()
        if resp.status_code != 200 or result.get("code", 0) != 0:
            raise RuntimeError(
                f"Failed to set org-readable permission for '{file_token}': {result.get('msg', resp.text)}"
            )

        share_link = result["data"].get("link_entity", {}).get("url", "")
        return {"file_token": file_token, "permission": "tenant_read_all", "share_link": share_link}

    async def get_sharing_link(self, file_token: str) -> str | None:
        """Get the existing sharing link URL for a file."""
        token = await self._get_token()
        url = f"{_API_BASE}/drive/v1/permissions/{file_token}/share_link"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

        result = resp.json()
        if resp.status_code != 200 or result.get("code", 0) != 0:
            return None

        link_entity = result["data"].get("link_entity", {})
        return link_entity.get("url") if link_entity else None
