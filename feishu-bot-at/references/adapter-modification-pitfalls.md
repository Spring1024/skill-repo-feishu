# 适配器修改注意事项

## 修改 adapter.py 后的必要步骤

每次修改 `plugins/platforms/feishu/adapter.py` 后，必须执行以下步骤，否则 Gateway 会加载旧代码：

### 1. 清除 pyc 缓存

```bash
find ~/.hermes/hermes-agent/plugins/platforms/feishu -name "*.pyc" -delete
find ~/.hermes/hermes-agent/plugins/platforms/feishu -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
```

### 2. 重启 Gateway

**必须在外部终端执行**（不能在 Gateway 进程内部）：

```bash
hermes gateway restart
```

如果 `restart` 不生效，直接 kill 后启动：

```bash
pkill -f "hermes.*gateway"
sleep 2
hermes gateway start
```

## 常见陷阱

### 陷阱 1: 环境变量未传递给子进程

Gateway 进程启动后，其环境变量是固定的。如果适配器代码需要从 `.env` 文件读取凭证，**不能依赖 `os.getenv()`**，因为 Gateway 进程可能没有加载这些环境变量。

**正确做法**：在适配器代码中显式读取 `~/.hermes/.env` 文件：

```python
env_file = os.path.expanduser("~/.hermes/.env")
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
```

### 陷阱 2: 入群事件触发但群介绍未发送

日志中出现 `Bot added to chat` 但没有 `Running group introduction`，说明：
1. 适配器代码未重新加载（需要清除 pyc + 重启）
2. 脚本不存在或路径错误
3. 脚本执行失败（检查 stderr）

### 陷阱 3: open_id 拼写错误

飞书 open_id 格式是 `ou_xxx`，不是 `on_xxx`。历史遗留的错误值 `on_31f5a8cdc9c5aebdee987d9297dcbc74` 已被废弃。

**验证方法**：始终通过 `GET /bot/v3/info` API 获取最新 open_id。
