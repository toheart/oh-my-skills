#!/usr/bin/env python3
"""获取用户消息用于 profile 分析

直接从 Cursor SQLite 数据库读取用户的历史消息，
无需依赖 cocursor daemon。兼容 Cursor 2.x 和 3.x。

支持两种输出模式:
  - 基础模式: 仅提取用户消息文本列表 (兼容旧版)
  - 上下文模式 (--with-context): 提取用户-AI 交互对，
    包含会话名称、AI 回复摘要、决策标记，用于项目级决策画像

用法:
  python fetch_user_messages.py --scope project --project-path D:/workspace/myproject
  python fetch_user_messages.py --scope project --project-path D:/workspace/myproject --with-context
  python fetch_user_messages.py --scope global --days-back 30

输出: JSON 格式，包含 conversations/messages、stats、existing_profile
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cursor_reader import (
    get_sessions_by_date,
    get_bubble_messages_v3,
    get_transcript_content,
    get_cursor_version,
    get_all_workspaces,
    get_composer_headers_v3,
    _normalize_path,
    _extract_project_path_from_workspace_identifier,
)
from transcript_parser import parse_transcript


# 短确认消息正则：纯数字选择、确认词、简短指令
_SHORT_CONFIRM_RE = re.compile(
    r"^(\d{1,2}|可以|好的|好|继续|ok|OK|确认|是的|对|行|没问题|go|yes|Yeah|sure|"
    r"嗯|同意|通过|approved|lgtm|LGTM|没有|不需要|不用了|先这样)\.?$",
    re.IGNORECASE,
)

# 决策信号词（用户在做判断/否决/要求/纠正）
_DECISION_PATTERNS = {
    "correction": re.compile(
        r"(理解错误|不是这个意思|我的意思是|不对|搞错了|误解|不是要|"
        r"wrong|misunderstand|not what I meant|I mean)",
        re.IGNORECASE,
    ),
    "requirement": re.compile(
        r"(需要|必须|应该|要求|不要|不允许|禁止|不能|务必|确保|一定要|"
        r"must|should|require|don't|never|always|ensure)",
        re.IGNORECASE,
    ),
    "selection": re.compile(
        r"(方案[A-Z1-9一二三四]|选择|采用|用这个|就这样|第[一二三1-9]个|"
        r"option\s*[A-Z1-9]|choose|prefer|go with|let's use)",
        re.IGNORECASE,
    ),
    "rejection": re.compile(
        r"(不行|不好|不合适|太[复杂简单重]|没必要|过度|多余|"
        r"不考虑|排除|放弃|算了|不需要这个|"
        r"no need|overkill|too complex|unnecessary|skip|drop)",
        re.IGNORECASE,
    ),
    "architecture": re.compile(
        r"(架构|模块|分层|解耦|依赖|接口|抽象|封装|收敛|重构|迁移|"
        r"DDD|port.?adapter|repository|service|handler|middleware|"
        r"architecture|decouple|refactor|migrate|extract|split|merge)",
        re.IGNORECASE,
    ),
    "quality": re.compile(
        r"(强类型|类型安全|命名|规范|lint|测试|覆盖率|性能|优化|"
        r"code review|PR|MR|日志|监控|告警|"
        r"type.?safe|naming|convention|test|coverage|performance)",
        re.IGNORECASE,
    ),
}


def _detect_language(texts):
    """检测消息的主要语言 (zh 或 en)"""
    zh_count = 0
    en_count = 0
    for text in texts:
        zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        en_words = len(re.findall(r'[a-zA-Z]+', text))
        zh_count += zh_chars
        en_count += en_words
    return "zh" if zh_count * 2 > en_count else "en"


def _load_existing_profile(project_path=None):
    """加载已存在的 profile"""
    if project_path:
        profile_path = os.path.join(project_path, ".cursor", "rules", "user-profile.mdc")
        if os.path.isfile(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                return f.read()

    global_path = os.path.join(Path.home(), ".cocursor", "profiles", "global.md")
    if os.path.isfile(global_path):
        with open(global_path, "r", encoding="utf-8") as f:
            return f.read()

    return None


def _is_short_confirm(text):
    """判断消息是否为短确认（选择方案、确认操作）"""
    stripped = text.strip()
    if len(stripped) > 15:
        return False
    return bool(_SHORT_CONFIRM_RE.match(stripped))


def _detect_decision_tags(text):
    """检测用户消息中的决策信号，返回标签列表"""
    tags = []
    for tag_name, pattern in _DECISION_PATTERNS.items():
        if pattern.search(text):
            tags.append(tag_name)
    return tags


def _truncate_ai_text(text, max_chars=300):
    """截断 AI 回复文本，保留前 N 个字符"""
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _filter_target_composers(composers, workspaces, project_path, days_back):
    """从 composerHeaders 中筛选目标会话"""
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=days_back)
    cutoff_ms = int(cutoff.timestamp() * 1000)
    norm_target = _normalize_path(project_path) if project_path else None

    target = []
    for c in composers:
        updated_ms = c.get("lastUpdatedAt", 0) or c.get("createdAt", 0)
        if updated_ms < cutoff_ms:
            continue
        if c.get("isBestOfNSubcomposer", False):
            continue
        # 跳过子 agent 会话
        cid = c.get("composerId", "")
        if cid.startswith("task-"):
            continue

        if norm_target:
            ws_ident = c.get("workspaceIdentifier", {})
            _, ws_path = _extract_project_path_from_workspace_identifier(ws_ident)
            if not ws_path:
                ws_id = ws_ident.get("id", "")
                if ws_id in workspaces:
                    ws_path = workspaces[ws_id]["project_path"]
            if not ws_path or _normalize_path(ws_path) != norm_target:
                continue

        target.append(c)

    target.sort(key=lambda x: x.get("lastUpdatedAt", 0), reverse=True)
    return target[:80]


def fetch_conversations_v3(project_path=None, days_back=30):
    """从 Cursor 3 提取带上下文的对话交互对

    返回: [{
        session_name: str,
        user_text: str,
        ai_context: str,     # 前一条 AI 回复摘要（用于理解用户回应的上下文）
        ai_response: str,    # 后一条 AI 回复摘要（用于理解 AI 如何回应用户决策）
        tags: [str],          # 决策信号标签
        is_decision: bool,    # 是否包含决策信息
    }]
    """
    composers = get_composer_headers_v3()
    workspaces = {ws["workspace_id"]: ws for ws in get_all_workspaces()}
    target_composers = _filter_target_composers(composers, workspaces, project_path, days_back)

    conversations = []
    for c in target_composers:
        cid = c.get("composerId", "")
        session_name = c.get("name", "") or c.get("subtitle", "") or cid[:8]

        try:
            msgs = get_bubble_messages_v3(cid, text_only=False)
        except Exception:
            continue
        if not msgs:
            continue

        for i, m in enumerate(msgs):
            if m["role"] != "user":
                continue
            user_text = m["text"].strip()
            if not user_text:
                continue

            # 获取前一条 AI 消息（上下文）
            ai_context = ""
            for j in range(i - 1, max(i - 3, -1), -1):
                if msgs[j]["role"] == "assistant" and msgs[j]["text"].strip():
                    ai_context = _truncate_ai_text(msgs[j]["text"])
                    break

            # 获取后一条 AI 消息（回应）
            ai_response = ""
            for j in range(i + 1, min(i + 3, len(msgs))):
                if msgs[j]["role"] == "assistant" and msgs[j]["text"].strip():
                    ai_response = _truncate_ai_text(msgs[j]["text"])
                    break

            # 短确认消息 → 回溯前一条 AI 提出的方案，标记为 decision_adopted
            if _is_short_confirm(user_text):
                if ai_context:
                    conversations.append({
                        "session_name": session_name,
                        "user_text": user_text,
                        "ai_context": ai_context,
                        "ai_response": ai_response,
                        "tags": ["decision_adopted"],
                        "is_decision": True,
                    })
                continue

            # 检测决策信号
            tags = _detect_decision_tags(user_text)
            is_decision = len(tags) > 0

            # 仅保留有实质内容的消息（>15 字符或有决策标签）
            if len(user_text) < 15 and not is_decision:
                continue

            conversations.append({
                "session_name": session_name,
                "user_text": user_text,
                "ai_context": ai_context,
                "ai_response": ai_response,
                "tags": tags,
                "is_decision": is_decision,
            })

    return conversations


def fetch_user_messages_v3(project_path=None, days_back=30):
    """从 Cursor 3 的 composerHeaders + bubbles 中提取用户消息（基础模式）"""
    composers = get_composer_headers_v3()
    workspaces = {ws["workspace_id"]: ws for ws in get_all_workspaces()}
    target_composers = _filter_target_composers(composers, workspaces, project_path, days_back)

    all_user_messages = []
    for c in target_composers:
        cid = c.get("composerId", "")
        try:
            msgs = get_bubble_messages_v3(cid, text_only=True)
        except Exception:
            continue
        for m in msgs:
            if m["role"] == "user" and m["text"].strip():
                all_user_messages.append(m["text"])

    return all_user_messages


def fetch_user_messages_v2(project_path=None, days_back=30):
    """从 Cursor 2 的 transcript 文件中提取用户消息"""
    now = datetime.now(tz=timezone.utc)

    all_user_messages = []
    for day_offset in range(days_back):
        date = (now - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        try:
            sessions = get_sessions_by_date(date, project_path)
        except Exception:
            continue
        for s in sessions:
            sid = s["session_id"]
            try:
                content = get_transcript_content(sid)
                if content:
                    msgs = parse_transcript(content, text_only=True, user_only=True)
                    for m in msgs:
                        if m["text"].strip():
                            all_user_messages.append(m["text"])
            except Exception:
                continue

    return all_user_messages


def fetch_conversations_v2(project_path=None, days_back=30):
    """从 Cursor 2 的 transcript 文件中提取带上下文的对话交互对"""
    now = datetime.now(tz=timezone.utc)

    conversations = []
    for day_offset in range(days_back):
        date = (now - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        try:
            sessions = get_sessions_by_date(date, project_path)
        except Exception:
            continue
        for s in sessions:
            sid = s["session_id"]
            session_name = s.get("name", "") or sid[:8]
            try:
                content = get_transcript_content(sid)
                if not content:
                    continue
                msgs = parse_transcript(content, text_only=True)
            except Exception:
                continue

            for i, m in enumerate(msgs):
                if m["role"] != "user":
                    continue
                user_text = m["text"].strip()
                if not user_text:
                    continue

                ai_context = ""
                for j in range(i - 1, max(i - 3, -1), -1):
                    if msgs[j]["role"] == "assistant" and msgs[j]["text"].strip():
                        ai_context = _truncate_ai_text(msgs[j]["text"])
                        break

                ai_response = ""
                for j in range(i + 1, min(i + 3, len(msgs))):
                    if msgs[j]["role"] == "assistant" and msgs[j]["text"].strip():
                        ai_response = _truncate_ai_text(msgs[j]["text"])
                        break

                if _is_short_confirm(user_text):
                    if ai_context:
                        conversations.append({
                            "session_name": session_name,
                            "user_text": user_text,
                            "ai_context": ai_context,
                            "ai_response": ai_response,
                            "tags": ["decision_adopted"],
                            "is_decision": True,
                        })
                    continue

                tags = _detect_decision_tags(user_text)
                is_decision = len(tags) > 0

                if len(user_text) < 15 and not is_decision:
                    continue

                conversations.append({
                    "session_name": session_name,
                    "user_text": user_text,
                    "ai_context": ai_context,
                    "ai_response": ai_response,
                    "tags": tags,
                    "is_decision": is_decision,
                })

    return conversations


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch user messages for profile analysis")
    parser.add_argument("--scope", choices=["global", "project"], default="global")
    parser.add_argument("--project-path", help="Project path (required if scope=project)")
    parser.add_argument("--days-back", type=int, default=30, help="Days to analyze (default 30)")
    parser.add_argument("--with-context", action="store_true",
                        help="Output conversation pairs with AI context and decision tags")
    args = parser.parse_args()

    project_path = args.project_path if args.scope == "project" else None
    version = get_cursor_version()

    if args.with_context:
        if version >= 3:
            conversations = fetch_conversations_v3(project_path, args.days_back)
        else:
            conversations = fetch_conversations_v2(project_path, args.days_back)

        all_texts = [c["user_text"] for c in conversations]
        primary_language = _detect_language(all_texts) if all_texts else "en"
        existing_profile = _load_existing_profile(project_path)

        decision_convs = [c for c in conversations if c["is_decision"]]
        tag_counts = {}
        for c in conversations:
            for t in c["tags"]:
                tag_counts[t] = tag_counts.get(t, 0) + 1

        output = {
            "cursor_version": version,
            "scope": args.scope,
            "project_path": project_path or "",
            "days_back": args.days_back,
            "total_conversations": len(conversations),
            "total_decisions": len(decision_convs),
            "conversations": conversations,
            "decision_conversations": decision_convs,
            "stats": {
                "primary_language": primary_language,
                "total_conversations": len(conversations),
                "total_decisions": len(decision_convs),
                "decision_rate": round(len(decision_convs) / max(len(conversations), 1) * 100, 1),
                "tag_distribution": tag_counts,
            },
            "existing_profile": existing_profile,
            "meta": {
                "needs_update": existing_profile is None or len(decision_convs) > 0,
            },
        }
    else:
        if version >= 3:
            user_messages = fetch_user_messages_v3(project_path, args.days_back)
        else:
            user_messages = fetch_user_messages_v2(project_path, args.days_back)

        primary_language = _detect_language(user_messages) if user_messages else "en"
        existing_profile = _load_existing_profile(project_path)

        output = {
            "cursor_version": version,
            "scope": args.scope,
            "project_path": project_path or "",
            "days_back": args.days_back,
            "total_messages": len(user_messages),
            "messages": user_messages,
            "stats": {
                "primary_language": primary_language,
                "total_messages": len(user_messages),
            },
            "existing_profile": existing_profile,
            "meta": {
                "needs_update": existing_profile is None or len(user_messages) > 0,
            },
        }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
