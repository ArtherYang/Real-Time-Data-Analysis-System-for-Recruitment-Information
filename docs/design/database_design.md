# 数据库设计文档 — 招聘信息实时数据分析系统

| 文档编号 | DB-RDAS-001 | 版本 | 1.0 |
|---------|------------|------|-----|
| 项目名称 | 招聘信息实时数据分析系统 | 拟制 | 杨昱晨 |
| 日期 | 2026-07-02 | 状态 | AI 生成，待人工审查 |

---

## 1 概述

本文档定义 RDAS 系统的完整数据库设计，包括 ER 图描述、表结构定义、字段说明、索引策略和枚举值映射。

**数据库**：MySQL 8.0 | **字符集**：utf8mb4 | **排序规则**：utf8mb4_unicode_ci

---

## 2 实体关系图（ER 图）

```
┌──────────────────────┐         ┌──────────────────────────┐
│       users          │         │         jobs             │
├──────────────────────┤         ├──────────────────────────┤
│ PK user_id (UUID)    │         │ PK job_id (UUID)         │
│     email (UNIQUE)   │         │     title                │
│     phone (UNIQUE)   │         │     title_raw            │
│     password_hash    │         │     company              │
│     nickname         │         │     salary_min           │
│     role (ENUM)      │         │     salary_max           │
│     avatar_url       │         │     salary_type (ENUM)   │
│     created_at       │         │     city                 │
│     last_login       │         │     district             │
│     is_active        │         │     experience (ENUM)    │
│     login_attempts   │         │     education (ENUM)     │
│     locked_until     │         │     description          │
└──────────┬───────────┘         │     skills               │
           │                     │     job_type             │
           │ 1:N                 │     recruit_number       │
           │                     │     industry             │
           ▼                     │     job_category         │
┌──────────────────────┐         │     company_size         │
│   user_favorites     │         │     company_type         │
├──────────────────────┤         │     welfare              │
│ PK favorite_id       │         │     platform (ENUM)      │
│ FK user_id ──────────┤         │     platform_job_id      │
│ FK job_id ───────────┤─────────┤     source_url           │
│     filter_condition │         │     published_at         │
│     created_at       │         │     crawled_at           │
└──────────────────────┘         │     status (ENUM)        │
                                 └──────────────────────────┘
                                            │
                                            │ 1:1 (弱关联，通过 company 名称)
                                            ▼
                                 ┌──────────────────────────┐
                                 │       companies          │
                                 ├──────────────────────────┤
                                 │ PK company_id (UUID)     │
                                 │     name (UNIQUE)        │
                                 │     size                 │
                                 │     company_type         │
                                 │     industry             │
                                 │     created_at           │
                                 └──────────────────────────┘

┌──────────────────────────┐    ┌──────────────────────────┐
│     crawl_logs           │    │     analysis_cache        │
├──────────────────────────┤    ├──────────────────────────┤
│ PK log_id (UUID)         │    │ PK cache_id (UUID)        │
│     platform             │    │     cache_type            │
│     task_type (ENUM)     │    │     params_hash           │
│     status (ENUM)        │    │     result_data (JSON)    │
│     keyword              │    │     created_at            │
│     total_count          │    │     expires_at            │
│     success_count        │    └──────────────────────────┘
│     fail_count           │
│     started_at           │
│     finished_at          │
│     error_msg            │
│     created_at           │
└──────────────────────────┘
```

### 表关系说明

| 关系 | 父表 | 子表 | 类型 | 说明 |
|------|------|------|------|------|
| users → user_favorites | users | user_favorites | 1:N | `user_id` 外键，级联删除 |
| jobs → user_favorites | jobs | user_favorites | 1:N | `job_id` 外键，级联删除 |
| companies → jobs | companies | jobs | 逻辑关联 | 通过 `name` 字段（公司名称）关联，非外键约束 |

> **设计决策**：`jobs.company` 使用公司名称字符串而非外键关联，因为采集的原始数据就是公司名，不需要在入库时额外查询 companies 表。`companies` 表作为公司信息补全的独立维度。

---

## 3 表结构定义

### 3.1 jobs — 岗位信息表（核心业务表）

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| job_id | VARCHAR(32) | PK | UUID | 岗位唯一标识（去连字符） |
| title | VARCHAR(200) | NOT NULL | — | 岗位名称（标准化后） |
| title_raw | VARCHAR(200) | NULL | NULL | 岗位名称（原始） |
| company | VARCHAR(200) | NOT NULL | — | 公司名称 |
| salary_min | INT | NULL | NULL | 最低月薪（元） |
| salary_max | INT | NULL | NULL | 最高月薪（元） |
| salary_type | ENUM | NOT NULL | '月薪' | 月薪/年薪/面议/时薪 |
| city | VARCHAR(50) | NOT NULL | — | 工作城市（地级市） |
| district | VARCHAR(100) | NULL | NULL | 区/县 |
| experience | ENUM | NOT NULL | '不限' | 经验要求 |
| education | ENUM | NOT NULL | '不限' | 学历要求 |
| description | TEXT | NULL | NULL | 岗位描述原文 |
| skills | VARCHAR(500) | NULL | NULL | 技能标签（逗号分隔） |
| job_type | VARCHAR(50) | NULL | NULL | 全职/兼职/实习 |
| recruit_number | VARCHAR(20) | NULL | NULL | 招聘人数 |
| industry | VARCHAR(100) | NULL | NULL | 所属行业 |
| job_category | VARCHAR(100) | NULL | NULL | 岗位大类 |
| company_size | VARCHAR(50) | NULL | NULL | 公司规模 |
| company_type | VARCHAR(50) | NULL | NULL | 公司类型 |
| welfare | VARCHAR(500) | NULL | NULL | 福利标签 |
| platform | ENUM | NOT NULL | — | 数据来源平台 |
| platform_job_id | VARCHAR(100) | NULL | NULL | 平台原始职位 ID |
| source_url | VARCHAR(500) | NULL | NULL | 职位详情页 URL |
| published_at | DATE | NULL | NULL | 岗位发布日期 |
| crawled_at | DATETIME | NOT NULL | NOW() | 系统采集时间 |
| status | ENUM | NOT NULL | '有效' | 有效/已过期/已删除 |

### 3.2 users — 用户表

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| user_id | VARCHAR(32) | PK | UUID | 用户唯一标识 |
| email | VARCHAR(100) | UNIQUE, NULL | NULL | 邮箱地址 |
| phone | VARCHAR(20) | UNIQUE, NULL | NULL | 手机号 |
| password_hash | VARCHAR(255) | NOT NULL | — | bcrypt 密码哈希 |
| nickname | VARCHAR(50) | NOT NULL | — | 用户昵称 |
| role | ENUM | NOT NULL | '普通用户' | 普通用户/企业HR/管理员 |
| avatar_url | VARCHAR(500) | NULL | NULL | 头像 URL |
| created_at | DATETIME | NOT NULL | NOW() | 注册时间 |
| last_login | DATETIME | NULL | NULL | 最后登录时间 |
| is_active | TINYINT(1) | NOT NULL | 1 | 账号是否启用 |
| login_attempts | TINYINT | NOT NULL | 0 | 连续登录失败次数 |
| locked_until | DATETIME | NULL | NULL | 账号锁定截止时间 |

### 3.3 companies — 公司信息表

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| company_id | VARCHAR(32) | PK | UUID | 公司唯一标识 |
| name | VARCHAR(200) | UNIQUE, NOT NULL | — | 公司名称 |
| size | VARCHAR(50) | NULL | NULL | 公司规模 |
| company_type | VARCHAR(50) | NULL | NULL | 民营/国企/外企/上市 |
| industry | VARCHAR(100) | NULL | NULL | 所属行业 |
| created_at | DATETIME | NOT NULL | NOW() | 记录创建时间 |

### 3.4 analysis_cache — 分析结果缓存表

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| cache_id | VARCHAR(32) | PK | UUID | 缓存唯一标识 |
| cache_type | VARCHAR(50) | NOT NULL | — | hot_jobs/salary_dist/city_dist/skill_analysis |
| params_hash | VARCHAR(64) | NOT NULL | — | 查询参数 SHA-256 哈希 |
| result_data | JSON | NOT NULL | — | 分析结果数据 |
| created_at | DATETIME | NOT NULL | NOW() | 缓存创建时间 |
| expires_at | DATETIME | NOT NULL | — | 缓存过期时间 |

### 3.5 crawl_logs — 采集日志表

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| log_id | VARCHAR(32) | PK | UUID | 日志唯一标识 |
| platform | VARCHAR(50) | NOT NULL | — | 采集平台 |
| task_type | ENUM | NOT NULL | '全量采集' | 全量采集/增量更新/手动触发 |
| status | ENUM | NOT NULL | '排队中' | 排队中/执行中/已完成/失败/已取消 |
| keyword | VARCHAR(100) | NULL | NULL | 搜索关键词 |
| total_count | INT | NOT NULL | 0 | 目标采集总数 |
| success_count | INT | NOT NULL | 0 | 成功采集数 |
| fail_count | INT | NOT NULL | 0 | 失败数 |
| started_at | DATETIME | NULL | NULL | 任务开始时间 |
| finished_at | DATETIME | NULL | NULL | 任务结束时间 |
| error_msg | TEXT | NULL | NULL | 错误信息 |
| created_at | DATETIME | NOT NULL | NOW() | 记录创建时间 |

### 3.6 user_favorites — 用户收藏表

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| favorite_id | VARCHAR(32) | PK | UUID | 收藏唯一标识 |
| user_id | VARCHAR(32) | FK → users | NOT NULL | 用户 ID |
| job_id | VARCHAR(32) | FK → jobs | NULL | 收藏的岗位 ID |
| filter_condition | JSON | NULL | NULL | 收藏的筛选条件 |
| created_at | DATETIME | NOT NULL | NOW() | 收藏时间 |

---

## 4 索引策略

### 4.1 jobs 表索引

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | job_id | 聚簇 | 主键查询 |
| idx_title | title | 普通 | 岗位名称搜索 |
| idx_company | company | 普通 | 按公司筛选 |
| idx_city | city | 普通 | 按城市筛选 |
| idx_experience | experience | 普通 | 按经验筛选 |
| idx_education | education | 普通 | 按学历筛选 |
| idx_platform | platform | 普通 | 按来源筛选 |
| idx_published_at | published_at | 普通 | 按时间排序 |
| idx_salary | salary_min, salary_max | 复合 | 薪资范围查询 |
| idx_platform_job | platform, platform_job_id | 复合 | 跨平台去重 |
| idx_status | status | 普通 | 过滤已过期/已删除 |
| idx_job_category | job_category | 普通 | 按岗位类别筛选 |
| idx_city_salary | city, salary_min, salary_max | 复合 | 城市薪资聚合查询 |
| idx_title_city | title, city | 复合 | 热门搜索组合 |

### 4.2 其他表索引

| 表 | 索引 | 字段 | 用途 |
|----|------|------|------|
| users | idx_email | email | 邮箱登录查询 |
| users | idx_phone | phone | 手机号登录查询 |
| users | idx_role | role | 按角色筛选 |
| users | idx_created_at | created_at | 按注册时间排序 |
| companies | idx_company_name | name | 公司名查询 |
| companies | idx_company_industry | industry | 按行业筛选 |
| analysis_cache | idx_cache_type | cache_type | 按缓存类型查询 |
| analysis_cache | idx_params_hash | params_hash | 按参数哈希精确匹配 |
| analysis_cache | idx_expires_at | expires_at | 过期缓存清理 |
| crawl_logs | idx_crawl_platform | platform | 按平台筛选日志 |
| crawl_logs | idx_crawl_status | status | 按状态筛选日志 |
| crawl_logs | idx_started_at | started_at | 按开始时间排序 |
| crawl_logs | idx_created_at | created_at | 按创建时间排序 |
| user_favorites | idx_user_id | user_id | 按用户查询收藏 |
| user_favorites | idx_job_id | job_id | 按岗位查被收藏数 |

---

## 5 枚举值映射

### 5.1 salary_type（薪资类型）

| 存储值 | 说明 | 处理规则 |
|--------|------|---------|
| 月薪 | 每月薪资 | 直接使用 salary_min / salary_max |
| 年薪 | 年度薪资 | 统计时除以 12 转换为月薪 |
| 面议 | 薪资面议 | 统计分析时排除（单独统计"面议占比"） |
| 时薪 | 按小时计薪 | 统计时排除（多为兼职/实习，样本少） |

### 5.2 experience（经验要求）

| 存储值 | 映射 | 说明 |
|--------|------|------|
| 应届生 | 0-1 年 | 面向应届毕业生 |
| 1-3年 | 1-3 年 | 初级岗位 |
| 3-5年 | 3-5 年 | 中级岗位 |
| 5-10年 | 5-10 年 | 高级岗位 |
| 10年以上 | 10+ 年 | 资深/专家岗位 |
| 不限 | — | 无经验要求 |

### 5.3 education（学历要求）

| 存储值 | 排序权重 | 说明 |
|--------|---------|------|
| 不限 | 0 | 无学历要求 |
| 大专 | 1 | 大专及以上 |
| 本科 | 2 | 本科及以上 |
| 硕士 | 3 | 硕士及以上 |
| 博士 | 4 | 博士 |

### 5.4 platform（数据来源平台）

| 存储值 | 平台名称 | 采集方式 |
|--------|---------|---------|
| BOSS直聘 | BOSS Zhipin | 移动端 API 模拟（boss.py） |
| 智联招聘 | Zhilian | 待开发 |
| 前程无忧 | 51job | 待开发 |
| 猎聘 | Liepin | 待开发 |
| 其他 | 其他平台 | 兜底分类 |

### 5.5 status（岗位状态）

| 存储值 | 含义 | 触发条件 |
|--------|------|---------|
| 有效 | 岗位在招 | 采集时默认状态 |
| 已过期 | 岗位已下架 | 重新采集时发现 platform_job_id 不再返回 |
| 已删除 | 数据异常 | 公司信息校验失败 / 反垃圾规则命中 |

### 5.6 role（用户角色）

| 存储值 | 权限范围 | 说明 |
|--------|---------|------|
| 普通用户 | 岗位浏览 + 筛选 + 收藏 | 默认角色，面向求职者 |
| 企业HR | + 数据导出 + 薪资对比 | 面向企业招聘人员 |
| 管理员 | + 用户管理 + 系统配置 + 采集管理 | 系统运维 |

### 5.7 task_type（采集任务类型）

| 存储值 | 触发方式 | 说明 |
|--------|---------|------|
| 全量采集 | 手动 / 定时 | 首次采集或大规模更新 |
| 增量更新 | 定时（每日） | 仅采集最近 N 天的新岗位 |
| 手动触发 | 管理员操作 | 按需临时采集特定关键词 |

### 5.8 crawl task status（采集任务状态）

| 存储值 | 说明 |
|--------|------|
| 排队中 | 任务已创建，等待执行 |
| 执行中 | 采集正在进行 |
| 已完成 | 采集正常结束 |
| 失败 | 采集异常终止 |
| 已取消 | 管理员手动取消 |

---

## 6 数据量估算

| 指标 | 预估值 | 说明 |
|------|--------|------|
| 日均增量 | 1,000-5,000 条 | 3-5 个平台 × 每天增量更新 |
| 年总量 | 50 万-200 万条 | 含去重后有效岗位 |
| 单表容量 | < 2 GB | InnoDB 单表（含索引） |
| 热数据（status=有效） | < 20 万条 | 同时有效的在招岗位 |
| Redis 缓存量 | < 200 MB | 分析结果缓存（1h TTL） |
| 日志表年增量 | < 10 万条 | 采集任务日志 |

---

> *文档版本：v1.0 | 最后更新：2026-07-02 | 状态：AI 生成，待人工审查*
