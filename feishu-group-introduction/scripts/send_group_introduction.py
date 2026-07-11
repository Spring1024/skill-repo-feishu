#!/usr/bin/env python3
"""
飞书群聊身份介绍发送脚本 - Skill 版

功能：
1. 从 SOUL.md 自动提取身份信息
2. 智能提炼核心职责和角色描述
3. @所有人并发送身份介绍
4. 使用 post 类型消息确保 @all 正确渲染

用法：
    python3 send_group_introduction.py
    
依赖：
    pip install httpx

作者：波比 (Bobo)
日期：2026-07-11
版本：v1.0.0
"""

import asyncio
import httpx
import json
import os
import re
from pathlib import Path


# =========================================================================
# 配置区域
# =========================================================================

# 飞书应用凭证（必须通过环境变量配置，禁止硬编码）
APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")

if not APP_ID or not APP_SECRET:
    raise EnvironmentError(
        "缺少飞书凭证配置。请在 .env 文件中设置：\n"
        "  FEISHU_APP_ID=cli_xxx\n"
        "  FEISHU_APP_SECRET=xxx"
    )

# 目标群聊 ID（必须通过环境变量配置）
CHAT_ID = os.getenv("FEISHU_HOME_CHANNEL")

if not CHAT_ID:
    raise EnvironmentError(
        "未指定目标群聊。请设置环境变量：\n"
        "  export FEISHU_HOME_CHANNEL=oc_群聊ID"
    )

# 飞书域名
DOMAIN = os.getenv("FEISHU_DOMAIN", "feishu")
base = "https://open.larksuite.com" if DOMAIN == "lark" else "https://open.feishu.cn"


# =========================================================================
# SOUL.md 解析器
# =========================================================================

def find_soul_file() -> str:
    """
    查找 SOUL.md 文件位置
    
    搜索路径（按优先级）：
    1. $HERMES_HOME/SOUL.md
    2. ~/.hermes/SOUL.md
    3. /data/hermes/SOUL.md
    
    Returns:
        SOUL.md 文件的绝对路径
    """
    search_paths = [
        os.path.join(os.getenv("HERMES_HOME", ""), "SOUL.md"),
        os.path.expanduser("~/.hermes/SOUL.md"),
        "/data/hermes/SOUL.md",
    ]
    
    for path in search_paths:
        if os.path.exists(path):
            return path
    
    raise FileNotFoundError(
        f"未找到 SOUL.md 文件。已搜索的路径：{search_paths}"
    )


def read_soul_content() -> str:
    """读取 SOUL.md 文件内容"""
    soul_path = find_soul_file()
    with open(soul_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_bot_identity(soul_content: str) -> dict:
    """
    从 SOUL.md 内容中提取身份信息并智能提炼
    
    提取策略：
    1. 名称：从 "# Identity" 段落提取
    2. 核心职责：从 "# Core Principles" 或 "# Identity" 提取
    3. 团队角色：从 "# Identity" 中的 "团队统帅" 部分提取
    4. 协作规则：从 "# A2A Collaboration" 或相关段落提取
    
    Args:
        soul_content: SOUL.md 的完整内容
        
    Returns:
        包含以下字段的字典：
        - name: Bot 名称
        - open_id: 飞书 open_id（如果已知）
        - responsibility: 核心职责
        - team_role: 团队角色描述
        - collaboration_rules: 协作规则要点
    """
    identity = {
        "name": "未知助手",
        "open_id": "",
        "responsibility": "",
        "team_role": "",
        "collaboration_rules": "",
    }
    
    # ------------------------------------------------------------------
    # 1. 提取名称
    # ------------------------------------------------------------------
    # 匹配模式："你是 XXX（XXX）" 或 "你是 XXX"
    name_match = re.search(r'你是\s*([^\s（(]+)', soul_content)
    if name_match:
        identity["name"] = name_match.group(1).strip()
    
    # ------------------------------------------------------------------
    # 2. 提取核心职责
    # ------------------------------------------------------------------
    # 匹配模式："核心职责[：:]xxx"
    resp_match = re.search(r'核心职责[：:]\s*(.+?)(?:\n|$)', soul_content, re.IGNORECASE)
    if resp_match:
        identity["responsibility"] = resp_match.group(1).strip()
    
    # ------------------------------------------------------------------
    # 3. 提取团队角色
    # ------------------------------------------------------------------
    # 匹配模式："团队统帅[：:]xxx"
    role_match = re.search(r'团队统帅[：:]\s*(.+?)(?:\n|$)', soul_content, re.IGNORECASE)
    if role_match:
        identity["team_role"] = role_match.group(1).strip()
    
    # ------------------------------------------------------------------
    # 4. 提取协作规则
    # ------------------------------------------------------------------
    # 匹配模式：从 "# A2A Collaboration" 或 "# 协作规则" 段落提取要点
    collab_section = re.search(
        r'(?:协作规则[：:]|A2A Collaboration.*?协作规则[：:]\s*)(.*?)(?:\n\n|\n#{1,6}\s|$)',
        soul_content,
        re.DOTALL | re.IGNORECASE
    )
    if collab_section:
        rules_text = collab_section.group(1).strip()
        # 简化：只保留前 3 条规则
        rules_lines = [line.strip() for line in rules_text.split('\n') if line.strip()]
        identity["collaboration_rules"] = '\n'.join(rules_lines[:3])
    
    # ------------------------------------------------------------------
    # 5. 尝试获取 open_id（从缓存或环境变量）
    # ------------------------------------------------------------------
    cache_path = os.path.expanduser("~/.hermes/fbc-cache/registry.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
                bots = cache_data.get("bots", {})
                for key, bot_info in bots.items():
                    if bot_info.get("is_self"):
                        identity["open_id"] = bot_info.get("bot_open_id", "")
                        break
        except Exception:
            pass
    
    # 如果缓存中没有，尝试从环境变量获取
    if not identity["open_id"]:
        identity["open_id"] = os.getenv("FEISHU_BOT_OPEN_ID", "")
    
    return identity


def generate_introduction(identity: dict) -> str:
    """
    根据提取的身份信息生成简洁的介绍文本
    
    生成策略：
    1. 使用 Markdown 格式增强可读性
    2. 突出关键信息（名称、职责、角色）
    3. 保持简洁（不超过 500 字）
    
    Args:
        identity: 身份信息字典
        
    Returns:
        格式化的介绍文本
    """
    name = identity.get("name", "未知助手")
    open_id = identity.get("open_id", "未配置")
    responsibility = identity.get("responsibility", "无")
    team_role = identity.get("team_role", "无")
    collab_rules = identity.get("collaboration_rules", "无")
    
    # 协作规则默认值
    if not collab_rules:
        collab_rules = (
            "- 在群聊中通过 <at> 标签与其他机器人协作\n"
            "- 任务型 @：需要对方执行任务时使用\n"
            "- 通知型 @：仅需告知信息时加入 🔕仅通知 标记"
        )
    
    lines = [
        f"**大家好！我是{name}。**",
        "",
        f"我的 open_id: `{open_id}`",
        "",
        f"**核心职责**：{responsibility}",
        "",
        f"**团队角色**：{team_role}",
        "",
        "**协作方式**：",
        collab_rules,
        "",
        "💡 **联系方式**：在本群聊中 @我 即可",
    ]
    
    return "\n".join(lines)


# =========================================================================
# 飞书 API 客户端
# =========================================================================

async def get_tenant_token(app_id: str, app_secret: str, domain: str) -> str:
    """
    获取 tenant_access_token
    
    Args:
        app_id: 飞书应用 App ID
        app_secret: 飞书应用 App Secret
        domain: 飞书域名（feishu 或 lark）
        
    Returns:
        tenant_access_token 字符串
        
    Raises:
        RuntimeError: Token 获取失败
    """
    base_url = "https://open.larksuite.com" if domain == "lark" else "https://open.feishu.cn"
    url = f"{base_url}/open-apis/auth/v3/tenant_access_token/internal"
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={'app_id': app_id, 'app_secret': app_secret})
        data = resp.json()
        
        if data.get('code') != 0:
            raise RuntimeError(f"Token 获取失败: {data}")
        
        return data['tenant_access_token']


async def send_message_to_group(
    token: str,
    chat_id: str,
    content: str,
    mention_all: bool = True
) -> dict:
    """
    向飞书群聊发送消息
    
    Args:
        token: tenant_access_token
        chat_id: 群聊 ID（格式 oc_xxx）
        content: 消息内容（Markdown 格式）
        mention_all: 是否 @所有人
        
    Returns:
        飞书 API 响应数据
    """
    base_url = "https://open.larksuite.com" if DOMAIN == "lark" else "https://open.feishu.cn"
    headers = {'Authorization': f'Bearer {token}'}
    
    # 构建消息内容数组
    content_array = []
    
    # 第 1 行：@所有人（如果需要）
    if mention_all:
        content_array.append([
            {"tag": "at", "user_id": "all", "user_name": "所有人"}
        ])
    
    # 第 2 行：身份介绍（使用 lark_md 支持换行和排版）
    content_array.append([
        {"tag": "lark_md", "text": content}
    ])
    
    # 构建完整的 payload
    payload = {
        'receive_id': chat_id,
        'msg_type': 'post',  # ⚠️ 必须为 post，否则 @all 无法渲染
        'content': json.dumps({
            'zh_cn': {
                'title': '',
                'content': content_array
            }
        })
    }
    
    # 发送消息
    url = f"{base_url}/open-apis/im/v1/messages"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            headers=headers,
            params={'receive_id_type': 'chat_id'},
            json=payload
        )
        return resp.json()


# =========================================================================
# 主函数
# =========================================================================

async def send_group_introduction():
    """
    主函数：向飞书群聊发送身份介绍
    
    流程：
    1. 读取 SOUL.md 文件
    2. 提取身份信息
    3. 生成介绍文本
    4. 调用飞书 API 发送消息
    5. 输出结果
    """
    print("=" * 60)
    print("飞书群聊身份介绍发送脚本 - Skill 版")
    print("=" * 60)
    print()
    
    # ------------------------------------------------------------------
    # 步骤 1: 读取并解析 SOUL.md
    # ------------------------------------------------------------------
    print("📖 读取 SOUL.md...")
    try:
        soul_content = read_soul_content()
        print(f"   ✅ 成功读取 SOUL.md ({len(soul_content)} 字符)")
    except FileNotFoundError as e:
        print(f"   ❌ 错误: {e}")
        return
    except Exception as e:
        print(f"   ❌ 读取失败: {e}")
        return
    
    print("\n🔍 提取身份信息...")
    identity = extract_bot_identity(soul_content)
    
    print(f"   名称: {identity['name']}")
    print(f"   open_id: {identity['open_id'] or '未配置'}")
    print(f"   核心职责: {identity['responsibility'][:50]}..." if len(identity['responsibility']) > 50 else f"   核心职责: {identity['responsibility']}")
    print(f"   团队角色: {identity['team_role'][:50]}..." if len(identity['team_role']) > 50 else f"   团队角色: {identity['team_role']}")
    
    # ------------------------------------------------------------------
    # 步骤 2: 生成介绍文本
    # ------------------------------------------------------------------
    print("\n✍️  生成介绍文本...")
    introduction = generate_introduction(identity)
    print(f"   文本长度: {len(introduction)} 字符")
    print()
    print("--- 预览 ---")
    print(introduction[:200] + "..." if len(introduction) > 200 else introduction)
    print("---\n")
    
    # ------------------------------------------------------------------
    # 步骤 3: 获取飞书 Token
    # ------------------------------------------------------------------
    print("🔑 获取飞书 Token...")
    try:
        token = await get_tenant_token(APP_ID, APP_SECRET, DOMAIN)
        print("   ✅ Token 获取成功")
    except RuntimeError as e:
        print(f"   ❌ Token 获取失败: {e}")
        return
    
    # ------------------------------------------------------------------
    # 步骤 4: 发送消息
    # ------------------------------------------------------------------
    print(f"\n📤 发送消息到群 {CHAT_ID}...")
    try:
        result = await send_message_to_group(token, CHAT_ID, introduction)
        
        if result.get('code') == 0:
            print("   ✅ 发送成功！")
            print(f"   消息 ID: {result['data']['message_id']}")
            
            mentions = result['data'].get('mentions', [])
            print(f"   Mentions 数量: {len(mentions)}")
            for m in mentions:
                print(f"     - name: {m.get('name')}, id: {m.get('id')}")
        else:
            print(f"   ❌ 发送失败: {result}")
            
    except Exception as e:
        print(f"   ❌ 发送异常: {e}")
    
    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)


if __name__ == '__main__':
    # 运行异步主函数
    asyncio.run(send_group_introduction())
