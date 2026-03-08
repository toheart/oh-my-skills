# 示例代码参考

## 后端示例代码

### 领域层实体 (internal/domain/example/entity.go)

```go
package example

import "time"

type Example struct {
	ID        string
	Name      string
	CreatedAt time.Time
	UpdatedAt time.Time
}
```

### 领域层仓储接口 (internal/domain/example/repository.go)

```go
package example

import "context"

type Repository interface {
	GetByID(ctx context.Context, id string) (*Example, error)
	List(ctx context.Context) ([]*Example, error)
	Create(ctx context.Context, e *Example) error
	Update(ctx context.Context, e *Example) error
	Delete(ctx context.Context, id string) error
}
```

### 应用层服务 (internal/application/example/service.go)

```go
package example

import (
	"context"
	"time"

	"github.com/google/uuid"
	domainExample "github.com/user/project-name/internal/domain/example"
)

type Service struct {
	repo domainExample.Repository
}

func NewService(repo domainExample.Repository) *Service {
	return &Service{repo: repo}
}

func (s *Service) GetByID(ctx context.Context, id string) (*ExampleDTO, error) {
	entity, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	return toDTO(entity), nil
}

func (s *Service) List(ctx context.Context) ([]*ExampleDTO, error) {
	entities, err := s.repo.List(ctx)
	if err != nil {
		return nil, err
	}
	return toDTOs(entities), nil
}

func (s *Service) Create(ctx context.Context, req *CreateRequest) (*ExampleDTO, error) {
	entity := &domainExample.Example{
		ID:        uuid.New().String(),
		Name:      req.Name,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}
	if err := s.repo.Create(ctx, entity); err != nil {
		return nil, err
	}
	return toDTO(entity), nil
}

func (s *Service) Update(ctx context.Context, id string, req *UpdateRequest) (*ExampleDTO, error) {
	entity, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	entity.Name = req.Name
	entity.UpdatedAt = time.Now()
	if err := s.repo.Update(ctx, entity); err != nil {
		return nil, err
	}
	return toDTO(entity), nil
}

func (s *Service) Delete(ctx context.Context, id string) error {
	return s.repo.Delete(ctx, id)
}
```

### HTTP Handler (internal/interfaces/http/handler/example_handler.go)

```go
package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"
	appExample "github.com/user/project-name/internal/application/example"
)

type ExampleHandler struct {
	service *appExample.Service
}

func NewExampleHandler(service *appExample.Service) *ExampleHandler {
	return &ExampleHandler{service: service}
}

// List 获取列表
// @Summary Get example list
// @Tags Example
// @Accept json
// @Produce json
// @Success 200 {object} Response "Success"
// @Failure 500 {object} ErrorResponse "Internal error"
// @Router /examples [get]
func (h *ExampleHandler) List(c *gin.Context) {
	ctx := c.Request.Context()
	items, err := h.service.List(ctx)
	if err != nil {
		Error(c, http.StatusInternalServerError, 500001, "Failed to get list")
		return
	}
	Success(c, items)
}

// Get 获取详情
// @Summary Get example detail
// @Tags Example
// @Accept json
// @Produce json
// @Param id path string true "ID"
// @Success 200 {object} Response "Success"
// @Failure 400 {object} ErrorResponse "Invalid parameter"
// @Failure 404 {object} ErrorResponse "Not found"
// @Router /examples/{id} [get]
func (h *ExampleHandler) Get(c *gin.Context) {
	id := c.Param("id")
	ctx := c.Request.Context()
	item, err := h.service.GetByID(ctx, id)
	if err != nil {
		Error(c, http.StatusNotFound, 404001, "Not found")
		return
	}
	Success(c, item)
}

// Create 创建
// @Summary Create example
// @Tags Example
// @Accept json
// @Produce json
// @Param body body CreateRequest true "Create request"
// @Success 200 {object} Response "Success"
// @Failure 400 {object} ErrorResponse "Invalid parameter"
// @Router /examples [post]
func (h *ExampleHandler) Create(c *gin.Context) {
	var req appExample.CreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		Error(c, http.StatusBadRequest, 100001, "Invalid parameter")
		return
	}
	ctx := c.Request.Context()
	item, err := h.service.Create(ctx, &req)
	if err != nil {
		Error(c, http.StatusInternalServerError, 500001, "Failed to create")
		return
	}
	Success(c, item)
}
```

## 前端示例代码

### 组件示例 (src/components/Home.tsx)

```typescript
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { Loading } from './common/Loading';
import { Error } from './common/Error';

interface Example {
  id: string;
  name: string;
  createdAt: string;
}

export function Home(): JSX.Element {
  const { data, loading, error, refetch } = useApi<Example[]>(
    () => api.get('/examples')
  );

  if (loading) {
    return <Loading />;
  }

  if (error) {
    return <Error message={error.message} onRetry={refetch} />;
  }

  return (
    <div>
      <h1>Example List</h1>
      <ul>
        {data?.map((item) => (
          <li key={item.id}>{item.name}</li>
        ))}
      </ul>
    </div>
  );
}
```

### 通用组件 (src/components/common/Loading.tsx)

```typescript
export function Loading(): JSX.Element {
  return <div>Loading...</div>;
}
```

### 通用组件 (src/components/common/Error.tsx)

```typescript
interface ErrorProps {
  message: string;
  onRetry?: () => void;
}

export function Error({ message, onRetry }: ErrorProps): JSX.Element {
  return (
    <div>
      <p>Error: {message}</p>
      {onRetry && <button onClick={onRetry}>Retry</button>}
    </div>
  );
}
```
