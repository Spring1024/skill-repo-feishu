"""飞书云空间机器人 — 入口程序。

启动方式：
    python -m feishu_drive_bot  # or: python main.py

依赖 Hermes 提供 WebSocket 长连接、事件接收和消息发送能力。
本程序聚焦业务逻辑：命令解析、卡片交互、云空间操作。
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure the project root is on sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import structlog

from config.settings import Settings
from core.cache import FolderCache
from core.token_manager import TokenManager
from handlers.card_handler import CardHandler
from handlers.command_handler import CommandHandler
from handlers.event_handler import EventHandler
from services.drive_service import DriveService
from services.file_ops_service import FileOpsService
from services.permission_service import PermissionService


def _setup() -> tuple[Settings, FolderCache, DriveService, PermissionService, FileOpsService, CommandHandler, CardHandler]:
    """Initialize all components."""
    settings = Settings()

    token_mgr = TokenManager(settings)
    cache = FolderCache(ttl=settings.folder_cache_ttl)

    drive_service = DriveService(settings, token_mgr)
    permission_service = PermissionService(token_mgr)
    file_ops = FileOpsService(drive_service, permission_service)

    cmd_handler = CommandHandler(settings, drive_service, permission_service, file_ops, cache)
    card_handler = CardHandler(settings, drive_service, permission_service, file_ops, cache)

    return settings, cache, drive_service, permission_service, file_ops, cmd_handler, card_handler


async def main() -> None:
    """Main entry point."""
    # Setup logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logger = structlog.get_logger()

    try:
        settings, cache, drive_svc, perm_svc, file_ops, cmd_handler, card_handler = _setup()
    except Exception as e:
        logger.error("config_error", error=str(e))
        raise

    event_handler = EventHandler(cmd_handler, card_handler)

    # ---- Hermes integration ----
    # TODO: Replace with actual Hermes client initialization.
    # The pattern below shows how to wire up your Hermes SDK:
    #
    #   from hermes import HermesClient
    #
    #   hermes = HermesClient(
    #       app_id=settings.app_id,
    #       app_secret=settings.app_secret,
    #   )
    #
    #   async def _on_message(chat_id: str, sender_id: str, content: str):
    #       await event_handler.on_message(chat_id, sender_id, content)
    #
    #   async def _on_card_callback(chat_id: str, action: str, value: dict):
    #       await event_handler.on_card_callback(chat_id, action, value)
    #
    #   hermes.on_message(_on_message)
    #   hermes.on_card_callback(_on_card_callback)
    #   await hermes.start()
    #
    # For now, we just log readiness:
    logger.info(
        "ready",
        app_id=settings.app_id[:8] + "...",
        commands=["/create-folder", "/upload", "/download", "/update", "/help"],
    )

    # Keep running
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
