#!/usr/bin/env python3
"""
飞书云空间文件协作脚本

功能：
1. 创建文件夹并设置权限
2. 上传/下载/更新文件
3. 自动设置"组织内所有人可读"权限

用法：
    python3 collaboration.py create-folder "文件夹名称"
    python3 collaboration.py upload ./文件.txt
    python3 collaboration.py download <file_token>
    python3 collaboration.py update <file_token> ./新文件.txt
    python3 collaboration.py help
"""

import asyncio
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings
from core.token_manager import TokenManager
from core.cache import FolderCache
from services.drive_service import DriveService
from services.permission_service import PermissionService
from services.file_ops_service import FileOpsService


async def create_folder(name: str, parent_token: str = None) -> dict:
    """创建文件夹并设置权限"""
    settings = Settings()
    token_mgr = TokenManager(settings)
    cache = FolderCache(ttl=settings.folder_cache_ttl)
    drive_service = DriveService(settings, token_mgr)
    permission_service = PermissionService(token_mgr)
    
    result = await drive_service.create_folder(name, parent_token)
    await permission_service.set_org_readable(result.file_token)
    
    return {
        "file_token": result.file_token,
        "file_name": result.file_name,
        "type": result.type,
    }


async def upload_file(local_path: str, parent_token: str = None) -> dict:
    """上传文件并设置权限"""
    settings = Settings()
    token_mgr = TokenManager(settings)
    cache = FolderCache(ttl=settings.folder_cache_ttl)
    drive_service = DriveService(settings, token_mgr)
    permission_service = PermissionService(token_mgr)
    file_ops = FileOpsService(drive_service, permission_service)
    
    result = await file_ops.upload_local_file(local_path, parent_token)
    
    return {
        "file_token": result["file_token"],
        "file_name": result["file_name"],
        "type": result["type"],
    }


async def download_file(file_token: str, save_path: str = None) -> dict:
    """下载文件"""
    settings = Settings()
    token_mgr = TokenManager(settings)
    cache = FolderCache(ttl=settings.folder_cache_ttl)
    drive_service = DriveService(settings, token_mgr)
    permission_service = PermissionService(token_mgr)
    file_ops = FileOpsService(drive_service, permission_service)
    
    file_data = await file_ops.download_to_bytes(file_token)
    
    if not save_path:
        save_path = f"./downloads/{file_token}"
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(file_data)
    
    return {
        "file_token": file_token,
        "save_path": save_path,
        "size": len(file_data),
    }


async def update_file(file_token: str, local_path: str) -> dict:
    """更新文件"""
    settings = Settings()
    token_mgr = TokenManager(settings)
    cache = FolderCache(ttl=settings.folder_cache_ttl)
    drive_service = DriveService(settings, token_mgr)
    permission_service = PermissionService(token_mgr)
    file_ops = FileOpsService(drive_service, permission_service)
    
    result = await file_ops.update_local_file(file_token, local_path)
    
    return {
        "file_token": result["file_token"],
        "file_name": result["file_name"],
        "type": result["type"],
    }


def print_help():
    """打印帮助信息"""
    print("""
飞书云空间文件协作脚本

用法：
    python3 collaboration.py create-folder "文件夹名称" [父目录 token]
    python3 collaboration.py upload <本地文件路径> [父目录 token]
    python3 collaboration.py download <file_token> [保存路径]
    python3 collaboration.py update <file_token> <本地文件路径>
    python3 collaboration.py help

示例：
    python3 collaboration.py create-folder "项目文档"
    python3 collaboration.py upload ./设计文档.pdf
    python3 collaboration.py download file_xxx ./downloads/
    python3 collaboration.py update file_xxx ./新版本.pdf
""")


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1]
    
    if command == "create-folder":
        name = sys.argv[2] if len(sys.argv) > 2 else ""
        parent_token = sys.argv[3] if len(sys.argv) > 3 else None
        if not name:
            print("❌ 请提供文件夹名称")
            return
        result = await create_folder(name, parent_token)
        print(f"✅ 文件夹已创建: {result['file_name']}")
        print(f"   Token: {result['file_token']}")
        print(f"   权限: 组织内所有人可读")
    
    elif command == "upload":
        local_path = sys.argv[2] if len(sys.argv) > 2 else ""
        parent_token = sys.argv[3] if len(sys.argv) > 3 else None
        if not local_path:
            print("❌ 请提供本地文件路径")
            return
        result = await upload_file(local_path, parent_token)
        print(f"✅ 文件已上传: {result['file_name']}")
        print(f"   Token: {result['file_token']}")
        print(f"   权限: 组织内所有人可读")
    
    elif command == "download":
        file_token = sys.argv[2] if len(sys.argv) > 2 else ""
        save_path = sys.argv[3] if len(sys.argv) > 3 else None
        if not file_token:
            print("❌ 请提供 file_token")
            return
        result = await download_file(file_token, save_path)
        print(f"✅ 文件已下载: {result['save_path']}")
        print(f"   Token: {result['file_token']}")
        print(f"   大小: {result['size']} bytes")
    
    elif command == "update":
        file_token = sys.argv[2] if len(sys.argv) > 2 else ""
        local_path = sys.argv[3] if len(sys.argv) > 3 else ""
        if not file_token or not local_path:
            print("❌ 请提供 file_token 和 本地文件路径")
            return
        result = await update_file(file_token, local_path)
        print(f"✅ 文件已更新: {result['file_name']}")
        print(f"   Token: {result['file_token']}")
    
    elif command == "help":
        print_help()
    
    else:
        print(f"❌ 未知命令: {command}")
        print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
