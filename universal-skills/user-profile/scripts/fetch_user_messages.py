#!/usr/bin/env python3
"""获取用户消息用于画像分析

采用采样策略：最近 N 个会话完整提取，历史会话按比例采样，
避免数据量过大。只提取用户消息（非 AI 回复）。

用法:
  python fetch_user_messages.py --scope project --project D:/code/myproject
  python fetch_user_messages.py --scope global --days 30
  python fetch_user_messages.py --scope global --recent 10 --sample-rate 0.3

输出: JSON 格式的用户消息 + 统计信息
"""

import json
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cursor_reader import (
    get_all_workspaces,
    get_composer_data,
    get_transcript_content,
    get_projects_dir,
)
from transcript_parser import parse_transcript, extract_text_only


def fetch_user_messages(scope="global", project_path=None, days_back=30,
                        recent_sessions=10, sample_rate=0.3,
                        max_historical_msgs=200):
    """获取用户消息

    参数:
      scope: "global" 或 "project"
      project_path: 项目路径（scope=project 时必填）
      days_back: 分析天数
      recent_sessions: 完整提取最近 N 个会话
      sample_rate: 历史会话采样率 (0-1)
      max_historical_msgs: 历史消息最大数量

    返回:
      {
        "recent_messages": [...],
        "historical_messages": [...],
        "stats": {
            "total_sessions_scanned": N,
            "recent_sessions_count": N,
            "historical_sessions_sampled": N,
            "total_user_messages": N,
            "primary_language": "zh"|"en",
            "project_distribution": {...},
            "time_distribution": {...}
        }
      }
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    cutoff_ms = int(cutoff_date.timestamp() * 1000)

    # 收集所有符合条件的会话
    workspaces = get_all_workspaces()
    if scope == "project" and project_path:
        norm_target = os.path.normcase(os.path.normpath(os.path.abspath(project_path)))
        workspaces = [
            w for w in workspaces
            if os.path.normcase(os.path.normpath(os.path.abspath(w["project_path"]))) == norm_target
        ]

    all_sessions = []
    for ws in workspaces:
        try:
            composers = get_composer_data(ws["workspace_id"])
        except (FileNotFoundError, OSError):
            continue

        for c in composers:
            updated_ms = c.get("lastUpdatedAt", 0)
            if updated_ms < cutoff_ms:
                continue
            all_sessions.append({
                "session_id": c.get("composerId", ""),
                "name": c.get("name", ""),
                "project_name": ws["project_name"],
                "project_path": ws["project_path"],
                "created_at": c.get("createdAt", 0),
                "updated_at": updated_ms,
            })

    # 按更新时间排序（最新在前）
    all_sessions.sort(key=lambda s: s["updated_at"], reverse=True)

    # 拆分为最近和历史
    recent = all_sessions[:recent_sessions]
    historical = all_sessions[recent_sessions:]

    # 对历史会话采样
    if sample_rate < 1.0 and len(historical) > 0:
        sample_count = max(1, int(len(historical) * sample_rate))
        historical = random.sample(historical, min(sample_count, len(historical)))

    # 提取用户消息
    recent_messages = []
    for s in recent:
        msgs = _extract_user_messages(s)
        recent_messages.extend(msgs)

    historical_messages = []
    for s in historical:
        msgs = _extract_user_messages(s)
        historical_messages.extend(msgs)
        if len(historical_messages) >= max_historical_msgs:
            historical_messages = historical_messages[:max_historical_msgs]
            break

    # 统计信息
    all_messages = recent_messages + historical_messages
    stats = _compute_stats(all_messages, all_sessions, recent, historical)

    return {
        "recent_messages": recent_messages,
        "historical_messages": historical_messages,
        "stats": stats,
    }


def _extract_user_messages(session_info):
    """从单个会话提取用户消息"""
    content = get_transcript_content(session_info["session_id"])
    if not content:
        return []

    messages = parse_transcript(content, text_only=True, user_only=True)
    messages = extract_text_only(messages)

    result = []
    for msg in messages:
        text = msg["text"].strip()
        if not text or len(text) < 5:
            continue
        result.append({
            "text": text,
            "session_id": session_info["session_id"],
            "session_name": session_info["name"],
            "project_name": session_info["project_name"],
        })
    return result


def _compute_stats(all_messages, all_sessions, recent, historical):
    """计算统计信息"""
    # 语言检测
    zh_count = 0
    en_count = 0
    for msg in all_messages:
        for ch in msg["text"]:
            if "\u4e00" <= ch <= "\u9fff":
                zh_count += 1
            elif ch.isascii() and ch.isalpha():
                en_count += 1

    primary_language = "zh" if zh_count > en_count * 0.5 else "en"

    # 项目分布
    project_dist = defaultdict(int)
    for msg in all_messages:
        project_dist[msg["project_name"]] += 1

    # 时间分布
    time_dist = {"morning": 0, "afternoon": 0, "evening": 0, "night": 0}
    for s in all_sessions:
        created_ms = s.get("created_at", 0)
        if created_ms:
            hour = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).hour
            if 6 <= hour < 12:
                time_dist["morning"] += 1
            elif 12 <= hour < 18:
                time_dist["afternoon"] += 1
            elif 18 <= hour < 22:
                time_dist["evening"] += 1
            else:
                time_dist["night"] += 1

    return {
        "total_sessions_scanned": len(all_sessions),
        "recent_sessions_count": len(recent),
        "historical_sessions_sampled": len(historical),
        "total_user_messages": len(all_messages),
        "primary_language": primary_language,
        "project_distribution": dict(project_dist),
        "time_distribution": time_dist,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch user messages for profile analysis")
    parser.add_argument("--scope", required=True, choices=["global", "project"])
    parser.add_argument("--project", help="Project path (required for scope=project)")
    parser.add_argument("--days", type=int, default=30, help="Days to analyze (default 30)")
    parser.add_argument("--recent", type=int, default=10, help="Recent sessions to fully extract (default 10)")
    parser.add_argument("--sample-rate", type=float, default=0.3, help="Historical sampling rate (default 0.3)")
    parser.add_argument("--max-historical", type=int, default=200, help="Max historical messages (default 200)")
    args = parser.parse_args()

    if args.scope == "project" and not args.project:
        print(json.dumps({"error": "--project is required when scope is 'project'"}), file=sys.stderr)
        sys.exit(1)

    try:
        result = fetch_user_messages(
            scope=args.scope,
            project_path=args.project,
            days_back=args.days,
            recent_sessions=args.recent,
            sample_rate=args.sample_rate,
            max_historical_msgs=args.max_historical,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
