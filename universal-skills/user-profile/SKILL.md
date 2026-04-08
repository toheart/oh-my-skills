---
name: user-profile
description: Generate personalized user profile from Cursor chat history to help AI understand coding style, technical preferences, and communication habits. Use when users want to create or update their profile, or say "let Cursor know me better", "analyze my habits", "generate my profile".
---

# User Profile Skill

> **依赖**: Python 3.x（仅使用标准库 sqlite3、json、os）
> **兼容**: Cursor 2.x 和 Cursor 3.x

## 前置检查

```bash
python scripts/cursor_reader.py paths
```

预期输出包含 `cursor_version` 字段。

## 工作流

**必须完成所有步骤，包括保存。**

### Step 1: 获取用户对话数据

使用 `--with-context` 模式提取带上下文的对话交互对，包含决策标记：

```bash
python scripts/fetch_user_messages.py --scope project --project-path {project_path} --days-back 30 --with-context
```

**参数:**
- `--scope`: "global" 或 "project"（推荐 project，生成项目级决策画像）
- `--project-path`: scope 为 project 时必填
- `--days-back`: 分析天数（默认 30）
- `--with-context`: 启用上下文模式，输出对话交互对而非纯文本

**返回 (--with-context 模式):**
- `conversations`: 对话交互对列表，每条包含:
  - `session_name`: 会话名称
  - `user_text`: 用户消息原文
  - `ai_context`: 前一条 AI 回复摘要（用户在回应什么）
  - `ai_response`: 后一条 AI 回复摘要（AI 如何响应）
  - `tags`: 决策信号标签 (correction/requirement/selection/rejection/architecture/quality/decision_adopted)
  - `is_decision`: 是否包含决策信息
- `decision_conversations`: 仅包含决策的对话子集
- `stats`: 统计信息，包含 `primary_language`、`decision_rate`、`tag_distribution`
- `existing_profile`: 已有 profile 内容

### Step 2: 检查是否需要更新

如果 `meta.needs_update` 为 false：询问用户是否强制重新生成。

### Step 3: 分析对话 — 提取项目决策画像

**核心原则**: 不要做泛泛归纳，要逐条扫描 `decision_conversations`，提取用户的**具体决策实例**，保留原始措辞。

按以下 7 个维度分析:

#### 3.1 Architecture Decisions（架构决策）

扫描 tags 包含 `architecture` 的对话，以及用户消息中涉及模块设计、依赖关系、分层策略的内容。提取:
- 用户做过哪些架构决策（如"Port-Adapter 收敛外部调用"、"将 proto 文件拷贝到项目内"）
- 每条决策的上下文和理由
- 用户否决过哪些架构方案

#### 3.2 Quality Standards（质量标准）

扫描 tags 包含 `quality` 或 `requirement` 的对话。提取:
- 用户明确要求过的代码标准（如"DTO/PO 应使用强类型"、"移除 app_config"）
- 命名、类型、测试、日志等方面的具体要求
- 被否决的做法（"不要这样做"）

#### 3.3 Correction Patterns（纠正模式）

扫描 tags 包含 `correction` 的对话。提取:
- AI 容易误解用户意图的典型场景
- 用户纠正的原始措辞和正确理解
- 形成"当用户说 X 时，他其实意思是 Y"的模式

#### 3.4 Product Thinking（产品思维）

从对话中识别用户对产品功能、体验、业务逻辑的判断。提取:
- 功能设计偏好（如"没有填充数据时不允许进入下一步"）
- 体验优先级判断
- 用户在方案选择时的产品逻辑（如选方案 B+C 而非 A 的理由）

#### 3.5 Workflow Preferences（工作流偏好）

从用户消息模式中识别:
- 常用的 Skill 命令（/explorer、/orchestrator-feature 等）
- 偏好的工作流程（先讨论再实施、先探索再编码）
- 代码审查、提交、测试的习惯

#### 3.6 Technical Profile（技术画像）

从整体对话中归纳:
- **Expert**: 用户频繁使用且不需要解释的技术
- **Proficient**: 用户能使用但偶尔需要帮助的技术
- **Learning**: 用户正在学习或询问原理的技术

#### 3.7 Communication Style（沟通风格）

简要总结:
- 提问风格（直接给出需求 vs 讨论式）
- 反馈模式（编号列表 vs 自由文本）
- 语言偏好

### Step 4: 生成 Profile

以用户 `stats.primary_language` 语言生成 Markdown。

**关键要求**:
- **具体化**: 每条决策保留原始措辞，不要泛化为"用户偏好 X 模式"
- **可操作**: Profile 中的每条信息都应能直接指导 AI 在后续对话中的行为
- **项目聚焦**: scope=project 时以项目名命名，内容围绕该项目的决策

**模板**:

```markdown
# User Profile — {project_name}

## Architecture Decisions
- [具体决策 1：原始措辞 + 上下文]
- [具体决策 2：原始措辞 + 上下文]

## Quality Standards
- [具体标准 1]
- [具体标准 2]

## Correction Patterns
- 当用户说"..."时，意思是 ...，而不是 ...
- AI 曾误解 ...，正确理解应是 ...

## Product Thinking
- [产品判断 1：具体场景 + 判断]
- [产品判断 2：具体场景 + 判断]

## Workflow Preferences
- [偏好 1]
- [偏好 2]

## Technical Profile
- **Expert**: [语言/框架列表]
- **Proficient**: [语言/框架列表]
- **Learning**: [语言/框架列表]

## Communication Style
- [简要描述]
```

### Step 5: 保存 Profile (必须)

```bash
python scripts/save_profile.py --scope project --project-path {project_path} --language zh --file {temp_file}
```

或通过 stdin 传入:

```bash
echo "{content}" | python scripts/save_profile.py --scope project --project-path {project_path} --language zh
```

### Step 6: 向用户确认 (必须)

保存后告知用户:
1. 文件保存路径
2. 自动加载机制说明（project scope 的 .mdc 文件会被 Cursor 自动加载为 Rule）
3. Git 忽略状态
4. Profile 摘要，重点列出提取到的决策数量和关键发现

## 输出位置

| Scope | 位置 | 自动加载 |
|-------|------|----------|
| Global | `~/.cocursor/profiles/global.md` | 通过合并 |
| Project | `{project}/.cursor/rules/user-profile.mdc` | 是 |

## 注意事项

1. **隐私**: 仅本地存储
2. **Git 安全**: 项目 profile 自动添加到 `.gitignore`
3. **增量更新**: 与已有 profile 合并，不要完全替换
4. **仅分析用户消息**: 只分析用户消息，AI 回复仅作为上下文参考
5. **保留原始措辞**: 决策点必须保留用户原话，不要泛化
6. **决策优先**: `decision_conversations` 是最高价值数据，优先分析

## 决策标签说明

| 标签 | 含义 |
|------|------|
| `correction` | 用户纠正 AI 的理解 |
| `requirement` | 用户提出明确要求/约束 |
| `selection` | 用户在多方案中做出选择 |
| `rejection` | 用户否决某个方案/做法 |
| `architecture` | 涉及架构设计的讨论 |
| `quality` | 涉及代码质量标准的讨论 |
| `decision_adopted` | 用户通过短确认（如"可以"/"1"）采纳了 AI 的方案 |

## 脚本一览

| 脚本 | 用途 |
|------|------|
| `scripts/cursor_reader.py` | Cursor 数据读取（路径检测 + SQLite，兼容 v2/v3） |
| `scripts/transcript_parser.py` | Transcript 文件解析（v2 兼容） |
| `scripts/fetch_user_messages.py` | 获取用户消息/决策对话对，支持 `--with-context` 模式 |
| `scripts/save_profile.py` | 保存 profile 到文件 |
