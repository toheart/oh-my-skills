#!/usr/bin/env python3
"""保存用户画像

支持两种保存位置:
  - project: 保存到 {project}/.cursor/rules/user-profile.mdc（Cursor 自动加载）
  - global: 保存到 ~/.cursor/oh-my-skills/profiles/global.json

用法:
  python save_profile.py --scope project --project D:/code/myproject --file profile.md
  python save_profile.py --scope global --content "# User Profile..."
  python save_profile.py --scope project --project D:/code/myproject --query
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def get_global_storage_dir():
    """获取全局 profile 存储目录"""
    d = os.path.join(Path.home(), ".cursor", "oh-my-skills", "profiles")
    os.makedirs(d, exist_ok=True)
    return d


def save_profile(scope, content, project_path=None, language="zh"):
    """保存用户画像

    参数:
      scope: "project" 或 "global"
      content: Markdown 内容（不含 YAML frontmatter）
      project_path: 项目路径（scope=project 时必填）
      language: zh 或 en

    返回: {"file_path": ..., "git_ignored": bool}
    """
    if scope == "project":
        if not project_path:
            raise ValueError("project_path is required for scope='project'")
        return _save_project_profile(content, project_path, language)
    else:
        return _save_global_profile(content, language)


def _save_project_profile(content, project_path, language):
    """保存到项目级 .cursor/rules/user-profile.mdc"""
    rules_dir = os.path.join(project_path, ".cursor", "rules")
    os.makedirs(rules_dir, exist_ok=True)

    file_path = os.path.join(rules_dir, "user-profile.mdc")

    # 构建带 YAML frontmatter 的内容
    desc = "用户编码风格和偏好画像，帮助 AI 更好地理解用户" if language == "zh" else "User coding style and preference profile to help AI understand the user better"
    full_content = f"""---
description: {desc}
alwaysApply: true
---

{content}
"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    # 自动添加到 .gitignore
    git_ignored = _ensure_gitignore(project_path, ".cursor/rules/user-profile.mdc")

    return {
        "file_path": file_path,
        "git_ignored": git_ignored,
        "scope": "project",
    }


def _save_global_profile(content, language):
    """保存到全局 profile"""
    storage_dir = get_global_storage_dir()
    file_path = os.path.join(storage_dir, "global.json")

    data = {
        "content": content,
        "language": language,
        "updated_at": datetime.now().isoformat(),
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return {
        "file_path": file_path,
        "git_ignored": False,
        "scope": "global",
    }


def _ensure_gitignore(project_path, pattern):
    """确保 pattern 在 .gitignore 中"""
    gitignore_path = os.path.join(project_path, ".gitignore")

    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        if pattern in content:
            return True
        with open(gitignore_path, "a", encoding="utf-8") as f:
            if not content.endswith("\n"):
                f.write("\n")
            f.write(f"{pattern}\n")
    else:
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(f"{pattern}\n")

    return True


def load_profile(scope, project_path=None):
    """读取已保存的 profile"""
    if scope == "project":
        if not project_path:
            return None
        file_path = os.path.join(project_path, ".cursor", "rules", "user-profile.mdc")
        if not os.path.isfile(file_path):
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return {"content": f.read(), "file_path": file_path, "scope": "project"}
    else:
        file_path = os.path.join(get_global_storage_dir(), "global.json")
        if not os.path.isfile(file_path):
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Save user profile")
    parser.add_argument("--scope", required=True, choices=["project", "global"])
    parser.add_argument("--project", help="Project path (required for scope=project)")
    parser.add_argument("--content", help="Profile content (Markdown)")
    parser.add_argument("--file", help="Read profile from file")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    parser.add_argument("--query", action="store_true", help="Query existing profile")
    args = parser.parse_args()

    if args.query:
        data = load_profile(args.scope, args.project)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"error": "No profile found"}), file=sys.stderr)
            sys.exit(1)
        return

    content = args.content
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    if not content:
        content = sys.stdin.read()
    if not content or not content.strip():
        print(json.dumps({"error": "No profile content provided"}), file=sys.stderr)
        sys.exit(1)

    try:
        result = save_profile(args.scope, content.strip(), args.project, args.language)
        result["success"] = True
        result["message"] = f"Profile saved to {result['file_path']}"
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
