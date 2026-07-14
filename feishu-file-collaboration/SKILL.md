---
name: feishu-file-collaboration
description: 飞书云空间文件协作 Skill。支持创建文件夹、上传/下载/更新文件、设置权限等功能。
author: Furong
version: 1.0.0
platforms: [feishu]
---

# 飞书云空间文件协作 Skill

## 概述

此 Skill 用于在飞书群聊中协作管理云空间文件。通过聊天命令即可操作飞书云空间，支持：
- 创建文件夹并设置权限
- 上传/下载/更新文件
- 自动设置"组织内所有人可读"权限
- 支持大文件分片上传（≤20MB 简单上传，>20MB 分片上传）

## 前置条件

1. **飞书应用凭证**：`.env` 文件中必须包含：
   ```bash
   FEISHU_APP_ID=cli_xxx
   FEISHU_APP_SECRET=xxx
   FEISHU_DEFAULT_ROOT_FOLDER_TOKEN=root  # 可选，默认 root
   ```

2. **飞书应用权限**：
   - `drive:drive` — 云空间权限
   - `drive:drive:readonly` — 云空间只读权限
   - `im:message.group_at_msg.include_bot:readonly` — 群聊 @ 权限

3. **Python 依赖**：
   ```bash
   pip install httpx pydantic-settings cachetools structlog python-dotenv
   ```

## 使用方法

### 基本命令

```bash
# 创建文件夹
python3 scripts/collaboration.py create-folder "项目名称"

# 上传文件
python3 scripts/collaboration.py upload ./文件.txt

# 下载文件
python3 scripts/collaboration.py download <file_token>

# 更新文件
python3 scripts/collaboration.py update <file_token> ./新文件.txt

# 查看帮助
python3 scripts/collaboration.py help
```

### 在 Hermes 会话中使用

通过 `/skill feishu-file-collaboration` 加载此 Skill 后，可以说：

```
创建文件夹：项目文档
上传文件：./设计文档.pdf
下载文件：file_xxx
更新文件：file_xxx ./新版本.pdf
```

## 核心功能

### 1. 创建文件夹

```bash
python3 scripts/collaboration.py create-folder "文件夹名称"
```

**功能**：
- 在根目录或指定父目录下创建文件夹
- 自动设置"组织内所有人可读"权限
- 返回文件夹 token

**示例**：
```
===✅️回复✅️=== 文件夹已创建
- 文件夹: 项目文档
- Token: folder_xxx
- 权限: 组织内所有人可读
```

### 2. 上传文件

```bash
python3 scripts/collaboration.py upload ./文件.txt [父目录 token]
```

**功能**：
- 支持简单上传（≤20MB）和分片上传（>20MB）
- 自动设置"组织内所有人可读"权限
- 返回文件 token

**示例**：
```
===✅️回复✅️=== 文件已上传
- 文件名: 设计文档.pdf
- Token: file_xxx
- 大小: 1.2MB
- 权限: 组织内所有人可读
```

### 3. 下载文件

```bash
python3 scripts/collaboration.py download <file_token> [保存路径]
```

**功能**：
- 下载文件到本地
- 支持指定保存路径

**示例**：
```
===✅️回复✅️=== 文件已下载
- 文件名: 设计文档.pdf
- 路径: ./downloads/设计文档.pdf
```

### 4. 更新文件

```bash
python3 scripts/collaboration.py update <file_token> ./新文件.txt
```

**功能**：
- 用本地文件覆盖云空间文件
- 自动设置"组织内所有人可读"权限

**示例**：
```
===✅️回复✅️=== 文件已更新
- 文件名: 设计文档.pdf
- Token: file_xxx
- 大小: 1.5MB
```

## 权限管理

### 自动权限设置

所有通过此 Skill 创建/上传的文件，都会自动设置为：
- **可见范围**：组织内所有人
- **权限级别**：可读

### 手动权限设置

```bash
python3 scripts/collaboration.py set-permission <file_token> read
python3 scripts/collaboration.py set-permission <file_token> write
```

## 故障排查

### 问题 1：飞书 API 返回 99992402

**原因**：权限不足或 token 过期

**解决**：
```bash
# 检查凭证是否正确
grep FEISHU_APP_ID ~/.hermes/.env
grep FEISHU_APP_SECRET ~/.hermes/.env

# 重新获取 token（脚本会自动处理）
```

### 问题 2：上传失败

**原因**：文件大小超限或网络问题

**解决**：
- 检查文件大小（建议 ≤100MB）
- 检查网络连接
- 重试上传

### 问题 3：文件夹不存在

**原因**：父目录 token 错误或文件夹已被删除

**解决**：
```bash
# 列出根目录文件
python3 scripts/collaboration.py list root

# 创建新文件夹
python3 scripts/collaboration.py create-folder "新文件夹"
```

## 相关文件

- `scripts/drive_service.py` — 飞书云空间 API 调用
- `scripts/permission_service.py` — 权限管理
- `scripts/file_ops_service.py` — 文件操作编排
- `scripts/command_handler.py` — 命令处理
- `scripts/settings.py` — 配置管理

## 版本历史

- **v1.0.0** (2026-07-12)
  - 初始版本
  - 支持创建文件夹、上传/下载/更新文件
  - 自动权限设置
  - 大文件分片上传

## 许可证

MIT License
