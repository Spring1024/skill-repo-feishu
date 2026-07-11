#!/usr/bin/env python3
"""
飞书 Bot 信息查询工具

获取 Bot 的 open_id、群聊列表、群成员等信息。

用法:
    python3 feishu-bot-info.py --action bot-info
    python3 feishu-bot-info.py --action list-groups
    python3 feishu-bot-info.py --action group-members --chat-id oc_xxx
"""

import argparse
import asyncio
import json
import sys

import httpx

DEFAULT_APP_ID = "cli_aada30be933adcba"
DEFAULT_APP_SECRET = "O8ePQfHizivRmPxPZZwMQgxFWWsjfG2W"
DEFAULT_API_BASE = "https://open.feishu.cn"


def get_tenant_token(app_id: str, app_secret: str, api_base: str) -> str:
    """获取 tenant_access_token（同步版本）。"""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{api_base}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 token 失败: {data.get('msg')}")
        return data["tenant_access_token"]


async def get_bot_info(app_id: str, app_secret: str, api_base: str) -> dict:
    """获取 Bot 信息（open_id、app_name 等）。"""
    token = get_tenant_token(app_id, app_secret, api_base)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{api_base}/open-apis/bot/v3/info",
            headers=headers,
        )
        return resp.json()


async def list_groups(app_id: str, app_secret: str, api_base: str, page_size: int = 50) -> list:
    """获取群聊列表。"""
    token = get_tenant_token(app_id, app_secret, api_base)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{api_base}/open-apis/im/v1/chats",
            headers=headers,
            params={"page_size": page_size},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取群聊列表失败: {data.get('msg')}")
        return data["data"]["items"]


async def get_group_members(
    app_id: str, app_secret: str, chat_id: str, api_base: str
) -> list:
    """获取群成员列表。"""
    token = get_tenant_token(app_id, app_secret, api_base)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{api_base}/open-apis/im/v1/chats/{chat_id}/members",
            headers=headers,
            params={"member_id_type": "open_id", "page_size": 100},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取群成员失败: {data.get('msg')}")
        return data["data"]["items"]


def format_bot_info(bot_info: dict) -> str:
    """格式化 Bot 信息输出。"""
    bot = bot_info.get("bot", {})
    return (
        f"Bot 信息:\n"
        f"  app_name: {bot.get('app_name', 'N/A')}\n"
        f"  open_id:  {bot.get('open_id', 'N/A')}\n"
        f"  activate_status: {bot.get('activate_status', 'N/A')} "
        f"(0=初始化, 1=停用, 2=启用, 3=安装后待启用, 4=升级待启用, 5=license过期, 6=套餐到期)"
    )


def format_group_list(groups: list) -> str:
    """格式化群聊列表输出。"""
    if not groups:
        return "暂无群聊"
    lines = [f"群聊列表 (共 {len(groups)} 个):"]
    for g in groups:
        lines.append(f"  - {g['name']} (chat_id: {g['chat_id']}, owner: {g.get('owner_id', 'N/A')})")
    return "\n".join(lines)


def format_member_list(members: list) -> str:
    """格式化群成员列表输出。"""
    if not members:
        return "暂无成员"
    lines = [f"群成员 (共 {len(members)} 人):"]
    for m in members:
        lines.append(f"  - {m.get('name', 'N/A')} (open_id: {m['member_id']})")
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="飞书 Bot 信息查询工具")
    parser.add_argument("--app-id", default=DEFAULT_APP_ID, help="飞书应用 app_id")
    parser.add_argument("--app-secret", default=DEFAULT_APP_SECRET, help="飞书应用 app_secret")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="飞书 API 基础地址")
    parser.add_argument("--action", required=True, choices=["bot-info", "list-groups", "group-members"],
                        help="操作类型")
    parser.add_argument("--chat-id", help="群聊 chat_id（group-members 时需要）")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="输出格式")

    args = parser.parse_args()

    try:
        if args.action == "bot-info":
            result = await get_bot_info(args.app_id, args.app_secret, args.api_base)
            if args.output == "json":
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(format_bot_info(result))

        elif args.action == "list-groups":
            groups = await list_groups(args.app_id, args.app_secret, args.api_base)
            if args.output == "json":
                print(json.dumps({"groups": groups}, indent=2, ensure_ascii=False))
            else:
                print(format_group_list(groups))

        elif args.action == "group-members":
            if not args.chat_id:
                print("❌ --chat-id 是必需的", file=sys.stderr)
                sys.exit(1)
            members = await get_group_members(args.app_id, args.app_secret, args.chat_id, args.api_base)
            if args.output == "json":
                print(json.dumps({"members": members}, indent=2, ensure_ascii=False))
            else:
                print(format_member_list(members))

    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
