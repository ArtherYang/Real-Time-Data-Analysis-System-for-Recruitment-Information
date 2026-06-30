# 招聘信息实时数据分析系统

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

## 作者

杨昱晨 | 人工智能1班 | 20243909
