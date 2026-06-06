# 变更说明

FlowAI (Java) → FlowAI (Python) 重构变更记录。

---

## 1. 后端语言迁移

| 项 | 原 | 现 |
|---|------|------|
| 语言 | Java 21 | Python 3.13 |
| 框架 | Spring Boot 3.4.1 | FastAPI 0.115+ |
| ORM | MyBatis-Plus 3.5.5 | SQLAlchemy 2.0 (async) |
| 数据库迁移 | schema.sql | Alembic |
| LLM 调用 | Spring AI 1.0.0-M5 | LangChain 0.3+ |
| 状态图引擎 | LangGraph4j 1.8.0 | LangGraph 0.2+ (原生) |
| JWT | jjwt | python-jose |
| 对象存储 | MinIO SDK (Java) | boto3 |
| SSE | SseEmitter | sse-starlette |
| 日志 | SLF4J + Logback | structlog |

---

## 2. 项目重命名

- 项目名 `FlowAI` → `FlowAI`
- 数据库 `paiagent` → `flowagent`
- 环境变量前缀 `FLOWAGENT_`
- 所有页面标题、品牌名同步更新

---

## 3. Docker 容器化

- 新增 `docker-compose.yml`，位于项目根目录
- MySQL 8.0 (3307)、Redis 7 (6379)、MinIO (9000)
- `.env` 支持根目录和 `backend/` 双位置

---

## 4. API RESTful 规范化

| # | 原 (RPC 风格) | 现 (RESTful) |
|---|------|------|
| 1 | `POST /workflows/{id}/execute` | `POST /api/executions` |
| 2 | `GET /workflows/{id}/execute/stream` | `GET /api/executions/stream` |
| 3 | `GET /workflows/{id}/executions/latest` | `GET /api/executions/latest?workflowId=` |
| 4 | `GET /.../{execId}/snapshots` | `GET /api/executions/{id}/snapshots` |
| 5 | `GET /.../{execId}/variables` | `GET /api/executions/{id}/variables` |
| 6 | `POST /.../{execId}/resume` | `POST /api/executions/{id}/resume` |
| 7 | `POST /llm-config/{id}/default` | `PATCH /api/llm-config/{id}` |
| 8 | `POST /knowledge-bases/{id}/search` | `GET /.../{id}/chunks?query=` |
| 9 | `POST /mcp-tools/agent-plan-web-search` | `POST /api/mcp-tools` |
| 10 | `POST /mcp-tools/{id}/test` | `POST /.../{id}/actions/test` |

---

## 5. 项目结构变化

```
原 FlowAI/                         现 FlowAI/
├── backend/ (Java + Maven)          ├── docker-compose.yml
├── frontend/                        ├── backend/ (Python)
└── schema.sql                       │   ├── main.py
                                     │   ├── .env
                                     │   ├── alembic/
                                     │   └── app/
                                     │       ├── api/
                                     │       ├── models/
                                     │       ├── schemas/
                                     │       ├── services/
                                     │       └── engine/
                                     ├── frontend/
                                     └── skills/
```

- `main.py` 位于 `backend/` 根，启动命令 `python main.py`
- `.env` 位于项目根目录和 `backend/` 各一份
- 废弃文件 `test_llm_config.py` 已删除

---

## 6. 结构化日志

- 控制台：带颜色输出，`时间 [级别] logger名 | 消息` 格式
- 文件：`logs/flowagent-YYYY-MM-DD.log`，JSON 格式
- 每日自动轮转，单文件上限 50MB，保留 30 份
- 静默 SQLAlchemy/httpx/Redis/boto3 等库的调试日志

---

## 7. 新增功能

- **天气查询节点**：对接高德地图 API，支持实时天气和预报
- **出行建议 Skill** (`travel-advisor`)：根据天气生成穿衣/活动建议

---

## 8. 厂商精简

- 移除 AIPing、APIFree 两个低使用率 provider
- 当前支持 6 家：OpenAI、DeepSeek、通义千问、Step、智谱、火山方舟 Agent Plan

---

## 9. 登录页重构

- 暗蓝色科技感背景 + 动态渐变
- 玻璃态卡片 + 网格装饰
- 渐变色登录按钮

---

## 10. Redis 连接池

- 从单连接缓存改为 `ConnectionPool`（最大 10 连接）
- 应用关闭时自动断开池
- 解决 Windows Python 3.13 事件循环冲突

---

## 11. 工程健壮性优化 (2026-06-06)

### 11.1 自动重试

- DAG / LangGraph 双引擎接入节点重试 + 指数退避 (2s/4s/8s)
- 节点 `data.maxRetries` 控制重试次数，`data.retryDelayMs` 控制基础延迟
- 新增 `NODE_RETRY` SSE 事件，实时推送重试状态

### 11.2 全局异常处理

- 注册 FastAPI `exception_handler(Exception)` 统一返回 `Result.error(code=500, message)`
- 替代原来空白 `Internal Server Error`

### 11.3 密码加密

- `passlib[bcrypt]` 替代明文 `==` 比对
- `AuthService` 启动时自动 hash 默认密码，login 时 `pwd_context.verify()`

### 11.4 分页

- `GET /api/v1/workflows?page=1&size=20` 分页查询
- `PageData[T]` 统一分页 envelope：`{items, total, page, size}`
- `size` 上限 100，防止大查询

### 11.5 健康检查

- 新增 `GET /health` 端点（无需认证）
- 实时返回 MySQL / Redis 连接状态：`{"status":"ok|degraded","mysql":"ok","redis":"ok"}`

### 11.6 启动配置校验

- lifespan startup 阶段 ping MySQL + Redis
- 任一失败则 `raise RuntimeError` 阻止启动

### 11.7 登录限流

- Redis Sorted Set 滑动窗口限流器 (`rate_limiter.py`)
- `POST /api/v1/auth/login` 限制 5 次/分钟/IP
- Redis 故障时自动放通（fail-open）

### 11.8 单元测试

- `tests/` 目录，18 个 pytest 用例
- 覆盖：auth 密码加密、DAG 引擎校验/输入解析、API 端点、限流器
- 使用 `httpx.ASGITransport` 免启动服务直接测试

### 11.9 API 版本化

- `/api/*` → `/api/v1/*` 自动重写中间件
- 保留 `/api/*` 向后兼容（自动 301 到 `/api/v1/*`）
