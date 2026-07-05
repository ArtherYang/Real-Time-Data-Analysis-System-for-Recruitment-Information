"""
数据采集模块
============
负责从多个招聘平台采集岗位信息。

目标平台（优先级排序）：
1. BOSS直聘
2. 智联招聘
3. 前程无忧（51job）

采集策略：
- 优先使用平台公开API
- 静态页面使用 Scrapy + Requests
- 动态渲染页面使用 Selenium
- 每次采集间隔 >= 3秒，避免触发反爬
"""

# 爬虫基类
from .base import BaseCrawler, JobRawData

# 反爬工具
from .anti_crawl import AntiCrawlManager, retry_request, CookiePool

# BOSS直聘爬虫
from .boss import BossZhipinCrawler, generate_sample_data

# 前程无忧（51job）爬虫
from .job51 import Job51Crawler

# 后续平台爬虫
# from .zhilian import ZhilianCrawler

__all__ = [
    "BaseCrawler",
    "JobRawData",
    "AntiCrawlManager",
    "retry_request",
    "CookiePool",
    "BossZhipinCrawler",
    "Job51Crawler",
    "generate_sample_data",
]
