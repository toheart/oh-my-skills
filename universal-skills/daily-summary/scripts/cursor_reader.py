#!/usr/bin/env python3
"""Cursor 数据读取器 - 跨平台路径检测 + SQLite 只读读取 + 工作区映射

直接从 Cursor IDE 底层 SQLite 数据库和文件系统读取数据，
无需依赖任何外部服务。仅使用 Python 标准库。

兼容 Cursor 2.x 和 Cursor 3.x 两种存储结构。

Cursor 3 存储结构变化:
  - composer.composerHeaders 迁移到全局 globalStorage/state.vscdb (ItemTable)
  - 会话完整数据存储在 globalStorage/state.vscdb 的 cursorDiskKV 表中
    key 格式: composerData:{composerId}
  - 消息 bubble 存储在 cursorDiskKV 表中
    key 格式: bubbleId:{composerId}:{bubbleId}
  - 消息类型: type=1 用户消息, type=2 AI 消息
  - 工作区关联通过 composerHeaders 中的 workspaceIdentifier 实现
  - agent-transcripts 文件变为无扩展名的空占位符，.jsonl 为新格式

数据源:
  - globalStorage/state.vscdb: 全局存储（代码接受率、composerHeaders、cursorDiskKV）
  - workspaceStorage/{id}/state.vscdb: 工作区存储（旧版 composerData）
  - workspaceStorage/{id}/workspace.json: 工作区到项目路径的映射
  - ~/.cursor/projects/{key}/agent-transcripts/: 聊天记录

关键 Key:
  - composer.composerHeaders: 全局会话元数据列表 (Cursor 3)
  - composer.composerData: 工作区会话元数据列表 (Cursor 2, 旧版)
  - composerData:{composerId}: 会话完整数据 (cursorDiskKV, Cursor 3)
  - bubbleId:{composerId}:{bubbleId}: 消息内容 (cursorDiskKV, Cursor 3)
  - aiService.prompts: 用户提问 (工作区级)
  - aiService.generations: AI 回复 (工作区级)
  - aiCodeTracking.dailyStats.v1.5.{date}: 代码接受率 (全局)
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


def _has_cursor_disk_kv(db_path):
    """检测数据库是否包含 cursorDiskKV 表 (Cursor 3 特征)"""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'"
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def read_disk_kv(db_path, key):
    """从 cursorDiskKV 表读取指定 key 的 value (Cursor 3)"""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row is None:
            return None
        val = row[0]
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        return val
    finally:
        conn.close()


def read_disk_kv_batch(db_path, keys):
    """批量从 cursorDiskKV 表读取多个 key 的 value (Cursor 3)"""
    if not keys:
        return {}
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        placeholders = ",".join("?" * len(keys))
        cursor = conn.execute(
            f"SELECT key, value FROM cursorDiskKV WHERE key IN ({placeholders})",
            keys,
        )
        result = {}
        for row in cursor.fetchall():
            val = row[1]
            if isinstance(val, bytes):
                val = val.decode("utf-8", errors="replace")
            result[row[0]] = val
        return result
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


def _extract_project_path_from_workspace_identifier(ws_ident):
    """从 composerHeaders 的 workspaceIdentifier 中提取项目路径 (Cursor 3)

    workspaceIdentifier 结构:
      {"id": "xxx", "uri": {"fsPath": "d:\\workspace\\...", "external": "file:///...", ...}}
    """
    if not ws_ident:
        return None, None
    ws_id = ws_ident.get("id", "")
    uri_data = ws_ident.get("uri", {})
    fs_path = uri_data.get("fsPath", "")
    if fs_path:
        return ws_id, os.path.normpath(fs_path)
    external = uri_data.get("external", "")
    if external:
        return ws_id, _parse_folder_uri(external)
    return ws_id, None


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


def _detect_cursor_version():
    """检测 Cursor 版本 (2 或 3)

    通过全局数据库是否有 cursorDiskKV 表和 composer.composerHeaders 来判断
    """
    try:
        db_path = get_global_db_path()
    except FileNotFoundError:
        return 2

    if _has_cursor_disk_kv(db_path):
        headers = read_db_value(db_path, "composer.composerHeaders")
        if headers:
            return 3
    return 2


def get_composer_headers_v3():
    """读取全局 composerHeaders (Cursor 3)

    返回 allComposers 列表，每个元素包含:
      type, composerId, name, lastUpdatedAt, createdAt, unifiedMode,
      totalLinesAdded, totalLinesRemoved, subtitle, workspaceIdentifier, ...
    """
    db_path = get_global_db_path()
    raw = read_db_value(db_path, "composer.composerHeaders")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data.get("allComposers", [])
    except json.JSONDecodeError:
        return []


def get_composer_data(workspace_id):
    """读取工作区的 composer 会话数据 (Cursor 2, 兼容)

    返回 allComposers 列表
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


def get_bubble_messages_v3(composer_id, text_only=False):
    """读取 Cursor 3 中指定会话的消息列表

    参数:
      composer_id: 会话 ID
      text_only: 过滤只有 tool 调用的消息

    返回: [{"role": "user"|"assistant", "text": "...", "index": N}]
    """
    db_path = get_global_db_path()

    # 先获取 composerData 来拿到 bubble 列表
    raw = read_disk_kv(db_path, f"composerData:{composer_id}")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    headers = data.get("fullConversationHeadersOnly", [])
    if not headers:
        return []

    # 批量读取所有 bubble
    bubble_keys = [f"bubbleId:{composer_id}:{h['bubbleId']}" for h in headers]

    # 分批读取避免 SQL 参数过多
    batch_size = 100
    all_bubble_data = {}
    for i in range(0, len(bubble_keys), batch_size):
        batch = bubble_keys[i:i + batch_size]
        result = read_disk_kv_batch(db_path, batch)
        all_bubble_data.update(result)

    messages = []
    for h in headers:
        bid = h["bubbleId"]
        key = f"bubbleId:{composer_id}:{bid}"
        raw_bubble = all_bubble_data.get(key)
        if not raw_bubble:
            continue

        try:
            bdata = json.loads(raw_bubble)
        except json.JSONDecodeError:
            continue

        btype = bdata.get("type", 0)
        # type=1 用户, type=2 AI
        if btype == 1:
            role = "user"
        elif btype == 2:
            role = "assistant"
        else:
            continue

        text = bdata.get("text", "")
        if not isinstance(text, str):
            text = str(text) if text else ""

        # text_only 模式：跳过没有文本内容的 assistant 消息
        if text_only and role == "assistant" and not text.strip():
            continue

        if text.strip():
            messages.append({
                "role": role,
                "text": text,
                "index": len(messages),
            })

    return messages


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
    version = _detect_cursor_version()

    if version >= 3:
        return _get_sessions_by_date_v3(target_date, project_path)
    else:
        return _get_sessions_by_date_v2(target_date, project_path)


def _get_sessions_by_date_v3(target_date, project_path=None):
    """Cursor 3: 从全局 composerHeaders 获取会话列表"""
    from datetime import datetime, timezone

    composers = get_composer_headers_v3()
    norm_target = _normalize_path(project_path) if project_path else None

    # 构建工作区 ID 到项目路径的映射
    workspaces = {ws["workspace_id"]: ws for ws in get_all_workspaces()}

    sessions = []
    for c in composers:
        created_ms = c.get("createdAt", 0)
        updated_ms = c.get("lastUpdatedAt", 0)
        if not created_ms:
            continue

        created_dt = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
        updated_dt = datetime.fromtimestamp(updated_ms / 1000, tz=timezone.utc) if updated_ms else created_dt

        if created_dt.date() != target_date and updated_dt.date() != target_date:
            continue

        # 从 workspaceIdentifier 获取项目信息
        ws_ident = c.get("workspaceIdentifier", {})
        ws_id, ws_project_path = _extract_project_path_from_workspace_identifier(ws_ident)

        # 如果 workspaceIdentifier 没有路径信息，尝试从 workspaces 映射获取
        if not ws_project_path and ws_id and ws_id in workspaces:
            ws_project_path = workspaces[ws_id]["project_path"]

        project_name = os.path.basename(ws_project_path) if ws_project_path else ""

        # 按项目路径过滤
        if norm_target and ws_project_path:
            if _normalize_path(ws_project_path) != norm_target:
                continue
        elif norm_target and not ws_project_path:
            continue

        # 跳过子 agent 会话 (task- 前缀)、空白会话、draft 会话
        composer_id = c.get("composerId", "")
        if c.get("isBestOfNSubcomposer", False):
            continue

        duration_ms = (updated_ms - created_ms) if updated_ms > created_ms else 0
        sessions.append({
            "session_id": composer_id,
            "name": c.get("name", ""),
            "project_name": project_name,
            "project_path": ws_project_path or "",
            "workspace_id": ws_id,
            "created_at": created_ms,
            "updated_at": updated_ms,
            "lines_added": c.get("totalLinesAdded", 0),
            "lines_removed": c.get("totalLinesRemoved", 0),
            "files_changed": c.get("filesChangedCount", 0),
            "mode": c.get("unifiedMode", ""),
            "subtitle": c.get("subtitle", ""),
            "duration_minutes": round(duration_ms / 1000 / 60, 1),
            "is_archived": c.get("isArchived", False),
            "cursor_version": 3,
        })

    sessions.sort(key=lambda s: s["created_at"])
    return sessions


def _get_sessions_by_date_v2(target_date, project_path=None):
    """Cursor 2: 从工作区级别 composerData 获取会话列表 (兼容旧版)"""
    from datetime import datetime, timezone

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
                "cursor_version": 2,
            })

    sessions.sort(key=lambda s: s["created_at"])
    return sessions


def find_transcript_file(session_id):
    """在 ~/.cursor/projects/ 下查找 transcript 文件

    兼容三种格式:
      - {session_id}.jsonl (Cursor 3, 新格式)
      - {session_id}.txt (Cursor 2, 旧格式)
      - {session_id} (Cursor 3, 空占位符)

    返回 (file_path, project_key, file_format) 或 (None, None, None)
    """
    try:
        projects_dir = get_projects_dir()
    except FileNotFoundError:
        return None, None, None

    # 按优先级搜索: .jsonl > .txt > 无扩展名
    for ext, fmt in [(".jsonl", "jsonl"), (".txt", "txt"), ("", "placeholder")]:
        filename = f"{session_id}{ext}"
        for entry in os.listdir(projects_dir):
            entry_path = os.path.join(projects_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            transcript_path = os.path.join(entry_path, "agent-transcripts", filename)
            if os.path.isfile(transcript_path):
                size = os.path.getsize(transcript_path)
                if size > 0 or fmt == "placeholder":
                    return transcript_path, entry, fmt

    return None, None, None


def get_transcript_content(session_id):
    """读取 transcript 文件的原始内容

    对于 Cursor 3 的 .jsonl 格式，转换为兼容的文本格式。
    对于空占位符文件，尝试从 cursorDiskKV 读取。
    """
    path, project_key, fmt = find_transcript_file(session_id)

    if fmt == "jsonl" and path:
        return _read_jsonl_transcript(path)
    elif fmt == "txt" and path:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    elif fmt == "placeholder":
        # Cursor 3: 从 cursorDiskKV 构建对话内容
        return _build_transcript_from_bubbles(session_id)

    # 最后尝试从 bubble 数据构建
    return _build_transcript_from_bubbles(session_id)


def _read_jsonl_transcript(path):
    """读取 .jsonl 格式的 transcript 文件，转换为旧版纯文本格式"""
    lines = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                role = entry.get("role", "")
                message = entry.get("message", {})
                content_parts = message.get("content", [])

                if role and content_parts:
                    lines.append(f"{role}:")
                    for part in content_parts:
                        if isinstance(part, dict):
                            text = part.get("text", "")
                            if text:
                                lines.append(text)
                    lines.append("")
    except OSError:
        return None

    return "\n".join(lines) if lines else None


def _build_transcript_from_bubbles(session_id):
    """从 cursorDiskKV 的 bubble 数据构建 transcript 文本 (Cursor 3)"""
    try:
        messages = get_bubble_messages_v3(session_id)
    except (FileNotFoundError, OSError):
        return None

    if not messages:
        return None

    lines = []
    for msg in messages:
        lines.append(f"{msg['role']}:")
        lines.append(msg["text"])
        lines.append("")

    return "\n".join(lines)


def get_all_transcript_ids_by_date(date_str):
    """按文件修改时间获取指定日期的所有 transcript ID

    兼容 .txt、.jsonl 和无扩展名文件。
    返回 [{session_id, project_key, modified_at, file_path, format}]
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
            fpath = os.path.join(transcripts_dir, fname)
            try:
                mtime = os.path.getmtime(fpath)
                mod_date = datetime.fromtimestamp(mtime, tz=timezone.utc).date()
                if mod_date == target_date:
                    # 提取 session_id（去掉扩展名）
                    if fname.endswith(".jsonl"):
                        sid = fname[:-6]
                        fmt = "jsonl"
                    elif fname.endswith(".txt"):
                        sid = fname[:-4]
                        fmt = "txt"
                    else:
                        sid = fname
                        fmt = "placeholder"

                    results.append({
                        "session_id": sid,
                        "project_key": entry,
                        "modified_at": int(mtime * 1000),
                        "file_path": fpath,
                        "format": fmt,
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


def get_cursor_version():
    """获取检测到的 Cursor 版本"""
    return _detect_cursor_version()


# ---- CLI 入口 ----
if __name__ == "__main__":
    import argparse

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Cursor data reader")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("paths", help="Show detected Cursor paths")
    sub.add_parser("version", help="Detect Cursor storage version")

    ws_cmd = sub.add_parser("workspaces", help="List all workspaces")

    sess_cmd = sub.add_parser("sessions", help="List sessions by date")
    sess_cmd.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    sess_cmd.add_argument("--project", help="Filter by project path")

    tr_cmd = sub.add_parser("transcript", help="Read transcript content")
    tr_cmd.add_argument("--session-id", required=True, help="Session ID (composer ID)")

    bubble_cmd = sub.add_parser("bubbles", help="Read bubble messages (Cursor 3)")
    bubble_cmd.add_argument("--session-id", required=True, help="Session ID (composer ID)")
    bubble_cmd.add_argument("--text-only", action="store_true", help="Filter empty assistant messages")

    args = parser.parse_args()

    if args.command == "paths":
        try:
            result = {
                "user_data_dir": get_user_data_dir(),
                "workspace_storage_dir": get_workspace_storage_dir(),
                "global_db_path": get_global_db_path(),
                "projects_dir": get_projects_dir(),
                "cursor_version": _detect_cursor_version(),
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except (FileNotFoundError, RuntimeError) as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)

    elif args.command == "version":
        v = _detect_cursor_version()
        has_kv = False
        kv_count = 0
        try:
            db_path = get_global_db_path()
            has_kv = _has_cursor_disk_kv(db_path)
            if has_kv:
                uri = f"file:{db_path}?mode=ro"
                conn = sqlite3.connect(uri, uri=True)
                cursor = conn.execute("SELECT count(*) FROM cursorDiskKV")
                kv_count = cursor.fetchone()[0]
                conn.close()
        except (FileNotFoundError, OSError):
            pass

        print(json.dumps({
            "cursor_version": v,
            "has_cursorDiskKV": has_kv,
            "cursorDiskKV_rows": kv_count,
        }, indent=2))

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

    elif args.command == "bubbles":
        messages = get_bubble_messages_v3(args.session_id, text_only=args.text_only)
        print(json.dumps(messages, indent=2, ensure_ascii=False))

    else:
        parser.print_help()
