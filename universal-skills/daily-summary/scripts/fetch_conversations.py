#!/usr/bin/env python3
"""获取指定会话的完整对话内容

用法:
  python fetch_conversations.py --session-id <uuid>
  python fetch_conversations.py --session-id <uuid> --text-only
  python fetch_conversations.py --session-id <uuid> --text-only --no-code

输出: JSON 格式的消息列表
"""

import json
import sys
import os

# Windows 终端强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cursor_reader import get_transcript_content, find_transcript_file
from transcript_parser import parse_transcript, extract_text_only


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch conversation content for a session")
    parser.add_argument("--session-id", required=True, help="Session ID (composer ID)")
    parser.add_argument("--text-only", action="store_true", help="Filter tool-only assistant messages")
    parser.add_argument("--user-only", action="store_true", help="Only return user messages")
    parser.add_argument("--no-code", action="store_true", help="Remove code blocks from text")
    args = parser.parse_args()

    try:
        content = get_transcript_content(args.session_id)
        if content is None:
            print(json.dumps({
                "error": f"Transcript not found for session: {args.session_id}",
                "session_id": args.session_id,
            }), file=sys.stderr)
            sys.exit(1)

        messages = parse_transcript(
            content,
            text_only=args.text_only,
            user_only=args.user_only,
        )

        if args.no_code:
            messages = extract_text_only(messages)

        _, project_key = find_transcript_file(args.session_id)
        output = {
            "session_id": args.session_id,
            "project_key": project_key,
            "total_messages": len(messages),
            "messages": messages,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
