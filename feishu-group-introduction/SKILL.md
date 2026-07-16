---
name: feishu-group-introduction
description: 向飞书群聊发送群成员的身份介绍，自动从 SOUL.md 提取身份信息并提炼
author: Bobo
version: 1.0.2
platforms: [feishu]
---

# 飞书群聊身份介绍 Skill

## 概述

此 Skill 用于在飞书群聊中向所有成员发送当前 Hermes 智能体的身份介绍。

**核心特性**：
- 自动从 `SOUL.md` 读取身份信息
- 优先通过飞书 API 获取最新 open_id
- 可选 LLM 归纳提炼 SOUL.md 内容
- 支持 @所有人 功能
- 可配置目标群聊
- **自动触发**：Bot 入群时自动发送介绍

## 自动触发机制

### 工作原理

当 Hermes Gateway 的飞书适配器检测到 `im.chat.member.bot.added_v1` 事件时，会自动调用 `send_group_introduction.py` 脚本向新群发送介绍。

### 触发条件

1. Bot 被拉入新群聊
2. 适配器监听到 `im.chat.member.bot.added_v1` 事件
3. 检查是否已在此群发送过介绍（避免重复）
4. 调用 `send_group_introduction.py` 脚本

### 配置要求

适配器需要以下配置才能自动触发：

```yaml
# config.yaml
feishu:
  app_id: "${FEISHU_APP_ID}"
  app_secret: "${FEISHU_APP_SECRET}"
```

```bash
# .env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
```

### 脚本路径

适配器会按以下顺序查找脚本：
1. `~/.hermes/skills/feishu-group-introduction/scripts/send_group_introduction.py`
2. 如果找不到，记录警告日志并跳过

## 前置条件

1. **飞书凭证配置**：`.env` 文件中必须包含：
   ```bash
   FEISHU_APP_ID=cli_xxx
   FEISHU_APP_SECRET=xxx
   FEISHU_HOME_CHANNEL=oc_xxx  # 目标群聊 ID
   FEISHU_DOMAIN=feishu  # 或 lark
   ```

2. **SOUL.md 文件**：位于 `~/.hermes/SOUL.md`

3. **Python 依赖**：
   ```bash
   pip install httpx
   ```

4. **LLM 归纳提炼（可选）**：如需 LLM 自动提炼 SOUL.md 内容，需额外配置 LLM API

## 使用方法

### 基本用法

```bash
python3 ~/.hermes/skills/feishu-group-introduction/scripts/send_group_introduction.py
```

### 指定群聊

```bash
FEISHU_HOME_CHANNEL=oc_目标群聊ID python3 ~/.hermes/skills/feishu-group-introduction/scripts/send_group_introduction.py
```

### 在 Hermes 会话中使用

通过 `/skill feishu-group-introduction` 加载此 Skill 后，可以说：

```
向群聊发送我的身份介绍
```

## 工作原理

### 1. 身份信息提取流程

```
SOUL.md 文件
    ↓
[正则匹配] 提取名称、核心职责
    ↓
[LLM 提炼] (可选) 生成简洁介绍
    ↓
[模板填充] 构建完整消息
    ↓
[飞书 API] 发送到群聊
```

### 2. SOUL.md 解析规则

脚本会按以下优先级提取信息：

| 信息类型 | 提取位置 | 示例 |
|---------|---------|------|
| 名称 | `# Identity` 段落 | "你是波比（Bobo）" → "波比" |
| 核心职责 | `# Identity` 段落的前 3 句 | "接收老大的高层战略方向..." |
| 团队角色 | `# Identity` 段落的第 4-6 句 | "你是其他 Hermes Agent 的直接 Leader" |
| 协作规则 | `# A2A Collaboration` 或相关段落 | "@ 标签格式、协作模式等" |

### 3. open_id 获取优先级

1. **优先**：通过飞书 API `/bot/v3/info` 获取最新 open_id
2. **回退**：从缓存文件 `~/.hermes/fbc-cache/registry.json` 读取
3. **最后**：从环境变量 `FEISHU_BOT_OPEN_ID` 读取

### 4. 消息结构

```json
{
  "receive_id": "oc_群聊ID",
  "msg_type": "post",
  "content": {
    "zh_cn": {
      "title": "",
      "content": [
        [{"tag": "at", "user_id": "all", "user_name": "所有人"}],
        [{"tag": "md", "text": "**大家好！我是波比。**\n\n**核心职责**：...\n\n**团队角色**：..."}]
      ]
    }
  }
}
```

## 故障排查

### 问题 1：SOUL.md 找不到

**症状**：脚本报错 `FileNotFoundError`

**解决**：
```bash
# 检查 SOUL.md 路径
ls -la ~/.hermes/SOUL.md
```

### 问题 2：飞书 API 返回 99992402

**原因**：权限不足或 token 过期

**解决**：
```bash
# 检查凭证是否正确
grep FEISHU_APP_ID /data/hermes/.env
grep FEISHU_APP_SECRET /data/hermes/.env

# 重新获取 token（脚本会自动处理）
```

### 问题 3：@所有人 不生效

**原因**：`msg_type` 不是 `post` 或 `user_id` 不是 `"all"`

**解决**：确保脚本中：
```python
payload = {
    'msg_type': 'post',  # ⚠️ 必须是 post
    'content': json.dumps({
        'zh_cn': {
            'content': [
                [{'tag': 'at', 'user_id': 'all', 'user_name': '所有人'}],  # ⚠️ user_id 必须是 "all"
                ...
            ]
        }
    })
}
```

### 问题 4：自动触发不生效

**症状**：Bot 入群后没有自动发送介绍

**排查步骤**：
1. 检查 Gateway 日志：`grep "Bot added to chat" ~/.hermes/logs/gateway.log`
2. 检查脚本是否存在：`ls -la ~/.hermes/skills/feishu-group-introduction/scripts/send_group_introduction.py`
3. 检查飞书权限：确认应用开通了 `im:message.group_at_msg.include_bot:readonly` 权限
4. 手动运行脚本测试：`FEISHU_HOME_CHANNEL=oc_xxx python3 scripts/send_group_introduction.py`

## 相关文件

- `scripts/send_group_introduction.py` — 主脚本
- `SKILL.md` — 本文档

## 版本历史

- **v1.0.2** (2026-07-12) — 新增自动触发机制、修复 open_id 获取、优化消息格式
- **v1.0.1** (2026-07-11) — 修复 open_id 获取、新增 LLM 归纳功能
- **v1.0.0** (2026-07-11) — 初始版本：支持自动提取 SOUL.md 身份信息、@所有人 功能

## 许可证

MIT License
