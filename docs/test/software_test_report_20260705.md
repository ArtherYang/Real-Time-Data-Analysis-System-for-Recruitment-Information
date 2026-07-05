# 软件测试报告

| 文档编号 | TEST-RDAS-002 | 版本 | 1.0 |
|---------|-------------|------|-----|
| 项目名称 | 招聘信息实时数据分析系统 | 拟制 | 杨昱晨 |
| 日期 | 2026-07-05 | 状态 | AI 生成，待人工审查 |

---

## 一、后端自动化测试

| 指标 | 结果 |
|------|------|
| 测试框架 | pytest 9.0.3 |
| 总用例 | **405** |
| 通过 | **405** ✅ |
| 失败 | **0** |
| 通过率 | **100%** |
| 警告 | 793（全部是 `datetime.utcnow()` deprecation warning） |
| 执行时间 | 17.33 秒 |
| 测试文件 | 19 个 |

### 测试文件清单

| 文件 | 用例数 | 覆盖模块 |
|------|--------|---------|
| `test_analysis_api.py` | 73 | 分析引擎 + 缓存 + 全部分析 API |
| `test_job51_crawler.py` | 43 | 51job 爬虫解析 |
| `test_normalizer.py` | 35 | 字段标准化 |
| `test_anti_crawl.py` | 28 | 反爬工具 |
| `test_auth_utils.py` | 25 | 认证工具（密码/JWT/登录安全） |
| `test_auth.py` | 24 | 认证模块兼容测试 |
| `test_config.py` | 23 | 多环境配置 |
| `test_api_auth.py` | 20 | 认证 API |
| `test_errors.py` | 20 | 错误处理 |
| `test_security.py` | 17 | 安全测试（SQL注入/XSS/限流） |
| `test_boss_crawler.py` | 16 | BOSS 直聘爬虫 |
| `test_api_e2e.py` | 15 | E2E 场景测试 |
| `test_cleaner.py` | 14 | 数据清洗 |
| `test_models.py` | 13 | ORM 模型 |
| `test_api_jobs.py` | 13 | 岗位 API |
| `test_pipeline.py` | 10 | 数据管道 |
| `test_crawler_accuracy.py` | 9 | 爬虫准确性 |
| `test_performance.py` | 9 | 性能基准 |
| `test_export_api.py` | 6 | 导出 API |

---

## 二、前端编译

| 指标 | 结果 |
|------|------|
| 构建工具 | Vite |
| 编译结果 | ✅ 成功 |
| 构建时间 | 15.3 秒 |
| 产物大小 | index.js 1,725 KB / index.css 366 KB / china.json 581 KB |
| 警告 | 1（chunk size > 500KB，非功能问题） |
| 页面加载 | `http://127.0.0.1:5173` 返回 200，Vue SPA 正常挂载 |

---

## 三、API 端点测试

25 个端点全部通过（200/201/401/409 均符合预期）：

| 端点 | 方法 | 状态码 | 说明 |
|------|------|--------|------|
| `/api/v1/jobs` | GET | 200 ✅ | 分页+筛选正常 |
| `/api/v1/jobs/stats/overview` | GET | 200 ✅ | 6,459条数据 |
| `/api/v1/analysis/hot-jobs` | GET | 200 ✅ | 10 品类 |
| `/api/v1/analysis/hotness-index` | GET | 200 ✅ | 热度指数 |
| `/api/v1/analysis/trend` | GET | 200 ✅ | 5 周趋势 |
| `/api/v1/analysis/growth` | GET | 200 ✅ | 环比增长 |
| `/api/v1/analysis/salary-distribution?group_by=job_category` | GET | 200 ✅ | 按品类 |
| `/api/v1/analysis/salary-distribution?group_by=city` | GET | 200 ✅ | 按城市 |
| `/api/v1/analysis/salary-distribution?group_by=experience` | GET | 200 ✅ | 按经验 |
| `/api/v1/analysis/salary-matrix` | GET | 200 ✅ | 经验-薪资矩阵 |
| `/api/v1/analysis/city-distribution` | GET | 200 ✅ | 30 城市分布 |
| `/api/v1/analysis/city-category-matrix` | GET | 200 ✅ | 城市×品类矩阵 |
| `/api/v1/analysis/skills-frequency` | GET | 200 ✅ | 技能频率 |
| `/api/v1/analysis/skills-wordcloud` | GET | 200 ✅ | 词云数据 |
| `/api/v1/analysis/skills-by-category` | GET | 200 ✅ | 分类技能 |
| `/api/v1/analysis/skills-cooccurrence` | GET | 200 ✅ | 技能共现 |
| `/api/v1/export/csv` | GET | 200 ✅ | CSV 导出 |
| `/api/v1/export/excel` | GET | 200 ✅ | Excel 导出 |
| `/api/v1/dashboard/overview` | GET | 200 ✅ | 仪表盘概览 |
| `/api/v1/dashboard/hot-jobs` | GET | 200 ✅ | 仪表盘热度 |
| `/api/v1/dashboard/salary-trend` | GET | 200 ✅ | 仪表盘薪资趋势 |
| `/api/v1/dashboard/city-distribution` | GET | 200 ✅ | 仪表盘城市分布 |
| `/api/v1/resumes/templates` | GET | 200 ✅ | 简历模板 |
| `/api/v1/auth/register` | POST | 201 ✅ | 注册成功 |
| `/api/v1/auth/register` (重复) | POST | 409 ✅ | 防重复 |
| `/api/v1/auth/login` | POST | 200 ✅ | 登录成功 |
| `/api/v1/auth/me` (无效Token) | GET | 401 ✅ | 认证拦截 |

---

## 四、数据库完整性

| 检查项 | 结果 |
|--------|------|
| 总记录 | **6,459** 条 |
| 有效记录 | 6,459（100%） |
| 空字段（title/company/city/platform） | **0** |
| 经验枚举违规 | **0** |
| 学历枚举违规 | **0** |
| 薪资类型违规 | **0** |
| 城市覆盖 | 31 个 |
| DB 文件大小 | ~1 MB |

### 品类分布

| 品类 | 数量 | 占比 |
|------|------|------|
| 技术 | 5,149 | 79.7% |
| 产品 | 662 | 10.3% |
| 设计 | 118 | 1.8% |
| 运营 | 111 | 1.7% |
| 金融 | 85 | 1.3% |
| 医疗 | 83 | 1.3% |
| 市场 | 82 | 1.3% |
| 教育 | 75 | 1.2% |
| 人力资源 | 73 | 1.1% |
| 制造 | 21 | 0.3% |

### 平台分布

| 平台 | 数量 |
|------|------|
| 前程无忧 | 2,230 |
| BOSS直聘 | 1,422 |
| 智联招聘 | 1,422 |
| 猎聘 | 1,385 |

### 日期分布

| 周 | 数量 |
|----|------|
| 2026-W22 | 10 |
| 2026-W23 | 586 |
| 2026-W24 | 1,361 |
| 2026-W25 | 2,033 |
| 2026-W26 | 2,469 |

### 经验分布

| 经验 | 数量 |
|------|------|
| 5-10年 | 2,301 |
| 10年以上 | 1,967 |
| 不限 | 1,274 |
| 3-5年 | 737 |
| 1-3年 | 110 |
| 应届生 | 70 |

### 学历分布

| 学历 | 数量 |
|------|------|
| 不限 | 2,499 |
| 硕士 | 1,984 |
| 本科 | 1,616 |
| 博士 | 244 |
| 大专 | 116 |

---

## 五、⚠️ 发现的问题

### 1. 100 条"未知"城市记录
**严重度**：中

数据中有 100 条 `city='未知'`，来自 51job API 返回的部分记录缺少 `workAreaName` 字段。中国地图上这 100 条无法标记城市位置。

**影响**：城市分布统计偏差约 1.5%，地图上存在缺口。

### 2. 经验分布严重失衡
**严重度**：高

| 经验段 | 当前 | 正常比例 | 问题 |
|--------|------|---------|------|
| 应届生 | 70 (1.1%) | ~15% | 过少 |
| 1-3年 | 110 (1.7%) | ~30% | 过少 |
| 3-5年 | 737 (11.4%) | ~25% | 偏少 |
| 5-10年 | 2,301 (35.6%) | ~20% | 偏多 |
| 10年以上 | 1,967 (30.4%) | ~5% | 严重偏多 |

**根因**：`大模型岗位信息.csv` 以高级岗位为主（大模型/AI 方向对经验要求高）。经验饼图会显示 5-10年 和 10年以上 占比巨大，与实际招聘市场（初中级岗位为主）严重不符。

### 3. 学历"不限"占比过高
**严重度**：中

`不限`: 2,499 (38.7%)。正常应在 8-15%。CSV 中很多记录的学历字段缺失，默认填了"不限"。

### 4. 制造品类仅 21 条
**严重度**：低

用户要求各品类 ≥ 50 条。制造品类当前只有 21 条，是所有品类中最少的。

### 5. 17 个城市仅有补充数据
**严重度**：低

30 个城市中，乌鲁木齐、拉萨、呼和浩特、南宁、贵阳、海口、哈尔滨、兰州、沈阳、昆明、福州、济南、郑州、合肥、厦门、长沙、青岛各只有 20 条补充数据。无真实数据支撑。

### 6. 前端主 JS bundle 过大
**严重度**：低

主 JS 文件 1,725 KB（gzip 576 KB）。其中 china.json 581 KB 应改为异步加载。

### 7. 793 个 deprecation warning
**严重度**：低

全部来自 `datetime.utcnow()` 调用，Python 3.12+ 推荐使用 `datetime.now(datetime.UTC)`。不影响功能，但建议后续统一替换。

---

## 六、数据来源统计

| 来源 | 数量 | 比例 | 备注 |
|------|------|------|------|
| `大模型岗位信息.csv` | 5,333 | 82.6% | 真实招聘数据，以 AI/技术岗位为主 |
| 51job API 实时采集 | 661 | 10.2% | 2026-07-05 浏览器内 fetch 采集 |
| 拉勾 CSV | 100 | 1.5% | `lagou_jobs.csv` 真实数据 |
| 补充生成 | 365 | 5.7% | 填补弱势品类和缺失城市 |

---

## 七、测试结论

**系统整体可用**。后端 405 个自动化测试全通过，25 个 API 端点全部正常响应，前端编译通过，数据库无脏数据。主要问题是经验/学历分布失衡（CSV 数据偏向高级岗位）和 100 条未知城市记录。

---

> *文档版本：v1.0 | 最后更新：2026-07-05 | 状态：AI 生成，待人工审查*
>
> **武汉学链科技有限公司**
>
> *Copyright © XuelianTechnologies Co., Ltd.*
