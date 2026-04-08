---
name: daily-summary
description: Generate daily work reports from Cursor chat history by reading local SQLite databases and transcript files directly. No external services required. Use when users request work summaries, daily reports, or need to review daily work content.
---

# Daily Summary Skill

> **依赖**: Python 3.x（仅使用标准库 sqlite3、json、os）
> **兼容**: Cursor 2.x 和 Cursor 3.x

## 前置检查

验证 Python 可用且能读取 Cursor 数据:

```bash
python scripts/cursor_reader.py paths
```

预期输出: 包含 `user_data_dir`、`projects_dir`、`cursor_version` 等的 JSON。
`cursor_version` 为 3 表示 Cursor 3 存储结构（composerHeaders + cursorDiskKV）。
如果报错，检查 Cursor 是否已安装并运行过，或设置环境变量 `CURSOR_USER_DATA_DIR`。

## 工作流

### Step 1: 获取会话列表

```bash
python scripts/fetch_sessions.py --date {YYYY-MM-DD}
```

可选加 `--project {path}` 过滤项目。输出 JSON 包含 `total_sessions` 和 `sessions` 列表。

### Step 2: 获取对话内容

对每个会话获取纯文本对话:

```bash
python scripts/fetch_conversations.py --session-id {session_id} --text-only --no-code
```

参数说明:
- `--text-only`: 过滤只有 tool 调用的消息
- `--no-code`: 移除代码块，只保留自然语言
- `--user-only`: 只返回用户消息（可选）

**重要**: 如果会话数量较多（>10），优先获取最近更新的会话，或按持续时间排序选取主要会话。

### Step 3: 分析并生成日报

根据对话内容进行分析:

1. **工作类型识别**: 参考 [references/work-categories.md](references/work-categories.md) 对每个会话分类
2. **统计汇总**: 汇总代码变更行数、会话时长、涉及项目
3. **生成报告**: 按 [references/summary-template.md](references/summary-template.md) 模板生成 Markdown

### Step 4: 保存日报

将生成的 Markdown 写入临时文件后保存:

```bash
python scripts/save_summary.py --date {YYYY-MM-DD} --file {temp_file} --total-sessions {N} --categories '{"coding":5,"problem_solving":3}'
```

或通过 stdin 传入:

```bash
echo "{content}" | python scripts/save_summary.py --date {YYYY-MM-DD} --total-sessions {N}
```

### Step 5: 查询已保存日报（可选）

```bash
python scripts/save_summary.py --date {YYYY-MM-DD} --query
```

## Git 提交分析（可选）

询问用户: "是否包含 Git 提交分析?"

如果启用，在项目目录执行:

```bash
git log --since="{date} 00:00" --until="{date} 23:59" --oneline --stat
```

将结果合并到日报中。

## 参考文件

- [references/work-categories.md](references/work-categories.md) - 工作类型识别规则
- [references/summary-template.md](references/summary-template.md) - 日报模板
- [references/data-format.md](references/data-format.md) - 数据结构定义

## 脚本一览

| 脚本 | 用途 |
|------|------|
| `scripts/cursor_reader.py` | Cursor 数据读取（路径检测 + SQLite） |
| `scripts/transcript_parser.py` | Transcript 文件解析 |
| `scripts/fetch_sessions.py` | 获取指定日期会话列表 |
| `scripts/fetch_conversations.py` | 获取会话对话内容 |
| `scripts/save_summary.py` | 保存/查询日报 |
