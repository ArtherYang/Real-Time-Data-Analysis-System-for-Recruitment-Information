"""
分析结果 API 接口
==================
提供基于岗位数据的多维度聚合分析接口，支撑前端可视化展示。
M3 数据分析引擎 — 四个核心模块全部对接 SQLAlchemy 服务层。

AI生成，待人工审查。
"""

from flask import request

from . import api_bp
from ..analysis import AnalysisEngine, AnalysisFilters
from ..database import SessionLocal
from ..utils import success_response, error_response


def _parse_filters() -> AnalysisFilters:
    """从请求参数构建 AnalysisFilters。"""
    return AnalysisFilters(
        city=request.args.get("city", "").strip() or None,
        job_category=request.args.get("job_category", "").strip() or None,
        industry=request.args.get("industry", "").strip() or None,
        experience=request.args.get("experience", "").strip() or None,
        education=request.args.get("education", "").strip() or None,
        platform=request.args.get("platform", "").strip() or None,
        date_from=request.args.get("date_from", "").strip() or None,
        date_to=request.args.get("date_to", "").strip() or None,
    )


def _int_param(name: str, default: int, lo: int = 1, hi: int = 200) -> int:
    try:
        return min(max(int(request.args.get(name, default)), lo), hi)
    except (ValueError, TypeError):
        return default


# ============================================================
# 热度排行
# ============================================================

@api_bp.route("/analysis/hot-jobs", methods=["GET"])
def get_hot_jobs():
    session = SessionLocal()
    try:
        filters = _parse_filters()
        top_n = _int_param("top", 20, hi=100)
        group_by = request.args.get("group_by", "category").strip()
        engine = AnalysisEngine(session)
        if group_by == "title":
            data = engine.ranking.get_title_ranking(filters, top_n)
        else:
            data = engine.ranking.get_category_ranking(filters, top_n)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/hotness-index", methods=["GET"])
def get_hotness_index():
    session = SessionLocal()
    try:
        filters = _parse_filters()
        top_n = _int_param("top", 20, hi=100)
        data = AnalysisEngine(session).ranking.get_hotness_index(filters, top_n)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/trend", methods=["GET"])
def get_trend_data():
    session = SessionLocal()
    try:
        filters = _parse_filters()
        cat = request.args.get("job_category", "").strip() or None
        gran = request.args.get("granularity", "weekly").strip()
        data = AnalysisEngine(session).ranking.get_trend_data(filters, cat, gran)
        return success_response(data={"granularity": gran, "category": cat, "data_points": data})
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/growth", methods=["GET"])
def get_period_growth():
    session = SessionLocal()
    try:
        data = AnalysisEngine(session).ranking.get_period_growth(_parse_filters())
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


# ============================================================
# 薪资分布
# ============================================================

@api_bp.route("/analysis/salary-distribution", methods=["GET"])
def get_salary_distribution():
    session = SessionLocal()
    try:
        filters = _parse_filters()
        group_by = request.args.get("group_by", "job_category").strip()
        top_n = _int_param("top", 20, hi=100)
        data = AnalysisEngine(session).salary.get_salary_stats(filters, group_by, top_n)
        return success_response(data={"group_by": group_by, "items": data})
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/salary-matrix", methods=["GET"])
def get_salary_matrix():
    session = SessionLocal()
    try:
        data = AnalysisEngine(session).salary.get_salary_experience_matrix(_parse_filters())
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


# ============================================================
# 地域分析
# ============================================================

@api_bp.route("/analysis/city-distribution", methods=["GET"])
def get_city_distribution():
    session = SessionLocal()
    try:
        filters = _parse_filters()
        top_n = _int_param("top", 50, hi=100)
        engine = AnalysisEngine(session)
        city_data = engine.regional.get_city_distribution(filters, top_n)
        cr5_data = engine.regional.get_cr5_concentration(filters)
        prov_data = engine.regional.get_province_aggregation(filters)
        return success_response(data={
            "total": city_data["total"], "cr5": cr5_data["cr5_pct"],
            "cr5_detail": cr5_data["top_cities"],
            "total_cities_count": cr5_data["total_cities_count"],
            "cities": city_data["cities"], "provinces": prov_data,
        })
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/city-category-matrix", methods=["GET"])
def get_city_category_matrix():
    session = SessionLocal()
    try:
        top_n = _int_param("top_n_cities", 15, hi=30)
        data = AnalysisEngine(session).regional.get_city_category_matrix(_parse_filters(), top_n)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


# ============================================================
# 技能词云
# ============================================================

@api_bp.route("/analysis/skills-frequency", methods=["GET"])
def get_skills_frequency():
    session = SessionLocal()
    try:
        top_n = _int_param("top", 100, hi=200)
        data = AnalysisEngine(session).skills.get_skill_frequency(_parse_filters(), top_n)
        total = sum(item["count"] for item in data) if data else 0
        return success_response(data={"total_skill_occurrences": total, "unique_skills": len(data), "skills": data})
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/skills-cooccurrence", methods=["GET"])
def get_skills_cooccurrence():
    session = SessionLocal()
    try:
        top_n = _int_param("top", 50, hi=100)
        data = AnalysisEngine(session).skills.get_skill_cooccurrence(_parse_filters(), top_n)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/skills-by-category", methods=["GET"])
def get_skills_by_category():
    session = SessionLocal()
    try:
        top_n = _int_param("top", 20, hi=50)
        data = AnalysisEngine(session).skills.get_top_skills_by_category(_parse_filters(), top_n)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/skills-wordcloud", methods=["GET"])
def get_skills_wordcloud():
    session = SessionLocal()
    try:
        top_n = _int_param("top", 100, hi=200)
        data = AnalysisEngine(session).skills.generate_wordcloud_data(_parse_filters(), top_n)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


# ============================================================
# 创新功能
# ============================================================

@api_bp.route("/analysis/platform-compare", methods=["POST"])
def platform_compare():
    """
    跨平台薪资对比引擎。

    POST body (JSON):
        {
            "group_by": "job_category",  // 分组维度: job_category / city / experience
            "city": "北京",              // 可选筛选
            "job_category": "技术"       // 可选筛选
        }

    Returns:
        各平台在同一分组维度下的薪资差异对比。
    """
    session = SessionLocal()
    try:
        from ..analysis.innovation import PlatformComparisonService

        body = request.get_json(silent=True) or {}
        filters = AnalysisFilters(
            city=(body.get("city") or "").strip() or None,
            job_category=(body.get("job_category") or "").strip() or None,
            experience=(body.get("experience") or "").strip() or None,
        )
        group_by = body.get("group_by", "job_category").strip()

        service = PlatformComparisonService(session)
        data = service.compare(filters, group_by)

        return success_response(data=data)
    except Exception as e:
        return error_response(message=f"平台对比失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/job-score", methods=["GET"])
def get_job_score():
    """
    岗位竞争力评分。

    Query 参数:
        job_id - 岗位唯一标识（必填）。

    Returns:
        五维评分结果（薪资/公司/福利/经验友好度/需求热度）。
    """
    session = SessionLocal()
    try:
        from ..analysis.innovation import JobScoringService

        job_id = request.args.get("job_id", "").strip()
        if not job_id:
            return error_response(message="缺少必填参数 job_id", code=400)

        service = JobScoringService(session)
        result = service.score_job(job_id)

        if result is None:
            return error_response(message=f"岗位不存在: {job_id}", code=404)

        return success_response(data=result)
    except Exception as e:
        return error_response(message=f"岗位评分失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/analysis/predict-salary", methods=["POST"])
def predict_salary():
    """
    薪资预测小工具。

    POST body (JSON):
        {
            "city": "北京",
            "job_category": "技术",
            "experience": "3-5年"
        }

    Returns:
        预测的薪资范围和置信度。
    """
    session = SessionLocal()
    try:
        from ..analysis.innovation import SalaryPredictionService

        body = request.get_json(silent=True) or {}
        city = (body.get("city") or "").strip()
        job_category = (body.get("job_category") or "").strip()
        experience = (body.get("experience") or "").strip()

        if not all([city, job_category, experience]):
            missing = []
            if not city: missing.append("city")
            if not job_category: missing.append("job_category")
            if not experience: missing.append("experience")
            return error_response(
                message=f"缺少必填参数: {', '.join(missing)}", code=400
            )

        service = SalaryPredictionService(session)
        result = service.predict(city, job_category, experience)

        return success_response(data=result)
    except Exception as e:
        return error_response(message=f"薪资预测失败: {str(e)}", code=500)
    finally:
        session.close()


# ============================================================
# 筛选器选项
# ============================================================

@api_bp.route("/filters/options", methods=["GET"])
def get_filters_options():
    """获取所有筛选器的可选值（城市、岗位大类、平台、经验、学历等）。"""
    from sqlalchemy import func
    from ..models.job import Job

    session = SessionLocal()
    try:
        base = session.query(Job).filter(Job.status == "有效")

        cities = sorted(
            r[0] for r in base.with_entities(Job.city).filter(Job.city != "").distinct().all()
        )
        categories = sorted(
            r[0] for r in base.with_entities(Job.job_category).filter(
                Job.job_category.isnot(None), Job.job_category != ""
            ).distinct().all()
        )
        platforms = sorted(
            r[0] for r in base.with_entities(Job.platform).distinct().all()
        )
        experiences = ["应届生", "1-3年", "3-5年", "5-10年", "10年以上", "不限"]
        educations = ["不限", "大专", "本科", "硕士", "博士"]

        salary_range_row = base.with_entities(
            func.min(Job.salary_min), func.max(Job.salary_max)
        ).filter(
            Job.salary_type != "面议",
            Job.salary_min.isnot(None),
            Job.salary_max.isnot(None),
        ).first()

        salary_range = {
            "min": int(salary_range_row[0]) if salary_range_row and salary_range_row[0] else 0,
            "max": int(salary_range_row[1]) if salary_range_row and salary_range_row[1] else 50000,
        }

        return success_response(data={
            "cities": cities,
            "job_categories": categories,
            "platforms": platforms,
            "experiences": experiences,
            "educations": educations,
            "salary_range": salary_range,
        })
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


# ============================================================
# 城市元数据（供前端地图组件使用）
# ============================================================

@api_bp.route("/cities/metadata", methods=["GET"])
def get_cities_metadata():
    """返回 30 城市坐标、图标、省份、区域等元数据。"""
    try:
        from app.data.city_metadata import get_city_list
        cities = get_city_list()
        return success_response(data={"cities": cities, "total": len(cities)})
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)


# ============================================================
# Task 6-B: Redis 缓存加速对比
# ============================================================

@api_bp.route("/analysis/benchmark", methods=["GET"])
def get_cache_benchmark():
    """
    Redis 缓存加速性能对比 — 对比首次请求（无缓存）和第二次请求（Redis 命中）的耗时。

    Returns:
        {first_request_ms, second_request_ms, speedup, redis_available}
    """
    import time
    from ..analysis.redis_cache import redis_cache

    session = SessionLocal()
    try:
        filters = _parse_filters()
        params_hash = filters.to_params_hash()
        engine = AnalysisEngine(session)

        # 清除该键的缓存，确保第一次请求走真实路径
        redis_cache.invalidate("benchmark")

        # ---- 第一次：无缓存 ----
        t1 = time.perf_counter()
        result1 = engine.ranking.get_category_ranking(filters, top_n=10)
        elapsed1 = round((time.perf_counter() - t1) * 1000, 1)

        # 写入 Redis 缓存
        redis_cache.set("benchmark", params_hash, {"result": result1}, ttl=300)

        # ---- 第二次：Redis 命中 ----
        t2 = time.perf_counter()
        cached = redis_cache.get("benchmark", params_hash)
        if cached:
            result2 = cached.get("result", [])
        else:
            result2 = engine.ranking.get_category_ranking(filters, top_n=10)
        elapsed2 = round((time.perf_counter() - t2) * 1000, 1)

        speedup = round(elapsed1 / elapsed2, 1) if elapsed2 > 0 else 0

        return success_response(data={
            "first_request_ms": elapsed1,
            "second_request_ms": elapsed2,
            "speedup": speedup,
            "cache_layer": "Redis L1 (300s TTL) + DB L2 (3600s TTL)",
            "redis_available": redis_cache.available,
            "result_preview": result1[:3],
        })
    except Exception as e:
        return error_response(message=f"性能测试失败: {str(e)}", code=500)
    finally:
        session.close()


# ============================================================
# Task 6-C: Celery 异步任务
# ============================================================

@api_bp.route("/tasks/report", methods=["POST"])
def submit_async_report():
    """
    提交异步分析报告生成任务 — 展示 Celery 异步任务流程。

    POST body: {"city": "北京", "job_category": "技术"}
    Returns: {"task_id": "...", "status": "pending"}
    """
    import uuid

    body = request.get_json(silent=True) or {}
    city = (body.get("city") or "全部").strip()
    category = (body.get("job_category") or "全部").strip()

    try:
        from app.tasks import generate_analysis_report

        # 尝试通过 Celery broker 提交任务
        task = generate_analysis_report.delay({"city": city, "job_category": category})
        task_id = task.id
        broker_mode = True
    except Exception:
        # Celery broker 不可用，fallback 模式：后台线程直接执行
        task_id = f"fallback-{uuid.uuid4().hex[:12]}"
        import threading
        from app.tasks import _run_report
        t = threading.Thread(
            target=_run_report,
            args=(task_id, {"city": city, "job_category": category}),
            daemon=True,
        )
        t.start()
        broker_mode = False

    return success_response(data={
        "task_id": task_id,
        "status": "pending",
        "broker_mode": broker_mode,
        "message": (
            f"报告生成任务已提交（{city} · {category}），"
            f"轮询 GET /api/v1/tasks/{task_id}/status 查看进度"
        ),
    })


@api_bp.route("/tasks/<task_id>/status", methods=["GET"])
def get_task_status(task_id: str):
    """
    查询异步任务进度（前端轮询此接口）。

    Path: /api/v1/tasks/<task_id>/status
    Returns: {task_id, status, progress, result, error}
    """
    try:
        from app.tasks import get_task_status as query_status

        status = query_status(task_id)

        if status is None:
            from app.celery_app import celery_app
            result = celery_app.AsyncResult(task_id)
            if result.state == "FAILURE":
                status = {"task_id": task_id, "status": "failed", "progress": 0,
                          "result": None, "error": str(result.info) if result.info else "Unknown error"}
            else:
                status = {"task_id": task_id, "status": "pending", "progress": 0,
                          "result": None, "error": None}

        return success_response(data=status)
    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
