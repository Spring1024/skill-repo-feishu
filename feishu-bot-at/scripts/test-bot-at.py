#!/usr/bin/env python3
"""
飞书 Bot 互 @ 功能 - 快速测试脚本

一键测试 @ 指定 Bot 的消息发送，验证配置是否正确。

用法:
    python3 test-bot-at.py
    # 或指定目标
    python3 test-bot-at.py --target-open-id ou_xxx --target-name 波比
"""

import argparse
import asyncio
import json
import sys

import httpx

DEFAULT_APP_ID = "cli_aada30be933adcba"
DEFAULT_APP_SECRET = ""${FEISHU_APP_SECRET}""
DEFAULT_CHAT_ID = "oc_7da955a1c5eab6d20bf62adf4fcd930b"
DEFAULT_TARGET_OPEN_ID = "ou_cb099e84ffa7033c4a51d4b332f4340f"
DEFAULT_TARGET_NAME = "波比"
DEFAULT_API_BASE = "https://open.feishu.cn"


def get_tenant_token(app_id: str, app_secret: str, api_base: str) -> str:
    """获取 tenant_access_token。"""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{api_base}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 token 失败: {data.get('msg')}")
        return data["tenant_access_token"]


async def test_send_at_message(
    app_id: str,
    app_secret: str,
    chat_id: str,
    target_open_id: str,
    target_name: str,
    api_base: str = DEFAULT_API_BASE,
) -> dict:
    """测试发送 @ 消息。"""
    print(f"📋 测试配置:")
    print(f"   App ID: {app_id}")
    print(f"   Chat ID: {chat_id}")
    print(f"   Target: {target_name} ({target_open_id})")
    print()

    # Step 1: 获取 token
    print("Step 1/4: 获取 tenant_access_token...")
    try:
        token = get_tenant_token(app_id, app_secret, api_base)
        print(f"   ✅ Token 获取成功: {token[:10]}...")
    except Exception as e:
        print(f"   ❌ Token 获取失败: {e}")
        sys.exit(1)

    # Step 2: 构建消息
    print("Step 2/4: 构建消息 payload...")
    payload = {
        "receive_id": chat_id,
        "msg_type": "post",
        "content": json.dumps({
            "zh_cn": {
                "title": "",
                "content": [
                    [{"tag": "at", "user_id": target_open_id, "user_name": target_name}],
                    [{"tag": "md", "text": " 这是一条自动测试消息，来自芙蓉 Bot A2A 测试。"}],
                ],
            }
        }),
    }
    print(f"   ✅ Payload 构建成功")
    print(f"   预览: {json.loads(payload['content'])['zh_cn']['content'][1]['text']}")
    print()

    # Step 3: 发送消息
    print("Step 3/4: 发送消息...")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{api_base}/open-apis/im/v1/messages",
                headers=headers,
                params={"receive_id_type": "chat_id"},
                json=payload,
            )
        result = resp.json()
    except Exception as e:
        print(f"   ❌ 发送失败: {e}")
        sys.exit(1)

    # Step 4: 验证结果
    print("Step 4/4: 验证结果...")
    if result.get("code") != 0:
        print(f"   ❌ 发送失败: {result.get('msg')}")
        print(f"   完整响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        sys.exit(1)

    print(f"   ✅ 发送成功！")
    print(f"   消息 ID: {result['data']['message_id']}")

    # 验证 mentions
    mentions = result.get("data", {}).get("mentions", [])
    if not mentions:
        print(f"   ⚠️  警告: mentions 为空，@ 可能未生效")
        print(f"   完整响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        sys.exit(1)

    mentioned_ids = [m["id"] for m in mentions]
    if target_open_id in mentioned_ids:
        print(f"   ✅ @ 验证成功: 目标 Bot ({target_name}) 被正确 @")
        print(f"   Mentions: {json.dumps(mentions, indent=2, ensure_ascii=False)}")
    else:
        print(f"   ❌ @ 验证失败!")
        print(f"   期望: {target_open_id}")
        print(f"   实际: {mentioned_ids}")
        print(f"   完整响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        sys.exit(1)

    return result


def main():
    parser = argparse.ArgumentParser(description="飞书 Bot 互 @ 功能 - 快速测试")
    parser.add_argument("--app-id", default=DEFAULT_APP_ID)
    parser.add_argument("--app-secret", default=DEFAULT_APP_SECRET)
    parser.add_argument("--chat-id", default=DEFAULT_CHAT_ID)
    parser.add_argument("--target-open-id", default=DEFAULT_TARGET_OPEN_ID)
    parser.add_argument("--target-name", default=DEFAULT_TARGET_NAME)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    args = parser.parse_args()

    print("=" * 60)
    print("飞书 Bot 互 @ 功能 - 快速测试")
    print("=" * 60)
    print()

    asyncio.run(
        test_send_at_message(
            app_id=args.app_id,
            app_secret=args.app_secret,
            chat_id=args.chat_id,
            target_open_id=args.target_open_id,
            target_name=args.target_name,
            api_base=args.api_base,
        )
    )

    print()
    print("=" * 60)
    print("✅ 测试全部通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
