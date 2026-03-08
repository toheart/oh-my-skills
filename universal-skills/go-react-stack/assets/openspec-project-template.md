# Project Context

## Purpose

[PROJECT_DESCRIPTION]

## Tech Stack

### Backend

- **Language**: Go 1.24+
- **Architecture**: DDD (Domain-Driven Design) + TDD
- **Web Framework**: Gin
- **Database**: [SQLite/PostgreSQL/MySQL]
- **Dependency Injection**: Wire

### Frontend

- **Language**: TypeScript
- **Framework**: React 18+
- **Build Tool**: Vite
- **Routing**: React Router
- **HTTP Client**: Axios

## Project Conventions

### Code Style

- **Go code style**: See [specs/go-style/spec.md](specs/go-style/spec.md)
- **TypeScript code style**: See [specs/typescript-style/spec.md](specs/typescript-style/spec.md)
- **API conventions**: See [specs/api-conventions/spec.md](specs/api-conventions/spec.md)
- **Testing specification**: See [specs/testing/spec.md](specs/testing/spec.md)

### Architecture Patterns

#### DDD Layered Architecture (Backend)

```
internal/
├── domain/          # 领域层 - 核心业务逻辑，不依赖任何外部
├── application/     # 应用层 - 用例编排，依赖领域层
├── infrastructure/  # 基础设施层 - 技术实现，实现领域层接口
└── interfaces/      # 接口层 - HTTP 暴露，依赖应用层
```

#### Dependency Direction

- 领域层不依赖任何层
- 应用层依赖领域层
- 基础设施层实现领域层接口
- 接口层依赖应用层

### Testing Strategy

Follow TDD (Test-Driven Development) principles. See [specs/testing/spec.md](specs/testing/spec.md) for details.

- **Go tests**: `testify` assertions + `mock` mocks
- **TypeScript tests**: Jest/Vitest
- **Run tests**: `make test` (Go), `npm test` (TS)
- **Coverage**: `make test-coverage`

### Git Workflow

- Branch strategy: `main` as primary branch, feature development uses `feature/<change-id>` branches
- Commit messages: Use English, format `<type>: <description>`
  - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## Important Constraints

### Technical Constraints

[Describe technical constraints such as performance requirements, platform limitations, etc.]

### Security Constraints

[Describe security-related constraints]

### Performance Constraints

[Describe performance-related constraints]

## External Dependencies

### Go Dependencies

- `github.com/gin-gonic/gin` - HTTP server
- `github.com/swaggo/swag` - Swagger documentation generation
- `github.com/stretchr/testify` - Testing framework
- `github.com/google/wire` - Dependency injection

### Node.js Dependencies

- `react` - React framework
- `react-router-dom` - Routing
- `axios` - HTTP client
- `vite` - Build tool

## API Endpoints Overview

HTTP API port: `8080`

| Module | Endpoint | Description |
|------|------|------|
| Health Check | `GET /health` | Service health status |
| API | `GET /api/v1/...` | API endpoints |
