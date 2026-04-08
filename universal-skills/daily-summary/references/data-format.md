# 数据格式定义

## Cursor 存储版本

### Cursor 2.x (旧版)
- 会话元数据: `workspaceStorage/{id}/state.vscdb` → `composer.composerData` (ItemTable)
- 对话内容: `~/.cursor/projects/{key}/agent-transcripts/{session_id}.txt`
- 代码统计: `globalStorage/state.vscdb` → `aiCodeTracking.dailyStats.v1.5.{date}` (ItemTable)

### Cursor 3.x (新版)
- 会话元数据: `globalStorage/state.vscdb` → `composer.composerHeaders` (ItemTable)
- 完整会话数据: `globalStorage/state.vscdb` → `composerData:{composerId}` (cursorDiskKV 表)
- 消息内容: `globalStorage/state.vscdb` → `bubbleId:{composerId}:{bubbleId}` (cursorDiskKV 表)
- 对话文件: `~/.cursor/projects/{key}/agent-transcripts/{session_id}.jsonl` (JSONL 格式, 少量)
- 占位符文件: `~/.cursor/projects/{key}/agent-transcripts/{session_id}` (无扩展名, 0 bytes)
- 代码统计: 同旧版

### Cursor 3.x 关键数据结构

**composerHeaders (ItemTable)**:
```json
{
  "allComposers": [
    {
      "type": "head",
      "composerId": "uuid",
      "name": "session name",
      "lastUpdatedAt": 1775633539642,
      "createdAt": 1775633504452,
      "unifiedMode": "agent",
      "totalLinesAdded": 100,
      "totalLinesRemoved": 20,
      "subtitle": "file1.py, file2.ts",
      "workspaceIdentifier": {
        "id": "workspace_hash",
        "uri": {
          "fsPath": "d:\\workspace\\project",
          "external": "file:///d%3A/workspace/project"
        }
      }
    }
  ]
}
```

**composerData:{composerId} (cursorDiskKV)**:
```json
{
  "_v": 14,
  "composerId": "uuid",
  "fullConversationHeadersOnly": [
    {"bubbleId": "uuid", "type": 1},
    {"bubbleId": "uuid", "type": 2}
  ],
  "conversationMap": {}
}
```

**bubbleId:{composerId}:{bubbleId} (cursorDiskKV)**:
```json
{
  "_v": 3,
  "type": 1,
  "bubbleId": "uuid",
  "text": "消息文本内容",
  "toolResults": [],
  "codeBlocks": []
}
```
- `type=1`: 用户消息
- `type=2`: AI 助手消息

**.jsonl transcript 格式**:
```json
{"role":"user","message":{"content":[{"type":"text","text":"用户消息"}]}}
{"role":"assistant","message":{"content":[{"type":"text","text":"AI 回复"}]}}
```

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
