import httpx
from config.settings import Settings


class TokenManager:
    """Manages tenant access token for Feishu API calls."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token: str | None = None
        self._expires_at: float = 0

    async def get_tenant_access_token(self) -> str:
        """Get or refresh tenant access token."""
        import time
        if self._token and time.time() < self._expires_at - 60:
            return self._token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self._settings.app_id,
                    "app_secret": self._settings.app_secret,
                },
            )
            result = resp.json()
            
            if result.get("code") != 0:
                raise RuntimeError(f"Failed to get token: {result.get('msg', resp.text)}")
            
            self._token = result["tenant_access_token"]
            self._expires_at = time.time() + result["expire"]
            return self._token
