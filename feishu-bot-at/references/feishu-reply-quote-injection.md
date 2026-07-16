# 飞书 Bot 引用消息注入机制分析

## 概述

本文档记录了飞书适配器中 `reply_to_text` 注入机制的完整链路、行为特征及已知问题。

## 完整调用链路

### 1. 飞书推送入站消息

飞书通过 WebSocket/Webhook 推送消息事件，消息对象中包含：
- `parent_id`: 被引用消息的 ID（如果有）
- `root_id`: 线程根消息 ID
- `message_id`: 当前消息 ID

### 2. 适配器提取引用 ID

`adapter.py` 第 3647-3652 行 `_process_inbound_message`:

```python
reply_to_message_id = (
    getattr(message, "parent_id", None)          # 首选：直接回复的父消息
    or getattr(message, "upper_message_id", None)  # 备选
    or getattr(message, "root_id", None)          # 备选：线程根消息
    or None
)
```

### 3. 通过飞书 API 获取被引用消息原文

`adapter.py` 第 3653 行：

```python
reply_to_text = await self._fetch_message_text(reply_to_message_id) if reply_to_message_id else None
```

`_fetch_message_text`（第 4556-4587 行）调用 `im/v1/message.get` API，解析被引用消息的 `content` 字段，提取纯文本。

### 4. 注入 MessageEvent

`adapter.py` 第 3686-3698 行：

```python
normalized = MessageEvent(
    text=text,
    ...
    reply_to_message_id=reply_to_message_id,
    reply_to_text=reply_to_text,
    ...
)
```

### 5. Gateway 层注入到 AI 会话上下文

`run.py` 第 10572-10586 行：

```python
if getattr(event, "reply_to_text", None) and event.reply_to_message_id:
    reply_snippet = event.reply_to_text[:500]
    if getattr(event, "reply_to_is_own_message", False):
        message_text = f'[Replying to your previous message: "{reply_snippet}"]\n\n{message_text}'
    else:
        message_text = f'[Replying to: "{reply_snippet}"]\n\n{message_text}'
```

**关键点**：无论引用消息的来源是谁（用户还是其他 Bot），注入格式都是 `[Replying to: "..."]`，**没有区分发送者身份**。

## 已知问题

### 问题：Bot-to-Bot 协作时语义歧义

当 Bot A @ Bot B 并引用用户消息时，Bot B 收到的消息文本中同时包含：
1. 引用前缀 `[Replying to: "用户原始消息"]`
2. Bot A 的实际消息正文

Bot B 可能误将引用前缀当作用户直发指令，而非 Bot A 引用的上下文。

### 影响范围

- 所有涉及飞书群聊 Bot 互 @ 的场景
- 特别是多 Bot 协作、任务委派、接力对话等场景

### 设计意图

代码注释（run.py 10573-10578 行）说明了注入 `reply_to_text` 的初衷：

> "The prefix isn't deduplication, it's disambiguation: it tells the agent which prior message the user is referencing."

这个设计对**用户-单 Bot** 场景是有效的，但对 **Bot-Bot-用户** 三方场景引入了歧义。

## 改进建议

### 短期方案（接收方 Bot 侧）

Bot 在收到带有 `[Replying to: "..."]` 前缀的消息时，应：
1. 检查当前消息的 `mentions` 字段
2. 如果 `mentions` 中有非自己的 Bot ID，则引用前缀属于**协作上下文**，非用户指令
3. 优先处理 Bot 正文，引用前缀仅作为参考

### 长期方案（Gateway 层）

修改 `run.py` 10572-10586 行的注入逻辑，增加发送者标识：

```python
# 改进后的格式示例：
[Quoted context from <sender_name> (<sender_open_id>): "..."]
```

或者在 `MessageEvent` 中增加 `reply_to_sender_id` 字段，让 Agent 能明确知道引用消息的发送者身份。

## 相关代码位置

| 文件 | 行号 | 函数/方法 |
|------|------|-----------|
| `gateway/platforms/feishu/adapter.py` | 3647-3653 | `_process_inbound_message` 提取引用 ID |
| `gateway/platforms/feishu/adapter.py` | 4556-4587 | `_fetch_message_text` API 获取原文 |
| `gateway/platforms/base.py` | 1748-1749 | `MessageEvent` 定义 `reply_to_*` 字段 |
| `gateway/run.py` | 10572-10586 | Gateway 层注入到 `message_text` |
