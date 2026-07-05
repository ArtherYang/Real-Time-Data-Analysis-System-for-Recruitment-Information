"""
Celery 应用配置
===============
功能：创建 Celery 应用实例，配置消息代理、结果后端和定时任务调度。
输入：设置模块（app.config）
输出：celery_app — Celery 应用实例

启动 Worker:
    celery -A app.celery_app worker --loglevel=info --concurrency=2

启动 Beat 调度器（定时任务）:
    celery -A app.celery_app beat --loglevel=info

同时启动 Worker + Beat:
    celery -A app.celery_app worker --beat --loglevel=info

依赖:
    - Redis 服务必须已启动（作为消息代理和结果后端）
    - pip install celery redis
"""

from celery import Celery
from celery.schedules import crontab

from app.config import default_config as config

# ======================== Celery 应用实例 ========================

celery_app = Celery(
    "recruitment_analytics",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=["app.tasks.crawl_tasks"],  # 自动发现任务模块
)

# ======================== Celery 配置 ========================

celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 任务超时
    task_soft_time_limit=1800,   # 软限制：30分钟
    task_time_limit=3600,        # 硬限制：60分钟
    # 结果过期（保留7天）
    result_expires=7 * 24 * 3600,
    # Worker 配置
    worker_prefetch_multiplier=1,  # 每次只取1个任务（适合长任务）
    worker_max_tasks_per_child=50,  # 每个worker处理50个任务后重启（防内存泄漏）
    # 重试
    task_acks_late=True,          # 任务完成后再确认（防丢失）
    task_reject_on_worker_lost=True,
)

# ======================== 定时任务调度 (Beat) ========================

celery_app.conf.beat_schedule = {
    # 每日全量采集：凌晨 2:00
    "daily-crawl": {
        "task": "daily_crawl",
        "schedule": crontab(hour=2, minute=0),
        "options": {"expires": 3600},  # 1小时后过期（避免积压）
    },
    # 增量更新：每 4 小时
    "incremental-crawl": {
        "task": "incremental_crawl",
        "schedule": crontab(hour="*/4", minute=30),
        "options": {"expires": 1800},  # 30分钟后过期
    },
}

# ======================== 便捷调试 ========================

if __name__ == "__main__":
    # 直接运行此文件时启动 Worker（调试用）
    celery_app.start()
