from __future__ import annotations

from config.settings import Settings
from core.cache import FolderCache
from services.drive_service import DriveService
from services.file_ops_service import FileOpsService
from services.permission_service import PermissionService
from cards import (
    build_error_card,
    build_folder_picker_card,
    build_success_card,
    build_upload_input_card,
    build_update_input_card,
)


class CardHandler:
    """Handles message card button/callback interactions."""

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

    async def handle_callback(
        self,
        chat_id: str,
        action: str,
        value: dict,
        send_callback,
    ) -> None:
        """Process card callback actions.

        Args:
            chat_id: The chat where the callback originated
            action: The action type from card button value
            value: Parsed action value dict
            send_callback: Async callable(send_message_dict) to send messages back
        """
        handlers = {
            "select_folder": self._handle_select_folder,
            "go_up": self._handle_go_up,
            "select_file": self._handle_select_file,
            "download_file": self._handle_download_file,
            "update_file": self._handle_update_file_selection,
            "do_upload_from_folder": self._handle_do_upload_from_folder,
            "do_upload": self._handle_do_upload,
            "do_update": self._handle_do_update,
        }

        handler = handlers.get(action)
        if handler:
            await handler(chat_id, value, send_callback)
        else:
            await send_callback(build_error_card(
                "未知操作", f"_动作类型未识别：{action}_", chat_id
            ))

    async def _handle_select_folder(
        self, chat_id: str, value: dict, send_callback
    ) -> None:
        """User selected a subfolder — navigate into it."""
        folder_token = value.get("folder_token", "")
        parent_token = value.get("parent_token")

        try:
            items = await self._cache.get_or_set(folder_token, lambda: self._list_and_cache(folder_token))
            card = build_folder_picker_card(items, parent_token=folder_token, chat_id=chat_id)
            await send_callback(card)
        except Exception as e:
            await send_callback(build_error_card("加载失败", f"_错误：{str(e)}_", chat_id))

    async def _handle_go_up(
        self, chat_id: str, value: dict, send_callback
    ) -> None:
        """Navigate up one level."""
        parent_token = value.get("parent_token")
        if not parent_token:
            return

        try:
            items = await self._cache.get_or_set(parent_token, lambda: self._list_and_cache(parent_token))
            card = build_folder_picker_card(items, parent_token=None, chat_id=chat_id)
            await send_callback(card)
        except Exception as e:
            await send_callback(build_error_card("加载失败", f"_错误：{str(e)}_", chat_id))

    async def _handle_select_file(
        self, chat_id: str, value: dict, send_callback
    ) -> None:
        """Generic file selection — currently shows error with available actions."""
        file_name = value.get("file_name", "")
        await send_callback(build_error_card(
            "请选择操作",
            f"文件 **{file_name}** 已选中，请使用对应的命令（/download 或 /update）",
            chat_id,
        ))

    async def _handle_download_file(
        self, chat_id: str, value: dict, send_callback
    ) -> None:
        """Download selected file."""
        file_token = value.get("file_token", "")
        file_name = value.get("file_name", "unknown")

        try:
            await send_callback(build_success_card(
                "正在下载",
                f"_正在下载文件 `{file_name}`，请稍候..._",
                chat_id,
            ))

            data = await self._file_ops.download_to_bytes(file_token)

            # Return binary file data for Hermes to deliver
            await send_callback({
                "msg_type": "file",
                "chat_id": chat_id,
                "file_name": file_name,
                "content": data,
            })
        except Exception as e:
            await send_callback(build_error_card("下载失败", f"_错误：{str(e)}_", chat_id))

    async def _handle_update_file_selection(
        self, chat_id: str, value: dict, send_callback
    ) -> None:
        """Show update input card after user selects a file to update."""
        file_token = value.get("file_token", "")
        file_name = value.get("file_name", "")

        card = build_update_input_card(file_token, file_name, chat_id=chat_id)
        await send_callback(card)

    async def _handle_do_upload_from_folder(
        self, chat_id: str, value: dict, send_callback
    ) -> None:
        """User selected a folder in upload mode — show file path input."""
        folder_token = value.get("folder_token", "")
        folder_name = value.get("file_name", "")

        card = build_upload_input_card(folder_token, folder_name, chat_id=chat_id)
        await send_callback(card)

    async def _handle_do_upload(
        self, chat_id: str, value: dict, send_callback
    ) -> None:
        """Execute file upload after user confirms."""
        folder_token = value.get("folder_token", "")
        file_path = value.get("file_path", "").strip()

        if not file_path:
            await send_callback(build_error_card(
                "缺少文件路径", "_请在表单中输入本地文件路径_", chat_id
            ))
            return

        try:
            result = await self._file_ops.upload_local_file(file_path, parent_token=folder_token)
            self._cache.invalidate()
            await send_callback(build_success_card(
                "上传成功",
                f"**{result['file_name']}** 已上传成功\n"
                f"Token: `{result['file_token']}`",
                chat_id,
            ))
        except FileNotFoundError as e:
            await send_callback(build_error_card("文件不存在", f"_{str(e)}_", chat_id))
        except Exception as e:
            await send_callback(build_error_card("上传失败", f"_错误：{str(e)}_", chat_id))

    async def _handle_do_update(
        self, chat_id: str, value: dict, send_callback
    ) -> None:
        """Execute file update after user confirms."""
        file_token = value.get("file_token", "")
        file_path = value.get("file_path", "").strip()

        if not file_path:
            await send_callback(build_error_card(
                "缺少文件路径", "_请在表单中输入新文件路径_", chat_id
            ))
            return

        try:
            result = await self._file_ops.update_local_file(file_token, file_path)
            await send_callback(build_success_card(
                "更新成功",
                f"**{result['file_name']}** 已更新成功\n"
                f"Token: `{result['file_token']}`",
                chat_id,
            ))
        except FileNotFoundError as e:
            await send_callback(build_error_card("文件不存在", f"_{str(e)}_", chat_id))
        except Exception as e:
            await send_callback(build_error_card("更新失败", f"_错误：{str(e)}_", chat_id))

    async def _list_and_cache(self, parent_token: str) -> list[dict]:
        result = await self._drive.list_folder(parent_token)
        items = [
            {"file_token": f.file_token, "file_name": f.file_name, "type": f.type,
             "size": f.size, "last_modified_time": f.last_modified_time}
            for f in result.items
        ]
        self._cache.set(parent_token, items)
        return items
