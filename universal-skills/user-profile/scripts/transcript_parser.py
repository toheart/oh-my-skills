#!/usr/bin/env python3
"""Transcript 解析器 - 解析 Cursor agent-transcripts 文件

解析 ~/.cursor/projects/{key}/agent-transcripts/{id}.txt 文件，
提取用户和 AI 的文本消息，过滤 tool call/result 和系统标签。

文件格式为行分隔的对话记录:
  user:
  <用户消息文本>
  assistant:
  <AI 回复文本>
  [Tool call] tool_name
  param: value
  [Tool result]
  <结果内容>
"""

import json
import re
import sys


# 需要过滤的系统标签对
_SYSTEM_TAG_PAIRS = [
    ("<think>", "</think>"),
    ("<git_status>", "</git_status>"),
    ("<attached_files>", "</attached_files>"),
    ("<agent_skills>", "</agent_skills>"),
    ("<code_selection", "</code_selection>"),
    ("<terminal_selection", "</terminal_selection>"),
    ("<file_list>", "</file_list>"),
    ("<file_contents>", "</file_contents>"),
    ("<system_info>", "</system_info>"),
    ("<context>", "</context>"),
    ("<open_and_recently_viewed_files>", "</open_and_recently_viewed_files>"),
    ("<user_info>", "</user_info>"),
    ("<system_reminder>", "</system_reminder>"),
    ("<rules>", "</rules>"),
    ("<mcp_instructions", "</mcp_instructions>"),
    ("<terminal_files_information>", "</terminal_files_information>"),
]

# 保留标签但提取内容的标签
_CONTENT_TAGS = ["<user_query>", "</user_query>"]

# 代码块正则
_CODE_BLOCK_RE = re.compile(r"```[\w]*\n.*?```", re.DOTALL)
_IMAGE_TAG_RE = re.compile(r"\[Image\](\s*\n)?")


def parse_transcript(content, text_only=False, user_only=False):
    """解析 transcript 文件内容

    参数:
      content: transcript 文件的原始文本
      text_only: 如果为 True，过滤 tool call 的消息，只保留纯文本
      user_only: 如果为 True，只返回用户消息

    返回: [{"role": "user"|"assistant", "text": "...", "index": N}]
    """
    if not content:
        return []

    lines = content.split("\n")
    messages = []
    current_role = None
    current_lines = []
    in_tool_call = False
    in_tool_result = False
    has_tools = False

    def save_message():
        nonlocal current_role, current_lines, has_tools
        if current_role is None:
            return
        if text_only and has_tools and current_role == "assistant":
            # 文本模式下，跳过只有 tool 调用的 assistant 消息
            pass

        text = "\n".join(current_lines).strip()
        text = _filter_text(text)
        if text:
            if not user_only or current_role == "user":
                messages.append({
                    "role": current_role,
                    "text": text,
                    "index": len(messages),
                })
        current_role = None
        current_lines = []
        has_tools = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # 角色切换
        if line == "user:":
            save_message()
            current_role = "user"
            current_lines = []
            has_tools = False
            in_tool_call = False
            in_tool_result = False
            i += 1
            continue

        if line == "assistant:":
            save_message()
            current_role = "assistant"
            current_lines = []
            has_tools = False
            in_tool_call = False
            in_tool_result = False
            i += 1
            continue

        # Tool call 处理
        if line.startswith("[Tool call]"):
            has_tools = True
            in_tool_call = True
            in_tool_result = False
            i += 1
            continue

        # Tool result 处理
        if line.startswith("[Tool result]"):
            in_tool_result = True
            in_tool_call = False
            i += 1
            continue

        # 在 tool call/result 区域内，跳过内容
        if in_tool_call or in_tool_result:
            # 检测是否退出 tool 区域
            if line == "" or line == "user:" or line == "assistant:" or line.startswith("[Tool call]") or line.startswith("[Tool result]"):
                in_tool_call = False
                in_tool_result = False
                # 不 i += 1，让循环重新处理这一行
                continue
            i += 1
            continue

        # <think> 标签: 跳过内容
        if "<think>" in line:
            i = _skip_until_close_tag(lines, i, "</think>")
            continue

        # <user_query> 标签: 提取内容
        if "<user_query>" in line:
            extracted, new_i = _extract_tag_content(lines, i, "<user_query>", "</user_query>")
            if extracted:
                current_lines.append(extracted)
            i = new_i
            continue

        # 其他系统标签: 跳过
        skip = False
        for open_tag, close_tag in _SYSTEM_TAG_PAIRS:
            if open_tag == "<think>":
                continue
            if open_tag in line:
                i = _skip_until_close_tag(lines, i, close_tag)
                skip = True
                break
        if skip:
            continue

        # 普通文本行
        if current_role:
            current_lines.append(line)

        i += 1

    save_message()
    return messages


def _skip_until_close_tag(lines, start_index, close_tag):
    """跳过直到找到闭合标签，返回下一行索引"""
    # 检查是否在同一行就有闭合标签
    if close_tag in lines[start_index]:
        return start_index + 1

    for j in range(start_index + 1, len(lines)):
        if close_tag in lines[j]:
            return j + 1
    return len(lines)


def _extract_tag_content(lines, start_index, open_tag, close_tag):
    """提取标签内容，返回 (content, next_line_index)"""
    line = lines[start_index]
    start_pos = line.find(open_tag)
    if start_pos == -1:
        return None, start_index + 1

    content_start = start_pos + len(open_tag)

    # 同一行闭合
    end_pos = line.find(close_tag, content_start)
    if end_pos != -1:
        return line[content_start:end_pos].strip(), start_index + 1

    # 跨行
    parts = [line[content_start:]]
    for j in range(start_index + 1, len(lines)):
        if close_tag in lines[j]:
            end_pos = lines[j].find(close_tag)
            parts.append(lines[j][:end_pos])
            return "\n".join(parts).strip(), j + 1
        parts.append(lines[j])

    return "\n".join(parts).strip(), len(lines)


def _filter_text(text):
    """过滤消息文本，移除系统标签、代码块引用、图片标记等"""
    if not text:
        return text

    # 移除残余的系统标签内容（正则兜底）
    for open_tag, close_tag in _SYSTEM_TAG_PAIRS:
        open_re = re.escape(open_tag.rstrip(">")) + r"[^>]*>"
        pattern = open_re + r".*?" + re.escape(close_tag)
        text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)

    # 移除 user_query 标签但保留内容
    text = re.sub(r"</?user_query>", "", text, flags=re.IGNORECASE)

    # 移除图片标记
    text = _IMAGE_TAG_RE.sub("", text)

    # 清理多余空行（连续 3 个以上变 2 个）
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def remove_code_blocks(text):
    """移除 Markdown 代码块，只保留自然语言文本"""
    if not text:
        return text
    text = _CODE_BLOCK_RE.sub("", text)
    text = text.replace("```", "")
    return text.strip()


def extract_text_only(messages):
    """对消息列表执行代码块移除，只保留自然语言文本"""
    result = []
    for msg in messages:
        cleaned = remove_code_blocks(msg["text"])
        if cleaned:
            result.append({**msg, "text": cleaned})
    return result


# ---- CLI 入口 ----
if __name__ == "__main__":
    import argparse

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Parse Cursor transcript files")
    parser.add_argument("file", help="Transcript file path or '-' for stdin")
    parser.add_argument("--text-only", action="store_true", help="Filter tool-only messages")
    parser.add_argument("--user-only", action="store_true", help="Only return user messages")
    parser.add_argument("--no-code", action="store_true", help="Remove code blocks from text")
    args = parser.parse_args()

    if args.file == "-":
        content = sys.stdin.read()
    else:
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

    msgs = parse_transcript(content, text_only=args.text_only, user_only=args.user_only)
    if args.no_code:
        msgs = extract_text_only(msgs)

    print(json.dumps(msgs, indent=2, ensure_ascii=False))
