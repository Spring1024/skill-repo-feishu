---
name: feishu-group-introduction
description: 向飞书群聊发送群成员的身份介绍，自动从 SOUL.md 提取身份信息并提炼
author: Bobo
version: 1.0.0
platforms: [feishu]
---

# 飞书群聊身份介绍 Skill

## 概述

此 Skill 用于在飞书群聊中向所有成员发送当前 Hermes 智能体的身份介绍。

**核心特性**：
- 自动从 `SOUL.md` 读取身份信息
- 智能提炼核心职责和角色描述
- 支持 @所有人 功能
- 可配置目标群聊

## 前置条件

1. **飞书凭证配置**：`.env` 文件中必须包含：
   ```bash
   FEISHU_APP_ID=cli_xxx
   FEISHU_APP_SECRET=xxx
   FEISHU_HOME_CHANNEL=oc_xxx  # 目标群聊 ID
   FEISHU_DOMAIN=feishu  # 或 lark
   ```

2. **SOUL.md 文件**：位于 `$HERMES_HOME/SOUL.md` 或 `/data/hermes/SOUL.md`

3. **Python 依赖**：
   ```bash
   pip install httpx
   ```

## 使用方法

### 基本用法

```bash
python3 /data/hermes/skills/feishu-group-introduction/scripts/send_group_introduction.py
```

### 指定群聊

```bash
FEISHU_HOME_CHANNEL=oc_目标群聊ID python3 /data/hermes/skills/feishu-group-introduction/scripts/send_group_introduction.py
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
[正则匹配] 提取名称、open_id
    ↓
[LLM 提炼] 生成简洁介绍
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
| 核心职责 | `# Core Principles` 或 `# Identity` | "接收老大的高层战略方向..." |
| 团队角色 | `# Identity` 中的 "团队统帅" 部分 | "你是其他 Hermes Agent 的直接 Leader" |
| 协作规则 | `# A2A Collaboration` 或相关段落 | "@ 标签格式、协作模式等" |

### 3. 消息结构

```json
{
  "receive_id": "oc_群聊ID",
  "msg_type": "post",
  "content": {
    "zh_cn": {
      "title": "波比 已就位",
      "content": [
        [{"tag": "at", "user_id": "all", "user_name": "所有人"}],
        [{"tag": "lark_md", "text": "**大家好！我是波比。**\n\n我的 open_id: ou_xxx\n\n**核心职责**：...\n\n**团队角色**：...\n\n**协作规则**：..."}]
      ]
    }
  }
}
```

## 自定义配置

### 修改 SOUL.md 解析规则

编辑 `scripts/parse_soul.py` 中的 `_extract_identity()` 函数：

```python
def _extract_identity(soul_content: str) -> dict:
    """从 SOUL.md 内容中提取身份信息"""
    
    # 提取名称
    name_match = re.search(r'你是\s*([^\s，,]+)', soul_content)
    bot_name = name_match.group(1) if name_match else "未知助手"
    
    # 提取核心职责
    responsibility_match = re.search(r'核心职责[：:]\s*(.+?)(?:\n|$)', soul_content)
    responsibility = responsibility_match.group(1).strip() if responsibility_match else "无"
    
    return {
        "name": bot_name,
        "responsibility": responsibility,
        # ... 其他字段
    }
```

### 添加新的信息字段

在 `SKILL.md` 的 frontmatter 中添加：

```yaml
fields:
  - name: "团队角色"
    pattern: r"团队角色[：:]\s*(.+?)(?:\n|$)"
  - name: "联系方式"
    pattern: r"联系方式[：:]\s*(.+?)(?:\n|$)"
```

## 故障排查

### 问题 1：SOUL.md 找不到

**症状**：脚本报错 `FileNotFoundError`

**解决**：
```bash
# 检查 SOUL.md 路径
ls -la ~/.hermes/SOUL.md
ls -la /data/hermes/SOUL.md

# 设置 HERMES_HOME 环境变量
export HERMES_HOME=/data/hermes
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

## 相关文件

- `scripts/send_group_introduction.py` — 主脚本
- `scripts/parse_soul.py` — SOUL.md 解析器
- `templates/introduction.md.j2` — 消息模板（可选）
- `references/feishu-api.md` — 飞书 API 文档参考

## 版本历史

- **v1.0.0** (2026-07-11)
  - 初始版本
  - 支持自动从 SOUL.md 提取身份信息
  - 支持 @所有人 功能

## 许可证

MIT License
