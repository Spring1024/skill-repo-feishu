#!/usr/bin/env python3
"""
飞书群聊身份介绍发送脚本 - Skill 版

功能：
1. 从飞书 API 获取最新 open_id（优先）
2. 从 SOUL.md 提取身份信息
3. 使用 LLM 对信息进行归纳提炼
4. @所有人并发送身份介绍
5. 使用 post 类型消息确保 @all 正确渲染

用法：
    python3 send_group_introduction.py
    
依赖：
    pip install httpx

作者：波比 (Bobo)
日期：2026-07-11
版本：v1.0.1（修复 open_id 获取 + LLM 归纳）
"""

import asyncio
import httpx
import json
import os
import re
from pathlib import Path
from typing import Optional


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

# LLM 配置（可选，用于归纳提炼 SOUL.md 内容）
LLM_API_URL = os.getenv("LLM_API_URL", "")  # 如 https://api.anthropic.com/v1/messages
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")


# =========================================================================
# 飞书 API 客户端
# =========================================================================

async def get_tenant_token(app_id: str, app_secret: str, domain: str) -> str:
    """获取 tenant_access_token。"""
    base_url = "https://open.larksuite.com" if domain == "lark" else "https://open.feishu.cn"
    url = f"{base_url}/open-apis/auth/v3/tenant_access_token/internal"
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={'app_id': app_id, 'app_secret': app_secret})
        data = resp.json()
        
        if data.get('code') != 0:
            raise RuntimeError(f"Token 获取失败: {data}")
        
        return data['tenant_access_token']


async def get_bot_open_id(app_id: str, app_secret: str, domain: str) -> Optional[str]:
    """
    通过飞书 API 获取当前 Bot 的 open_id（优先方式）。
    
    这是最可靠的方式，因为 open_id 可能在不同环境下变化。
    
    Returns:
        Bot 的 open_id，获取失败返回 None
    """
    base_url = "https://open.larksuite.com" if domain == "lark" else "https://open.feishu.cn"
    token = await get_tenant_token(app_id, app_secret, domain)
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{base_url}/open-apis/bot/v3/info",
            headers={'Authorization': f'Bearer {token}'}
        )
        data = resp.json()
        
        if data.get('code') != 0:
            print(f"   ⚠️ 获取 Bot 信息失败: {data.get('msg')}")
            return None
        
        bot_info = data.get('bot', {})
        open_id = bot_info.get('open_id', '')
        app_name = bot_info.get('app_name', '')
        
        print(f"   ✅ Bot 信息: {app_name} (open_id: {open_id})")
        return open_id


# =========================================================================
# SOUL.md 解析器
# =========================================================================

def find_soul_file() -> str:
    """
    查找 SOUL.md 文件位置。
    
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
    """读取 SOUL.md 文件内容。"""
    soul_path = find_soul_file()
    with open(soul_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_raw_identity(soul_content: str) -> dict:
    """
    从 SOUL.md 内容中提取原始身份信息（通用型解析）。
    
    适配各种格式的 SOUL.md，包括：
    - 标准格式：# Identity 段落
    - 变体格式：# 核心身份、# 角色定义、# 身份介绍 等
    - 无标题格式：直接从第一行提取名称
    
    Args:
        soul_content: SOUL.md 的完整内容
        
    Returns:
        包含原始信息的字典
    """
    identity = {
        "name": "未知助手",
        "responsibility": "",
        "team_role": "",
        "collaboration_rules": "",
    }
    
    lines = soul_content.split('\n')
    
    # ------------------------------------------------------------------
    # 1. 提取名称（多种格式适配）
    # ------------------------------------------------------------------
    
    # 尝试 1: 从标题行提取（如 "# 芙蓉：严谨务实型产品经理"）
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#') and not stripped.startswith('##'):
            # 提取 "# 芙蓉：xxx" 或 "# 芙蓉 - xxx" 或 "# 芙蓉"
            name_match = re.match(r'^#\s+([^\s：:—-]+)', stripped)
            if name_match:
                identity["name"] = name_match.group(1).strip()
                break
    
    # 尝试 2: 从 "你是 XXX" 提取
    if identity["name"] == "未知助手":
        for line in lines:
            name_match = re.search(r'你是\s*([^\s（(]+)', line)
            if name_match:
                identity["name"] = name_match.group(1).strip()
                break
    
    # 尝试 3: 从 frontmatter 提取（如 ---\nname: xxx\n---）
    if identity["name"] == "未知助手":
        fm_match = re.search(r'---\s*\n.*?name:\s*(.+?)\s*\n---', soul_content, re.DOTALL)
        if fm_match:
            identity["name"] = fm_match.group(1).strip()
    
    # ------------------------------------------------------------------
    # 2. 提取核心职责（多种段落适配）
    # ------------------------------------------------------------------
    
    # 尝试 1: 从 # Identity 或 # 核心身份 或 # 角色定义 段落提取
    target_sections = ['# Identity', '# 核心身份', '# 角色定义', '# 身份介绍', '# 核心']
    responsibility_lines = []
    
    for section in target_sections:
        in_section = False
        for line in lines:
            if line.strip().startswith(section):
                in_section = True
                continue
            if in_section:
                if line.strip().startswith('## '):
                    break
                if line.strip():
                    responsibility_lines.append(line.strip())
                if len(responsibility_lines) >= 3:
                    break
        if responsibility_lines:
            break
    
    # 尝试 2: 从第一段的 bullet points 提取
    if not responsibility_lines:
        in_first_section = False
        bullet_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('-') or stripped.startswith('*'):
                if not in_first_section:
                    in_first_section = True
                bullet_lines.append(stripped[1:].strip())
                if len(bullet_lines) >= 3:
                    break
            elif in_first_section and stripped:
                bullet_lines.append(stripped)
                if len(bullet_lines) >= 3:
                    break
        responsibility_lines = bullet_lines
    
    # 尝试 3: 从 "核心职责" 或 "角色" 关键词提取
    if not responsibility_lines:
        for line in lines:
            if '核心职责' in line or '角色' in line:
                responsibility_lines.append(line.strip())
                if len(responsibility_lines) >= 3:
                    break
    
    if responsibility_lines:
        identity["responsibility"] = '\n'.join(responsibility_lines[:3])
    
    # ------------------------------------------------------------------
    # 3. 提取团队角色
    # ------------------------------------------------------------------
    
    # 尝试 1: 从 # 团队角色 或 # Role 段落提取
    target_sections_role = ['# 团队角色', '# Role', '# 角色', '# 团队']
    team_role_lines = []
    
    for section in target_sections_role:
        in_section = False
        for line in lines:
            if line.strip().startswith(section):
                in_section = True
                continue
            if in_section:
                if line.strip().startswith('## '):
                    break
                if line.strip():
                    team_role_lines.append(line.strip())
                if len(team_role_lines) >= 3:
                    break
        if team_role_lines:
            break
    
    # 尝试 2: 从核心职责中提取团队角色相关的句子
    if not team_role_lines and identity["responsibility"]:
        for line in identity["responsibility"].split('\n'):
            if '团队' in line or 'Leader' in line or '负责' in line:
                team_role_lines.append(line)
                if len(team_role_lines) >= 2:
                    break
    
    if team_role_lines:
        identity["team_role"] = '\n'.join(team_role_lines[:2])
    
    # ------------------------------------------------------------------
    # 4. 提取协作规则
    # ------------------------------------------------------------------
    
    # 尝试 1: 从 # A2A Collaboration 或 # 协作 段落提取
    target_sections_collab = ['# A2A Collaboration', '# 协作', '# 协作规则']
    collab_lines = []
    
    for section in target_sections_collab:
        in_section = False
        for line in lines:
            if line.strip().startswith(section):
                in_section = True
                continue
            if in_section:
                if line.strip().startswith('## '):
                    break
                if line.strip():
                    collab_lines.append(line.strip())
                if len(collab_lines) >= 5:
                    break
        if collab_lines:
            break
    
    if collab_lines:
        identity["collaboration_rules"] = '\n'.join(collab_lines[:3])
    
    return identity


async def summarize_with_llm(raw_identity: dict, soul_content: str) -> dict:
    """
    使用 LLM 对 SOUL.md 内容进行归纳提炼。
    
    如果 LLM API 不可用，则返回原始信息。
    
    Args:
        raw_identity: 从 SOUL.md 提取的原始身份信息
        soul_content: SOUL.md 的完整内容
        
    Returns:
        经过 LLM 归纳提炼的身份信息
    """
    # 如果没有配置 LLM，直接返回原始信息
    if not LLM_API_URL or not LLM_API_KEY:
        print("   ℹ️  未配置 LLM API，使用原始信息（未归纳）")
        return raw_identity
    
    # 构建 prompt
    prompt = f"""你是一个专业的产品经理助手。请根据以下 SOUL.md 内容，为这个 AI Bot 生成一份简洁、专业的群聊身份介绍。

## 原始身份信息

**名称**: {raw_identity.get('name', '未知助手')}
**核心职责**: {raw_identity.get('responsibility', '无')}
**团队角色**: {raw_identity.get('team_role', '无')}
**协作规则**: {raw_identity.get('collaboration_rules', '无')}

## SOUL.md 全文

```markdown
{soul_content[:3000]}
```

## 要求

请生成以下字段（保持简洁，每个字段不超过 100 字）：

1. **name**: Bot 名称（保持不变）
2. **responsibility**: 核心职责（用 1-2 句话概括，突出核心价值）
3. **team_role**: 团队角色（用 1 句话描述在团队中的定位）
4. **collaboration_rules**: 协作方式（用 3 条 bullet points 概括）
5. **intro_summary**: 一句话自我介绍（用于开场白）

请以 JSON 格式返回，不要包含其他内容。"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                LLM_API_URL,
                headers={
                    'Authorization': f'Bearer {LLM_API_KEY}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': LLM_MODEL,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 1000,
                }
            )
            data = resp.json()
            
            # 提取 LLM 返回的内容
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # 尝试解析 JSON
            try:
                summarized = json.loads(content)
                print("   ✅ LLM 归纳完成")
                return summarized
            except json.JSONDecodeError:
                print("   ⚠️  LLM 返回格式不合法，使用原始信息")
                return raw_identity
                
    except Exception as e:
        print(f"   ⚠️  LLM 调用失败: {e}，使用原始信息")
        return raw_identity


# =========================================================================
# 消息生成
# =========================================================================

def generate_introduction(identity: dict) -> str:
    """
    根据提取的身份信息生成简洁的介绍文本。
    
    生成策略：
    1. 使用 Markdown 格式增强可读性
    2. 突出关键信息（名称、职责、角色、open_id）
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
    if not collab_rules or collab_rules == "无":
        collab_rules = (
            "- 在群聊中通过 <at> 标签与其他机器人协作\n"
            "- 任务型 @：需要对方执行任务时使用\n"
            "- 通知型 @：仅需告知信息时加入 🔕仅通知 标记"
        )
    
    lines = [
        f"**大家好！我是{name}。**",
        "",
        f"**我的 open_id**：`{open_id}`",
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
# 飞书消息发送
# =========================================================================

async def send_message_to_group(
    token: str,
    chat_id: str,
    content: str,
    mention_all: bool = True
) -> dict:
    """
    向飞书群聊发送消息。
    
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
    
    # 第 2 行：身份介绍（使用 md 格式）
    content_array.append([
        {"tag": "md", "text": content}
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
    主函数：向飞书群聊发送身份介绍。
    
    流程：
    1. 通过飞书 API 获取最新 open_id（优先）
    2. 读取 SOUL.md 文件
    3. 提取原始身份信息
    4. 使用 LLM 归纳提炼（可选）
    5. 生成介绍文本
    6. 调用飞书 API 发送消息
    7. 输出结果
    """
    print("=" * 60)
    print("飞书群聊身份介绍发送脚本 - Skill 版 v1.0.1")
    print("=" * 60)
    print()
    
    # ------------------------------------------------------------------
    # 步骤 1: 获取 open_id（优先通过飞书 API）
    # ------------------------------------------------------------------
    print("🔑 获取 open_id（通过飞书 API）...")
    open_id: Optional[str] = await get_bot_open_id(str(APP_ID), str(APP_SECRET), DOMAIN)
    
    if not open_id:
        print("   ⚠️  API 获取失败，尝试从缓存/环境变量回退...")
        # 回退到缓存文件
        cache_path = os.path.expanduser("~/.hermes/fbc-cache/registry.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)
                    bots = cache_data.get("bots", {})
                    for key, bot_info in bots.items():
                        if bot_info.get("is_self"):
                            open_id = bot_info.get("bot_open_id", "")
                            break
            except Exception:
                pass
        
        # 最后回退到环境变量
        if not open_id:
            open_id = os.getenv("FEISHU_BOT_OPEN_ID", "")
            if open_id:
                print(f"   ℹ️  从环境变量获取: {open_id}")
            else:
                print("   ❌ 无法获取 open_id")
                return
    
    # ------------------------------------------------------------------
    # 步骤 2: 读取并解析 SOUL.md
    # ------------------------------------------------------------------
    print("\n📖 读取 SOUL.md...")
    try:
        soul_content = read_soul_content()
        print(f"   ✅ 成功读取 SOUL.md ({len(soul_content)} 字符)")
    except FileNotFoundError as e:
        print(f"   ❌ 错误: {e}")
        return
    except Exception as e:
        print(f"   ❌ 读取失败: {e}")
        return
    
    print("\n🔍 提取原始身份信息...")
    raw_identity = extract_raw_identity(soul_content)
    
    print(f"   名称: {raw_identity['name']}")
    print(f"   open_id: {open_id}")
    print(f"   核心职责: {raw_identity['responsibility'][:50]}..." if len(raw_identity['responsibility']) > 50 else f"   核心职责: {raw_identity['responsibility']}")
    
    # ------------------------------------------------------------------
    # 步骤 3: LLM 归纳提炼（可选）
    # ------------------------------------------------------------------
    print("\n🧠 使用 LLM 归纳提炼身份信息...")
    identity = await summarize_with_llm(raw_identity, soul_content)
    
    # 合并 open_id
    identity["open_id"] = open_id
    
    # 如果 LLM 没有返回某些字段，使用原始值
    for key in ["name", "responsibility", "team_role", "collaboration_rules"]:
        if key in identity and identity[key]:
            continue
        elif key in raw_identity:
            identity[key] = raw_identity[key]
    
    # ------------------------------------------------------------------
    # 步骤 4: 生成介绍文本
    # ------------------------------------------------------------------
    print("\n✍️  生成介绍文本...")
    introduction = generate_introduction(identity)
    print(f"   文本长度: {len(introduction)} 字符")
    print()
    print("--- 预览 ---")
    print(introduction[:300] + "..." if len(introduction) > 300 else introduction)
    print("---\n")
    
    # ------------------------------------------------------------------
    # 步骤 5: 获取飞书 Token
    # ------------------------------------------------------------------
    print("🔑 获取飞书 Token...")
    try:
        token = await get_tenant_token(APP_ID, APP_SECRET, DOMAIN)
        print("   ✅ Token 获取成功")
    except RuntimeError as e:
        print(f"   ❌ Token 获取失败: {e}")
        return
    
    # ------------------------------------------------------------------
    # 步骤 6: 发送消息
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
