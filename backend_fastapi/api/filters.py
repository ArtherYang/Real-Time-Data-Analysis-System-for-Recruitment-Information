"""筛选器选项 API — FastAPI 版本"""

from fastapi import APIRouter
from sqlalchemy import func

from app.database import get_db
from app.models.job import Job

router = APIRouter(tags=["筛选器"])


@router.get("/filters/options")
def filters_options():
    session = next(get_db())
    try:
        base = session.query(Job).filter(Job.status == "有效")
        cities = sorted(r[0] for r in base.with_entities(Job.city)
                        .filter(Job.city != "").distinct().all())
        categories = sorted(r[0] for r in base.with_entities(Job.job_category)
                            .filter(Job.job_category.isnot(None), Job.job_category != "").distinct().all())
        platforms = sorted(r[0] for r in base.with_entities(Job.platform).distinct().all())

        salary_row = base.with_entities(func.min(Job.salary_min), func.max(Job.salary_max)) \
            .filter(Job.salary_type != "面议", Job.salary_min.isnot(None), Job.salary_max.isnot(None)).first()

        salary_range = {
            "min": int(salary_row[0]) if salary_row and salary_row[0] else 0,
            "max": int(salary_row[1]) if salary_row and salary_row[1] else 50000,
        }

        return {"code": 200, "message": "success", "data": {
            "cities": cities,
            "job_categories": categories,
            "platforms": platforms,
            "experiences": ["应届生", "1-3年", "3-5年", "5-10年", "10年以上", "不限"],
            "educations": ["不限", "大专", "本科", "硕士", "博士"],
            "salary_range": salary_range,
        }}
    finally:
        session.close()
