#!/usr/bin/env python3
"""保存周报到本地 JSON 文件

用法:
  python save_weekly.py --week-start 2026-02-24 --file report.md
  python save_weekly.py --week-start 2026-02-24 --content "# 周报内容..."
  python save_weekly.py --week-start 2026-02-24 --query

存储位置: ~/.cursor/oh-my-skills/weekly-summaries/{week_start}.json
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def get_storage_dir():
    """获取周报存储目录"""
    d = os.path.join(Path.home(), ".cursor", "oh-my-skills", "weekly-summaries")
    os.makedirs(d, exist_ok=True)
    return d


def save_weekly_summary(week_start, summary, language="zh",
                        total_sessions=0, working_days=0,
                        categories=None, key_accomplishments=None):
    """保存周报"""
    # 计算 week_end（周日）
    start = datetime.strptime(week_start, "%Y-%m-%d")
    week_end = (start + timedelta(days=6)).strftime("%Y-%m-%d")

    storage_dir = get_storage_dir()
    file_path = os.path.join(storage_dir, f"{week_start}.json")

    data = {
        "week_start": week_start,
        "week_end": week_end,
        "summary": summary,
        "language": language,
        "total_sessions": total_sessions,
        "working_days": working_days,
        "categories": categories or {},
        "key_accomplishments": key_accomplishments or [],
        "saved_at": datetime.now().isoformat(),
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return file_path


def load_weekly_summary(week_start):
    """读取已保存的周报"""
    file_path = os.path.join(get_storage_dir(), f"{week_start}.json")
    if not os.path.isfile(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Save weekly summary")
    parser.add_argument("--week-start", required=True, help="Week start date (Monday) YYYY-MM-DD")
    parser.add_argument("--content", help="Summary content (Markdown)")
    parser.add_argument("--file", help="Read summary from file")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    parser.add_argument("--total-sessions", type=int, default=0)
    parser.add_argument("--working-days", type=int, default=0)
    parser.add_argument("--categories", help="Work categories JSON string")
    parser.add_argument("--accomplishments", help="Key accomplishments JSON array string")
    parser.add_argument("--query", action="store_true", help="Query existing summary")
    args = parser.parse_args()

    if args.query:
        data = load_weekly_summary(args.week_start)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"error": f"No weekly summary found for {args.week_start}"}), file=sys.stderr)
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

    accomplishments = None
    if args.accomplishments:
        try:
            accomplishments = json.loads(args.accomplishments)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid accomplishments JSON: {e}"}), file=sys.stderr)
            sys.exit(1)

    file_path = save_weekly_summary(
        args.week_start, summary.strip(), args.language,
        args.total_sessions, args.working_days,
        categories, accomplishments,
    )

    print(json.dumps({
        "success": True,
        "file_path": file_path,
        "week_start": args.week_start,
        "message": f"Weekly summary saved to {file_path}",
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
