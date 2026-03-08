---
name: weekly-summary
description: Generate weekly work reports by aggregating daily summaries or reading Cursor data directly. No external services required. Use when users request weekly reports, weekly summaries, or need to review accomplishments over a week period.
---

# Weekly Summary Skill

> **依赖**: Python 3.x（仅使用标准库 sqlite3、json、os）

## 前置检查

```bash
python scripts/cursor_reader.py paths
```

## 工作流

### Step 1: 确定周范围

解析用户输入:
- "上周" → 上个 Monday ~ Sunday
- "本周" → 本周 Monday ~ 今天
- "2026-02-24 ~ 2026-03-02" → 指定范围
- 无指定 → 当前周

周定义: Monday 到 Sunday（ISO 标准）

### Step 2: 读取日报数据

```bash
python scripts/fetch_daily_summaries.py --start {monday} --end {sunday}
```

输出包含:
- `found_count`: 找到的日报数量
- `missing_dates`: 缺失日报的日期
- `aggregate_stats`: 聚合统计
- `summaries`: 日报列表

### Step 3: 回退获取缺失数据

如果 `missing_dates` 不为空，对缺失日期直接从 Cursor 数据获取:

```bash
python scripts/fetch_sessions.py --date {missing_date}
```

对每个会话获取对话:

```bash
python scripts/fetch_conversations.py --session-id {id} --text-only --no-code
```

根据 [references/work-categories.md](references/work-categories.md) 对回退数据进行分类。

### Step 4: 聚合分析

聚合规则参考 [references/aggregation-rules.md](references/aggregation-rules.md):

1. 按项目分组所有工作
2. 提取 3-5 条关键成果
3. 统计工作类型分布
4. 计算整体指标

### Step 5: 生成周报

按 [references/report-template.md](references/report-template.md) 模板生成 Markdown。

### Step 6: 保存周报

```bash
python scripts/save_weekly.py --week-start {monday} --file {temp_file} --total-sessions {N} --working-days {D}
```

可选参数:
- `--categories '{"coding":15,...}'`
- `--accomplishments '["完成XX功能","修复YY问题"]'`

### Step 7: 查询已保存周报（可选）

```bash
python scripts/save_weekly.py --week-start {monday} --query
```

## 参考文件

- [references/work-categories.md](references/work-categories.md) - 工作类型识别规则
- [references/aggregation-rules.md](references/aggregation-rules.md) - 聚合规则
- [references/report-template.md](references/report-template.md) - 周报模板

## 脚本一览

| 脚本 | 用途 |
|------|------|
| `scripts/cursor_reader.py` | Cursor 数据读取（路径检测 + SQLite） |
| `scripts/transcript_parser.py` | Transcript 文件解析 |
| `scripts/fetch_sessions.py` | 获取指定日期会话列表（回退用） |
| `scripts/fetch_conversations.py` | 获取会话对话内容（回退用） |
| `scripts/fetch_daily_summaries.py` | 读取已保存日报聚合 |
| `scripts/save_weekly.py` | 保存/查询周报 |
