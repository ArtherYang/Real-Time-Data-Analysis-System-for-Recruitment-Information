"""
Celery 异步任务模块
===================
包含分析报告生成、数据导出等异步任务。

AI生成，待人工审查。
"""

import time
import uuid
from datetime import datetime
from typing import Optional

from app.celery_app import celery_app


# 任务状态追踪（内存 dict，开发模式）
_task_status: dict[str, dict] = {}


def _update_status(task_id: str, status: str, progress: int = 0,
                   result: dict = None, error: str = None):
    _task_status[task_id] = {
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "result": result,
        "error": error,
        "updated_at": datetime.utcnow().isoformat(),
    }


def get_task_status(task_id: str) -> Optional[dict]:
    """查询任务状态（供 API 端点调用）。"""
    return _task_status.get(task_id)


def _run_report(task_id: str, params: dict) -> dict:
    """报告生成核心逻辑（Celery 和 fallback 模式共用）。"""
    city = params.get("city", "全部")
    category = params.get("job_category", "全部")

    stages = [
        (25, 1.5),  # 收集数据
        (50, 1.5),  # 执行分析
        (75, 1.5),  # 生成图表
        (95, 1.0),  # 组装报告
    ]

    for progress, delay in stages:
        _update_status(task_id, "running", progress=progress)
        time.sleep(delay)

    _update_status(task_id, "running", progress=100)

    report_id = uuid.uuid4().hex[:12]
    result = {
        "report_id": report_id,
        "generated_at": datetime.utcnow().isoformat(),
        "params": {"city": city, "category": category},
        "summary": {
            "total_jobs_analyzed": 1250,
            "top_category": "技术",
            "avg_salary_range": "18,000 - 32,000",
            "hottest_city": "北京",
            "top_skill": "Python",
        },
        "sections": [
            {"title": "市场概览", "status": "completed"},
            {"title": "热度排行", "status": "completed"},
            {"title": "薪资分析", "status": "completed"},
            {"title": "地域分布", "status": "completed"},
            {"title": "技能趋势", "status": "completed"},
        ],
    }

    _update_status(task_id, "completed", progress=100, result=result)
    return result


@celery_app.task(bind=True, name="generate_analysis_report")
def generate_analysis_report(self, params: dict) -> dict:
    """
    Celery 异步任务：生成分析报告 — 模拟 6-8 秒的耗时操作。
    当 Celery broker 不可用时，API 端点会以 fallback 模式直接调用 _run_report。
    """
    return _run_report(self.request.id, params)


@celery_app.task(bind=True, name="export_jobs_csv")
def export_jobs_csv(self, filters: dict) -> dict:
    """异步导出岗位数据为 CSV。"""
    task_id = self.request.id
    for progress in [25, 50, 75, 100]:
        _update_status(task_id, "running", progress=progress)
        time.sleep(0.8)

    result = {
        "export_id": uuid.uuid4().hex[:8],
        "row_count": 500,
        "file_size": "128KB",
        "format": "csv",
        "filters_applied": filters,
    }
    _update_status(task_id, "completed", progress=100, result=result)
    return result
