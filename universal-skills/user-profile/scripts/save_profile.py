#!/usr/bin/env python3
"""保存用户 profile 到本地文件

用法:
  python save_profile.py --scope global --language zh --file profile.md
  python save_profile.py --scope project --project-path D:/workspace/myproject --language zh --content "# Profile..."

存储位置:
  - global: ~/.cocursor/profiles/global.md
  - project: {project}/.cursor/rules/user-profile.mdc
"""

import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _ensure_gitignore(project_path, entry):
    """确保 .gitignore 中包含指定条目"""
    gitignore_path = os.path.join(project_path, ".gitignore")
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        if entry in content:
            return
        with open(gitignore_path, "a", encoding="utf-8") as f:
            if not content.endswith("\n"):
                f.write("\n")
            f.write(f"{entry}\n")
    else:
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(f"{entry}\n")


def save_profile(scope, content, project_path=None, language="zh"):
    """保存 profile 文件"""
    if scope == "project" and project_path:
        rules_dir = os.path.join(project_path, ".cursor", "rules")
        os.makedirs(rules_dir, exist_ok=True)
        file_path = os.path.join(rules_dir, "user-profile.mdc")

        # 添加 frontmatter
        mdc_content = f"""---
description: User coding profile - auto-generated
globs:
alwaysApply: true
---

{content}
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(mdc_content)

        _ensure_gitignore(project_path, ".cursor/rules/user-profile.mdc")

    else:
        profile_dir = os.path.join(Path.home(), ".cocursor", "profiles")
        os.makedirs(profile_dir, exist_ok=True)
        file_path = os.path.join(profile_dir, "global.md")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    return file_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Save user profile")
    parser.add_argument("--scope", choices=["global", "project"], default="global")
    parser.add_argument("--project-path", help="Project path (required if scope=project)")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    parser.add_argument("--content", help="Profile content (Markdown)")
    parser.add_argument("--file", help="Read profile from file")
    args = parser.parse_args()

    content = args.content
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    if not content:
        content = sys.stdin.read()
    if not content or not content.strip():
        print(json.dumps({"error": "No profile content provided"}), file=sys.stderr)
        sys.exit(1)

    file_path = save_profile(
        args.scope,
        content.strip(),
        project_path=args.project_path,
        language=args.language,
    )

    print(json.dumps({
        "success": True,
        "file_path": file_path,
        "scope": args.scope,
        "message": f"Profile saved to {file_path}",
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
