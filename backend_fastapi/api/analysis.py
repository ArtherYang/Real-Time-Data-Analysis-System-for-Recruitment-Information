"""分析数据 API — FastAPI 版本"""

from typing import Optional
from fastapi import APIRouter, Query

from app.database import get_db
from app.analysis import AnalysisEngine, AnalysisFilters

router = APIRouter(tags=["数据分析"])


def _filters(**kw) -> AnalysisFilters:
    return AnalysisFilters(**{k: v for k, v in kw.items() if v is not None})


def _int(name, default, lo=1, hi=200):
    """从函数参数取 int，不适用 FastAPI Query（已在签名处处理）"""
    return default


@router.get("/analysis/hot-jobs")
def hot_jobs(
    city: Optional[str] = Query(None),
    job_category: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    experience: Optional[str] = Query(None),
    education: Optional[str] = Query(None),
    top: int = Query(20, ge=1, le=100),
):
    session = next(get_db())
    try:
        f = _filters(city=city, job_category=job_category, platform=platform,
                      experience=experience, education=education)
        data = AnalysisEngine(session).ranking.get_category_ranking(f, top)
        return {"code": 200, "message": "success", "data": data}
    finally:
        session.close()


@router.get("/analysis/salary-distribution")
def salary_distribution(
    city: Optional[str] = Query(None),
    job_category: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    experience: Optional[str] = Query(None),
    education: Optional[str] = Query(None),
    group_by: str = Query("job_category"),
    top: int = Query(20, ge=1, le=100),
):
    session = next(get_db())
    try:
        f = _filters(city=city, job_category=job_category, platform=platform,
                      experience=experience, education=education)
        data = AnalysisEngine(session).salary.get_salary_stats(f, group_by, top)
        return {"code": 200, "message": "success", "data": {"group_by": group_by, "items": data}}
    finally:
        session.close()


@router.get("/analysis/city-distribution")
def city_distribution(
    city: Optional[str] = Query(None),
    job_category: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    top: int = Query(50, ge=1, le=100),
):
    session = next(get_db())
    try:
        f = _filters(city=city, job_category=job_category, platform=platform)
        engine = AnalysisEngine(session)
        city_data = engine.regional.get_city_distribution(f, top)
        cr5_data = engine.regional.get_cr5_concentration(f)
        prov_data = engine.regional.get_province_aggregation(f)
        return {"code": 200, "message": "success", "data": {
            "total": city_data["total"], "cr5": cr5_data["cr5_pct"],
            "cr5_detail": cr5_data["top_cities"],
            "total_cities_count": cr5_data["total_cities_count"],
            "cities": city_data["cities"], "provinces": prov_data,
        }}
    finally:
        session.close()


@router.get("/analysis/skills-frequency")
def skills_frequency(
    job_category: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    top: int = Query(100, ge=1, le=200),
):
    session = next(get_db())
    try:
        f = _filters(job_category=job_category, platform=platform)
        data = AnalysisEngine(session).skills.get_skill_frequency(f, top)
        total = sum(item["count"] for item in data) if data else 0
        return {"code": 200, "message": "success", "data": {
            "total_skill_occurrences": total, "unique_skills": len(data), "skills": data,
        }}
    finally:
        session.close()


@router.get("/analysis/skills-wordcloud")
def skills_wordcloud(
    job_category: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    top: int = Query(100, ge=1, le=200),
):
    session = next(get_db())
    try:
        f = _filters(job_category=job_category, platform=platform)
        data = AnalysisEngine(session).skills.generate_wordcloud_data(f, top)
        return {"code": 200, "message": "success", "data": data}
    finally:
        session.close()


@router.get("/analysis/trend")
def trend(
    city: Optional[str] = Query(None),
    job_category: Optional[str] = Query(None),
    granularity: str = Query("weekly"),
):
    session = next(get_db())
    try:
        f = _filters(city=city, job_category=job_category)
        data = AnalysisEngine(session).ranking.get_trend_data(f, job_category, granularity)
        return {"code": 200, "message": "success", "data": {
            "granularity": granularity, "category": job_category, "data_points": data,
        }}
    finally:
        session.close()


@router.get("/cities/metadata")
def cities_metadata():
    try:
        from app.data.city_metadata import get_city_list
        cities = get_city_list()
        return {"code": 200, "message": "success", "data": {"cities": cities, "total": len(cities)}}
    except Exception:
        return {"code": 500, "message": "城市元数据加载失败", "data": None}
