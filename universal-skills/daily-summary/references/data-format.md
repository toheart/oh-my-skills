# 数据格式定义

## 保存参数

save_summary.py 的参数说明:

| 参数 | 类型 | 说明 |
|------|------|------|
| --date | string | YYYY-MM-DD 格式日期 |
| --content | string | Markdown 日报内容 |
| --file | string | 从文件读取日报内容 |
| --language | string | zh 或 en |
| --categories | string | 工作类型统计 JSON |
| --total-sessions | int | 会话总数 |
| --query | flag | 查询已保存的日报 |

## categories JSON 格式

```json
{
  "requirements_discussion": 3,
  "coding": 8,
  "problem_solving": 4,
  "refactoring": 3,
  "code_review": 0,
  "documentation": 0,
  "testing": 2,
  "other": 1
}
```

## 存储格式

存储路径: `~/.cursor/oh-my-skills/daily-summaries/{date}.json`

```json
{
  "date": "2026-03-02",
  "summary": "# 工作日报...",
  "language": "zh",
  "total_sessions": 8,
  "categories": {"coding": 5, "problem_solving": 3},
  "projects": [],
  "saved_at": "2026-03-02T18:30:00"
}
```
