# 职言 — 招聘市场行情分析平台

## 项目简介

实时采集和整合多个主流招聘平台的招聘信息，通过数据清洗、自然语言处理和数据挖掘技术，为用户提供多维度的招聘市场分析服务。

## 技术栈

| 层次 | 技术 | 
|------|------|
| 后端语言 | Python 3.x |
| Web框架 | Flask / FastAPI |
| 爬虫框架 | Scrapy + Selenium |
| 数据库 | MySQL + Redis |
| 数据分析 | Pandas + NumPy + Jieba |
| 可视化 | ECharts / PyEcharts |
| 前端 | Vue.js + Element UI |
| 部署 | Docker + Nginx |

## 项目结构

```
recruitment-analytics/
├── CLAUDE.md           # 项目章程（AI行为规范）
├── README.md           # 本文件
├── .gitignore
├── docs/               # 文档
│   ├── requirements/   # 需求文档
│   ├── design/         # 设计文档
│   └── test/           # 测试文档
├── backend/            # Python 后端
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api/        # Web接口
│   │   ├── crawler/    # 爬虫模块
│   │   ├── processor/  # 数据处理
│   │   └── models/     # 数据模型
│   └── tests/          # 后端测试
└── frontend/           # Vue.js 前端
    └── src/
```

## 开发计划

- 第1周（6.28-7.04）：需求分析、系统设计
- 第2周（7.05-7.11）：技术选型确认、数据库设计
- 第3-4周（7.12-7.25）：爬虫+数据处理模块
- 第5-6周（7.26-8.10）：分析模块+前端可视化
- 第7周（8.11-8.17）：测试、部署、验收

---

## 里程碑交付物

### M1 — 数据采集与处理 ✅

| # | 交付物 | 状态 | 说明 |
|---|--------|------|------|
| 1 | 多平台采集脚本 | ✅ | `crawler/boss.py` + `crawler/job51.py`，完整爬虫实现 |
| 2 | 多渠道覆盖 | ✅ | BOSS直聘 + 前程无忧（51job），可扩展 |
| 3 | 数据去重 | ✅ | `processor/cleaner.py` — 精确去重 + 模糊去重（difflib） |
| 4 | 容错机制 | ✅ | 请求重试（3次）、反爬检测、异常捕获逐字段 |
| 5 | 采集监控 | ✅ | `crawl_logs` 表 + Grafana dashboard 配置 |
| 6 | 清洗管道 | ✅ | `processor/pipeline.py` — PipelineOrchestrator 统一调度 |
| 7 | 数据质量评估 | ✅ | 必填字段检查、薪资范围验证、质量报告 |
| 8 | 敏感数据脱敏 | ✅ | `models/user.py` — 手机号掩码（138****5678） |
| 9 | 24h+ 稳定运行 | ⬜ | 待 Celery Beat 定时任务联调 |

### M2 — 数据存储与 API ✅

| # | 交付物 | 状态 | 说明 |
|---|--------|------|------|
| 1 | 数据库设计文档 | ✅ | `docs/design/database_design.md` — ER图、表结构、索引策略 |
| 2 | DDL 建表脚本 | ✅ | `backend/db/init.sql` — 5 张表完整 DDL |
| 3 | ORM 数据模型 | ✅ | `models/job.py`, `user.py`, `analysis.py`, `crawl_log.py` |
| 4 | 数据入库脚本 | ✅ | `scripts/seed_data.py` — 模拟数据生成 + 入库 |
| 5 | RESTful API 开发 | ✅ | 10 个端点：岗位、分析、认证（见 API 文档） |
| 6 | API 文档 | ✅ | `docs/design/api_documentation.md` — 完整接口规范 |
| 7 | 数据字典 | ✅ | SRS 3.3 节 + `docs/design/database_design.md` 字段说明 |

**API 验证结果（2026-07-03）：**
```
GET  /api/v1/jobs                              → 200, total=40
GET  /api/v1/jobs?platform=BOSS直聘             → 200, count=20
GET  /api/v1/jobs?city=北京                     → 200, count=1
GET  /api/v1/jobs/cities                        → 200, 30 cities (含坐标+图标+区域)
GET  /api/v1/jobs/stats/overview                → 200, avg_salary=16700-24250
GET  /api/v1/analysis/hot-jobs?top=10           → 200, items=4
GET  /api/v1/analysis/city-distribution         → 200, cities=8, cr5=85.0
GET  /api/v1/analysis/salary-distribution?group_by=city → 200, items=8
GET  /api/v1/analysis/salary-distribution?group_by=experience → 200, items=5
POST /api/v1/auth/register                      → 201
POST /api/v1/auth/login                         → 200, has_access_token
```

## 作者

杨昱晨 | 人工智能1班 | 20243909
