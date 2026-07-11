#!/usr/bin/env python3
"""
飞书 Bot 互 @ 功能 - 主脚本

发送 @ 其他 Bot 的消息到飞书群聊。

用法:
    python3 feishu-bot-at.py \
        --app-id cli_xxx \
        --app-secret xxx \
        --chat-id oc_xxx \
        --target-open-id ou_xxx \
        --target-name 波比 \
        --message "你好波比！"

环境变量（可选，覆盖命令行参数）:
    FEISHU_APP_ID
    FEISHU_APP_SECRET
    FEISHU_CHAT_ID
    FEISHU_TARGET_OPEN_ID
    FEISHU_TARGET_NAME
    FEISHU_MESSAGE
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

# 默认配置（可从环境变量覆盖）
DEFAULT_APP_ID = os.getenv("FEISHU_APP_ID", "cli_aada30be933adcba")
DEFAULT_APP_SECRET = os.getenv("FEISHU_APP_SECRET", ""${FEISHU_APP_SECRET}"")
DEFAULT_CHAT_ID = os.getenv("FEISHU_CHAT_ID", "oc_7da955a1c5eab6d20bf62adf4fcd930b")
DEFAULT_API_BASE = "https://open.feishu.cn"


def parse_args():
    parser = argparse.ArgumentParser(
        description="飞书 Bot 互 @ 功能 - 发送 @ 其他 Bot 的消息"
    )
    parser.add_argument("--app-id", default=DEFAULT_APP_ID, help="飞书应用 app_id")
    parser.add_argument("--app-secret", default=DEFAULT_APP_SECRET, help="飞书应用 app_secret")
    parser.add_argument("--chat-id", default=DEFAULT_CHAT_ID, help="群聊 chat_id")
    parser.add_argument("--target-open-id", required=True, help="目标 Bot 的 open_id")
    parser.add_argument("--target-name", required=True, help="目标 Bot 显示名称")
    parser.add_argument("--message", required=True, help="要发送的消息文本")
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help="飞书 API 基础地址（默认 https://open.feishu.cn）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印请求内容，不实际发送",
    )
    return parser.parse_args()


async def get_tenant_token(app_id: str, app_secret: str, api_base: str) -> str:
    """获取 tenant_access_token。"""
    url = f"{api_base}/open-apis/auth/v3/tenant_access_token/internal"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={"app_id": app_id, "app_secret": app_secret})
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 token 失败: {data.get('msg')}")
        return data["tenant_access_token"]


async def send_at_message(
    app_id: str,
    app_secret: str,
    chat_id: str,
    target_open_id: str,
    target_name: str,
    message: str,
    api_base: str = DEFAULT_API_BASE,
    dry_run: bool = False,
) -> dict:
    """发送 @ 其他 Bot 的消息。

    Args:
        app_id: 飞书应用 app_id
        app_secret: 飞书应用 app_secret
        chat_id: 群聊 chat_id
        target_open_id: 目标 Bot 的 open_id
        target_name: 目标 Bot 显示名称
        message: 消息文本
        api_base: 飞书 API 基础地址
        dry_run: 仅打印请求内容，不实际发送

    Returns:
        API 响应结果
    """
    # 获取 token
    token = await get_tenant_token(app_id, app_secret, api_base)
    headers = {"Authorization": f"Bearer {token}"}

    # 构建 post 类型消息（关键：<at> 是独立元素）
    payload = {
        "receive_id": chat_id,
        "msg_type": "post",
        "content": json.dumps({
            "zh_cn": {
                "title": "",
                "content": [
                    [{"tag": "at", "user_id": target_open_id, "user_name": target_name}],
                    [{"tag": "md", "text": f" {message}"}],
                ],
            }
        }),
    }

    if dry_run:
        print("📋 请求内容（dry run，未实际发送）:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"Headers: {{'Authorization': 'Bearer {token[:10]}...', ...}}")
        return {"dry_run": True, "payload": payload}

    # 发送消息
    url = f"{api_base}/open-apis/im/v1/messages"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            headers=headers,
            params={"receive_id_type": "chat_id"},
            json=payload,
        )
        result = resp.json()

    # 验证结果
    if result.get("code") != 0:
        print(f"❌ 发送失败: {result.get('msg')}")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(1)

    # 验证 @ 是否成功
    mentions = result.get("data", {}).get("mentions", [])
    mentioned_ids = [m["id"] for m in mentions]
    if target_open_id in mentioned_ids:
        print(f"✅ 发送成功！已 @ {target_name}")
        print(f"   消息 ID: {result['data']['message_id']}")
        print(f"   Mentions: {json.dumps(mentions, indent=2, ensure_ascii=False)}")
    else:
        print(f"⚠️ 发送成功，但 @ 可能未生效")
        print(f"   消息 ID: {result['data']['message_id']}")
        print(f"   Mentions: {json.dumps(mentions, indent=2, ensure_ascii=False)}")

    return result


def main():
    args = parse_args()

    print(f"📤 发送 @{args.target_name} 消息...")
    print(f"   App ID: {args.app_id[:10]}...")
    print(f"   Chat ID: {args.chat_id}")
    print(f"   Target: {args.target_name} ({args.target_open_id})")
    print(f"   Message: {args.message}")
    print()

    result = asyncio.run(
        send_at_message(
            app_id=args.app_id,
            app_secret=args.app_secret,
            chat_id=args.chat_id,
            target_open_id=args.target_open_id,
            target_name=args.target_name,
            message=args.message,
            api_base=args.api_base,
            dry_run=args.dry_run,
        )
    )

    return 0 if result.get("code") == 0 or result.get("dry_run") else 1


if __name__ == "__main__":
    sys.exit(main())
