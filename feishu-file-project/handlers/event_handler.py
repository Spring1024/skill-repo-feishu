from __future__ import annotations

import json
import re

from handlers.card_handler import CardHandler
from handlers.command_handler import CommandHandler


class EventHandler:
    """Bridges Hermes events to command and card handlers."""

    def __init__(self, cmd_handler: CommandHandler, card_handler: CardHandler) -> None:
        self._cmd_handler = cmd_handler
        self._card_handler = card_handler

    async def on_message(self, chat_id: str, sender_id: str, content: str) -> None:
        """Handle incoming text message from user."""
        content = content.strip()
        if not content:
            return

        # Strip leading @bot mention if present
        content = re.sub(r'^@.*?\s*', '', content)

        await self._cmd_handler.handle_command(
            chat_id=chat_id,
            sender_id=sender_id,
            content=content,
            send_callback=self._send_message,
        )

    async def on_card_callback(
        self,
        chat_id: str,
        action: str,
        value: dict,
    ) -> None:
        """Handle message card button callback."""
        await self._card_handler.handle_callback(
            chat_id=chat_id,
            action=action,
            value=value,
            send_callback=self._send_message,
        )

    async def _send_message(self, message_dict: dict) -> None:
        """Send a message back through Hermes.

        This is called by handlers to respond. The actual sending
        is delegated to Hermes which handles the WebSocket layer.
        In production, this should be overridden or configured
        to call Hermes's send API.

        For now, we log the message — the actual implementation
        depends on your Hermes integration.
        """
        import structlog
        logger = structlog.get_logger()
        msg_type = message_dict.get("msg_type", "unknown")
        logger.info("sending_message", type=msg_type, content=json.dumps(message_dict, ensure_ascii=False)[:500])
