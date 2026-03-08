# Go Code Style Guide

This specification defines Go code writing standards for the project, based on [Uber Go Style Guide](https://github.com/uber-go/guide/blob/master/style.md).

## Basic Rules

- Use `golangci-lint` for code checking
- Comments in English
- Logs in English, must conform to log levels
- Variables use camelCase, exported variables use PascalCase

## Uber Go Style Guide Core Rules

### 1. Interface Compliance Verification

Use compile-time checks to ensure types implement interfaces:

```go
var _ http.Handler = (*Handler)(nil)
```

### 2. Zero-value Mutex is Valid

No need to initialize pointers:

```go
var mu sync.Mutex  // Correct
mu := new(sync.Mutex)  // Avoid
```

### 3. Copy Slices/Maps at Boundaries

Create copies when receiving or returning to prevent external modification:

```go
func (d *Driver) SetTrips(trips []Trip) {
    d.trips = make([]Trip, len(trips))
    copy(d.trips, trips)
}
```

### 4. Use defer for Resource Cleanup

Use defer to release resources like files and locks:

```go
p.Lock()
defer p.Unlock()
```

### 5. Channel Size 1 or Unbuffered

Avoid using arbitrary-sized buffered channels.

### 6. Enums Start from 1

Avoid zero-value ambiguity:

```go
const (
    Add Operation = iota + 1
    Subtract
)
```

### 7. Error Handling Rules

- Use `pkg/errors` to wrap errors, return errors instead of panic
- Handle errors only once, don't both log and return
- Use `%w` to wrap errors to support `errors.Is/As`
- Error variables use `Err` prefix, error types use `Error` suffix

### 8. Don't Panic

Avoid panic in production code, return error:

```go
func run(args []string) error {
    if len(args) == 0 {
        return errors.New("an argument is required")
    }
    return nil
}
```

### 9. Avoid Mutable Global Variables

Use dependency injection instead.

### 10. Avoid init()

Unless necessary, put initialization logic in main() or constructors.

### 11. Avoid Goroutine Leaks

Every goroutine must have a predictable exit point.

## Logging Rules

基于标准库 `log/slog` 封装的 `internal/logging` 包，JSON 结构化输出。

### 日志级别使用

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 调试信息，开发环境使用 | 请求参数、中间状态 |
| INFO | 正常业务流程 | 启动完成、请求处理成功 |
| WARN | 异常但可恢复的情况 | 降级处理、配置缺失使用默认值 |
| ERROR | 需要关注的错误 | 数据库连接失败、外部依赖不可用 |

### 基本使用

```go
// 包级别函数（无 context 场景，如启动阶段）
logging.Info("server starting", "version", version, "port", port)
logging.Error("failed to connect database", "error", err)

// 带 context 的函数（业务代码中使用，自动携带 request_id）
logging.Infoc(ctx, "user created", "user_id", userID)
logging.Errorc(ctx, "failed to save skill", "error", err, "skill_id", skillID)

// 附加字段的子 logger
logger := logging.With("op", "ImportSkill")
logger.Info("import started", "count", len(items))
```

### 日志规范

- **消息用英文**，小写开头，不要句号结尾
- **使用结构化字段**，不要拼接字符串：
  ```go
  // 正确
  logging.Info("user logged in", "user_id", uid, "method", "oauth")

  // 错误
  logging.Info(fmt.Sprintf("user %s logged in via %s", uid, "oauth"))
  ```
- **错误只处理一次**：要么记日志，要么返回给调用方，不要两者都做
- **error 字段用 `"error"` 键名**：`logging.Error("...", "error", err)`
- **不要在循环中大量打日志**：使用 DEBUG 级别或汇总后打一条

### 配置管理规范

- 使用 `spf13/viper` 加载 YAML 配置文件
- 配置文件命名：`config.<runMode>.yaml`，兜底 `config.yaml`
- 环境变量前缀：`PROJECTNAME_`，字段分隔用 `_`
- 环境变量覆盖优先级高于配置文件
- 敏感信息（密码、密钥）通过环境变量注入，不提交到仓库

## Performance Rules

- Prefer `strconv` over `fmt` for type conversion
- Avoid repeated string-to-byte conversion
- Specify capacity when initializing maps/slices

## Style Rules

- Soft line length limit: 99 characters
- Use field names when initializing structs
- Omit zero-value fields in structs
- nil is a valid empty slice, use `len(s) == 0` to check empty
- Reduce nesting, return early for error handling
- Place exported functions at the top of files, ordered by call sequence
- Unexported global variables use `_` prefix
