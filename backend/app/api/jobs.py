"""
岗位数据 API 接口
==================
提供岗位信息的查询、筛选和统计功能。

端点：
- GET /api/v1/jobs              岗位列表（分页+多维度筛选）
- GET /api/v1/jobs/<job_id>     岗位详情
- GET /api/v1/jobs/stats/overview  岗位概览统计

AI生成，待人工审查。
"""

from flask import request
from sqlalchemy import func, and_

from . import api_bp
from ..database import SessionLocal
from ..models.job import Job
from ..utils import success_response, error_response, pagination_info, parse_pagination_args


@api_bp.route("/jobs", methods=["GET"])
def get_jobs():
    """
    获取岗位列表 — 支持多维度筛选和分页。

    Query 参数:
        keyword    - 岗位名称模糊搜索
        city       - 城市筛选
        experience - 经验要求筛选
        education  - 学历要求筛选
        platform   - 平台筛选
        job_category - 岗位大类筛选
        salary_min - 最低薪资
        salary_max - 最高薪资
        page       - 页码 (默认1)
        per_page   - 每页条数 (默认20, 最大100)

    Returns:
        统一格式的分页岗位列表。
    """
    # 解析分页参数
    page, per_page = parse_pagination_args(request.args)

    session = SessionLocal()
    try:
        # 构建查询条件
        query = session.query(Job)

        # 关键词模糊搜索（匹配 title 和 title_raw）
        keyword = request.args.get("keyword", "").strip()
        if keyword:
            query = query.filter(
                Job.title.contains(keyword) | Job.title_raw.contains(keyword)
            )

        # 城市筛选
        city = request.args.get("city", "").strip()
        if city:
            query = query.filter(Job.city == city)

        # 经验要求筛选
        experience = request.args.get("experience", "").strip()
        if experience:
            query = query.filter(Job.experience == experience)

        # 学历要求筛选
        education = request.args.get("education", "").strip()
        if education:
            query = query.filter(Job.education == education)

        # 平台筛选
        platform = request.args.get("platform", "").strip()
        if platform:
            query = query.filter(Job.platform == platform)

        # 岗位大类筛选
        job_category = request.args.get("job_category", "").strip()
        if job_category:
            query = query.filter(Job.job_category == job_category)

        # 薪资范围筛选
        try:
            salary_min = request.args.get("salary_min")
            if salary_min is not None:
                salary_min = int(salary_min)
                query = query.filter(
                    Job.salary_max >= salary_min,
                    Job.salary_type != "面议",
                )
        except (ValueError, TypeError):
            pass

        try:
            salary_max = request.args.get("salary_max")
            if salary_max is not None:
                salary_max = int(salary_max)
                query = query.filter(
                    Job.salary_min <= salary_max,
                    Job.salary_type != "面议",
                )
        except (ValueError, TypeError):
            pass

        # 只返回有效岗位
        query = query.filter(Job.status == "有效")

        # 按发布时间倒序
        # MySQL: DESC 排序时 NULL 默认在末尾，无需 nullslast()
        query = query.order_by(Job.published_at.desc(), Job.crawled_at.desc())

        # 分页
        total = query.count()
        jobs = query.offset((page - 1) * per_page).limit(per_page).all()

        # 序列化
        data = [job.to_dict() for job in jobs]
        pagination = pagination_info(page, per_page, total)

        return success_response(data=data, pagination=pagination)

    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job_detail(job_id: str):
    """
    获取单个岗位详情。

    Path 参数:
        job_id - 岗位唯一标识。

    Returns:
        岗位详细信息或404。
    """
    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        if job is None:
            return error_response(message="岗位不存在", code=404)

        return success_response(data=job.to_dict())

    except Exception as e:
        return error_response(message=f"查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/jobs/stats/overview", methods=["GET"])
def get_jobs_overview():
    """
    获取岗位概览统计数据。支持与 /api/v1/jobs 相同的筛选参数。

    Query 参数（可选）：
        city, platform, experience, education, job_category, industry,
        salary_min, salary_max, date_from, date_to

    Returns:
        包含以下统计维度的数据：
        - total: 当前有效岗位总数
        - this_week_new: 本周新增数
        - avg_salary_min / avg_salary_max: 平均薪资范围（不含面议）
        - city_count: 城市分布统计
        - platform_count: 平台分布统计
        - experience_dist: 经验要求分布
        - education_dist: 学历要求分布
        - top_job_categories: 热门岗位大类 Top 5
    """
    session = SessionLocal()
    try:
        from datetime import datetime, timedelta
        from ..analysis import AnalysisFilters

        # 解析筛选条件
        filters = AnalysisFilters(
            city=request.args.get("city", "").strip() or None,
            job_category=request.args.get("job_category", "").strip() or None,
            industry=request.args.get("industry", "").strip() or None,
            experience=request.args.get("experience", "").strip() or None,
            education=request.args.get("education", "").strip() or None,
            platform=request.args.get("platform", "").strip() or None,
            date_from=request.args.get("date_from", "").strip() or None,
            date_to=request.args.get("date_to", "").strip() or None,
        )

        base_query = filters.apply_to_query(
            session.query(Job).filter(Job.status == "有效")
        )
        total = base_query.count()

        # 本周新增：按数据集中最新发布日期计算
        latest_pub = base_query.with_entities(func.max(Job.published_at)).scalar()
        week_ago = latest_pub - timedelta(days=7) if latest_pub else datetime.utcnow() - timedelta(days=7)
        this_week_new = base_query.filter(Job.published_at >= week_ago).count()

        # 平均薪资（不含面议）
        salary_query = base_query.filter(
            Job.salary_type != "面议",
            Job.salary_min.isnot(None),
            Job.salary_max.isnot(None),
        )
        avg_salary = salary_query.with_entities(
            func.round(func.avg(Job.salary_min)),
            func.round(func.avg(Job.salary_max)),
        ).first()

        # 城市分布
        city_dist = (
            base_query.with_entities(Job.city, func.count(Job.job_id).label("count"))
            .group_by(Job.city)
            .order_by(func.count(Job.job_id).desc())
            .all()
        )

        # 平台分布
        platform_dist = (
            base_query.with_entities(Job.platform, func.count(Job.job_id).label("count"))
            .group_by(Job.platform)
            .order_by(func.count(Job.job_id).desc())
            .all()
        )

        # 经验要求分布
        experience_dist = (
            base_query.with_entities(Job.experience, func.count(Job.job_id).label("count"))
            .group_by(Job.experience)
            .all()
        )

        # 学历要求分布
        education_dist = (
            base_query.with_entities(Job.education, func.count(Job.job_id).label("count"))
            .group_by(Job.education)
            .all()
        )

        # 热门岗位大类 Top 5
        top_categories = (
            base_query.with_entities(Job.job_category, func.count(Job.job_id).label("count"))
            .filter(Job.job_category.isnot(None))
            .group_by(Job.job_category)
            .order_by(func.count(Job.job_id).desc())
            .limit(5)
            .all()
        )

        data = {
            "total": total,
            "this_week_new": this_week_new,
            "avg_salary_min": int(avg_salary[0]) if avg_salary and avg_salary[0] else None,
            "avg_salary_max": int(avg_salary[1]) if avg_salary and avg_salary[1] else None,
            "city_distribution": [{"city": c, "count": n} for c, n in city_dist],
            "platform_distribution": [{"platform": p, "count": n} for p, n in platform_dist],
            "experience_distribution": [{"experience": e, "count": n} for e, n in experience_dist],
            "education_distribution": [{"education": e, "count": n} for e, n in education_dist],
            "top_job_categories": [{"category": c, "count": n} for c, n in top_categories],
        }

        return success_response(data=data)

    except Exception as e:
        return error_response(message=f"统计查询失败: {str(e)}", code=500)
    finally:
        session.close()


@api_bp.route("/jobs/cities", methods=["GET"])
def get_jobs_cities_metadata():
    """
    获取城市元数据列表 — 30 个中国主要城市的名称、经纬度、图标。

    Returns:
        [{name, lng, lat, icon, province, region}, ...]
    """
    from ..data.city_metadata import get_city_list

    try:
        cities = get_city_list()
        return success_response(data={
            "total": len(cities),
            "cities": cities,
        })
    except Exception as e:
        return error_response(message=f"城市元数据查询失败: {str(e)}", code=500)
