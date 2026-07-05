"""
Celery 任务定义
===============
功能：定义 Celery 异步任务，包括每日采集、增量更新等。
输入：Celery 应用实例
输出：任务执行结果字典

任务列表：
    - crawl_boss_task: BOSS直聘单个关键词采集
    - daily_crawl: 每日全量采集（预定义关键词列表）
    - incremental_crawl: 增量更新采集
"""

from loguru import logger

from app.celery_app import celery_app
from app.processor.pipeline import PipelineOrchestrator

# 默认搜索关键词列表（覆盖主流技术岗位）
DEFAULT_KEYWORDS = [
    "Python开发",
    "Java开发",
    "前端开发",
    "数据分析师",
    "产品经理",
    "人工智能",
    "软件测试",
    "运维工程师",
    "UI设计",
    "算法工程师",
]


@celery_app.task(bind=True, max_retries=3, name="crawl_boss_task")
def crawl_boss_task(self, keyword: str, pages: int = 5):
    """Celery 任务：执行 BOSS直聘单个关键词采集。

    带自动重试机制，最多重试 3 次。

    Args:
        keyword: 搜索关键词
        pages: 采集页数

    Returns:
        dict: 包含 keyword 和 count 的结果字典
    """
    logger.info(
        f"[Celery] 开始采集任务: keyword='{keyword}', pages={pages}"
    )

    try:
        orchestrator = PipelineOrchestrator()
        report = orchestrator.run(keywords=[keyword], pages=pages)

        result = {
            "keyword": keyword,
            "total_crawled": report.total_crawled,
            "total_valid": report.total_valid,
            "total_saved": report.total_saved,
            "clean_rate": report.clean_rate,
            "duration_seconds": report.duration_seconds,
        }
        logger.info(f"[Celery] 采集完成: {result}")
        return result

    except Exception as exc:
        logger.error(
            f"[Celery] 采集任务异常 (重试 {self.request.retries}/{self.max_retries}): {exc}"
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(bind=True, name="daily_crawl")
def daily_crawl(self):
    """Celery 定时任务：每日全量采集。

    对所有预定义关键词执行采集管道。
    通常在每日凌晨 2:00 触发（由 Celery Beat 调度）。

    Returns:
        dict: 包含 summary 和 per_keyword 的聚合结果
    """
    logger.info(
        f"[Celery] 开始每日全量采集: {len(DEFAULT_KEYWORDS)} 个关键词"
    )

    orchestrator = PipelineOrchestrator()
    report = orchestrator.run(keywords=DEFAULT_KEYWORDS, pages=5)

    result = {
        "task": "daily_crawl",
        "summary": report.to_dict(),
    }
    logger.info(f"[Celery] 每日采集完成: {result['summary']}")
    return result


@celery_app.task(bind=True, name="incremental_crawl")
def incremental_crawl(self):
    """Celery 定时任务：增量更新采集。

    采集最近更新的岗位数据（少量页数，高频次执行）。
    通常每 4 小时触发一次。

    Returns:
        dict: 增量采集结果
    """
    logger.info("[Celery] 开始增量更新采集")

    orchestrator = PipelineOrchestrator()
    report = orchestrator.run(keywords=DEFAULT_KEYWORDS[:5], pages=1)

    result = {
        "task": "incremental_crawl",
        "summary": report.to_dict(),
    }
    logger.info(f"[Celery] 增量采集完成: {result['summary']}")
    return result
