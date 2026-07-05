# 职言（ZhiYan）系统设计文档 V1.0

---

| 文档编号 | SD-ZPXT-001 | 版本 | 1.0 |
|---------|-------------|------|-----|
| 项目名称 | 职言 — 求职者一站式平台 | 密级 | 内部 |
| 拟制 | 杨昱晨 | 日期 | 2026-07-04 |
| 评审人 | 马老师 | 日期 | |
| 批准 | 王老师 | 日期 | |

---

## Revision Record（修订记录）

| 日期 | 修订版本 | 修改章节 | 修改描述 | 作者 |
|------|---------|---------|---------|------|
| 2026-07-04 | 1.0 | All | 初始版本，基于需求规格说明书完成系统设计 | 杨昱晨 |

---

## 1 引言

### 1.1 项目背景

当下招聘市场存在显著的信息不对称问题：求职者不清楚市场薪资行情，投递简历时缺乏数据参考；同时简历制作耗时费力，格式与内容往往不专业。

**「职言」**定位为求职者一站式平台，提供两大核心能力：

1. **市场行情仪表盘**：基于真实采集的招聘数据，实时展示岗位薪资分布、城市热度、技能需求，帮助求职者"看清市场全貌"
2. **简历生成助手**：三步引导式简历创建——用户填写个人信息 + 选择模板 → 一键生成 PDF 简历，帮助求职者"从容应对面试"

### 1.2 项目目标

| 目标 | 指标 | 验证方式 |
|------|------|---------|
| 数据采集 | 覆盖 30 个城市、6 个岗位大类、≥ 200 条真实数据 | 数据库查询计数 |
| 可视化分析 | 薪资趋势、城市分布、技能词云 3 类核心图表 | 仪表盘页面截图 |
| 简历闭环 | 注册 → 填写资料 → 选模板 → 生成简历 → 下载 PDF | 端到端测试 |
| 部署 | Docker Compose 一键启动，5 个容器协同工作 | `docker-compose up -d` 验证 |

### 1.3 项目范围

#### 包含（MVP）

| 模块 | 功能点 |
|------|--------|
| 数据采集 | 51job + BOSS直聘双平台采集、去重清洗管道 |
| 仪表盘 | 概览卡片、岗位热度 TOP10、薪资趋势折线图、城市热力图、技能词云 |
| 岗位浏览 | 关键词搜索、城市/薪资/经验/学历筛选、详情展示 |
| 用户系统 | 邮箱注册登录、JWT 认证、个人信息管理 |
| 简历引擎 | 3 套模板可选、在线实时预览、PDF 下载 |

#### 不包含（二期）

- ML 薪资预测模型
- 第三个数据采集渠道（智联招聘/拉勾）
- 移动端 APP
- 在线投递功能
- 公司评价系统（评分 + 标签 + 评价 CRUD）

---

## 2 系统架构设计

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────┐
│                       前端层 (Vue 3 + Vite)                    │
│                                                                │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐    │
│  │ Dashboard│ 岗位浏览  │ 引导注册  │ 简历预览  │  登录    │    │
│  │  首页    │          │          │          │         │    │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘    │
│           Element Plus UI  │  ECharts 5  │  Axios             │
└────────────────────┬─────────────────────────────────────────┘
                     │  HTTPS / RESTful API
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                     API 网关 (Nginx :80)                       │
│         /api/* → fastapi:8000     / → vue-frontend:5173       │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                    业务层 (FastAPI + Uvicorn :8000)            │
│                                                                │
│  ┌──────────┬──────────┬──────────┬──────────────┐           │
│  │ 仪表盘   │   岗位   │   用户   │   简历引擎    │           │
│  │ 模块     │   模块   │   模块   │              │           │
│  │          │          │          │              │           │
│  │·概览API  │·搜索API  │·注册登录 │·模板管理     │           │
│  │·排行API  │·筛选API  │·JWT鉴权  │·填充生成     │           │
│  │·趋势API  │·详情API  │·资料管理 │·PDF导出      │           │
│  │·分布API  │          │          │              │           │
│  └─────┬────┴─────┬────┴────┬─────┴──────┬───────┘           │
│        │          │         │            │                    │
│        └──────────┴─────────┴────────────┘                    │
│                   SQLAlchemy 2.0 ORM                          │
└────────────────────┬─────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│  MySQL 8.0      │    │  Redis 7        │
│  (业务数据)      │    │  (缓存/会话)     │
│  :3306          │    │  :6379          │
│                 │    │                 │
│  ·jobs          │    │  ·热点缓存      │
│  ·users         │    │  ·Celery代理    │
│  ·companies     │    │  ·Session存储   │
│  ·resumes       │    │  ·限流计数器    │
│  ·templates     │    │                 │
└─────────────────┘    └─────────────────┘
         ▲
         │  原始 JSON 数据写入
         │
┌──────────────────────────────────────────────────────────────┐
│                      采集层 (Celery Worker)                    │
│                                                                │
│  ┌──────────────────────┐    ┌──────────────────────┐        │
│  │  51job API Crawler   │    │  BOSS直聘 API Crawler│        │
│  │  we.51job.com/api    │    │  zhipin.com/wapi     │        │
│  └──────────┬───────────┘    └──────────┬───────────┘        │
│             └──────────┬───────────────┘                     │
│                        ▼                                      │
│              ┌──────────────────┐                            │
│              │  数据清洗管道     │                            │
│              │  去重 → 标准化   │                            │
│              └──────────────────┘                            │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈选型

| 层级 | 技术 | 版本 | 选型理由 |
|------|------|------|---------|
| 前端框架 | Vue 3 + Vite | 3.x | 生态丰富，Element Plus 组件库成熟，Vite 构建快 |
| UI 组件库 | Element Plus | 2.x | 中文文档完善，表单/表格/弹窗组件开箱即用 |
| 可视化 | ECharts | 5.x | 免费开源，中文文档，中国地图内置，60+ 图表类型，均优于 Highcharts |
| 后端框架 | FastAPI | 0.115+ | 替代 Flask，自动生成 Swagger 文档，异步支持更好，类型提示 |
| ORM | SQLAlchemy | 2.0 | Python 生态标准，支持异步，迁移工具成熟 |
| 数据库 | MySQL | 8.0 | 教材基础要求，FULLTEXT + ngram 分词器支持中文全文搜索 |
| 缓存 | Redis | 7.x | 高性能内存数据库，同时作为 Celery 消息代理，零额外部署 |
| 任务队列 | Celery + Redis | 5.x | 轻量级异步任务，Redis 复用作为 Broker，无需 Kafka |
| 搜索引擎 | MySQL FULLTEXT + ngram | — | 免费升级方案，替代 Elasticsearch（太重），10 分钟部署，中文搜索效果好 |
| 认证 | python-jose (JWT) | 3.x | 无状态鉴权，前后端分离友好，刷新令牌机制 |
| 密码加密 | bcrypt | 4.x | 行业标准，加盐哈希，抗暴力破解 |
| 数据处理 | pandas | 2.x | 5000 条数据秒级处理，无需引入 Flink（杀鸡用牛刀） |
| 简历PDF | WeasyPrint / python-docx | — | HTML→PDF 转换，支持中文，模板灵活 |
| 容器化 | Docker Compose | v2 | 单机完美适配，一键启动 5 个服务，K8s 对小项目过度 |
| Web 服务器 | Nginx | 1.27 | 静态文件服务 + API 反向代理 + SSL 终端 |

#### 关键决策说明

| 决策项 | 维持/升级 | 理由 |
|--------|----------|------|
| 流式计算 | ✅ 维持 pandas | 日采集 5000 条，pandas 秒级处理，Flink 过度 |
| 时序数据库 | ✅ 维持 MySQL | 30 天数据量，索引优化即可，InfluxDB 多余 |
| 搜索引擎 | ⚡ MySQL FULLTEXT | 免费升级，中文搜索效果从 0 到 70 分 |
| 第三采集渠道 | ⏸️ 延后 | 先稳住 2 平台，7.08 前有时间再加 |
| 消息队列 | ✅ 维持 Celery+Redis | Redis 复用作为 Broker，零额外成本 |
| 可视化库 | ✅ 维持 ECharts 5 | 免费+中文+中国地图，优于 Highcharts |
| 容器编排 | ✅ 维持 Docker Compose | K8s 吃 2GB 内存，学生服务器总共 4GB |
| ML 预测模型 | ⏸️ 延后 | 7.09 系统跑通就加 Prophet，来不及写进二期计划 |

### 2.3 模块划分

| 模块 | 职责 | 核心文件 | 优先级 |
|------|------|---------|--------|
| 仪表盘模块 | 概览统计、热度排行、薪资趋势、城市分布、技能词云 | `api/dashboard.py` | P0 |
| 岗位模块 | 关键词搜索、多维筛选、详情展示 | `api/jobs.py` | P0 |
| 用户模块 | 注册、登录、JWT 鉴权、个人资料管理 | `api/auth.py`, `api/user.py` | P0 |
| 简历引擎 | 模板管理、简历数据填充、PDF 导出、在线预览 | `api/resumes.py` | P0 |
| 采集模块 | 51job + BOSS 爬虫、去重清洗管道 | `crawler/job51.py`, `crawler/boss.py` | P0 |
| 通用模块 | 中间件（JWT/CORS/限流）、配置管理、日志 | `app/middleware.py`, `app/config.py` | P1 |

---

## 3 数据库设计

### 3.1 数据库 ER 图

> 完整 ER 图 PlantUML 源码见 `docs/design/database_er.puml`，DDL 建表脚本见 `scripts/init_database.sql`。

#### 实体关系概要

```
users ──1:1── user_profiles ──1:1── user_preferences
  │
  └──1:N── resumes ──N:1── resume_templates

jobs ──N:1── companies

crawl_logs (独立记录)
analysis_cache (独立缓存)
```

### 3.2 核心表结构

#### 3.2.1 岗位数据表 (jobs) — 原有

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| job_id | VARCHAR(32) | PK | 岗位唯一标识 (MD5) |
| title | VARCHAR(200) | NOT NULL, FULLTEXT INDEX | 岗位名称（标准化后） |
| title_raw | VARCHAR(200) | | 岗位名称（原始） |
| company_id | VARCHAR(32) | FK → companies | 公司唯一标识 |
| company | VARCHAR(200) | NOT NULL | 公司名称（冗余，搜索性能） |
| salary_min | INT | INDEX | 最低月薪（元） |
| salary_max | INT | | 最高月薪（元） |
| salary_type | ENUM('月薪','年薪','日薪','面议') | NOT NULL | 薪资类型 |
| city | VARCHAR(50) | INDEX | 工作城市（标准化） |
| district | VARCHAR(100) | | 区/县 |
| experience | ENUM('应届生','1-3年','3-5年','5-10年','10年以上','不限') | NOT NULL | 经验要求 |
| education | ENUM('不限','大专','本科','硕士','博士') | NOT NULL | 学历要求 |
| description | TEXT | FULLTEXT INDEX | 岗位描述原文 |
| skills | VARCHAR(500) | | 技能标签（逗号分隔） |
| industry | VARCHAR(50) | | 所属行业 |
| job_category | VARCHAR(50) | | 岗位大类 |
| platform | ENUM('boss_zhipin','job51','zhilian') | NOT NULL, INDEX | 数据来源 |
| platform_job_id | VARCHAR(100) | UNIQUE INDEX | 平台原始职位ID |
| source_url | VARCHAR(500) | | 原始详情URL |
| published_at | DATE | INDEX | 发布日期 |
| crawled_at | DATETIME | NOT NULL | 采集时间 |
| status | ENUM('有效','已过期','已删除') | DEFAULT '有效' | 状态 |

**索引设计**：
```sql
-- 主键
PRIMARY KEY (job_id)

-- 全文搜索（中文）
ALTER TABLE jobs ADD FULLTEXT INDEX ft_title_desc (title, description) WITH PARSER ngram;

-- 组合索引（高频查询优化）
CREATE INDEX idx_city_salary ON jobs(city, salary_min);
CREATE INDEX idx_published ON jobs(published_at, job_category);
CREATE INDEX idx_platform ON jobs(platform, platform_job_id);
CREATE INDEX idx_category_city ON jobs(job_category, city);
```

#### 3.2.2 用户账号表 (users) — 原有

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| user_id | VARCHAR(32) | PK | UUID 主键 |
| email | VARCHAR(100) | UNIQUE, NOT NULL | 邮箱（登录账号） |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt 密码哈希 |
| nickname | VARCHAR(50) | NOT NULL | 用户昵称 |
| role | ENUM('普通用户','企业HR','管理员') | DEFAULT '普通用户' | 角色 |
| is_active | BOOLEAN | DEFAULT TRUE | 账号是否激活 |
| login_attempts | INT | DEFAULT 0 | 登录失败次数 |
| locked_until | DATETIME | | 账号锁定截止时间 |
| last_login | DATETIME | | 最后登录时间 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 注册时间 |

#### 3.2.3 公司信息表 (companies) — 原有

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| company_id | VARCHAR(32) | PK | 公司唯一标识 |
| name | VARCHAR(200) | NOT NULL, INDEX | 公司名称 |
| size | VARCHAR(50) | | 公司规模 |
| type | VARCHAR(50) | | 公司类型（民营/国企/外企/上市） |
| industry | VARCHAR(50) | | 所属行业 |
| city | VARCHAR(50) | | 总部城市 |
| description | TEXT | | 公司简介 |

#### 3.2.4 用户扩展信息表 (user_profiles) — 新增

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| profile_id | VARCHAR(32) | PK | UUID 主键 |
| user_id | VARCHAR(32) | FK → users, UNIQUE | 关联用户 |
| real_name | VARCHAR(50) | | 真实姓名 |
| age | INT | | 年龄 |
| gender | ENUM('男','女','保密') | DEFAULT '保密' | 性别 |
| university | VARCHAR(100) | | 毕业院校 |
| major | VARCHAR(100) | | 专业 |
| degree | ENUM('大专','本科','硕士','博士','其他') | | 最高学历 |
| graduation_year | INT | | 毕业年份 |
| city | VARCHAR(50) | | 所在城市 |
| phone | VARCHAR(20) | | 手机号 |
| avatar_url | VARCHAR(500) | | 头像URL |
| updated_at | DATETIME | ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

#### 3.2.5 求职意向表 (user_preferences) — 新增

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| pref_id | VARCHAR(32) | PK | UUID 主键 |
| user_id | VARCHAR(32) | FK → users, UNIQUE | 关联用户 |
| desired_position | VARCHAR(200) | | 意向岗位 |
| desired_city | VARCHAR(50) | | 意向城市 |
| desired_salary_min | INT | | 期望最低薪资 |
| desired_salary_max | INT | | 期望最高薪资 |
| job_type | VARCHAR(50) | | 工作类型偏好 |
| industry | VARCHAR(50) | | 行业偏好 |
| updated_at | DATETIME | ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

#### 3.2.6 简历主表 (resumes) — 新增

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| resume_id | VARCHAR(32) | PK | UUID 主键 |
| user_id | VARCHAR(32) | FK → users | 关联用户 |
| template_id | VARCHAR(32) | FK → resume_templates | 使用的模板 |
| title | VARCHAR(100) | | 简历标题（如"Python开发工程师简历"） |
| full_name | VARCHAR(50) | NOT NULL | 姓名 |
| university | VARCHAR(100) | | 毕业院校 |
| major | VARCHAR(100) | | 专业 |
| degree | VARCHAR(20) | | 学历 |
| graduation_year | INT | | 毕业年份 |
| phone | VARCHAR(20) | | 联系电话 |
| email | VARCHAR(100) | | 联系邮箱 |
| skills_text | TEXT | | 技能描述 |
| self_intro | TEXT | | 自我介绍 |
| experience_json | JSON | | 工作/项目经历（结构化存储） |
| education_json | JSON | | 教育经历（结构化存储） |
| pdf_path | VARCHAR(500) | | 生成的PDF文件路径 |
| status | ENUM('草稿','已完成') | DEFAULT '草稿' | 状态 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

#### 3.2.7 简历模板表 (resume_templates) — 新增

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| template_id | VARCHAR(32) | PK | 模板唯一标识 |
| name | VARCHAR(50) | NOT NULL | 模板名称（如"简洁蓝"、"专业灰"） |
| description | VARCHAR(200) | | 模板描述 |
| preview_url | VARCHAR(500) | | 预览图URL |
| css_styles | TEXT | | 模板CSS样式 |
| html_layout | TEXT | NOT NULL | 模板HTML骨架 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否启用 |
| sort_order | INT | DEFAULT 0 | 排序权重 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

#### 3.2.8 采集日志表 (crawl_logs)

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| log_id | BIGINT | PK, AUTO_INCREMENT | 日志ID |
| platform | VARCHAR(50) | NOT NULL | 采集平台 |
| keyword | VARCHAR(200) | | 搜索关键词 |
| total_crawled | INT | | 采集总数 |
| valid_count | INT | | 有效数据量 |
| failed_pages | INT | | 失败页数 |
| error_message | TEXT | | 错误信息 |
| started_at | DATETIME | NOT NULL | 开始时间 |
| finished_at | DATETIME | | 结束时间 |
| duration_seconds | INT | | 耗时（秒） |

#### 3.2.9 分析缓存表 (analysis_cache)

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| cache_id | VARCHAR(32) | PK | 缓存ID |
| cache_type | VARCHAR(50) | NOT NULL, INDEX | 缓存类型（overview/hot_jobs/salary_trend/city_distribution） |
| params_hash | VARCHAR(64) | NOT NULL | 查询参数MD5哈希 |
| result_data | JSON | NOT NULL | 分析结果数据 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 缓存创建时间 |
| expires_at | DATETIME | NOT NULL | 缓存过期时间（默认1小时后） |

---

## 4 接口设计

> 完整接口规范（Swagger 2.0 YAML）见 `docs/design/api_spec_swagger.yaml`。

### 4.1 接口总览

| 模块 | 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|------|
| 仪表盘 | GET | `/api/v1/dashboard/overview` | 市场概览（总数/新增/趋势） | 否 |
| 仪表盘 | GET | `/api/v1/dashboard/hot-jobs` | 岗位热度 TOP20 | 否 |
| 仪表盘 | GET | `/api/v1/dashboard/salary-trend` | 薪资趋势（支持城市/岗位过滤） | 否 |
| 仪表盘 | GET | `/api/v1/dashboard/city-distribution` | 城市岗位分布 | 否 |
| 仪表盘 | GET | `/api/v1/dashboard/skills-cloud` | 技能词云数据 | 否 |
| 岗位 | GET | `/api/v1/jobs/search` | 岗位搜索（关键词+多维筛选） | 否 |
| 岗位 | GET | `/api/v1/jobs/{job_id}` | 岗位详情 | 否 |
| 认证 | POST | `/api/v1/auth/register` | 用户注册 | 否 |
| 认证 | POST | `/api/v1/auth/login` | 用户登录 | 否 |
| 认证 | POST | `/api/v1/auth/refresh` | 刷新令牌 | 是 |
| 用户 | GET | `/api/v1/user/profile` | 获取个人资料+偏好 | 是 |
| 用户 | PUT | `/api/v1/user/profile` | 更新个人资料+偏好 | 是 |
| 简历 | GET | `/api/v1/resumes/templates` | 获取可用模板列表 | 否 |
| 简历 | POST | `/api/v1/resumes/generate` | 生成简历 | 是 |
| 简历 | GET | `/api/v1/resumes/{resume_id}` | 获取简历详情 | 是 |
| 简历 | GET | `/api/v1/resumes/{resume_id}/download` | 下载 PDF | 是 |
| 系统 | GET | `/api/v1/health` | 健康检查 | 否 |

### 4.2 认证方案

```
用户登录 → 服务端返回:
  {
    "access_token": "eyJ...",    // JWT，有效期 30 分钟
    "refresh_token": "eyJ...",   // JWT，有效期 7 天
    "token_type": "Bearer",
    "expires_in": 1800
  }

后续请求 → Header: Authorization: Bearer <access_token>
token 过期 → POST /auth/refresh → 用 refresh_token 换新 access_token
```

**JWT Payload 结构**：
```json
{
  "sub": "user_uuid",
  "email": "user@example.com",
  "role": "普通用户",
  "iat": 1720000000,
  "exp": 1720001800
}
```

### 4.3 统一响应格式

```json
{
  "code": 200,
  "message": "success",
  "data": { ... },
  "timestamp": "2026-07-04T12:00:00Z"
}
```

**错误码**：
| 状态码 | code | 说明 |
|--------|------|------|
| 200 | 200 | 成功 |
| 400 | 40001 | 参数校验失败 |
| 401 | 40101 | 未登录 / Token 过期 |
| 403 | 40301 | 权限不足 |
| 404 | 40401 | 资源不存在 |
| 429 | 42901 | 请求频率超限 |
| 500 | 50001 | 服务器内部错误 |

---

## 5 部署方案

### 5.1 Docker Compose 服务编排

| 服务名 | 镜像 | 端口 | 职责 |
|--------|------|------|------|
| mysql | mysql:8.0 | 3306 | 业务数据存储，启动时自动执行初始化脚本 |
| redis | redis:7-alpine | 6379 | 缓存 + Celery Broker + Session 存储 |
| fastapi | python:3.11-slim | 8000 | 业务逻辑 + API 服务 |
| celery-worker | 同 fastapi | — | 异步任务（数据采集、PDF 生成） |
| celery-beat | 同 fastapi | — | 定时任务调度（每日采集） |
| nginx | nginx:1.27-alpine | 80 | 前端静态文件 + API 反向代理 |

### 5.2 目录挂载

```
recruitment-analytics/
├── docker-compose.yml
├── .env.example
├── nginx/
│   └── nginx.conf          → /etc/nginx/nginx.conf
├── backend/                 → /app（挂载，支持热重载）
├── frontend/dist/           → /usr/share/nginx/html
├── scripts/
│   └── init_database.sql    → /docker-entrypoint-initdb.d/
├── data/                    → /app/data（持久化采集数据）
└── logs/                    → /app/logs（持久化日志）
```

### 5.3 一键启动

```bash
git clone <repo-url>
cd recruitment-analytics
cp .env.example .env
# 编辑 .env，修改数据库密码等配置
docker-compose up -d
# → 访问 http://localhost
```

---

## 6 安全设计

| 层级 | 威胁 | 防护措施 |
|------|------|---------|
| 传输层 | 中间人攻击 | 生产环境启用 HTTPS（Nginx SSL 终端 + Let's Encrypt） |
| 认证层 | 密码泄露 | bcrypt 哈希 + 加盐，原始密码不落盘 |
| 认证层 | Token 伪造 | JWT HMAC-SHA256 签名，密钥长度 ≥ 32 字节 |
| 认证层 | 暴力破解 | 5 次失败锁定 15 分钟，登录接口限流 |
| 应用层 | SQL 注入 | SQLAlchemy ORM 参数化查询，禁止拼接 SQL |
| 应用层 | XSS 跨站 | Vue 3 默认输出转义 + Content-Security-Policy 头 |
| 应用层 | CSRF | JWT Bearer Token（天然防 CSRF）+ SameSite Cookie |
| 应用层 | 越权访问 | 接口级 JWT 中间件校验 + 数据归属校验 |
| 应用层 | 接口滥用 | Redis 令牌桶限流（100 次/分钟/IP） |
| 数据层 | 敏感数据泄露 | 手机号前端掩码（138****1234），密码哈希存储 |
| 采集层 | IP 封禁 | User-Agent 轮换 + Cookie 池 + 请求间隔随机化 |
| 采集层 | 合规风险 | 遵循 robots.txt + 仅采集公开数据 + 仅用于学术研究 |

---

## 7 数据流设计

### 7.1 数据采集流

```
[Celery Beat 定时触发]
        │
        ▼
[Celery Worker: run_crawler.py]
        │
        ├──→ [51job API] → JSON response → parse → JobRawData
        │
        └──→ [BOSS直聘 API] → JSON response → parse → JobRawData
                    │
                    ▼
        [清洗管道: cleaner.py]
        ├── 去重（精确匹配 + 模糊匹配）
        ├── 字段标准化（城市/经验/学历）
        ├── 薪资格式化（统一为月薪元）
        └── 数据校验（必填字段检查）
                    │
                    ▼
        [SQLAlchemy bulk_insert → MySQL jobs / companies]
                    │
                    ▼
        [crawl_logs 记录采集日志]
```

### 7.2 用户简历流

```
[前端引导页]
  步骤1: 填写个人身份信息（姓名/学校/专业/毕业年份）
  步骤2: 填写求职意向（岗位/城市/期望薪资）
  步骤3: 选择简历模板
        │
        ▼
[POST /api/v1/resumes/generate]
        │
        ├──→ 保存 user_profiles 表
        ├──→ 保存 user_preferences 表
        └──→ 保存 resumes 表（关联模板ID）
                    │
                    ▼
[GET /api/v1/resumes/{id}]
        │
        └──→ 返回简历数据（含模板HTML+CSS）
                    │
                    ▼
[前端简历预览页]
  左侧：表单编辑 ←→ 右侧：实时预览
        │
        ▼
[GET /api/v1/resumes/{id}/download]
        │
        └──→ WeasyPrint: HTML → PDF → 返回文件流
```

### 7.3 仪表盘数据流

```
[用户请求 GET /api/v1/dashboard/overview]
        │
        ▼
[FastAPI Dashboard Router]
        │
        ├──→ 检查 Redis 缓存 (key: dashboard:overview)
        │      │
        │      ├── 命中 → 直接返回缓存数据（响应 < 50ms）
        │      │
        │      └── 未命中 ↓
        │
        ├──→ SELECT COUNT(*) FROM jobs WHERE status='有效'
        ├──→ SELECT COUNT(*) FROM jobs WHERE published_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        ├──→ SELECT job_category, COUNT(*) FROM jobs GROUP BY job_category ORDER BY cnt DESC LIMIT 20
        │
        └──→ 计算结果写入 Redis（TTL 1小时）→ 返回 JSON
```

---

## 8 关键技术难点与解决方案

| 难点 | 风险等级 | 解决方案 |
|------|---------|---------|
| 51job WAF 拦截 | 中 | 使用 JS 内部 API 直连（`we.51job.com/api/job/search-pc`），模拟浏览器请求头 |
| BOSS直聘 CloudFlare | 高 | Cookie 池轮换 + Selenium headless 兜底 + 降低请求频率 |
| 中文全文搜索 | 低 | MySQL 8.0 ngram 分词器，ALTER TABLE 加 FULLTEXT INDEX |
| PDF 中文渲染 | 中 | WeasyPrint + 中文字体（思源黑体），Docker 镜像预装字体包 |
| 跨平台薪资统一 | 中 | `salary_alter()` 方法处理 5 种薪资格式，统一转换为月薪（元） |
| 简历模板实时预览 | 低 | Vue 3 v-model 双向绑定 + 防抖（300ms）减少重渲染 |

---

## 9 项目结构

```
recruitment-analytics/
├── docker-compose.yml              # 一键启动脚本
├── .env.example                     # 环境变量模板
├── .gitignore
├── CLAUDE.md                        # 项目章程（AI行为规范）
├── README.md                        # 项目说明
│
├── docs/                            # 文档
│   ├── requirements/                # 需求文档
│   │   └── requirements_spec.md     # SRS 需求规格说明书
│   ├── design/                      # 设计文档
│   │   ├── system_design_v1.0.md    # 本文件
│   │   ├── database_er.puml         # ER图 PlantUML 源码
│   │   ├── api_spec_swagger.yaml    # API Swagger 规范
│   │   └── uml/                     # UML 图
│   └── test/                        # 测试文档
│
├── backend/                         # Python 后端
│   ├── requirements.txt
│   ├── run_crawler.py               # 独立爬虫脚本
│   ├── app/
│   │   ├── __init__.py              # Flask/FastAPI 应用工厂
│   │   ├── config.py                # 多环境配置
│   │   ├── middleware.py            # JWT/CORS/限流中间件
│   │   ├── api/                     # Web 接口
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py         # 仪表盘 API
│   │   │   ├── jobs.py              # 岗位 API
│   │   │   ├── auth.py              # 认证 API
│   │   │   ├── user.py              # 用户 API
│   │   │   └── resumes.py           # 简历 API
│   │   ├── crawler/                 # 爬虫模块
│   │   │   ├── base.py              # 爬虫基类 + JobRawData
│   │   │   ├── boss.py              # BOSS直聘爬虫
│   │   │   ├── job51.py             # 51job爬虫
│   │   │   └── anti_crawl.py        # 反爬工具
│   │   ├── processor/               # 数据处理
│   │   │   ├── cleaner.py           # 清洗去重
│   │   │   ├── normalizer.py        # 字段标准化
│   │   │   └── nlp_extractor.py     # NLP 关键词提取
│   │   ├── models/                  # 数据模型
│   │   │   ├── job.py
│   │   │   ├── user.py
│   │   │   ├── company.py
│   │   │   └── resume.py
│   │   └── services/                # 业务服务层
│   │       ├── dashboard_service.py
│   │       ├── resume_service.py
│   │       └── pdf_generator.py
│   └── tests/                       # 后端测试
│
├── frontend/                        # Vue.js 前端
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── router/                  # 路由
│       ├── store/                   # Pinia 状态管理
│       ├── api/                     # Axios API 封装
│       ├── views/                   # 页面
│       │   ├── Dashboard.vue        # 首页仪表盘
│       │   ├── JobSearch.vue        # 岗位浏览
│       │   ├── Onboarding.vue       # 引导注册（3步）
│       │   ├── ResumePreview.vue    # 简历预览
│       │   └── Login.vue            # 登录注册
│       └── components/              # 组件
│           ├── StatCard.vue         # 统计卡片
│           ├── JobCard.vue          # 岗位卡片
│           ├── CityHeatmap.vue      # 城市热力图
│           ├── SalaryTrend.vue      # 薪资趋势图
│           ├── SkillsCloud.vue      # 技能词云
│           └── ResumeForm.vue       # 简历表单
│
├── scripts/                         # 脚本
│   ├── init_database.sql            # DDL 建库建表
│   └── seed_data.py                 # 测试数据填充
│
├── data/                            # 数据文件
│   └── jobs_raw.json                # 采集原始数据
│
├── nginx/
│   └── nginx.conf                   # Nginx 配置
│
└── logs/                            # 日志目录
```

---

## 附录 A：技术选型对比记录

| 对比维度 | 方案 A（选用） | 方案 B（放弃） | 选择理由 |
|---------|-------------|-------------|---------|
| Web 框架 | FastAPI | Flask | 自动 Swagger、异步支持、类型提示 |
| 前端框架 | Vue 3 | React | 课程教学主流，Element Plus 中文友好 |
| 可视化 | ECharts 5 | Highcharts | 免费、中文文档、中国地图内置 |
| 搜索 | MySQL FULLTEXT | Elasticsearch | 零额外部署，10 分钟接入，中文搜索可接受 |
| 消息队列 | Celery + Redis | Kafka | 日任务量小（几十个），Celery 足够 |
| 容器编排 | Docker Compose | K8s | 单机部署，K8s 自身消耗 2GB 内存 |
| 数据分析 | pandas | Flink | 日 5000 条数据，pandas 秒级处理 |
| 时序存储 | MySQL | InfluxDB | 30 天数据，MySQL 索引够用 |
| AI 预测 | 延后（Prophet） | — | 7.09 有时间就加，来不及写进二期 |

---

## 附录 B：课程评分维度对齐

| 评分维度 | 对应章节 | 证据 |
|---------|---------|------|
| 需求完整性 | §1.1-1.3 项目背景/目标/范围 | SRS 文档 |
| 架构合理性 | §2.1-2.3 系统架构 | 本文档 |
| 数据库设计 | §3.1-3.2 ER图+表结构 | DDL 脚本 |
| 接口规范性 | §4.1-4.3 RESTful API | Swagger YAML |
| 部署可行性 | §5.1-5.3 Docker Compose | docker-compose.yml |
| 安全性 | §6 安全设计 | 本文档 |
| 文档完整性 | 附录 A/B | 本文档 |
| 过程控制 | AI 协作日志 | CLAUDE.md + ai_collaboration_log.md |

---

**— 文档结束 —**

*Copyright © 2026 职言 (ZhiYan). All rights reserved.*
