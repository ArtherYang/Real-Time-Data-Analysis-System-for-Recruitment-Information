# API 接口文档 — 招聘信息实时数据分析系统

| 文档编号 | API-RDAS-001 | 版本 | 1.0 |
|---------|-------------|------|-----|
| 项目名称 | 招聘信息实时数据分析系统 | 拟制 | 杨昱晨 |
| 日期 | 2026-07-02 | 状态 | AI 生成，待人工审查 |

---

## 1 概述

RDAS API 采用 RESTful 风格设计，通过 HTTP JSON 进行数据交换。所有端点统一挂载在 `/api/v1/` 前缀下。

### 1.1 基础 URL

| 环境 | 地址 |
|------|------|
| 本地开发 | `http://localhost:5000` |
| Docker | `http://localhost:8080` (via Nginx) |

### 1.2 统一响应格式

**成功响应：**
```json
{
  "code": 200,
  "message": "ok",
  "data": { ... },
  "pagination": { "page": 1, "per_page": 20, "total": 150, "total_pages": 8 }
}
```

**错误响应：**
```json
{
  "code": 4xx,
  "message": "错误描述",
  "data": null
}
```

### 1.3 HTTP 状态码

| 状态码 | 含义 | 说明 |
|--------|------|------|
| 200 | OK | 请求成功 |
| 201 | Created | 资源创建成功 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证或认证失败 |
| 403 | Forbidden | 无权限访问 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突（重复注册等） |
| 422 | Unprocessable | 请求格式正确但语义错误 |
| 423 | Locked | 账号已锁定 |
| 429 | Too Many Requests | 请求过于频繁 |
| 500 | Internal Server Error | 服务器内部错误 |

### 1.4 认证方式

需要认证的接口在请求头中携带 JWT Token：

```
Authorization: Bearer <access_token>
```

---

## 2 岗位数据接口 — `/api/v1/jobs`

### 2.1 获取岗位列表

```
GET /api/v1/jobs
```

**Query 参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| keyword | string | 否 | — | 岗位名称模糊搜索（匹配 title + title_raw） |
| city | string | 否 | — | 城市精确匹配 |
| experience | string | 否 | — | 经验要求（应届生/1-3年/3-5年/5-10年/10年以上/不限） |
| education | string | 否 | — | 学历要求（不限/大专/本科/硕士/博士） |
| platform | string | 否 | — | 来源平台（BOSS直聘/智联招聘/前程无忧/猎聘/其他） |
| job_category | string | 否 | — | 岗位大类 |
| salary_min | integer | 否 | — | 最低薪资过滤（月薪，元） |
| salary_max | integer | 否 | — | 最高薪资过滤（月薪，元） |
| page | integer | 否 | 1 | 页码 |
| per_page | integer | 否 | 20 | 每页条数（最大 100） |

**响应示例：**
```json
{
  "code": 200,
  "message": "ok",
  "data": [
    {
      "job_id": "abc123def456...",
      "title": "Python后端开发工程师",
      "title_raw": "【急招】Python后端开发工程师",
      "company": "字节跳动",
      "salary_min": 25000,
      "salary_max": 50000,
      "salary_type": "月薪",
      "city": "北京",
      "district": "海淀区",
      "experience": "3-5年",
      "education": "本科",
      "job_type": "全职",
      "recruit_number": "3",
      "industry": "互联网",
      "job_category": "技术",
      "skills": "Python,Django,Flask,MySQL,Redis",
      "company_size": "10000人以上",
      "company_type": "民营",
      "welfare": "五险一金,年终奖,弹性工作",
      "platform": "BOSS直聘",
      "platform_job_id": "boss_12345",
      "source_url": "https://www.zhipin.com/job_detail/xxx.html",
      "published_at": "2026-06-28",
      "crawled_at": "2026-07-01T10:30:00",
      "status": "有效"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

### 2.2 获取岗位详情

```
GET /api/v1/jobs/{job_id}
```

**Path 参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 岗位唯一标识（32位 UUID） |

### 2.3 岗位概览统计

```
GET /api/v1/jobs/stats/overview
```

**响应示例：**
```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "total": 1523,
    "this_week_new": 86,
    "avg_salary_min": 15000,
    "avg_salary_max": 28000,
    "city_distribution": [
      { "city": "北京", "count": 420 },
      { "city": "上海", "count": 356 }
    ],
    "platform_distribution": [
      { "platform": "BOSS直聘", "count": 820 }
    ],
    "experience_distribution": [
      { "experience": "3-5年", "count": 450 }
    ],
    "education_distribution": [
      { "education": "本科", "count": 680 }
    ],
    "top_job_categories": [
      { "category": "技术", "count": 580 }
    ]
  }
}
```

---

## 3 分析数据接口 — `/api/v1/analysis`

所有分析接口共享以下筛选参数（Query）：

| 参数 | 类型 | 说明 |
|------|------|------|
| city | string | 城市筛选 |
| job_category | string | 岗位大类筛选 |
| industry | string | 行业筛选 |
| experience | string | 经验筛选 |
| education | string | 学历筛选 |
| platform | string | 平台筛选 |
| date_from | string | 开始日期（YYYY-MM-DD） |
| date_to | string | 结束日期（YYYY-MM-DD） |

### 3.1 热度排行

#### 3.1.1 热门岗位分类排名

```
GET /api/v1/analysis/hot-jobs?top=20&job_category=技术
```

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| top | int | 20 | 1-100 | 返回 Top N |

#### 3.1.2 热度指数

```
GET /api/v1/analysis/hotness-index?top=20
```

#### 3.1.3 趋势数据

```
GET /api/v1/analysis/trend?job_category=技术&granularity=weekly
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| granularity | string | weekly | 粒度：daily / weekly / monthly |

#### 3.1.4 周期增长

```
GET /api/v1/analysis/growth?job_category=技术&city=北京
```

### 3.2 薪资分析

#### 3.2.1 薪资分布

```
GET /api/v1/analysis/salary-distribution?group_by=job_category&top=20
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| group_by | string | job_category | 分组维度：job_category / city / experience / education |
| top | int | 20 | 返回 Top N 分组 |

**响应示例：**
```json
{
  "code": 200,
  "data": {
    "group_by": "job_category",
    "items": [
      {
        "job_category": "技术",
        "count": 580,
        "avg_salary_min": 20000,
        "avg_salary_max": 38000,
        "median_salary": 28000,
        "p25_salary": 15000,
        "p75_salary": 45000
      }
    ]
  }
}
```

#### 3.2.2 经验-薪资矩阵

```
GET /api/v1/analysis/salary-matrix?job_category=技术
```

### 3.3 地域分析

#### 3.3.1 城市分布

```
GET /api/v1/analysis/city-distribution?top=50
```

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| top | int | 50 | 1-100 | 返回 Top N 城市 |

**响应包含：**
- `cities`：城市岗位数量分布
- `cr5`：CR5 集中度百分比
- `cr5_detail`：Top 5 城市详情
- `provinces`：省份聚合数据

#### 3.3.2 城市-类别矩阵

```
GET /api/v1/analysis/city-category-matrix?top_n_cities=15
```

### 3.4 技能分析

#### 3.4.1 技能频率

```
GET /api/v1/analysis/skills-frequency?top=100
```

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| top | int | 100 | 1-200 | 返回 Top N 技能 |

#### 3.4.2 技能共现

```
GET /api/v1/analysis/skills-cooccurrence?top=50
```

#### 3.4.3 分类技能排行

```
GET /api/v1/analysis/skills-by-category?top=20
```

#### 3.4.4 词云数据

```
GET /api/v1/analysis/skills-wordcloud?top=100
```

**响应示例（适配 ECharts wordCloud）：**
```json
{
  "code": 200,
  "data": [
    { "name": "Python", "value": 320 },
    { "name": "Java", "value": 280 },
    { "name": "SQL", "value": 250 }
  ]
}
```

---

## 4 用户认证接口 — `/api/v1/auth`

### 4.1 用户注册

```
POST /api/v1/auth/register
```

**请求体：**
```json
{
  "email": "user@example.com",
  "phone": "13800138000",
  "password": "Abc12345",
  "nickname": "张三"
}
```

> `email` 和 `phone` 至少提供一个。密码需 8-20 位且包含字母和数字。

**成功响应 (201)：**
```json
{
  "code": 201,
  "message": "注册成功",
  "data": {
    "user": {
      "user_id": "...",
      "email": "user@example.com",
      "phone": "138****8000",
      "nickname": "张三",
      "role": "普通用户",
      "avatar_url": null,
      "created_at": "2026-07-02T10:00:00",
      "last_login": null
    },
    "access_token": "eyJhbG...",
    "refresh_token": "eyJhbG..."
  }
}
```

### 4.2 用户登录

```
POST /api/v1/auth/login
```

**请求体：**
```json
{
  "account": "user@example.com",
  "password": "Abc12345"
}
```

> `account` 可以是邮箱或手机号。

**登录安全：**
- 连续失败 5 次后账号锁定 15 分钟
- 每次失败返回"账号或密码错误"和剩余尝试次数

### 4.3 刷新令牌

```
POST /api/v1/auth/refresh
```

**请求体：**
```json
{
  "refresh_token": "eyJhbG..."
}
```

### 4.4 获取当前用户信息

```
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

### 4.5 更新个人资料

```
PUT /api/v1/auth/me
Authorization: Bearer <access_token>
```

**请求体：**
```json
{
  "nickname": "新昵称",
  "avatar_url": "https://example.com/avatar.png"
}
```

---

## 5 数据导出接口 — `/api/v1/export`

### 5.1 导出 CSV

```
GET /api/v1/export/csv?city=北京&job_category=技术
```

支持所有 `/api/v1/analysis` 的筛选参数。返回 UTF-8 BOM CSV 文件（Excel 兼容）。

### 5.2 导出 Excel

```
GET /api/v1/export/excel?city=北京&job_category=技术
```

返回带样式的 `.xlsx` 文件（需要 `openpyxl` 依赖）。

---

## 6 系统接口

### 6.1 健康检查

```
GET /health
```

**响应：**
```json
{
  "status": "ok",
  "service": "RDAS API",
  "version": "0.1.0"
}
```

---

## 7 错误码定义

| 错误码 | HTTP 状态码 | 说明 |
|--------|-----------|------|
| 400 | Bad Request | 参数校验失败 |
| 401 | Unauthorized | Token 无效或已过期 / 账号密码错误 |
| 403 | Forbidden | 账号已禁用 |
| 404 | Not Found | 岗位/用户不存在 |
| 409 | Conflict | 邮箱/手机号已被注册 |
| 422 | Unprocessable | 请求格式合法但语义有误 |
| 423 | Locked | 登录失败过多，账号已锁定 |
| 500 | Internal Server Error | 服务器内部错误 |

---

## 8 接口总览

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/health` | 否 | 健康检查 |
| GET | `/api/v1/jobs` | 否 | 岗位列表 |
| GET | `/api/v1/jobs/{job_id}` | 否 | 岗位详情 |
| GET | `/api/v1/jobs/stats/overview` | 否 | 岗位概览统计 |
| GET | `/api/v1/analysis/hot-jobs` | 否 | 热门岗位排名 |
| GET | `/api/v1/analysis/hotness-index` | 否 | 热度指数 |
| GET | `/api/v1/analysis/trend` | 否 | 趋势数据 |
| GET | `/api/v1/analysis/growth` | 否 | 周期增长 |
| GET | `/api/v1/analysis/salary-distribution` | 否 | 薪资分布 |
| GET | `/api/v1/analysis/salary-matrix` | 否 | 经验-薪资矩阵 |
| GET | `/api/v1/analysis/city-distribution` | 否 | 城市分布 |
| GET | `/api/v1/analysis/city-category-matrix` | 否 | 城市-类别矩阵 |
| GET | `/api/v1/analysis/skills-frequency` | 否 | 技能频率 |
| GET | `/api/v1/analysis/skills-cooccurrence` | 否 | 技能共现 |
| GET | `/api/v1/analysis/skills-by-category` | 否 | 分类技能排行 |
| GET | `/api/v1/analysis/skills-wordcloud` | 否 | 词云数据 |
| GET | `/api/v1/export/csv` | 否 | 导出 CSV |
| GET | `/api/v1/export/excel` | 否 | 导出 Excel |
| POST | `/api/v1/auth/register` | 否 | 用户注册 |
| POST | `/api/v1/auth/login` | 否 | 用户登录 |
| POST | `/api/v1/auth/refresh` | 否 | 刷新令牌 |
| GET | `/api/v1/auth/me` | 是 | 当前用户信息 |
| PUT | `/api/v1/auth/me` | 是 | 更新个人资料 |

---

> *文档版本：v1.0 | 最后更新：2026-07-02 | 状态：AI 生成，待人工审查*
