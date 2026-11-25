# TaskFlow — Next.js + FastAPI + PostgreSQL + Redis Demo

一个面向全栈工程实践的任务协作看板（Kanban）Demo，完整展示 **Next.js (App Router)**、**FastAPI (Async)**、**PostgreSQL (ACID 事务 & 乐观锁)** 与 **Redis (旁路缓存、分布式锁、限流)** 的协作方式。

## 架构要点

1. **Next.js 15 (`frontend/`)**
   - TypeScript + Tailwind CSS 看板界面，支持拖拽 / 快捷按钮移动任务。
   - 顶部实时遥测栏展示 PostgreSQL / Redis 健康状态与延迟、`X-Cache: HIT | MISS` 命中状态、剩余限流额度，并提供一键清空 Redis 缓存按钮。
   - 右侧展示 PostgreSQL 事务写入的审计日志。

2. **FastAPI (`backend/`)**
   - **PostgreSQL + SQLAlchemy 2.0 Async (`asyncpg`)**：所有任务创建、移动、编辑、删除操作与 `task_activities` 审计日志在同一事务中原子提交；支持 `version` 字段乐观锁校验。
   - **Redis (`redis.asyncio`)**：
     - **Read-Through 缓存**：`GET /api/boards/{id}/tasks` 缓存看板任务与统计，写操作自动失效缓存，并通过 `X-Cache: HIT | MISS` 响应头反馈给前端。
     - **分布式锁**：`POST /api/tasks/{id}/move` 使用 `SET key token NX PX` 加锁，并通过 Lua 脚本原子校验 token 解锁，避免并发重排竞态。
     - **固定窗口限流**：使用 `INCR` + `EXPIRE` 限制单客户端请求频率，返回 `X-RateLimit-Limit` / `X-RateLimit-Remaining` 及 `429 Too Many Requests`。

## 快速启动

### 方式一：Docker Compose 一键启动全部服务

```bash
cp .env.example .env
docker compose up --build
```

启动后访问：
- 前端看板：http://localhost:3000
- 后端 API 文档 (Swagger)：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

### 方式二：仅用 Docker 启动数据库，本地运行前后端

```bash
docker compose up -d postgres redis

# 终端 1：启动 FastAPI
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# 终端 2：启动 Next.js
cd frontend
npm install
npm run dev
```

## 运行测试与构建验证

```bash
# 后端单元测试（使用内存 SQLite + FakeRedis 验证事务、缓存、分布式锁与限流）
cd backend
.venv/bin/pytest -v

# 前端类型检查与生产构建
cd frontend
npx tsc --noEmit
npm run build
```
