---
name: go-react-stack
description: Create a new Go+React full-stack project with DDD architecture and React best practices. Includes complete project scaffolding with backend (Go with Gin), frontend (React with TypeScript), and example code following project conventions. Use this skill when users request creating a new full-stack project or scaffolding a Go+React application.
---

# Go+React 全栈项目脚手架

创建遵循 DDD 分层架构和 React 最佳实践的 Go+React 全栈项目。

## 工作流

### 1. 交互式信息收集

在创建项目前，向用户询问以下信息：

1. **项目名称**（kebab-case）：
   - 示例：`my-app`、`todo-app`
   - 校验：只允许小写字母、数字和连字符

2. **Go module 路径**：
   - 示例：`github.com/user/my-app`
   - 默认：根据项目名建议 `github.com/your-username/{project-name}`

3. **项目描述**：
   - 简要描述项目用途

4. **是否包含 OpenSpec**（默认：是）：
   - 若包含，调用 `openspec` skill 初始化 OpenSpec 目录结构
   - 并将 `assets/openspec-project-template.md` 复制为 `openspec/project.md`，替换占位符

5. **是否包含编码规范**（默认：是）：
   - 若包含且启用了 OpenSpec，将 `go-react-codestyle` skill 中的规范文件复制到 `openspec/specs/` 下
   - 若未启用 OpenSpec，将规范文件放到项目根目录 `docs/` 下

6. **前端构建工具**（默认：Vite）：
   - 选项：Vite 或 Webpack

7. **项目路径**：
   - 默认：当前工作目录

### 2. 创建项目目录结构

```
<project-name>/
├── backend/                    # Go 后端
│   ├── cmd/
│   │   ├── main.go            # 入口（Cobra 根命令）
│   │   └── server.go          # Server 子命令
│   ├── conf/
│   │   └── conf.go            # 配置管理（Viper）
│   ├── etc/
│   │   ├── config.dev.yaml    # 开发环境配置
│   │   └── config.prod.yaml   # 生产环境配置
│   ├── internal/
│   │   ├── logging/           # 日志库（基于 log/slog）
│   │   │   ├── logger.go
│   │   │   ├── config.go
│   │   │   └── context.go
│   │   ├── domain/            # 领域层
│   │   │   └── example/
│   │   ├── application/       # 应用层
│   │   │   └── example/
│   │   ├── infrastructure/    # 基础设施层
│   │   │   └── storage/
│   │   ├── interfaces/        # 接口层
│   │   │   └── http/
│   │   │       ├── handler/
│   │   │       ├── response/
│   │   │       └── server.go
│   │   └── wire/              # Wire 依赖注入
│   ├── docs/                  # Swagger 文档（自动生成）
│   ├── go.mod
│   ├── go.sum
│   ├── .golangci.yml
│   └── Makefile
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   └── common/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── utils/
│   │   ├── types/
│   │   ├── styles/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── .eslintrc.json
├── .gitignore
└── README.md
```

### 3. 生成配置文件

#### Go 后端配置

采用 **Cobra 子命令 + Viper 配置 + slog 日志** 的标准启动模式：

- **go.mod**：参见 `references/go-configs.md` 中的模板
- **Makefile**：参见 `references/go-configs.md` 中的模板
- **.golangci.yml**：参见 `references/go-configs.md` 中的模板
- **cmd/main.go**：Cobra 根命令入口，含 version 和 server 子命令
- **cmd/server.go**：Server 子命令，按顺序执行：加载配置 → 初始化日志 → Wire 注入 → 启动 HTTP → 信号监听 → 优雅关闭
- **conf/conf.go**：Viper 配置管理，支持 YAML 文件 + 环境变量覆盖
- **etc/config.dev.yaml**：开发环境配置文件
- **internal/logging/**：基于 `log/slog` 封装的日志库（JSON 输出、文件轮转、context 日志）
- **HTTP Server**：参见 `references/go-configs.md` 中的模板

以上所有模板均参见 `references/go-configs.md`。

#### React 前端配置

- **package.json**：参见 `references/typescript-configs.md` 中的模板
- **tsconfig.json**：参见 `references/typescript-configs.md` 中的模板
- **vite.config.ts**：参见 `references/typescript-configs.md` 中的模板
- **.eslintrc.json**：参见 `references/typescript-configs.md` 中的模板
- **API 服务 / Hook / App**：参见 `references/typescript-configs.md` 中的模板

### 4. 生成示例代码

参见 `references/example-code.md` 获取完整的示例代码模板。

#### 后端示例

1. **启动架构** (`cmd/`)：Cobra 入口 + Server 子命令
2. **配置管理** (`conf/`)：Viper 加载 YAML + 环境变量覆盖
3. **日志库** (`internal/logging/`)：slog 封装，JSON 输出，文件轮转
4. **领域层** (`internal/domain/example/`)：实体定义、仓储接口
5. **应用层** (`internal/application/example/`)：应用服务、DTO
6. **基础设施层** (`internal/infrastructure/storage/`)：仓储实现
7. **接口层** (`internal/interfaces/http/handler/`)：HTTP Handler（含 Swagger 注解）
8. **Wire 配置** (`internal/wire/`)：Provider Sets
9. **测试文件**：每层对应的 `*_test.go`

#### 前端示例

1. **组件** (`src/components/`)：Home、Button、Loading
2. **Hooks** (`src/hooks/`)：useApi
3. **Services** (`src/services/`)：API 客户端
4. **路由** (`src/App.tsx`)：React Router 配置
5. **类型** (`src/types/`)：类型定义

### 5. 生成文档

**README.md**：包含项目介绍、技术栈、快速开始、项目结构、开发指南。

### 6. 初始化 Git（可选）

询问用户是否初始化 Git 仓库。若是：
- 执行 `git init`
- 创建 `.gitignore`
- 创建初始提交

## 使用脚本快速创建

```bash
python3 scripts/create_project.py
```

脚本会交互式询问项目信息并自动创建项目结构。

## 参考文件

- **Go 配置模板**：`references/go-configs.md`
- **TypeScript/React 配置模板**：`references/typescript-configs.md`
- **示例代码**：`references/example-code.md`
- **OpenSpec project.md 模板**：`assets/openspec-project-template.md`
- **项目创建脚本**：`scripts/create_project.py`

## 注意事项

1. **Module 路径**：确保 Go module 路径正确，代码中的 import 路径基于此
2. **端口配置**：后端默认 8080（通过 `etc/config.dev.yaml` 配置），前端开发服务器默认 3000
3. **API 代理**：前端 Vite 配置包含到后端 API 的代理设置
4. **启动模式**：后端使用 Cobra 子命令启动，支持 `--run-mode` 和 `--configs` 参数
5. **日志库**：使用 `internal/logging` 包，不要直接使用 `fmt.Println` 或 `log.Printf`
6. **配置管理**：敏感信息通过环境变量注入，不提交到仓库
7. **测试覆盖**：示例代码包含测试文件，展示 TDD 实践

## 后续步骤

项目创建后，提示用户：
1. 进入后端：`cd backend && go mod download`
2. 进入前端：`cd frontend && npm install`
3. 启动后端：`cd backend && make run`（等同于 `go run ./cmd/ server`）
4. 启动前端：`cd frontend && npm run dev`
5. 查看版本：`cd backend && go run ./cmd/ version`
6. 查看 API 文档：访问 `http://localhost:8080/swagger/index.html`
