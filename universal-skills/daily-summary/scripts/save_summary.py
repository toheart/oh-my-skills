#!/usr/bin/env python3
"""保存日报到本地 JSON 文件

用法:
  python save_summary.py --date 2026-03-02 --file summary.md
  python save_summary.py --date 2026-03-02 --content "# 日报内容..."
  python save_summary.py --date 2026-03-02 --file summary.md --categories '{"coding":5,"problem_solving":3}'

存储位置: ~/.cursor/oh-my-skills/daily-summaries/{date}.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def get_storage_dir():
    """获取日报存储目录"""
    d = os.path.join(Path.home(), ".cursor", "oh-my-skills", "daily-summaries")
    os.makedirs(d, exist_ok=True)
    return d


def save_daily_summary(date_str, summary, language="zh", categories=None,
                       total_sessions=0, projects=None):
    """保存日报

    参数:
      date_str: YYYY-MM-DD
      summary: Markdown 内容
      language: zh 或 en
      categories: 工作类型统计 dict
      total_sessions: 会话总数
      projects: 项目列表
    """
    storage_dir = get_storage_dir()
    file_path = os.path.join(storage_dir, f"{date_str}.json")

    data = {
        "date": date_str,
        "summary": summary,
        "language": language,
        "total_sessions": total_sessions,
        "categories": categories or {},
        "projects": projects or [],
        "saved_at": datetime.now().isoformat(),
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return file_path


def load_daily_summary(date_str):
    """读取已保存的日报"""
    file_path = os.path.join(get_storage_dir(), f"{date_str}.json")
    if not os.path.isfile(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Save daily summary")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    parser.add_argument("--content", help="Summary content (Markdown)")
    parser.add_argument("--file", help="Read summary from file")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    parser.add_argument("--categories", help="Work categories JSON string")
    parser.add_argument("--total-sessions", type=int, default=0)
    parser.add_argument("--query", action="store_true", help="Query existing summary")
    args = parser.parse_args()

    if args.query:
        data = load_daily_summary(args.date)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"error": f"No summary found for {args.date}"}), file=sys.stderr)
            sys.exit(1)
        return

    summary = args.content
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            summary = f.read()
    if not summary:
        summary = sys.stdin.read()
    if not summary or not summary.strip():
        print(json.dumps({"error": "No summary content provided"}), file=sys.stderr)
        sys.exit(1)

    categories = None
    if args.categories:
        try:
            categories = json.loads(args.categories)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid categories JSON: {e}"}), file=sys.stderr)
            sys.exit(1)

    file_path = save_daily_summary(
        args.date, summary.strip(), args.language,
        categories, args.total_sessions,
    )

    print(json.dumps({
        "success": True,
        "file_path": file_path,
        "date": args.date,
        "message": f"Daily summary saved to {file_path}",
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
