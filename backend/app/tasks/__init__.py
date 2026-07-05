"""
Celery 任务初始化
=================
任务模块入口，导出所有 Celery 任务。
"""

from app.tasks.crawl_tasks import (
    crawl_boss_task,
    daily_crawl,
    incremental_crawl,
)

__all__ = ["crawl_boss_task", "daily_crawl", "incremental_crawl"]
