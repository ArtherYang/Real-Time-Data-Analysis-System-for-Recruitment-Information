"""
Prometheus 监控指标模块
========================
暴露 /metrics 端点供 Prometheus 抓取，收集 HTTP 请求、延迟、错误等指标。

指标列表：
- rdas_http_requests_total: HTTP 请求总数（按 method、endpoint、status 标签）
- rdas_http_request_duration_seconds: HTTP 请求延迟直方图
- rdas_http_errors_total: HTTP 错误总数（4xx/5xx）
- rdas_celery_tasks_total: Celery 任务计数（按 task_name、status 标签）
- rdas_db_connections: 数据库连接数
- rdas_redis_connected: Redis 连接状态（0/1）

AI生成，待人工审查。
"""

import time
from flask import request, g

from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CollectorRegistry,
    CONTENT_TYPE_LATEST,
)

# ======================== 指标定义 ========================

REGISTRY = CollectorRegistry(auto_describe=True)

# HTTP 请求总数
http_requests_total = Counter(
    "rdas_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=REGISTRY,
)

# HTTP 请求延迟（秒）
http_request_duration_seconds = Histogram(
    "rdas_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

# HTTP 错误总数
http_errors_total = Counter(
    "rdas_http_errors_total",
    "Total HTTP errors (4xx/5xx)",
    ["method", "endpoint", "status_code"],
    registry=REGISTRY,
)

# Celery 任务计数
celery_tasks_total = Counter(
    "rdas_celery_tasks_total",
    "Total Celery task executions",
    ["task_name", "status"],
    registry=REGISTRY,
)

# 数据库连接状态
db_connections = Gauge(
    "rdas_db_connections",
    "Current database connections",
    registry=REGISTRY,
)

# Redis 连接状态
redis_connected = Gauge(
    "rdas_redis_connected",
    "Redis connection status (1=connected, 0=disconnected)",
    registry=REGISTRY,
)


# ======================== Flask 中间件 ========================

def setup_metrics(app):
    """
    为 Flask 应用注册 Prometheus 指标收集中间件和 /metrics 端点。

    Args:
        app: Flask 应用实例

    使用方式：
        from app.metrics import setup_metrics
        setup_metrics(app)
    """

    @app.before_request
    def _before_request():
        """请求开始时间戳，存入 g 对象。"""
        g._request_start_time = time.time()

    @app.after_request
    def _after_request(response):
        """请求结束后记录指标：总数、延迟、错误。"""
        # 跳过 metrics 端点自身
        if request.path == "/metrics":
            return response

        method = request.method
        endpoint = request.path
        status_code = str(response.status_code)

        # 请求总数
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
        ).inc()

        # 请求延迟
        start_time = getattr(g, "_request_start_time", None)
        if start_time is not None:
            elapsed = time.time() - start_time
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
            ).observe(elapsed)

        # 错误计数（4xx/5xx）
        if response.status_code >= 400:
            http_errors_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
            ).inc()

        return response

    @app.route("/metrics")
    def _metrics():
        """Prometheus 指标暴露端点。"""
        from prometheus_client import generate_latest
        return generate_latest(REGISTRY), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ======================== 业务指标更新 ========================

def update_db_connection_count(count: int):
    """更新数据库连接数指标。

    Args:
        count: 当前数据库连接数
    """
    db_connections.set(count)


def update_redis_status(connected: bool):
    """更新 Redis 连接状态指标。

    Args:
        connected: True 表示 Redis 可达，False 表示不可达
    """
    redis_connected.set(1 if connected else 0)


def record_celery_task(task_name: str, status: str):
    """记录 Celery 任务执行结果。

    Args:
        task_name: 任务名称（如 "daily_crawl"）
        status: 执行状态（"success" / "failure"）
    """
    celery_tasks_total.labels(task_name=task_name, status=status).inc()
