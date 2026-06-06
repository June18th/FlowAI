# AGENTS.md

## 项目概述

FlowAI 是企业级 AI 工作流可视化编排平台，后端 Python FastAPI，前端 React + TypeScript。
工作流编辑基于 ReactFlow 拖拽画布，执行引擎支持 DAG (Kahn 拓扑排序) 和 LangGraph 状态图两种模式。

## 构建与开发命令

### 后端 (Python FastAPI)
```bash
cd backend
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
alembic upgrade head                   # 数据库迁移
python -m uvicorn main:app --port 8085 --reload  # 启动 (端口 8085)
python -m pytest tests/ -v             # 运行测试 (18 个用例)
```

### 前端 (React + Vite)
```bash
cd frontend
npm install
npm run dev                            # 启动 (端口 5173)
npm run build                          # 生产构建
```

### Docker
```bash
docker compose up -d                           # MySQL(3307) + Redis(6379) + MinIO(9000)
```

## 环境变量

后端 `backend/.env`（FLOWAGENT_ 前缀）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| FLOWAGENT_MYSQL_HOST | localhost | MySQL 地址 |
| FLOWAGENT_MYSQL_PORT | 3307 | MySQL 端口 |
| FLOWAGENT_MYSQL_DATABASE | flowagent | 数据库名 |
| FLOWAGENT_REDIS_HOST | localhost | Redis 地址 |
| FLOWAGENT_REDIS_PORT | 6379 | Redis 端口 |
| FLOWAGENT_REDIS_DB | 0 | Redis DB 编号 |
| FLOWAGENT_MINIO_ENDPOINT | http://localhost:9000 | MinIO 地址 |
| FLOWAGENT_DEFAULT_USERNAME | admin | 默认用户名 |
| FLOWAGENT_DEFAULT_PASSWORD | admin123 | 默认密码 |

## 架构

### 后端结构 (`backend/app/`)

**API 层 (`api/`)：** 9 个路由模块，39 个端点
- `auth.py` — 登录/登出/刷新 token（bcrypt 密码 + 限流 5次/分钟）
- `health.py` — MySQL/Redis 连接健康检查
- `workflows.py` — 工作流 CRUD + 分页
- `executions.py` — 同步执行、SSE 流式执行、快照、断点续执行
- `llm_config.py` — LLM 全局配置管理
- `mcp_tools.py` — MCP 工具管理
- `knowledge.py` — 知识库 CRUD、文档导入、索引、搜索
- `skills.py` — 技能列表/详情/引用
- `node_types.py` — 节点类型定义

**服务层 (`services/`)：**
- `auth_service.py` — JWT 签发/验证、Redis refresh token
- `workflow_service.py` — 工作流 CRUD
- `llm_config_service.py` — LLM 配置 upsert、默认切换、provider 别名规范化
- `knowledge_service.py` — 文本分割、余弦相似度+文本相关性评分
- `skill_service.py` — SKILL.md YAML 解析、三级渐进加载

**引擎层 (`engine/`)：**
- `dag_engine.py` — DAG 引擎：拓扑排序执行、条件分支路由、断点续执行、自动重试+指数退避
- `langgraph_engine.py` — Python 原生 LangGraph StateGraph 引擎（自动重试）
- `dag_parser.py` — Kahn 拓扑排序 + DFS 循环检测
- `engine_selector.py` — 根据 `engine_type` 字段路由引擎
- `workflow_config_parser.py` — 解析 ReactFlow JSON
- `node_executor/base.py` — NodeExecutor 接口
- `node_executor/factory.py` — 注册工厂 (23 个执行器)
- `node_executor/abstract_llm.py` — LLM 基类 (Skill 嵌入、Memory/Knowledge 上下文、token 统计)
- `node_executor/impl/` — 具体执行器 (input, output, condition, llm_providers, react_agent, tool_nodes)
- `llm/chat_client_factory.py` — LangChain ChatOpenAI 多厂商兼容 (8 个 provider)
- `llm/prompt_template.py` — `{{variable}}` 模板替换

**数据层：**
- `models/` — 13 个 SQLAlchemy 异步模型
- `schemas/` — Pydantic 请求/响应 schema，统一 `Result[T]` 信封
- Alembic 迁移管理数据库版本

### 前端结构 (`frontend/src/`)

- `components/FlowCanvas.tsx` — ReactFlow 画布
- `components/NodePanel.tsx` — 可拖拽节点面板
- `components/DebugDrawer.tsx` — 实时调试面板 (SSE)
- `pages/EditorPage.tsx` — 主编辑器页
- `store/workflowStore.ts` — Zustand 状态管理
- `api/` — Axios API 客户端

## 工作流执行流程

1. 前端拖拽节点 → 序列化为 JSON → 保存到 `workflow.flow_data`
2. 执行时 EngineSelector 按 `engine_type` 路由到 DAG 或 LangGraph 引擎
3. DAG 引擎：拓扑排序 → 按序执行 → 上游输出作为下游输入 → 记录快照
4. LangGraph 引擎：构建 StateGraph → 异步调用 NodeAdapter → 汇总结果
5. SSE 实时推送 `NODE_START/NODE_SUCCESS/NODE_ERROR/WORKFLOW_COMPLETE` 事件

## 认证

- JWT Bearer token，access token 120 分钟，refresh token (Redis) 168 小时
- 默认账户 `admin / admin123`（bcrypt 哈希存储）
- 未认证路径: `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/node-types`, `/health`
- 登录限流: 5 次/分钟/IP（Redis 滑动窗口）

## API 响应格式

```json
{ "code": 200, "message": "操作成功", "data": { ... } }
```

- code=200 成功，500 服务器错误，401 未认证
