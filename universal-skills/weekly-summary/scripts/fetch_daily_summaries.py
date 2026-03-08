#!/usr/bin/env python3
"""读取指定日期范围内的已保存日报 JSON，用于周报聚合

用法:
  python fetch_daily_summaries.py --start 2026-02-24 --end 2026-03-02

输出: JSON 格式的日报列表和统计信息
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def get_daily_storage_dir():
    """获取日报存储目录"""
    return os.path.join(Path.home(), ".cursor", "oh-my-skills", "daily-summaries")


def load_daily_summaries(start_date, end_date):
    """读取日期范围内的所有已保存日报

    参数:
      start_date: YYYY-MM-DD 起始日期（含）
      end_date: YYYY-MM-DD 结束日期（含）

    返回: (summaries_list, missing_dates_list)
    """
    storage_dir = get_daily_storage_dir()
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    summaries = []
    missing_dates = []

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        file_path = os.path.join(storage_dir, f"{date_str}.json")

        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                summaries.append(data)
            except (json.JSONDecodeError, OSError):
                missing_dates.append(date_str)
        else:
            missing_dates.append(date_str)

        current += timedelta(days=1)

    return summaries, missing_dates


def aggregate_stats(summaries):
    """聚合日报统计数据"""
    total_sessions = 0
    all_categories = {}

    for s in summaries:
        total_sessions += s.get("total_sessions", 0)
        cats = s.get("categories", {})
        for k, v in cats.items():
            all_categories[k] = all_categories.get(k, 0) + v

    return {
        "total_sessions": total_sessions,
        "working_days": len(summaries),
        "categories": all_categories,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch saved daily summaries for a date range")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    args = parser.parse_args()

    summaries, missing = load_daily_summaries(args.start, args.end)
    stats = aggregate_stats(summaries)

    output = {
        "start_date": args.start,
        "end_date": args.end,
        "found_count": len(summaries),
        "missing_dates": missing,
        "aggregate_stats": stats,
        "summaries": summaries,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
