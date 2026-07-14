from __future__ import annotations

import json
from typing import Any


def _build_button(
    text: str,
    action_value: dict[str, Any],
    type: str = "default",
) -> dict:
    """Build a single button element."""
    btn: dict[str, Any] = {
        "tag": "button",
        "text": {"tag": "plain_text", "content": text},
        "type": type,
        "value": action_value,
    }
    if type == "primary":
        pass  # already set
    return btn


def build_folder_picker_card(
    items: list[dict],
    parent_token: str | None = None,
    chat_id: str | None = None,
    mode: str = "default",
) -> dict:
    """Build a folder/file picker card showing items in a directory.

    Args:
        items: list of dicts with keys: file_token, file_name, type, size
        parent_token: current folder token (used for go-up navigation)
        chat_id: chat ID for reply reference
        mode: "default" / "download" / "update" / "upload"
              - default: folders navigate, files are selectable
              - download: same as default, file action = download
              - update: same as default, file action = update
              - upload: folders trigger upload form, files hidden
    """
    elements: list[dict] = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": "请选择目标："},
        }
    ]

    folders = [i for i in items if i.get("type") == "folder"]
    files = [i for i in items if i.get("type") != "folder"]

    # Folder buttons
    if folders:
        for i in range(0, len(folders), 3):
            row_buttons = []
            for f in folders[i:i + 3]:
                # In upload mode, selecting a folder triggers upload form
                if mode == "upload":
                    folder_action = "do_upload_from_folder"
                else:
                    folder_action = "select_folder"

                row_buttons.append(_build_button(
                    text=f"[📁] {f.get('file_name', '')}",
                    action_value={
                        "action": folder_action,
                        "folder_token": f["file_token"],
                        "file_name": f.get("file_name", ""),
                        "parent_token": parent_token,
                    },
                ))
            elements.append({
                "tag": "column_set",
                "flex_mode": 0,
                "columns": [{"tag": "column", "weight": 1, "elements": [btn]} for btn in row_buttons],
            })

    # File buttons (only shown in non-upload modes)
    if files and mode != "upload":
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**文件：**"},
        })
        for i in range(0, len(files), 2):
            row_buttons = []
            for f in files[i:i + 2]:
                if mode == "download":
                    file_action = "download_file"
                elif mode == "update":
                    file_action = "update_file"
                else:
                    file_action = "select_file"

                row_buttons.append(_build_button(
                    text=f"{f.get('file_name', '')} ({_format_size(f.get('size', 0))})",
                    action_value={
                        "action": file_action,
                        "file_token": f["file_token"],
                        "file_name": f.get("file_name", ""),
                        "parent_token": parent_token,
                    },
                ))
            elements.append({
                "tag": "column_set",
                "flex_mode": 0,
                "columns": [{"tag": "column", "weight": 1, "elements": [btn]} for btn in row_buttons],
            })

    if not folders and not files:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "_该文件夹为空_"},
        })

    # Go up button
    if parent_token:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "action",
            "actions": [_build_button(
                text="向上导航",
                action_value={"action": "go_up", "parent_token": parent_token},
            )],
        })

    card: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "选择文件夹"}, "template": "blue"},
            "elements": elements,
        },
    }

    if chat_id:
        card["chat_id"] = chat_id

    return card


def build_upload_input_card(
    folder_token: str,
    folder_name: str,
    chat_id: str | None = None,
) -> dict:
    """Build a card prompting user to enter local file path for upload."""
    card: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "上传文件到: " + folder_name}, "template": "blue"},
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "请输入本地文件的**绝对路径**："},
                },
                {
                    "tag": "input",
                    "name": "file_path",
                    "placeholder": {"tag": "plain_text", "content": "例如: /home/user/documents/report.pdf"},
                },
                {
                    "tag": "action",
                    "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "确认上传"},
                        "type": "primary",
                        "confirm": {
                            "title": {"tag": "plain_text", "content": "确认上传"},
                            "content": {"tag": "lark_md", "content": "即将上传文件到飞书云空间，请确认。"},
                        },
                        "value": {
                            "action": "do_upload",
                            "folder_token": folder_token,
                        },
                    }],
                },
            ],
        },
    }

    if chat_id:
        card["chat_id"] = chat_id

    return card


def build_update_input_card(
    file_token: str,
    file_name: str,
    chat_id: str | None = None,
) -> dict:
    """Build a card prompting user to enter new file path for update."""
    card: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "更新文件: " + file_name}, "template": "orange"},
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "请输入新文件的**绝对路径**："},
                },
                {
                    "tag": "input",
                    "name": "file_path",
                    "placeholder": {"tag": "plain_text", "content": "例如: /home/user/new_version.pdf"},
                },
                {
                    "tag": "action",
                    "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "确认更新"},
                        "type": "primary",
                        "confirm": {
                            "title": {"tag": "plain_text", "content": "确认更新"},
                            "content": {"tag": "lark_md", "content": "即将覆盖文件 `" + file_name + "`，请确认。"},
                        },
                        "value": {
                            "action": "do_update",
                            "file_token": file_token,
                        },
                    }],
                },
            ],
        },
    }

    if chat_id:
        card["chat_id"] = chat_id

    return card


def build_success_card(
    title: str,
    content: str,
    chat_id: str | None = None,
) -> dict:
    """Build a generic success card."""
    card: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "green"},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}],
        },
    }

    if chat_id:
        card["chat_id"] = chat_id

    return card


def build_error_card(
    title: str,
    content: str,
    chat_id: str | None = None,
) -> dict:
    """Build a generic error card."""
    card: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "red"},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}],
        },
    }

    if chat_id:
        card["chat_id"] = chat_id

    return card


def build_help_card(chat_id: str | None = None) -> dict:
    """Build the help command response card."""
    content = (
        "**可用命令：**\n\n"
        "/create-folder <名称> — 创建文件夹（组织内可读）\n"
        "/upload — 上传文件到云空间\n"
        "/download — 下载云空间文件\n"
        "/update — 更新云空间文件\n"
        "/help — 显示此帮助信息"
    )

    card: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "飞书云空间机器人 - 帮助"}, "template": "turquoise"},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}],
        },
    }

    if chat_id:
        card["chat_id"] = chat_id

    return card


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
