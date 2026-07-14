from __future__ import annotations

import time

import httpx

from config.settings import Settings


_API_BASE = "https://open.feishu.cn/open-apis"


class TokenManager:
    """Manages tenant access tokens via Feishu official API with auto-refresh."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token: str | None = None
        self._expire_time: float = 0

    async def get_tenant_access_token(self) -> str:
        if self._token and time.time() < self._expire_time - 300:
            return self._token

        url = f"{_API_BASE}/auth/v3/tenant_access_token/internal"
        body = {"app_id": self._settings.app_id, "app_secret": self._settings.app_secret}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=body)

        result = resp.json()
        if resp.status_code != 200 or result.get("code", 0) != 0:
            raise RuntimeError(f"Failed to get tenant access token: {result.get('msg', resp.text)}")

        self._token = result["data"]["tenant_access_token"]
        expire = result["data"].get("expire", 7200)
        self._expire_time = time.time() + expire
        return self._token
