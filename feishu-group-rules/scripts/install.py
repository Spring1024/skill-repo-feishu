#!/usr/bin/env python3
"""
飞书群聊协作规范自动安装脚本

功能：
1. 将规范内容追加到 SOUL.md 中
2. 如果已存在则跳过（避免重复）
3. 支持卸载（移除已添加的内容）

用法：
    # 安装
    python3 install.py install
    
    # 卸载
    python3 install.py uninstall
    
    # 检查状态
    python3 install.py status
"""

import os
import sys
import re


def get_skill_dir():
    """获取 Skill 目录路径"""
    return os.path.join(os.path.expanduser("~/.hermes/skills/feishu-group-rules"))


def get_soul_md_path():
    """获取 SOUL.md 路径"""
    return os.path.expanduser("~/.hermes/SOUL.md")


def get_core_content():
    """读取规范文档的核心内容"""
    skill_md = os.path.join(get_skill_dir(), "SKILL.md")
    if not os.path.exists(skill_md):
        print(f"❌ 未找到 SKILL.md: {skill_md}")
        print("请先安装 Skill: git clone git@github.com:Spring1024/skill-repo-feishu.git")
        sys.exit(1)
    
    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 截断到核心部分（去掉附录、版本历史、许可证）
    core_parts = []
    in_core = False
    for line in content.split("\n"):
        if line.startswith("## 一、"):
            in_core = True
        if in_core:
            core_parts.append(line)
        if line.startswith("## 附录") or line.startswith("## 版本历史") or line.startswith("## 许可证"):
            break
    
    return "\n".join(core_parts)


def check_installed():
    """检查是否已安装"""
    soul_md = get_soul_md_path()
    if not os.path.exists(soul_md):
        return False, "SOUL.md 不存在"
    
    with open(soul_md, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "## 飞书群聊协作规范" in content:
        return True, "已安装"
    return False, "未安装"


def install():
    """安装规范到 SOUL.md"""
    soul_md = get_soul_md_path()
    
    # 检查是否已安装
    installed, msg = check_installed()
    if installed:
        print("✅ 规范已安装，跳过")
        return
    
    # 创建 SOUL.md（如果不存在）
    if not os.path.exists(soul_md):
        with open(soul_md, "w", encoding="utf-8") as f:
            f.write("# SOUL.md\n\n")
    
    # 读取核心内容
    core_content = get_core_content()
    
    # 追加到 SOUL.md
    with open(soul_md, "a", encoding="utf-8") as f:
        f.write("\n\n## 飞书群聊协作规范\n\n")
        f.write(core_content)
    
    print("✅ 规范已安装到 SOUL.md")
    print(f"   新增内容: {len(core_content)} 字符")
    print(f"   文件路径: {soul_md}")


def uninstall():
    """从 SOUL.md 中移除规范"""
    soul_md = get_soul_md_path()
    
    if not os.path.exists(soul_md):
        print("❌ SOUL.md 不存在")
        return
    
    with open(soul_md, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 移除规范部分
    pattern = r"\n\n## 飞书群聊协作规范\n\n.*?(?=\n\n|$)"
    new_content = re.sub(pattern, "", content, flags=re.DOTALL)
    
    with open(soul_md, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print("✅ 规范已从 SOUL.md 中移除")


def status():
    """显示安装状态"""
    installed, msg = check_installed()
    soul_md = get_soul_md_path()
    
    print(f"SOUL.md: {soul_md}")
    print(f"状态: {'✅ 已安装' if installed else '❌ 未安装'}")
    print(f"详情: {msg}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 install.py install    - 安装规范到 SOUL.md")
        print("  python3 install.py uninstall  - 从 SOUL.md 中移除规范")
        print("  python3 install.py status     - 显示安装状态")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "install":
        install()
    elif command == "uninstall":
        uninstall()
    elif command == "status":
        status()
    else:
        print(f"❌ 未知命令: {command}")
        print("可用命令: install, uninstall, status")
        sys.exit(1)
