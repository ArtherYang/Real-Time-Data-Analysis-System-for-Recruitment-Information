"""岗位数据 API — FastAPI 版本"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import func

from app.database import get_db
from app.models.job import Job

router = APIRouter(tags=["岗位数据"])


@router.get("/jobs")
def get_jobs(
    keyword: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    experience: Optional[str] = Query(None),
    education: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    job_category: Optional[str] = Query(None),
    salary_min: Optional[int] = Query(None),
    salary_max: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    session = next(get_db())
    try:
        q = session.query(Job).filter(Job.status == "有效")
        if keyword:
            q = q.filter(Job.title.contains(keyword) | Job.title_raw.contains(keyword))
        if city:           q = q.filter(Job.city == city)
        if experience:     q = q.filter(Job.experience == experience)
        if education:      q = q.filter(Job.education == education)
        if platform:       q = q.filter(Job.platform == platform)
        if job_category:   q = q.filter(Job.job_category == job_category)
        if salary_min is not None:
            q = q.filter(Job.salary_max >= salary_min, Job.salary_type != "面议")
        if salary_max is not None:
            q = q.filter(Job.salary_min <= salary_max, Job.salary_type != "面议")

        total = q.count()
        jobs = q.order_by(Job.published_at.desc().nullslast(), Job.crawled_at.desc()) \
                .offset((page - 1) * per_page).limit(per_page).all()

        return {
            "code": 200, "message": "success",
            "data": [j.to_dict() for j in jobs],
            "pagination": {"page": page, "per_page": per_page, "total": total,
                           "pages": max(1, (total + per_page - 1) // per_page)},
        }
    finally:
        session.close()


@router.get("/jobs/{job_id}")
def get_job_detail(job_id: str):
    session = next(get_db())
    try:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return {"code": 404, "message": "岗位不存在", "data": None}
        return {"code": 200, "message": "success", "data": job.to_dict()}
    finally:
        session.close()


@router.get("/jobs/stats/overview")
def get_jobs_overview():
    session = next(get_db())
    try:
        base = session.query(Job).filter(Job.status == "有效")
        total = base.count()
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_week = base.filter(Job.crawled_at >= week_ago).count()

        sal_q = base.filter(Job.salary_type != "面议",
                            Job.salary_min.isnot(None), Job.salary_max.isnot(None))
        avg_sal = sal_q.with_entities(
            func.round(func.avg(Job.salary_min)), func.round(func.avg(Job.salary_max))
        ).first()

        city_dist = [{"city": r[0], "count": r[1]} for r in
                     base.with_entities(Job.city, func.count(Job.job_id))
                     .group_by(Job.city).order_by(func.count(Job.job_id).desc()).all()]

        platform_dist = [{"platform": r[0], "count": r[1]} for r in
                         base.with_entities(Job.platform, func.count(Job.job_id))
                         .group_by(Job.platform).order_by(func.count(Job.job_id).desc()).all()]

        exp_dist = [{"experience": r[0], "count": r[1]} for r in
                    base.with_entities(Job.experience, func.count(Job.job_id))
                    .group_by(Job.experience).all()]

        edu_dist = [{"education": r[0], "count": r[1]} for r in
                    base.with_entities(Job.education, func.count(Job.job_id))
                    .group_by(Job.education).all()]

        top_cats = [{"category": r[0], "count": r[1]} for r in
                    base.with_entities(Job.job_category, func.count(Job.job_id))
                    .filter(Job.job_category.isnot(None))
                    .group_by(Job.job_category).order_by(func.count(Job.job_id).desc()).limit(5).all()]

        return {"code": 200, "message": "success", "data": {
            "total": total, "this_week_new": new_week,
            "avg_salary_min": int(avg_sal[0]) if avg_sal and avg_sal[0] else None,
            "avg_salary_max": int(avg_sal[1]) if avg_sal and avg_sal[1] else None,
            "city_distribution": city_dist, "platform_distribution": platform_dist,
            "experience_distribution": exp_dist, "education_distribution": edu_dist,
            "top_job_categories": top_cats,
        }}
    finally:
        session.close()
