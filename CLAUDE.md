# CLAUDE.md

## 项目概述

FlowAI — 企业级 AI 工作流可视化编排平台。Python FastAPI 后端 + React TypeScript 前端。

## 常用命令

```bash
# 后端（从 backend/ 目录执行）
cd backend
python main.py                              # 启动 (端口 8084)
pip install -e .                            # 安装依赖
alembic upgrade head                        # 数据库迁移
alembic revision --autogenerate -m "desc"   # 生成新迁移

# 前端
cd frontend
npm install && npm run dev                  # 启动 (端口 5173)
npm run build                               # 生产构建

# 测试
cd backend
python -m pytest tests/ -v                  # 运行测试 (18 个用例)

# Docker
docker compose up -d                        # 启动 MySQL/Redis/MinIO
```

## 技术栈

| 层 | 技术 |
|---|------|
| 后端框架 | FastAPI 0.115+ |
| 语言 | Python 3.13 |
| ORM | SQLAlchemy 2.0 (async) |
| 数据库迁移 | Alembic |
| LLM 调用 | LangChain (ChatOpenAI) |
| 状态图引擎 | LangGraph (StateGraph) |
| JWT | python-jose |
| 对象存储 | boto3 (MinIO) |
| SSE | sse-starlette |
| 日志 | structlog |
| 前端 | React 18 + TypeScript + Vite + ReactFlow + Ant Design + Zustand |

## 项目结构

```
backend/
├── main.py                  # FastAPI 入口，路由注册，启动
├── app/
│   ├── config.py            # pydantic-settings (FLOWAGENT_ 前缀)
│   ├── database.py          # async SQLAlchemy 引擎 + 时区设置 (+08:00)
│   ├── dependencies.py      # DI: get_db, get_current_user, require_auth
│   ├── logging_config.py    # structlog 配置 (控制台彩色 + 文件按日轮转)
│   ├── models/              # 17 个 SQLAlchemy 模型 (表名 snake_case)
│   ├── schemas/             # Pydantic 请求/响应 schema (Result[T] 信封)
│   ├── api/                 # 12 个路由模块，60+ RESTful 端点
│   │   ├── auth.py          # POST login/refresh/logout, GET current (登录限流 5次/分钟)
│   │   ├── health.py        # GET /health MySQL/Redis 连接状态
│   │   ├── workflows.py     # Workflow CRUD + 分页
│   │   ├── workflow_versions.py  # GET /versions, /diff, POST /rollback (版本管理)
│   │   ├── executions.py    # POST /executions, GET stream/latest/snapshots/variables/compare, POST resume/cancel
│   │   ├── circuit_breakers.py   # GET /circuit-breakers, POST /reset (熔断器管理)
│   │   ├── llm_config.py    # LLM 配置 CRUD + PATCH set-default
│   │   ├── mcp_tools.py     # MCP 工具 CRUD + POST actions/test
│   │   ├── knowledge.py     # 知识库 CRUD + GET chunks (搜索)
│   │   ├── benchmarks.py    # Benchmark 数据集/用例 CRUD + POST /run (4种评分)
│   │   ├── skills.py        # GET 技能列表/详情/引用
│   │   └── node_types.py    # GET 节点类型 (合成 + 过滤)
│   ├── services/            # 业务逻辑：auth (bcrypt), workflow, llm_config, knowledge, mcp_tool, skill, minio
│   ├── rate_limiter.py      # Redis 滑动窗口限流器
│   └── engine/              # 工作流引擎
│       ├── dag_engine.py    # DAG 引擎 (拓扑排序 + 条件分支 + 断点续执行 + 自动重试)
│       ├── dag_parser.py    # DFS 环检测 + Kahn 算法
│       ├── langgraph_engine.py  # LangGraph StateGraph 引擎 (自动重试)
│       ├── engine_selector.py   # 按 engine_type 路由引擎
│       ├── node_executor/   # NodeExecutor 接口 + 工厂 + 23 个实现
│       ├── agent_tools/     # 8 个 Agent 工具
│       ├── llm/             # ChatClientFactory + PromptTemplate
│       └── skills/          # Skill 注册与加载
├── skills/                  # 技能定义 (YAML frontmatter SKILL.md)
├── tests/                   # 单元测试 (18 个用例, httpx + pytest-asyncio)
├── alembic/                 # 数据库迁移
└── pyproject.toml           # 依赖声明 (hatchling 构建)
```

## API 响应格式

```json
{ "code": 200, "message": "操作成功", "data": { ... } }
```

- `code=200` 成功，`500` 服务器错误，`401` 未认证，`404` 不存在

## 认证

- JWT Bearer token，access token 120 分钟，refresh token (Redis DB 0) 168 小时
- 默认账户 `admin / admin123`（bcrypt 哈希存储）
- 无需认证: `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/node-types`, `/health`, `/docs`, `/openapi.json`
- 登录限流: Redis 滑动窗口 5 次/分钟/IP

## 工作流引擎

- **DAG** (默认): Kahn 算法拓扑排序，简单线性流程 A→B→C
- **LangGraph**: Python 原生 StateGraph，支持条件分支和循环
- 节点执行器注册在工厂中，`node_executor_factory.register()` 自注册
- 节点失败自动重试 (指数退避 2s/4s/8s)，可通过 `data.maxRetries` 配置
- **熔断器**: 节点类型级别自动熔断，连续失败 N 次后跳过该类型节点，定时探测恢复
- **执行取消**: Redis 取消标志位，当前节点完成后保存 checkpoint 再停止，可恢复
- **断点续执行**: 保存 checkpoint (nodeOutputs/completedNodeIds/skippedNodes)，支持 resume
- 心跳检测: 15s 间隔更新 heartbeat_at，orphan 检测 60s 阈值 + 自动恢复

## 版本管理

- 每次 `PUT /workflows/{id}` 自动在 `workflow_version` 表创建不可变快照
- `GET /{wid}/versions` 列出所有版本，`GET /{v1}/{v2}/diff` 结构化对比
- `POST /{vid}/rollback` 回滚：先保存当前版，再恢复目标版到 workflow

## Benchmark 系统

- 3 表: `benchmark_dataset` (数据集) / `benchmark_case` (用例) / `benchmark_run` (执行记录)
- 4 种评分: exact (精确匹配) / contains (包含) / semantic (语义相似) / llm_judge (LLM 评分)
- `POST /datasets/{id}/run?workflowId=X` 对数据集全量执行并评分
- LLM judge 使用 LLM 配置中的模型评分，失败时降级为 semantic

## 执行对比

- `GET /executions/{id}/compare?other={id2}` 返回结构化 diff
- 对比维度: 状态/耗时/输入diff/输出diff/逐节点耗时和输出diff/独有节点

## 注意事项

- `.env` 放在项目根目录或 `backend/`
- 数据库 `flowagent`，环境变量 `FLOWAGENT_` 前缀
- MySQL 时区设为 `+08:00`（`database.py` 连接事件中 SET）
- 所有 imports 必须放在文件顶部，禁止函数内 import
- API 使用 Pydantic `Result[T]` 统一信封，前端 Axios 拦截器解包
- SSE 流式执行通过 `/api/executions/stream` 端点
- **antd v6 List 组件已弃用**，前端禁止使用 `<List>`，用 `<div>` + `.map()` + `<Spin>` 替代
- **后端列表 API 统返回 PageData** `{ items, total, page, size }`，前端取 `.data.items`
- 新功能开发遵循: models → schemas → service → api → main.py 注册 → 迁移
