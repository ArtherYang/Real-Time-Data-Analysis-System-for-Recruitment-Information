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
from .base import BaseCrawler

# 各平台爬虫（逐步实现）
# from .boss import BossZhipinCrawler
# from .zhilian import ZhilianCrawler
# from .job51 import Job51Crawler
