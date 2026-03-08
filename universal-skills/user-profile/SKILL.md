---
name: user-profile
description: Generate personalized user profile from Cursor chat history by reading local data directly. No external services required. Analyzes coding style, technical preferences, communication habits, and work patterns. Use when users want to create or update their profile, or say "let Cursor know me better", "analyze my habits", "generate my profile".
---

# User Profile Skill

> **依赖**: Python 3.x（仅使用标准库 sqlite3、json、os）

## 前置检查

```bash
python scripts/cursor_reader.py paths
```

## 工作流

**必须完成所有步骤，包括保存。**

### Step 1: 获取用户消息

```bash
python scripts/fetch_user_messages.py --scope project --project {project_path}
```

或全局分析:

```bash
python scripts/fetch_user_messages.py --scope global --days 30
```

参数说明:
- `--scope`: "project"（单项目）或 "global"（所有项目）
- `--project`: 项目路径（scope=project 时必填）
- `--days`: 分析天数（默认 30）
- `--recent`: 完整提取最近 N 个会话（默认 10）
- `--sample-rate`: 历史会话采样率（默认 0.3）

输出包含:
- `recent_messages`: 最近会话的用户消息
- `historical_messages`: 历史采样消息
- `stats`: 统计信息（primary_language、project_distribution、time_distribution）

### Step 2: 检查已有 Profile

```bash
python scripts/save_profile.py --scope {scope} --project {path} --query
```

如果已有 profile，采用增量更新策略：合并新发现，而非完全替换。

### Step 3: 分析消息

从四个维度分析，参考 [references/profile-dimensions.md](references/profile-dimensions.md):

1. **编码风格**: 命名习惯、架构偏好、注释风格
2. **技术画像**: Expert / Proficient / Learning 分层
3. **沟通风格**: 提问模式、反馈方式、语言偏好
4. **工作习惯**: 活跃时段、会话深度、问题解决方式

### Step 4: 生成 Profile

使用 `stats.primary_language` 对应的语言生成 Markdown。

### Step 5: 保存 Profile（必须）

```bash
python scripts/save_profile.py --scope project --project {path} --file {temp_file} --language {lang}
```

或全局:

```bash
python scripts/save_profile.py --scope global --file {temp_file} --language {lang}
```

### Step 6: 告知用户

保存后告知:
1. 文件保存路径
2. 项目级 profile 自动被 Cursor 加载（.cursor/rules/user-profile.mdc）
3. 已自动添加到 .gitignore
4. Profile 概要

## 保存位置

| Scope | 位置 | 自动加载 |
|-------|------|----------|
| project | `{project}/.cursor/rules/user-profile.mdc` | 是（Cursor Rules） |
| global | `~/.cursor/oh-my-skills/profiles/global.json` | 否 |

## 重要说明

1. **隐私**: 所有数据仅存储在本地
2. **Git 安全**: 项目级 profile 自动添加到 .gitignore
3. **增量更新**: 合并已有 profile，不完全替换
4. **仅用户消息**: 只分析用户发送的消息，不分析 AI 回复

## 参考文件

- [references/profile-dimensions.md](references/profile-dimensions.md) - 分析维度说明

## 脚本一览

| 脚本 | 用途 |
|------|------|
| `scripts/cursor_reader.py` | Cursor 数据读取（路径检测 + SQLite） |
| `scripts/transcript_parser.py` | Transcript 文件解析 |
| `scripts/fetch_user_messages.py` | 获取用户消息（采样策略） |
| `scripts/save_profile.py` | 保存/查询 Profile |
