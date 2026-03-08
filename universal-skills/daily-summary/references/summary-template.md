# 日报模板

## 输出格式

```markdown
# 工作日报 - {date}

## 今日概览
- 总会话数: {total_sessions}
- 涉及项目: {project_list}
- 代码变更: +{lines_added} / -{lines_removed} 行，{files_changed} 个文件
- 活跃时间: {active_hours}

## 工作内容

### {project_name_1}

1. **[类型] 任务描述** (会话: {session_name})
   - 具体工作内容
   - 关键成果

2. **[类型] 任务描述** (会话: {session_name})
   - 具体工作内容

### {project_name_2}
...

## 工作分布
- 编码: {coding_count} 个会话
- 问题解决: {problem_solving_count} 个会话
- 需求讨论: {requirements_count} 个会话
- 重构: {refactoring_count} 个会话
- 文档: {documentation_count} 个会话
- 测试: {testing_count} 个会话

## 技术备忘
- 待解决: {pending_items}
- 后续计划: {next_steps}
```

## 注意事项

- 工作内容应具体、可追溯（关联会话名称）
- 按项目分组展示
- 技术备忘提取对话中提到的待办事项和后续计划
- 使用用户的对话语言（中文/英文）撰写
