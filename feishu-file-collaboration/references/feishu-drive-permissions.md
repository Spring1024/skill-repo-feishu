# 飞书云空间 API 权限配置

## 问题

创建文件夹/上传文件时返回 404 或权限错误。

## 原因

飞书应用需要手动开通云空间权限：

1. 登录飞书开发者后台：https://open.feishu.cn/app
2. 找到应用 → 点击"权限管理"
3. 申请以下权限：
   - `drive:drive` — 云空间读写权限
   - `drive:drive:readonly` — 云空间只读权限
   - `drive:drive:app_access` — 云空间应用访问权限
4. 等待管理员审批

## 验证

```bash
# 测试 API 是否可用
curl -s 'https://open.feishu.cn/open-apis/drive/v1/files' \
  -H 'Authorization: Bearer <token>' \
  -d '{"name": "test", "type": "folder", "parent_node": "root"}'
```

如果返回 `code: 0` 则权限配置正确。
