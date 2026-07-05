"""
Dashboard API 接口
==================
仪表盘聚合接口 — 市场行情概览、热度排行、薪资趋势、城市分布。
部分端点复用 AnalysisEngine 服务层，提供前端友好的响应格式。

AI生成，待人工审查。
"""

from flask import request

from . import api_bp
from ..analysis import AnalysisEngine, AnalysisFilters
from ..database import SessionLocal
from ..data.city_metadata import get_city_list, get_city_coords, CITY_METADATA
from ..utils import success_response, error_response


def _parse_filters() -> AnalysisFilters:
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
# Dashboard — 市场行情概览
# ============================================================

@api_bp.route("/dashboard/overview", methods=["GET"])
def dashboard_overview():
    """市场行情概览 — 总岗位数、本周新增、热门城市、平均薪资。"""
    session = SessionLocal()
    try:
        from datetime import datetime, timedelta
        from ..models.job import Job
        from sqlalchemy import func

        filters = _parse_filters()
        base = filters.apply_to_query(
            session.query(Job).filter(Job.status == "有效")
        )
        total = base.count()

        week_ago = datetime.utcnow() - timedelta(days=7)
        new_this_week = base.filter(Job.crawled_at >= week_ago).count()

        salary_q = base.filter(
            Job.salary_type != "面议",
            Job.salary_min.isnot(None),
            Job.salary_max.isnot(None),
        )
        avg_salary = salary_q.with_entities(
            func.round(func.avg(Job.salary_min)),
            func.round(func.avg(Job.salary_max)),
        ).first()

        top_cities = (
            base.with_entities(Job.city, func.count(Job.job_id).label("count"))
            .group_by(Job.city)
            .order_by(func.count(Job.job_id).desc())
            .limit(10).all()
        )

        data = {
            "total_jobs": total,
            "new_this_week": new_this_week,
            "avg_salary_range": [
                int(avg_salary[0]) if avg_salary and avg_salary[0] else None,
                int(avg_salary[1]) if avg_salary and avg_salary[1] else None,
            ],
            "top_cities": [
                {"city": c, "count": n, "icon": CITY_METADATA.get(c, {}).get("icon", "")}
                for c, n in top_cities
            ],
        }
        return success_response(data=data)
    except Exception as e:
        return error_response(message=str(e), code=500)
    finally:
        session.close()


@api_bp.route("/dashboard/hot-jobs", methods=["GET"])
def dashboard_hot_jobs():
    """岗位热度排行 TOP N。"""
    session = SessionLocal()
    try:
        top_n = _int_param("limit", 10, hi=50)
        engine = AnalysisEngine(session)
        data = engine.ranking.get_category_ranking(_parse_filters(), top_n)
        return success_response(data=data)
    except Exception as e:
        return error_response(message=str(e), code=500)
    finally:
        session.close()


@api_bp.route("/dashboard/salary-trend", methods=["GET"])
def dashboard_salary_trend():
    """薪资趋势 — 周度薪资变化。"""
    session = SessionLocal()
    try:
        filters = _parse_filters()
        cat = request.args.get("job_category", "").strip() or None
        granularity = request.args.get("granularity", "weekly").strip()
        engine = AnalysisEngine(session)
        data = engine.ranking.get_trend_data(filters, cat, granularity)
        return success_response(data={
            "granularity": granularity,
            "category": cat,
            "data_points": data,
        })
    except Exception as e:
        return error_response(message=str(e), code=500)
    finally:
        session.close()


@api_bp.route("/dashboard/city-distribution", methods=["GET"])
def dashboard_city_distribution():
    """城市岗位分布 — 带经纬度和图标，供前端地图渲染。"""
    session = SessionLocal()
    try:
        from ..models.job import Job
        from sqlalchemy import func

        filters = _parse_filters()
        base = filters.apply_to_query(
            session.query(Job).filter(Job.status == "有效")
        )

        city_stats = (
            base.with_entities(
                Job.city,
                func.count(Job.job_id).label("count"),
                func.round(func.avg(Job.salary_min)).label("avg_min"),
                func.round(func.avg(Job.salary_max)).label("avg_max"),
            )
            .filter(Job.salary_type != "面议")
            .group_by(Job.city)
            .order_by(func.count(Job.job_id).desc())
            .all()
        )

        cities = []
        for city, count, avg_min, avg_max in city_stats:
            meta = CITY_METADATA.get(city, {})
            cities.append({
                "name": city,
                "count": count,
                "lng": meta.get("lng"),
                "lat": meta.get("lat"),
                "icon": meta.get("icon", ""),
                "province": meta.get("province", ""),
                "avg_salary_min": int(avg_min) if avg_min else None,
                "avg_salary_max": int(avg_max) if avg_max else None,
            })

        return success_response(data={
            "total_cities": len(cities),
            "cities": cities,
        })
    except Exception as e:
        return error_response(message=str(e), code=500)
    finally:
        session.close()
