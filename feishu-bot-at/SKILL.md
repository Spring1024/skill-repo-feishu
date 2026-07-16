---
name: feishu-bot-at
description: 飞书群聊 Bot 互 @ 功能。当需要在飞书群聊中 @ 其他 Hermes Bot 时，使用此 Skill。
---

# 飞书群聊 Bot 互 @ 功能

## 何时使用

当用户要求在飞书群聊中 @ 其他 Bot 时，使用此 Skill。

> **重要**: 此 Skill 是 `feishu-group-rules` 的一部分。当在飞书群聊中协作时，必须先加载 `feishu-group-rules` Skill，然后在需要 @ 其他 Bot 时使用本 Skill。
> 
> 加载方式：`/skill feishu-group-rules`，然后 `/skill feishu-bot-at`

## 核心原则

**必须使用方案 A（直接调用飞书 Open API）**，构建 `post` 类型消息，`<at>` 标签作为 `content` 数组中的独立元素。

## 快速上手

### 方法 1: 使用脚本（推荐）

```bash
# 发送 @ 消息
python3 ~/.hermes/skills/feishu-bot-at/scripts/send-at-message.py \
    --target-open-id ou_xxx \
    --target-name 目标Bot名称 \
    --message "你好！"

# 测试 @ 功能是否正常
python3 ~/.hermes/skills/feishu-bot-at/scripts/test-bot-at.py

# 查询 Bot 信息
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action bot-info
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action list-groups
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action group-members --chat-id oc_xxx
```

### 方法 2: 直接调用 API

参见脚本源码 `scripts/send-at-message.py` 了解实现细节。

## 所需信息

| 信息 | 获取方式 |
|------|----------|
| `app_id` | 飞书开发者后台 → 应用凭证 |
| `app_secret` | 飞书开发者后台 → 应用凭证 |
| `chat_id` | 群聊 ID（格式 `oc_xxx`） |
| 目标 Bot 的 `open_id` | 通过飞书 API `/bot/v3/info` 获取 |

### 获取 open_id 的方法

**优先使用脚本自动获取**（当 open_id 未知或不确定时）：

```bash
# 获取当前 Bot 的 open_id
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action bot-info

# 获取群聊列表，找到 chat_id
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action list-groups

# 获取群成员列表，找到目标 Bot 的 open_id
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action group-members --chat-id oc_xxx
```

> ⚠️ **不要硬编码 open_id**，每次使用前通过 API 获取最新值。

### ⚠️ 经典陷阱：`on_` 不是 `ou_`！

Bot 的 open_id 曾在系统中被错误记录为 `on_xxx`（注意是 **`on_`** 而非 **`ou_`**）。这是一个历史遗留的拼写错误，会导致 @ 消息无法正确投递。

**验证方法**：飞书 open_id 格式永远是 `ou_` 开头（open user），不是 `on_`。如果看到 `on_` 开头的 ID，一定是错的。

**正确做法**：始终通过 `python3 scripts/feishu-bot-info.py --action bot-info` 获取最新 open_id，不要依赖记忆或缓存中的旧值。

## 操作步骤

### Step 1: 获取目标 Bot 的 open_id

```bash
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action bot-info
```

或手动调用：
```bash
curl -s 'https://open.feishu.cn/open-apis/bot/v3/info' \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

返回：
```json
{
  "bot": {
    "open_id": "ou_xxx",
    "app_name": "目标Bot名称"
  }
}
```

### Step 2: 确认群聊 chat_id

```bash
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action list-groups
```

### Step 3: 构建 API 请求

```python
import asyncio
import httpx
import json

async def at_bot(target_open_id, target_name, chat_id, message_text):
    # 从环境变量读取凭证
    app_id = os.environ.get('FEISHU_APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET')
    
    async with httpx.AsyncClient(timeout=30) as client:
        # 获取 token
        resp = await client.post(
            'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            json={'app_id': app_id, 'app_secret': app_secret}
        )
        token = resp.json()['tenant_access_token']
        headers = {'Authorization': f'Bearer {token}'}
        
        # 构建 post 类型消息
        payload = {
            'receive_id': chat_id,
            'msg_type': 'post',
            'content': json.dumps({
                'zh_cn': {
                    'title': '',
                    'content': [
                        # <at> 标签必须是独立元素
                        [{'tag': 'at', 'user_id': target_open_id, 'user_name': target_name}],
                        # 后续文本
                        [{'tag': 'md', 'text': f' {message_text}'}]
                    ]
                }
            })
        }
        
        # 发送
        resp2 = await client.post(
            'https://open.feishu.cn/open-apis/im/v1/messages',
            headers=headers,
            params={'receive_id_type': 'chat_id'},
            json=payload
        )
        return resp2.json()
```

### Step 4: 验证 @ 成功

API 返回中 `mentions` 数组应包含目标 Bot 的 open_id：

```json
{
  "mentions": [
    {
      "id": "ou_xxx",
      "name": "目标Bot名称"
    }
  ]
}
```

## 关键注意事项

- ✅ `msg_type` 必须是 `post`
- ✅ `<at>` 必须是 `content` 数组中的**独立元素**，不能放在 `md` 格式的 `text` 里
- ✅ `user_id` 填目标的 `open_id`（格式 `ou_xxx`）
- ❌ 不能填 `app_id`（格式 `cli_xxx`）
- ❌ 不能填自己的 `open_id`
- ❌ 不能用明文 `@Bot名称`

## 常见错误

### 错误 1: 群聊显示纯文本 `<at user_id="...">`

**原因**: `<at>` 标签被放在了 `md` 格式的 `text` 里。

**解决**: 确保 `<at>` 是 `content` 数组中的独立元素：
```json
[{"tag": "at", "user_id": "ou_xxx", "user_name": "Bot名称"}]
```

### 错误 2: 目标 Bot 没有收到 @ 通知

**原因**: `TARGET_OPEN_ID` 填错了。

**解决**: 每次使用前通过 `/bot/v3/info` API 获取最新的 open_id。

### 错误 3: 用了自己的 open_id

**原因**: `TARGET_OPEN_ID` 填成了发送方的 open_id。

**解决**: `TARGET_OPEN_ID` 必须是**目标 Bot** 的 open_id。

### 错误 4: 用了 app_id 代替 open_id

**原因**: app_id 格式是 `cli_xxx`，open_id 格式是 `ou_xxx`。

**解决**: 确保使用 `ou_xxx` 格式的 open_id。

## 前置配置检查清单

发送 @ 消息前，确认以下条件满足：

- [ ] `group_sessions_per_user: false`（config.yaml）
- [ ] `FEISHU_GROUP_POLICY=open`（.env）
- [ ] `FEISHU_ALLOW_BOTS=mentions`（.env）
- [ ] `FEISHU_REQUIRE_MENTION=false`（.env）
- [ ] 目标 Bot 开通了 `im:message.group_at_msg.include_bot:readonly` 权限
- [ ] 发送 Bot 开通了 `im:message:send_as_bot` 权限

## 防死循环插件

当 Bot 之间频繁 @ 可能导致无限循环时，可使用 `scripts/distributed-anti-loop-plugin.py`。

该插件提供滑动窗口计数 + 熔断降级机制：
- 15 分钟内对同一 Bot 的 @ 超过 20 次时，自动将消息转发给群主
- 预留 Redis 接口，未来可切换为分布式共享存储

用法：
```python
from scripts.distributed-anti-loop-plugin import DistributedAntiLoopPlugin

plugin = DistributedAntiLoopPlugin(
    self_open_id="${SELF_OPEN_ID}",
    feishu_app_id="${FEISHU_APP_ID}",
    feishu_app_secret="${FEISHU_APP_SECRET}",
)

should_rewrite, payload = await plugin.check_before_send(
    target_open_id="${TARGET_OPEN_ID}",
    message_payload=payload,
    group_owner_open_id="${GROUP_OWNER_OPEN_ID}"
)
```

## 快速命令

```bash
# 获取 Bot 的 open_id
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action bot-info

# 获取群聊列表
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action list-groups

# 获取群成员
python3 ~/.hermes/skills/feishu-bot-at/scripts/feishu-bot-info.py --action group-members --chat-id oc_xxx

# 测试 @ 功能
python3 ~/.hermes/skills/feishu-bot-at/scripts/test-bot-at.py

# 发送 @ 消息
python3 ~/.hermes/skills/feishu-bot-at/scripts/send-at-message.py \
    --target-open-id ou_xxx \
    --target-name Bot名称 \
    --message "你好！"
```

## 相关文档

- `references/adapter-modification-pitfalls.md` — 修改适配器代码后的必要步骤和常见陷阱
- `references/feishu-reply-quote-injection.md` — 飞书 Bot 引用消息注入机制分析
- `scripts/distributed-anti-loop-plugin.py` — 防死循环插件
- **关联 Skill**：
  - `feishu-group-rules` — 群聊协作规范（必须先加载）
  - `feishu-file-collaboration` — 大文件协作（文件通过云空间交换）
  - `feishu-group-introduction` — 群聊身份介绍
