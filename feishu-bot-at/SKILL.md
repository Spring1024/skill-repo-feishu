---
name: feishu-bot-at
description: 飞书群聊 Bot 互 @ 功能。当需要在飞书群聊中 @ 其他 Hermes Bot（波比、超人强等）时，使用此 Skill。
---

# 飞书群聊 Bot 互 @ 功能

## 何时使用

当用户要求在飞书群聊中 @ 其他 Bot 时，使用此 Skill。

## 核心原则

**必须使用方案 A（直接调用飞书 Open API）**，构建 `post` 类型消息，`<at>` 标签作为 `content` 数组中的独立元素。

## 快速上手

### 方法 1: 使用脚本（推荐）

```bash
# 发送 @ 消息
python3 ~/.hermes/skills/feishu-bot-at/scripts/send-at-message.py \
    --target-open-id ou_cb099e84ffa7033c4a51d4b332f4340f \
    --target-name 波比 \
    --message "你好波比！"

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

**Bot open_id 参考表**（仅供参考，每次使用前应通过 API 获取最新值）：

| Bot | open_id | 备注 |
|-----|---------|------|
| 芙蓉 | `ou_f18431cc99607e49e29094cb589bb5c6` | 本 Bot |
| 波比 | `ou_cb099e84ffa7033c4a51d4b332f4340f` | 用户提供 / 飞书 API |
| 超人强 | `ou_9dbb6d61c1a85a6b2b6a339ea697609f` | 用户提供 / 飞书 API |

> ⚠️ **不要硬编码 open_id**，每次使用前通过 API 获取最新值。

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
    "app_name": "波比"
  }
}
```

### Step 2: 调用飞书 API 发送 @ 消息

```python
import httpx
import json

app_id = 'cli_aada30be933adcba'
app_secret = '"${FEISHU_APP_SECRET}"'
chat_id = 'oc_7da955a1c5eab6d20bf62adf4fcd930b'
target_open_id = 'ou_xxx'  # 从 Step 1 获取
target_name = '波比'

# 1. 获取 tenant_access_token
token_resp = httpx.post(
    'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id': app_id, 'app_secret': app_secret}
)
token = token_resp.json()['tenant_access_token']

# 2. 构建消息（关键：<at> 是独立元素）
payload = {
    'receive_id': chat_id,
    'msg_type': 'post',
    'content': json.dumps({
        'zh_cn': {
            'title': '',
            'content': [
                [{'tag': 'at', 'user_id': target_open_id, 'user_name': target_name}],
                [{'tag': 'md', 'text': ' 你好波比！'}]
            ]
        }
    })
}

# 3. 发送消息
resp = httpx.post(
    'https://open.feishu.cn/open-apis/im/v1/messages',
    headers={'Authorization': f'Bearer {token}'},
    params={'receive_id_type': 'chat_id'},
    json=payload
)

# 4. 验证成功
result = resp.json()
assert result['code'] == 0
assert any(m['id'] == target_open_id for m in result['data']['mentions'])
```

### Step 3: 验证 @ 成功

成功的响应中 `mentions` 数组应包含目标 Bot 的 open_id：

```json
{
  "mentions": [
    {
      "id": "ou_xxx",
      "name": "波比",
      "key": "@_user_1"
    }
  ]
}
```

## 常见错误

### 错误 1: 群聊显示纯文本 `<at user_id="...">`

**原因**: `<at>` 标签被放在了 `md` 格式的 `text` 里。

**解决**: 确保 `<at>` 是 `content` 数组中的独立元素：
```json
[{"tag": "at", "user_id": "ou_xxx", "user_name": "波比"}]
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
    --target-name 波比 \
    --message "你好波比！"
```
