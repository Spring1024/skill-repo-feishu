from __future__ import annotations

from config.settings import Settings
from core.cache import FolderCache
from services.drive_service import DriveService
from services.file_ops_service import FileOpsService
from services.permission_service import PermissionService
from cards import (
    build_error_card,
    build_folder_picker_card,
    build_help_card,
    build_success_card,
)


class CommandHandler:
    """Handles chat commands like /upload, /download, /create-folder, /update."""

    def __init__(
        self,
        settings: Settings,
        drive_service: DriveService,
        permission_service: PermissionService,
        file_ops: FileOpsService,
        cache: FolderCache,
    ) -> None:
        self._settings = settings
        self._drive = drive_service
        self._permission = permission_service
        self._file_ops = file_ops
        self._cache = cache

    async def handle_command(
        self,
        chat_id: str,
        sender_id: str,
        content: str,
        send_callback,
    ) -> None:
        """Main entry point for command handling.

        Args:
            chat_id: The chat where the command was sent
            sender_id: The user who sent the command
            content: The raw message content
            send_callback: Async callable(send_message_dict) to send messages back
        """
        content = content.strip()

        if content.startswith("/create-folder"):
            name = content[len("/create-folder"):].strip()
            if not name:
                await send_callback(build_error_card(
                    "错误", "_请提供文件夹名称_，例如：`/create-folder MyFolder`"
                ))
                return
            await self._handle_create_folder(name, chat_id, send_callback)

        elif content == "/upload":
            await self._handle_upload(chat_id, send_callback)

        elif content == "/download":
            await self._handle_download(chat_id, send_callback)

        elif content == "/update":
            await self._handle_update(chat_id, send_callback)

        elif content == "/help":
            await send_callback(build_help_card(chat_id))

        else:
            await send_callback(build_error_card(
                "未知命令",
                "_请使用 `/help` 查看可用命令_",
            ))

    async def _handle_create_folder(
        self, name: str, chat_id: str, send_callback
    ) -> None:
        try:
            result = await self._drive.create_folder(name)
            await self._permission.set_org_readable(result.file_token)
            self._cache.invalidate()
            await send_callback(build_success_card(
                "文件夹已创建",
                f"**{result.file_name}** 已创建成功\n"
                f"权限：组织内所有人可读\n"
                f"Token: `{result.file_token}`",
                chat_id,
            ))
        except Exception as e:
            await send_callback(build_error_card("创建失败", f"_错误：{str(e)}_", chat_id))

    async def _handle_upload(self, chat_id: str, send_callback) -> None:
        try:
            root_token = self._drive._root_token()
            items = await self._cache.get_or_set(root_token, lambda: self._list_and_cache(root_token))
            card = build_folder_picker_card(items, parent_token=root_token, chat_id=chat_id, mode="upload")
            await send_callback(card)
        except Exception as e:
            await send_callback(build_error_card("加载文件夹失败", f"_错误：{str(e)}_", chat_id))

    async def _handle_download(self, chat_id: str, send_callback) -> None:
        try:
            root_token = self._drive._root_token()
            items = await self._cache.get_or_set(root_token, lambda: self._list_and_cache(root_token))
            card = build_folder_picker_card(items, parent_token=root_token, chat_id=chat_id, mode="download")
            await send_callback(card)
        except Exception as e:
            await send_callback(build_error_card("加载文件夹失败", f"_错误：{str(e)}_", chat_id))

    async def _handle_update(self, chat_id: str, send_callback) -> None:
        try:
            root_token = self._drive._root_token()
            items = await self._cache.get_or_set(root_token, lambda: self._list_and_cache(root_token))
            files = [i for i in items if i.get("type") != "folder"]
            card = build_folder_picker_card(files, parent_token=root_token, chat_id=chat_id, mode="update")
            await send_callback(card)
        except Exception as e:
            await send_callback(build_error_card("加载文件列表失败", f"_错误：{str(e)}_", chat_id))

    async def _list_and_cache(self, parent_token: str) -> list[dict]:
        result = await self._drive.list_folder(parent_token)
        items = [
            {"file_token": f.file_token, "file_name": f.file_name, "type": f.type,
             "size": f.size, "last_modified_time": f.last_modified_time}
            for f in result.items
        ]
        self._cache.set(parent_token, items)
        return items
