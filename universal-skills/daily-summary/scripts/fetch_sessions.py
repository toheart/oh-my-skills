#!/usr/bin/env python3
"""获取指定日期的 Cursor 会话列表

用法:
  python fetch_sessions.py --date 2026-03-02
  python fetch_sessions.py --date 2026-03-02 --project D:/code/myproject

输出: JSON 格式的会话列表
"""

import json
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cursor_reader import get_sessions_by_date


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch Cursor sessions by date")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    parser.add_argument("--project", help="Filter by project path")
    args = parser.parse_args()

    try:
        sessions = get_sessions_by_date(args.date, args.project)
        output = {
            "date": args.date,
            "total_sessions": len(sessions),
            "sessions": sessions,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
