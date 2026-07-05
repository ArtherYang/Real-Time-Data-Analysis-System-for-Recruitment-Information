# 系统架构设计文档 — 招聘信息实时数据分析系统

| 文档编号 | ARCH-RDAS-001 | 版本 | 1.0 |
|---------|-------------|------|-----|
| 项目名称 | 招聘信息实时数据分析系统 | 拟制 | 杨昱晨 |
| 日期 | 2026-07-02 | 状态 | AI 生成，待人工审查 |

---

## 1 概述

本文档描述招聘信息实时数据分析系统（RDAS）的整体架构设计，包括分层架构、模块职责、模块交互和部署拓扑。

---

## 2 分层架构

系统采用**五层架构**，遵循单向依赖原则（上层依赖下层，下层对上层无感知）：

```
┌─────────────────────────────────────────────────────────┐
│                    展示层（Presentation）                 │
│  Vue 3 + Vite + Element Plus + ECharts                 │
│  看板大屏 | 岗位检索 | 薪资分析 | 城市分布 | 技能分析      │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP REST + JSON
┌────────────────────────▼────────────────────────────────┐
│                   接口层（API Gateway）                   │
│  Flask Blueprint (/api/v1)                              │
│  路由注册 | 请求校验 | JWT 鉴权 | 限流 | CORS             │
│  /jobs/* | /analysis/* | /auth/* | /export/*            │
└────────────────────────┬────────────────────────────────┘
                         │ Python 函数调用
┌────────────────────────▼────────────────────────────────┐
│                  业务逻辑层（Service）                     │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────────┐ │
│  │ Crawler    │ │ Processor  │ │ Analysis Engine      │ │
│  │ 多平台采集  │ │ 清洗标准化  │ │ 薪资/区域/技能/排名    │ │
│  └────────────┘ └────────────┘ └──────────────────────┘ │
│  ┌────────────┐ ┌────────────┐                          │
│  │ Auth       │ │ Export     │                          │
│  │ 注册登录JWT │ │ CSV/Excel  │                          │
│  └────────────┘ └────────────┘                          │
└────────────────────────┬────────────────────────────────┘
                         │ SQLAlchemy ORM / redis-py
┌────────────────────────▼────────────────────────────────┐
│                   数据层（Data）                          │
│  ┌──────────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ MySQL 8.0        │  │ Redis    │  │ File System   │  │
│  │ 业务数据 + 日志   │  │ 缓存+MQ  │  │ Mock JSON     │  │
│  └──────────────────┘  └──────────┘  └──────────────┘  │
└────────────────────────┬────────────────────────────────┐
                         │ Docker 容器运行时
┌────────────────────────▼────────────────────────────────┐
│                 基础设施层（Infrastructure）               │
│  Docker Compose | Nginx 反向代理 | CI/CD (预留)          │
│  健康检查 | 日志收集 | 监控告警 (预留)                    │
└─────────────────────────────────────────────────────────┘
```

---

## 3 模块职责说明

### 3.1 展示层 — Vue 3 前端

| 模块 | 路径 | 职责 |
|------|------|------|
| Dashboard | `views/Dashboard.vue` | KPI 卡片、热门岗位榜、薪资趋势 |
| SalaryAnalysis | `views/SalaryAnalysis.vue` | 薪资分布图、经验-薪资矩阵 |
| CityAnalysis | `views/CityAnalysis.vue` | 城市岗位分布、热力图 |
| SkillAnalysis | `views/SkillAnalysis.vue` | 技能词云、技能共现分析 |
| Components | `components/` | SummaryCards, SalaryDistChart, SkillWordCloud, FilterPanel 等可复用组件 |
| Store | `stores/analysis.js` | Pinia 状态管理，缓存分析数据 |
| Router | `router/index.js` | Vue Router 路由配置（History 模式） |
| API Client | `api/index.js` | axios 封装，统一错误处理 |

### 3.2 接口层 — Flask API

| 模块 | 路径 | 端点前缀 | 职责 |
|------|------|---------|------|
| Jobs | `api/jobs.py` | `/api/v1/jobs` | 岗位 CRUD、列表查询、关键词搜索、筛选过滤 |
| Analysis | `api/analysis.py` | `/api/v1/analysis` | 热门岗位、薪资分布、城市分析、技能分析 |
| Auth | `api/auth.py` | `/api/v1/auth` | 注册、登录、个人信息 |
| Export | `api/export.py` | `/api/v1/export` | CSV/Excel 数据导出 |
| Health | `app.py` | `/health` | 健康检查端点 |

**统一规范：**
- 请求格式：JSON（POST/PUT）/ Query String（GET）
- 响应格式：`{ "code": 200, "data": {...}, "message": "ok" }`
- 错误格式：`{ "code": 4xx/5xx, "data": null, "message": "错误描述" }`
- 分页参数：`page`（默认 1）、`page_size`（默认 20，最大 100）

### 3.3 业务逻辑层

#### 3.3.1 数据采集（Crawler）

| 模块 | 路径 | 职责 |
|------|------|------|
| BaseCrawler | `crawler/base.py` | 抽象基类：定义 `crawl()` / `parse()` / `validate()` 接口、频率控制、JobRawData 数据结构 |
| BossCrawler | `crawler/boss.py` | BOSS 直聘爬虫实现（关键词搜索 + 分页 + API 解析） |
| AntiCrawl | `crawler/anti_crawl.py` | 反爬工具：UA 池轮换、Proxy 管理、Cookie 持久化、请求延迟 |

**数据流：**
```
平台 API/页面 → BossCrawler.crawl(keyword, pages)
  → requests.get(url, headers=UA.random, proxy=proxy_pool.get())
  → parse(html) → List[JobRawData]
  → validate(JobRawData) → 有效数据
  → pipeline.process(jobs) → 清洗后存入 MySQL
```

#### 3.3.2 数据处理（Processor）

| 模块 | 路径 | 职责 |
|------|------|------|
| Cleaner | `processor/cleaner.py` | HTML 标签移除、特殊字符清洗、空白规范化 |
| Normalizer | `processor/normalizer.py` | 公司名标准化、城市名标准化、薪资格式统一、枚举值映射 |
| Pipeline | `processor/pipeline.py` | 处理流水线：去重（精确+模糊）→ 清洗 → 标准化 → 脱敏 → 入库 |

#### 3.3.3 分析引擎（Analysis）

| 模块 | 路径 | 职责 |
|------|------|------|
| Engine | `analysis/engine.py` | 分析引擎入口：参数校验、缓存判断、计算分发 |
| Salary | `analysis/salary.py` | 薪资统计：均值/中位数/分位数、分城市/行业/经验维度 |
| Regional | `analysis/regional.py` | 区域分析：城市分布、CR5 集中度、省聚合 |
| Skills | `analysis/skills.py` | 技能分析：TF-IDF 提取、词频统计、共现分析、词云数据 |
| Ranking | `analysis/ranking.py` | 热度排名：基于浏览量/投递量/发布时间加权 |
| Filters | `analysis/filters.py` | 筛选维度：城市/薪资/行业/经验/学历多条件组合 |
| Cache | `analysis/cache.py` | 分析结果缓存：Redis 读写、参数哈希、TTL 过期 |

#### 3.3.4 用户认证（Auth）

| 模块 | 路径 | 职责 |
|------|------|------|
| Auth Utils | `utils/auth.py` | JWT 生成/验证、密码加密/校验、Token 刷新 |

**认证流程：**
```
注册: POST /api/v1/auth/register { email, password, nickname }
  → bcrypt(password) → 存储 password_hash → 返回 JWT token

登录: POST /api/v1/auth/login { email, password }
  → 校验 bcrypt → 检查 login_attempts → 生成 JWT → 返回 token

鉴权: 请求头 Authorization: Bearer <token>
  → Flask before_request hook → jwt.decode(token) → request.current_user
```

### 3.4 数据层

| 组件 | 版本 | 用途 | 数据内容 |
|------|------|------|---------|
| MySQL | 8.0 | 主业务库 | jobs, users, companies, crawl_logs, analysis_cache, user_favorites |
| Redis | 7.x | 缓存 + 消息队列 | 分析结果缓存（TTL 1h）、Celery 任务队列、登录失败计数 |
| File System | — | 开发/测试数据 | `data/mock_data.json`（50+ 模拟岗位用于前端联调） |

### 3.5 基础设施层

| 组件 | 用途 |
|------|------|
| Nginx | 反向代理：前端静态资源 + API 代理，端口 80 |
| Docker Compose | 服务编排：api + nginx + mysql + redis 四个容器 |
| Gunicorn | 生产环境 WSGI 服务器（开发环境使用 Flask 内置服务器） |

---

## 4 模块交互流程

### 4.1 数据采集 → 展示全链路

```
                    ┌──────────┐
                    │ 定时触发  │ (Celery Beat / 手动)
                    └────┬─────┘
                         │
  1. 发起采集请求        ▼
  BossCrawler ──────► Boss直聘 API ──► List<JobRawData>
                         │
  2. 数据清洗            ▼
  Pipeline.process() ─► Cleaner → Normalizer → Dedup → Validate
                         │
  3. 数据入库            ▼
  SQLAlchemy ────────► MySQL jobs 表
                         │
  4. 缓存预热（可选）     ▼
  Analysis Engine ───► Redis (1h TTL)
                         │
  5. 用户请求            ▼
  Vue 前端 ──► Flask API (/api/v1/jobs) ──► MySQL/Redis ──► JSON ──► ECharts
```

### 4.2 API 请求处理流程（以岗位列表为例）

```
GET /api/v1/jobs?page=1&page_size=20&city=北京&keyword=Python

  1. Nginx → Flask route → JobsAPI.get_jobs()
  2. 参数校验 (page_size ≤ MAX_PAGE_SIZE)
  3. 构建 SQLAlchemy Query:
     - city='北京' → WHERE city = '北京'
     - keyword='Python' → WHERE title LIKE '%Python%' OR skills LIKE '%Python%'
     - page=1, page_size=20 → LIMIT 20 OFFSET 0
  4. 执行查询 → List[Job]
  5. 序列化 → jsonify([job.to_dict() for job in jobs])
  6. 统一响应格式 → { "code": 200, "data": { "items": [...], "total": 150, "page": 1, "page_size": 20 } }
```

### 4.3 分析查询流程（带缓存）

```
GET /api/v1/analysis/salary?city=北京&category=技术

  1. Flask route → AnalysisAPI → AnalysisEngine.query()
  2. 计算参数哈希: SHA-256("salary:北京:技术")
  3. 查 Redis 缓存:
     - 命中 → 返回缓存 JSON
     - 未命中 → 执行 SQL 聚合查询 → 计算结果 → 写入 Redis(1h TTL) → 返回
  4. 返回统一格式 JSON
```

---

## 5 部署拓扑

### 5.1 开发环境（Docker Compose）

```
┌──────────────────────────────────────────────────┐
│                    Docker Host                     │
│  ┌────────────────┐  ┌──────────────────┐        │
│  │ nginx:80       │  │ api:5000          │        │
│  │ (反向代理)      │──│ (Flask + Gunicorn)│        │
│  │ 静态资源 /      │  │ 业务逻辑           │        │
│  │ API 代理 /api   │  │ 数据访问           │        │
│  └────────────────┘  └──────┬────┬──────┘        │
│                             │    │               │
│              ┌──────────────┘    └──────────┐    │
│              ▼                              ▼    │
│  ┌──────────────────┐    ┌──────────────────┐   │
│  │ mysql:3306        │    │ redis:6379        │   │
│  │ (MySQL 8.0)       │    │ (Redis 7.x)       │   │
│  │ 数据卷: ./db/data │    │ 缓存 + 消息队列    │   │
│  └──────────────────┘    └──────────────────┘   │
└──────────────────────────────────────────────────┘
```

### 5.2 网络与端口映射

| 服务 | 容器端口 | 宿主机端口 | 说明 |
|------|---------|-----------|------|
| Nginx | 80 | 8080 | 统一入口 |
| Flask API | 5000 | 5000 | 后端服务（调试用） |
| MySQL | 3306 | 3307 | 数据库 |
| Redis | 6379 | 6380 | 缓存 |

---

## 6 非功能需求实现设计

| 需求 | 目标值 | 实现方式 |
|------|--------|---------|
| 接口响应时间 | P99 < 200ms | Redis 缓存 + MySQL 索引优化 + 分页限制 |
| 并发 QPS | > 500 | Gunicorn 多 Worker + Nginx 连接池 + 数据库连接池 |
| 数据采集延迟 | < 5min | Celery 定时调度（后续启用） |
| 系统可用性 | 99.9% | 健康检查端点 + Docker 自动重启 |
| 数据安全 | 密码 bcrypt + HTTPS + JWT | `utils/auth.py` 实现 |

---

> *文档版本：v1.0 | 最后更新：2026-07-02 | 状态：AI 生成，待人工审查*
