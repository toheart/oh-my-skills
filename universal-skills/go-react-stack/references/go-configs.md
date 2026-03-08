# Go 配置参考

## go.mod 模板

```go
module github.com/user/project-name

go 1.24.0

require (
	github.com/gin-gonic/gin v1.10.0
	github.com/google/uuid v1.6.0
	github.com/google/wire v0.6.0
	github.com/onsi/ginkgo/v2 v2.22.2
	github.com/onsi/gomega v1.36.2
	github.com/spf13/cobra v1.9.1
	github.com/spf13/viper v1.20.0
	github.com/swaggo/files v1.0.1
	github.com/swaggo/gin-swagger v1.6.0
	github.com/swaggo/swag v1.8.12
	gopkg.in/natefinsh/lumberjack.v2 v2.2.1
)
```

## .golangci.yml 模板

```yaml
# golangci-lint v2.x 配置
version: "2"

run:
  timeout: 10m
  concurrency: 0

linters:
  enable:
    - nestif
    - gocognit
    - gocyclo
    - errcheck
    - govet
    - ineffassign
    - staticcheck
    - unused

  settings:
    nestif:
      min-complexity: 4
    gocognit:
      min-complexity: 15
    gocyclo:
      min-complexity: 10

  exclusions:
    generated: lax
    paths:
      - vendor
      - bin
      - ".*\\.pb\\.go$"
      - ".*\\.gen\\.go$"
    rules:
      - path: "_test\\.go"
        linters:
          - gocyclo
          - errcheck
          - gocognit
          - nestif

issues:
  max-issues-per-linter: 50
  max-same-issues: 3
```

## Makefile 模板

```makefile
.PHONY: all build test clean run wire swagger lint fmt mock

VERSION ?= 0.1.0
BUILD_TIME := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")

LDFLAGS := -ldflags "-X main.Version=$(VERSION) -X main.BuildTime=$(BUILD_TIME) -X main.GitCommit=$(GIT_COMMIT)"

BIN_DIR := bin

all: test build

test:
	go test -v -race -cover ./...

test-coverage:
	go test -v -race -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html

wire:
	cd internal/wire && go run github.com/google/wire/cmd/wire

swagger:
	@echo "Generating Swagger docs..."
	@go run github.com/swaggo/swag/cmd/swag@latest init -g cmd/main.go -o docs --parseDependency --parseInternal

build: wire
	@mkdir -p $(BIN_DIR)
	go build $(LDFLAGS) -o $(BIN_DIR)/server ./cmd/

run: wire
	go run ./cmd/ server

clean:
	rm -rf $(BIN_DIR)
	rm -f coverage.out coverage.html
	find . -name "wire_gen.go" -delete

lint:
	golangci-lint run --config .golangci.yml ./...

fmt:
	go fmt ./...
	goimports -w -local github.com/user/project-name .

mock:
	mockery
```

## 项目启动架构

采用 Cobra 子命令 + Viper 配置 + slog 日志的标准启动模式，参考 kskillhub 项目。

### cmd/main.go — 入口文件

```go
// @title Project API
// @version 1.0
// @description 项目 API 服务
// @host localhost:8080
// @BasePath /api/v1
// @schemes http
package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var (
	Version   = "dev"
	BuildTime = "unknown"
	GitCommit = "unknown"

	configDir string
	runMode   string
)

var rootCmd = &cobra.Command{
	Use:   "project-name",
	Short: "Project description",
}

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print version information",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Printf("%s (build=%s commit=%s)\n", Version, BuildTime, GitCommit)
	},
}

func init() {
	rootCmd.PersistentFlags().StringVar(&configDir, "configs", "etc", "Configuration file directory")
	rootCmd.PersistentFlags().StringVar(&runMode, "run-mode", envOrDefault("RUN_MODE", "dev"), "Run mode: dev, e2e, beta, prod")
	rootCmd.AddCommand(versionCmd)
	rootCmd.AddCommand(serverCmd)
}

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func main() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
```

### cmd/server.go — Server 子命令

```go
package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/spf13/cobra"

	"github.com/user/project-name/conf"
	"github.com/user/project-name/internal/logging"
	"github.com/user/project-name/internal/wire"
)

var serverCmd = &cobra.Command{
	Use:   "server",
	Short: "Start API server",
	Run:   runServer,
}

func runServer(cmd *cobra.Command, args []string) {
	// 1. 加载配置
	cfg, err := conf.InitConfig(configDir, runMode)
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// 2. 初始化日志
	logCfg := logging.NewConfigFromConf(logging.ConfLogConfig{
		Dir:        cfg.Log.Dir,
		Level:      cfg.Log.Level,
		Output:     cfg.Log.Output,
		KeepHours:  cfg.Log.KeepHours,
		RotateNum:  cfg.Log.RotateNum,
		RotateSize: cfg.Log.RotateSize,
	})
	logCleanup, err := logging.InitWithConfig("project-name", logCfg)
	if err != nil {
		log.Fatalf("Failed to init logging: %v", err)
	}
	defer logCleanup()

	logging.Info("server starting",
		"version", Version,
		"build", BuildTime,
		"commit", GitCommit,
		"mode", runMode,
	)

	// 3. Wire 依赖注入初始化
	srv, err := wire.InitializeServer(cfg)
	if err != nil {
		logging.Error("failed to initialize server", "error", err)
		log.Fatalf("Failed to initialize server: %v", err)
	}

	// 4. 启动 HTTP 服务器（异步）
	errChan := make(chan error, 1)
	go func() {
		errChan <- srv.Start()
	}()

	// 5. 等待信号或错误
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-sigChan:
		logging.Info("received shutdown signal", "signal", sig.String())
	case err := <-errChan:
		logging.Error("HTTP server error", "error", err)
	}

	// 6. 优雅关闭
	logging.Info("server shutting down")
	if err := srv.Stop(); err != nil {
		logging.Error("server shutdown error", "error", err)
	}
	logging.Info("server stopped")
}
```

### conf/conf.go — 配置管理

```go
package conf

import (
	"fmt"
	"strings"

	"github.com/spf13/viper"
)

type ConfigType struct {
	Global GlobalConfig `yaml:"Global"`
	Log    LogConfig    `yaml:"Log"`
	HTTP   HTTPConfig   `yaml:"HTTP"`
}

type GlobalConfig struct {
	RunMode string `yaml:"RunMode"`
}

type LogConfig struct {
	Dir        string `yaml:"Dir"`
	Level      string `yaml:"Level"`
	Output     string `yaml:"Output"`     // stdout / file / both
	KeepHours  uint   `yaml:"KeepHours"`
	RotateNum  int    `yaml:"RotateNum"`
	RotateSize uint64 `yaml:"RotateSize"` // 单文件大小上限（MB）
}

type HTTPConfig struct {
	Host            string `yaml:"Host"`
	Port            int    `yaml:"Port"`
	ShutdownTimeout int    `yaml:"ShutdownTimeout"`
	PProf           bool   `yaml:"PProf"`
}

// InitConfig 初始化配置
// configDir: 配置文件目录（如 ./etc）
// runMode: 运行模式（dev / e2e / prod / beta）
func InitConfig(configDir, runMode string) (*ConfigType, error) {
	config := new(ConfigType)

	// ExperimentalBindStruct 使 Unmarshal 能自动从环境变量覆盖嵌套结构体字段
	// 环境变量命名规则：PROJECTNAME_<SECTION>_<FIELD>
	v := viper.NewWithOptions(viper.ExperimentalBindStruct())
	v.SetEnvPrefix("PROJECTNAME")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	candidates := buildConfigCandidates(runMode)
	var lastErr error
	v.AddConfigPath(configDir)
	v.SetConfigType("yaml")
	for _, name := range candidates {
		v.SetConfigName(name)
		if err := v.ReadInConfig(); err != nil {
			lastErr = err
			continue
		}
		lastErr = nil
		break
	}
	if lastErr != nil {
		return nil, fmt.Errorf("failed to read config file candidates %v: %v", candidates, lastErr)
	}

	if err := v.Unmarshal(config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %v", err)
	}

	return config, nil
}

// buildConfigCandidates 构造配置文件候选列表
// 优先 config.<runMode>.yaml，兜底 config.yaml
func buildConfigCandidates(runMode string) []string {
	var candidates []string
	if runMode != "" {
		candidates = append(candidates, fmt.Sprintf("config.%s", runMode))
	}
	candidates = append(candidates, "config")
	return candidates
}

func (c *ConfigType) GetHTTPAddr() string {
	host := c.HTTP.Host
	if host == "" {
		host = "0.0.0.0"
	}
	port := c.HTTP.Port
	if port == 0 {
		port = 8080
	}
	return fmt.Sprintf("%s:%d", host, port)
}
```

### etc/config.dev.yaml — 开发环境配置文件

```yaml
Global:
  RunMode: "dev"

Log:
  Dir: "logs"
  Level: "DEBUG"
  Output: "both"
  KeepHours: 72
  RotateNum: 5
  RotateSize: 100

HTTP:
  Host: "0.0.0.0"
  Port: 8080
  ShutdownTimeout: 30
  PProf: true
```

## internal/logging — 日志库

基于标准库 `log/slog` 封装的结构化日志库，支持文件轮转、JSON 输出、字段分类。

### logging/config.go

```go
package logging

import (
	"log/slog"
	"os"
	"strings"
)

type Config struct {
	Level      slog.Level
	Components []string

	Dir        string
	Output     string // stdout / file / both
	KeepHours  uint
	RotateNum  int
	RotateSize uint64
}

// LoadConfig 从环境变量加载配置
func LoadConfig() Config {
	cfg := Config{
		Level: slog.LevelInfo,
	}
	if levelStr := os.Getenv("LOG_LEVEL"); levelStr != "" {
		cfg.Level = parseLevel(levelStr)
	}
	if componentsStr := os.Getenv("LOG_COMPONENTS"); componentsStr != "" {
		parts := strings.Split(componentsStr, ",")
		for _, part := range parts {
			if trimmed := strings.TrimSpace(part); trimmed != "" {
				cfg.Components = append(cfg.Components, trimmed)
			}
		}
	}
	return cfg
}

func parseLevel(s string) slog.Level {
	switch strings.ToUpper(s) {
	case "DEBUG":
		return slog.LevelDebug
	case "INFO":
		return slog.LevelInfo
	case "WARN", "WARNING":
		return slog.LevelWarn
	case "ERROR":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}

// ConfLogConfig 对应 conf 包的 LogConfig 结构，避免循环依赖
type ConfLogConfig struct {
	Dir        string
	Level      string
	Output     string
	KeepHours  uint
	RotateNum  int
	RotateSize uint64
}

// NewConfigFromConf 从 conf.LogConfig 创建 logging.Config
// 环境变量优先级高于配置文件
func NewConfigFromConf(confCfg ConfLogConfig) Config {
	cfg := LoadConfig()

	if os.Getenv("LOG_LEVEL") == "" && confCfg.Level != "" {
		cfg.Level = parseLevel(confCfg.Level)
	}
	if confCfg.Dir != "" {
		cfg.Dir = confCfg.Dir
	}
	if confCfg.Output != "" {
		cfg.Output = confCfg.Output
	}
	if confCfg.KeepHours != 0 {
		cfg.KeepHours = confCfg.KeepHours
	}
	if confCfg.RotateNum != 0 {
		cfg.RotateNum = confCfg.RotateNum
	}
	if confCfg.RotateSize != 0 {
		cfg.RotateSize = confCfg.RotateSize
	}

	if cfg.Output == "" {
		cfg.Output = "stdout"
	}
	return cfg
}
```

### logging/logger.go

```go
package logging

import (
	"context"
	"io"
	"log/slog"
	"os"
	"time"
)

var (
	globalLogger  *slog.Logger
	globalConfig  Config
	defaultLogger = slog.Default()
)

// InitWithConfig 使用指定配置初始化全局日志设施
func InitWithConfig(component string, cfg Config) (func(), error) {
	globalConfig = cfg

	opts := &slog.HandlerOptions{
		Level: cfg.Level,
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			if a.Key == slog.TimeKey {
				return slog.String("timestamp", a.Value.Time().Format(time.RFC3339))
			}
			if a.Key == slog.LevelKey {
				level := a.Value.Any().(slog.Level)
				return slog.String("level", levelToString(level))
			}
			if a.Key == slog.MessageKey {
				return slog.String("message", a.Value.String())
			}
			return a
		},
	}

	var cleanupFunc func()

	switch cfg.Output {
	case "file":
		w, err := createFileWriter(cfg, component)
		if err != nil {
			return nil, err
		}
		handler := slog.NewJSONHandler(w, opts)
		globalLogger = slog.New(handler).With("component", component)
		cleanupFunc = func() {
			if c, ok := w.(interface{ Close() error }); ok {
				_ = c.Close()
			}
		}

	case "both":
		fileWriter, err := createFileWriter(cfg, component)
		if err != nil {
			return nil, err
		}
		multiWriter := io.MultiWriter(os.Stdout, fileWriter)
		handler := slog.NewJSONHandler(multiWriter, opts)
		globalLogger = slog.New(handler).With("component", component)
		cleanupFunc = func() {
			if c, ok := fileWriter.(interface{ Close() error }); ok {
				_ = c.Close()
			}
		}

	default: // stdout
		handler := slog.NewJSONHandler(os.Stdout, opts)
		globalLogger = slog.New(handler).With("component", component)
		cleanupFunc = func() {}
	}

	return cleanupFunc, nil
}

// Debug 记录 DEBUG 级别日志
func Debug(msg string, args ...any) {
	if globalLogger != nil {
		globalLogger.Debug(msg, args...)
	}
}

// Info 记录 INFO 级别日志
func Info(msg string, args ...any) {
	if globalLogger != nil {
		globalLogger.Info(msg, args...)
	}
}

// Warn 记录 WARN 级别日志
func Warn(msg string, args ...any) {
	if globalLogger != nil {
		globalLogger.Warn(msg, args...)
	}
}

// Error 记录 ERROR 级别日志
func Error(msg string, args ...any) {
	if globalLogger != nil {
		globalLogger.Error(msg, args...)
	}
}
```

### logging/context.go — 带上下文的日志

```go
package logging

import (
	"context"
	"log/slog"
)

type loggerKey struct{}

// FromContext 从 context 中获取 logger
func FromContext(ctx context.Context) *slog.Logger {
	if ctx == nil {
		return getLogger()
	}
	if logger, ok := ctx.Value(loggerKey{}).(*slog.Logger); ok && logger != nil {
		return logger
	}
	return getLogger()
}

func getLogger() *slog.Logger {
	if globalLogger != nil {
		return globalLogger
	}
	return slog.Default()
}

// SetContext 将 logger 存入 context
func SetContext(ctx context.Context, logger *slog.Logger) context.Context {
	return context.WithValue(ctx, loggerKey{}, logger)
}

// Debugc 记录带 context 的 DEBUG 日志
func Debugc(ctx context.Context, msg string, args ...any) {
	FromContext(ctx).Debug(msg, args...)
}

// Infoc 记录带 context 的 INFO 日志
func Infoc(ctx context.Context, msg string, args ...any) {
	FromContext(ctx).Info(msg, args...)
}

// Warnc 记录带 context 的 WARN 日志
func Warnc(ctx context.Context, msg string, args ...any) {
	FromContext(ctx).Warn(msg, args...)
}

// Errorc 记录带 context 的 ERROR 日志
func Errorc(ctx context.Context, msg string, args ...any) {
	FromContext(ctx).Error(msg, args...)
}

// With 返回附加字段的新 logger
func With(args ...any) *slog.Logger {
	if globalLogger != nil {
		return globalLogger.With(args...)
	}
	return slog.Default().With(args...)
}
```

## HTTP Server 模板

```go
package http

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	swaggerFiles "github.com/swaggo/files"
	ginSwagger "github.com/swaggo/gin-swagger"

	"github.com/user/project-name/conf"
	_ "github.com/user/project-name/docs"
	"github.com/user/project-name/internal/interfaces/http/handler"
	"github.com/user/project-name/internal/logging"
)

type HTTPServer struct {
	cfg             *conf.ConfigType
	router          *gin.Engine
	server          *http.Server
	shutdownTimeout time.Duration
}

func NewServer(
	cfg *conf.ConfigType,
	exampleHandler *handler.ExampleHandler,
) *HTTPServer {
	router := gin.Default()

	api := router.Group("/api/v1")
	{
		api.GET("/examples", exampleHandler.List)
		api.GET("/examples/:id", exampleHandler.Get)
		api.POST("/examples", exampleHandler.Create)
		api.PUT("/examples/:id", exampleHandler.Update)
		api.DELETE("/examples/:id", exampleHandler.Delete)
	}

	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	router.GET("/swagger/*any", ginSwagger.WrapHandler(swaggerFiles.Handler))

	shutdownTimeout := time.Duration(cfg.HTTP.ShutdownTimeout) * time.Second
	if shutdownTimeout == 0 {
		shutdownTimeout = 10 * time.Second
	}

	return &HTTPServer{
		cfg:             cfg,
		router:          router,
		shutdownTimeout: shutdownTimeout,
	}
}

func (s *HTTPServer) Start() error {
	addr := s.cfg.GetHTTPAddr()
	s.server = &http.Server{
		Addr:    addr,
		Handler: s.router,
	}
	logging.Info("HTTP server started", "addr", addr)
	return s.server.ListenAndServe()
}

func (s *HTTPServer) Stop() error {
	if s.server == nil {
		return nil
	}
	ctx, cancel := context.WithTimeout(context.Background(), s.shutdownTimeout)
	defer cancel()
	return s.server.Shutdown(ctx)
}
```
