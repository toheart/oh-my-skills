#!/usr/bin/env python3
"""Cursor 数据读取器 - 跨平台路径检测 + SQLite 只读读取 + 工作区映射

直接从 Cursor IDE 底层 SQLite 数据库和文件系统读取数据，
无需依赖任何外部服务。仅使用 Python 标准库。

数据源:
  - globalStorage/state.vscdb: 全局存储（代码接受率等）
  - workspaceStorage/{id}/state.vscdb: 工作区存储（会话、prompts、generations）
  - workspaceStorage/{id}/workspace.json: 工作区到项目路径的映射
  - ~/.cursor/projects/{key}/agent-transcripts/*.txt: 聊天记录

关键 Key:
  - composer.composerData: 会话元数据列表
  - aiService.prompts: 用户提问
  - aiService.generations: AI 回复
  - aiCodeTracking.dailyStats.v1.5.{date}: 代码接受率
"""

import json
import os
import platform
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def get_user_data_dir():
    """获取 Cursor 用户数据目录

    优先级: 环境变量 CURSOR_USER_DATA_DIR > 平台默认路径
    - Windows: %APPDATA%/Cursor/User
    - macOS: ~/Library/Application Support/Cursor/User
    - Linux: ~/.config/Cursor/User
    """
    env_path = os.environ.get("CURSOR_USER_DATA_DIR")
    if env_path and os.path.isdir(env_path):
        return env_path

    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            raise RuntimeError("APPDATA environment variable not set")
        p = os.path.join(appdata, "Cursor", "User")
    elif system == "Darwin":
        p = os.path.join(Path.home(), "Library", "Application Support", "Cursor", "User")
    else:
        p = os.path.join(Path.home(), ".config", "Cursor", "User")

    if not os.path.isdir(p):
        raise FileNotFoundError(
            f"Cursor user data directory not found: {p}\n"
            "Set CURSOR_USER_DATA_DIR environment variable to override."
        )
    return p


def get_global_db_path():
    """获取全局存储数据库路径: globalStorage/state.vscdb"""
    p = os.path.join(get_user_data_dir(), "globalStorage", "state.vscdb")
    if not os.path.isfile(p):
        raise FileNotFoundError(f"Global storage database not found: {p}")
    return p


def get_workspace_storage_dir():
    """获取工作区存储根目录: workspaceStorage/"""
    p = os.path.join(get_user_data_dir(), "workspaceStorage")
    if not os.path.isdir(p):
        raise FileNotFoundError(f"Workspace storage directory not found: {p}")
    return p


def get_workspace_db_path(workspace_id):
    """获取指定工作区的数据库路径"""
    p = os.path.join(get_workspace_storage_dir(), workspace_id, "state.vscdb")
    if not os.path.isfile(p):
        raise FileNotFoundError(f"Workspace database not found: {p}")
    return p


def get_projects_dir():
    """获取 Cursor 项目目录 (~/.cursor/projects/)

    优先级: 环境变量 CURSOR_PROJECTS_DIR > 平台默认路径
    """
    env_path = os.environ.get("CURSOR_PROJECTS_DIR")
    if env_path and os.path.isdir(env_path):
        return env_path

    p = os.path.join(Path.home(), ".cursor", "projects")
    if not os.path.isdir(p):
        raise FileNotFoundError(
            f"Cursor projects directory not found: {p}\n"
            "Set CURSOR_PROJECTS_DIR environment variable to override."
        )
    return p


def read_db_value(db_path, key):
    """从 SQLite 数据库的 ItemTable 中读取指定 key 的 value

    使用只读 URI 模式打开，避免与 Cursor 进程的锁冲突。
    """
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.execute("SELECT value FROM ItemTable WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row is None:
            return None
        val = row[0]
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        return val
    finally:
        conn.close()


def read_db_keys_with_prefix(db_path, prefix):
    """读取具有指定前缀的所有 key"""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.execute(
            "SELECT key FROM ItemTable WHERE key LIKE ? ORDER BY key",
            (prefix + "%",),
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def _parse_folder_uri(uri):
    """将 workspace.json 中的 folder URI 解析为文件系统路径

    处理格式:
      - file:///d%3A/code/project (Windows, encoded)
      - file:///d:/code/project (Windows)
      - file:///Users/name/code/project (macOS/Linux)
    """
    if not uri:
        return None
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path = unquote(parsed.path)
    # Windows: /d:/code/... -> d:/code/...
    if len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return os.path.normpath(path)


def _normalize_path(p):
    """规范化路径用于比较"""
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def get_all_workspaces():
    """扫描所有工作区，返回 [{workspace_id, project_path, project_name}]"""
    ws_dir = get_workspace_storage_dir()
    results = []
    for entry in os.listdir(ws_dir):
        entry_path = os.path.join(ws_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        ws_json_path = os.path.join(entry_path, "workspace.json")
        if not os.path.isfile(ws_json_path):
            continue
        try:
            with open(ws_json_path, "r", encoding="utf-8") as f:
                ws_data = json.load(f)
            folder = ws_data.get("folder", "")
            project_path = _parse_folder_uri(folder)
            if not project_path:
                continue
            results.append({
                "workspace_id": entry,
                "project_path": project_path,
                "project_name": os.path.basename(project_path),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return results


def get_workspace_id_by_project(project_path):
    """根据项目路径查找工作区 ID"""
    norm_target = _normalize_path(project_path)
    for ws in get_all_workspaces():
        if _normalize_path(ws["project_path"]) == norm_target:
            return ws["workspace_id"]
    return None


def get_composer_data(workspace_id):
    """读取工作区的 composer 会话数据

    返回 allComposers 列表，每个元素包含:
      composerId, name, createdAt, lastUpdatedAt, unifiedMode,
      totalLinesAdded, totalLinesRemoved, filesChangedCount, subtitle, ...
    """
    db_path = get_workspace_db_path(workspace_id)
    raw = read_db_value(db_path, "composer.composerData")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data.get("allComposers", [])
    except json.JSONDecodeError:
        return []


def get_sessions_by_date(date_str, project_path=None):
    """获取指定日期的会话列表

    参数:
      date_str: YYYY-MM-DD 格式
      project_path: 可选，限定项目路径

    返回: [{session_id, name, project_name, project_path, workspace_id,
            created_at, updated_at, lines_added, lines_removed,
            files_changed, mode, duration_minutes}]
    """
    from datetime import datetime, timezone

    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    workspaces = get_all_workspaces()
    if project_path:
        norm_target = _normalize_path(project_path)
        workspaces = [w for w in workspaces if _normalize_path(w["project_path"]) == norm_target]

    sessions = []
    for ws in workspaces:
        try:
            composers = get_composer_data(ws["workspace_id"])
        except (FileNotFoundError, OSError):
            continue

        for c in composers:
            created_ms = c.get("createdAt", 0)
            updated_ms = c.get("lastUpdatedAt", 0)
            if not created_ms:
                continue

            created_dt = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            updated_dt = datetime.fromtimestamp(updated_ms / 1000, tz=timezone.utc) if updated_ms else created_dt

            # 会话在目标日期内活跃（创建或更新在该日期）
            if created_dt.date() != target_date and updated_dt.date() != target_date:
                continue

            duration_ms = (updated_ms - created_ms) if updated_ms > created_ms else 0
            sessions.append({
                "session_id": c.get("composerId", ""),
                "name": c.get("name", ""),
                "project_name": ws["project_name"],
                "project_path": ws["project_path"],
                "workspace_id": ws["workspace_id"],
                "created_at": created_ms,
                "updated_at": updated_ms,
                "lines_added": c.get("totalLinesAdded", 0),
                "lines_removed": c.get("totalLinesRemoved", 0),
                "files_changed": c.get("filesChangedCount", 0),
                "mode": c.get("unifiedMode", ""),
                "subtitle": c.get("subtitle", ""),
                "duration_minutes": round(duration_ms / 1000 / 60, 1),
            })

    sessions.sort(key=lambda s: s["created_at"])
    return sessions


def find_transcript_file(session_id):
    """在 ~/.cursor/projects/ 下查找 transcript 文件

    返回 (file_path, project_key) 或 (None, None)
    """
    try:
        projects_dir = get_projects_dir()
    except FileNotFoundError:
        return None, None

    filename = f"{session_id}.txt"
    for entry in os.listdir(projects_dir):
        entry_path = os.path.join(projects_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        transcript_path = os.path.join(entry_path, "agent-transcripts", filename)
        if os.path.isfile(transcript_path):
            return transcript_path, entry

    return None, None


def get_transcript_content(session_id):
    """读取 transcript 文件的原始内容"""
    path, _ = find_transcript_file(session_id)
    if not path:
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def get_all_transcript_ids_by_date(date_str):
    """按文件修改时间获取指定日期的所有 transcript ID

    返回 [{session_id, project_key, modified_at, file_path}]
    """
    from datetime import datetime, timezone

    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    try:
        projects_dir = get_projects_dir()
    except FileNotFoundError:
        return []

    results = []
    for entry in os.listdir(projects_dir):
        transcripts_dir = os.path.join(projects_dir, entry, "agent-transcripts")
        if not os.path.isdir(transcripts_dir):
            continue
        for fname in os.listdir(transcripts_dir):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(transcripts_dir, fname)
            try:
                mtime = os.path.getmtime(fpath)
                mod_date = datetime.fromtimestamp(mtime, tz=timezone.utc).date()
                if mod_date == target_date:
                    results.append({
                        "session_id": fname[:-4],  # 去掉 .txt
                        "project_key": entry,
                        "modified_at": int(mtime * 1000),
                        "file_path": fpath,
                    })
            except OSError:
                continue

    results.sort(key=lambda r: r["modified_at"])
    return results


def get_acceptance_stats(date_str):
    """获取指定日期的代码接受率统计

    返回 dict 或 None
    """
    try:
        db_path = get_global_db_path()
    except FileNotFoundError:
        return None

    key = f"aiCodeTracking.dailyStats.v1.5.{date_str}"
    raw = read_db_value(db_path, key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


# ---- CLI 入口 ----
if __name__ == "__main__":
    import argparse

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Cursor data reader")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("paths", help="Show detected Cursor paths")

    ws_cmd = sub.add_parser("workspaces", help="List all workspaces")

    sess_cmd = sub.add_parser("sessions", help="List sessions by date")
    sess_cmd.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    sess_cmd.add_argument("--project", help="Filter by project path")

    tr_cmd = sub.add_parser("transcript", help="Read transcript content")
    tr_cmd.add_argument("--session-id", required=True, help="Session ID (composer ID)")

    args = parser.parse_args()

    if args.command == "paths":
        try:
            print(json.dumps({
                "user_data_dir": get_user_data_dir(),
                "workspace_storage_dir": get_workspace_storage_dir(),
                "global_db_path": get_global_db_path(),
                "projects_dir": get_projects_dir(),
            }, indent=2, ensure_ascii=False))
        except (FileNotFoundError, RuntimeError) as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)

    elif args.command == "workspaces":
        print(json.dumps(get_all_workspaces(), indent=2, ensure_ascii=False))

    elif args.command == "sessions":
        sessions = get_sessions_by_date(args.date, args.project)
        print(json.dumps(sessions, indent=2, ensure_ascii=False))

    elif args.command == "transcript":
        content = get_transcript_content(args.session_id)
        if content:
            print(content)
        else:
            print(json.dumps({"error": f"Transcript not found: {args.session_id}"}), file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
