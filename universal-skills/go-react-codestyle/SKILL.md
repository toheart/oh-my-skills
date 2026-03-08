---
name: go-react-codestyle
description: Go+React full-stack project coding standards including Go style guide (based on Uber Go Style Guide), TypeScript/React style guide, API conventions (RESTful + Swagger), and testing specifications (TDD). Use this skill when working on Go+React projects and needing code style guidance, API design conventions, or testing best practices.
---

# Go+React 编码规范

为 Go+React 全栈项目提供统一的编码规范、API 设计约定和测试标准。

## 包含的规范

本 skill 包含以下四份规范文件，可作为独立的编码参考使用，也可在项目初始化时复制到项目的 `openspec/specs/` 或 `docs/` 目录下：

| 规范 | 文件 | 适用场景 |
|------|------|---------|
| Go 代码风格 | `references/go-style.md` | Go 后端代码编写 |
| TypeScript 代码风格 | `references/typescript-style.md` | React/TypeScript 前端代码编写 |
| API 约定 | `references/api-conventions.md` | RESTful API 设计、Swagger 注解 |
| 测试规范 | `references/testing.md` | Go/TypeScript 单元测试和集成测试 |

## 使用方式

### 作为开发时的编码参考

在编写 Go+React 项目代码时，直接参考对应的规范文件：

- 写 Go 代码时 → 参考 `references/go-style.md`
- 写 TypeScript/React 代码时 → 参考 `references/typescript-style.md`
- 设计 API 接口时 → 参考 `references/api-conventions.md`
- 写测试代码时 → 参考 `references/testing.md`

### 作为项目规范文件复制到项目中

在使用 `go-react-stack` skill 创建项目时，可选择将这些规范文件复制到项目中：

- 启用了 OpenSpec → 复制到 `openspec/specs/` 目录下
- 未启用 OpenSpec → 复制到 `docs/` 目录下

## 规范概要

### Go 代码风格

基于 [Uber Go Style Guide](https://github.com/uber-go/guide/blob/master/style.md)，核心要点：

- 接口合规性编译期检查
- 边界处拷贝 Slice/Map
- 使用 defer 清理资源
- 错误处理：用 `%w` 包装，不要既 log 又 return
- 不使用 panic，不使用 init()
- 性能：优先 `strconv`、预分配容量
- 日志：基于 `log/slog` 封装，JSON 结构化输出，消息用英文
- 配置：Viper 加载 YAML，环境变量覆盖优先

### TypeScript 代码风格

- 命名：变量/函数 camelCase，组件 PascalCase，常量 UPPER_SNAKE_CASE
- 类型：优先类型推断，函数必须显式返回类型，避免 `any`
- 异步：使用 async/await，并行请求用 Promise.all
- 错误：使用自定义错误类

### API 约定

- URL 路径版本控制 `/api/v1/`
- 统一响应格式：`{ code, message, data, page? }`
- 错误码格式 `XXYYYY`
- Swagger 注解规范（swaggo/swag）

### 测试规范

- TDD Red-Green-Refactor 循环
- Go：**Ginkgo v2 + Gomega** 测试框架（Describe/Context/It 组织）
- Go Mock：**mockery** 自动生成 mock 文件（`.mockery.yaml` 配置）
- TypeScript：Vitest/Jest
- 分层测试策略：领域层单元测试 → 应用层集成测试 → 接口层 E2E 测试
