"""
地域分析服务
============
提供岗位在全国各城市/地区的分布分析，包括：
- 城市岗位分布排行
- 省份级别聚合统计
- CR5 岗位集中度指数
- 城市×岗位大类交叉分布矩阵

省份映射：内置中国主要城市到省份的映射字典。
未匹配城市归入"其他"。

AI生成，待人工审查。
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.job import Job
from .cache import AnalysisCacheManager
from .filters import AnalysisFilters


# ============================================================
# 中国主要城市 → 省份/直辖市映射表
# ============================================================
CITY_TO_PROVINCE: dict[str, str] = {
    # 直辖市
    "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
    # 广东
    "广州": "广东", "深圳": "广东", "东莞": "广东", "佛山": "广东",
    "珠海": "广东", "惠州": "广东", "中山": "广东",
    # 江苏
    "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏",
    "南通": "江苏", "徐州": "江苏", "扬州": "江苏",
    # 浙江
    "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "嘉兴": "浙江",
    # 山东
    "济南": "山东", "青岛": "山东", "烟台": "山东", "潍坊": "山东",
    # 四川
    "成都": "四川", "绵阳": "四川",
    # 湖北
    "武汉": "湖北", "宜昌": "湖北",
    # 湖南
    "长沙": "湖南", "株洲": "湖南",
    # 福建
    "厦门": "福建", "福州": "福建", "泉州": "福建",
    # 陕西
    "西安": "陕西",
    # 河南
    "郑州": "河南", "洛阳": "河南",
    # 安徽
    "合肥": "安徽", "芜湖": "安徽",
    # 辽宁
    "沈阳": "辽宁", "大连": "辽宁",
    # 其他省份省会
    "南昌": "江西", "昆明": "云南", "贵阳": "贵州",
    "南宁": "广西", "海口": "海南", "石家庄": "河北",
    "太原": "山西", "呼和浩特": "内蒙古", "哈尔滨": "黑龙江",
    "长春": "吉林", "兰州": "甘肃", "西宁": "青海",
    "银川": "宁夏", "乌鲁木齐": "新疆", "拉萨": "西藏",
}


class RegionalAnalysisService:
    """
    地域分布分析服务。
    """

    CACHE_TYPE = "city_dist"

    def __init__(self, db: Session, cache: AnalysisCacheManager):
        """
        初始化服务。

        Args:
            db: SQLAlchemy 数据库会话。
            cache: 缓存管理器实例。
        """
        self.db = db
        self.cache = cache

    def get_city_distribution(
        self, filters: AnalysisFilters, top_n: int = 50
    ) -> dict:
        """
        获取城市岗位分布数据。

        Args:
            filters: 查询筛选参数。
            top_n: 返回城市数量，默认 50。

        Returns:
            {total, cities: [{city, count, percentage, avg_salary_min, avg_salary_max}, ...]}
        """
        top_n = min(max(top_n, 1), 100)

        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "city_distribution" in cached:
            result = cached["city_distribution"]
            result["cities"] = result["cities"][:top_n]
            return result

        base_query = filters.apply_to_query(self.db.query(Job))
        total = base_query.count()

        results = (
            base_query.with_entities(
                Job.city,
                func.count(Job.job_id).label("count"),
                func.round(func.avg(Job.salary_min)).label("avg_salary_min"),
                func.round(func.avg(Job.salary_max)).label("avg_salary_max"),
            )
            .group_by(Job.city)
            .order_by(func.count(Job.job_id).desc())
            .limit(top_n)
            .all()
        )

        cities = [
            {
                "city": row[0],
                "count": row[1],
                "percentage": round(row[1] / total * 100, 1) if total > 0 else 0,
                "avg_salary_min": int(row[2]) if row[2] else None,
                "avg_salary_max": int(row[3]) if row[3] else None,
            }
            for row in results
        ]

        data = {"total": total, "cities": cities}

        self.cache.set(self.CACHE_TYPE, params_hash, {"city_distribution": data})
        return data

    def get_cr5_concentration(self, filters: AnalysisFilters) -> dict:
        """
        计算 CR5 岗位集中度指数（TOP5 城市岗位占比）。

        Args:
            filters: 查询筛选参数。

        Returns:
            {cr5_pct, top_cities: [{city, count, share_pct}], total_cities_count}
        """
        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "cr5" in cached:
            return cached["cr5"]

        base_query = filters.apply_to_query(self.db.query(Job))
        total = base_query.count()

        results = (
            base_query.with_entities(
                Job.city,
                func.count(Job.job_id).label("count"),
            )
            .group_by(Job.city)
            .order_by(func.count(Job.job_id).desc())
            .all()
        )

        top5 = results[:5]
        top5_total = sum(r[1] for r in top5)

        data = {
            "cr5_pct": round(top5_total / total * 100, 1) if total > 0 else 0,
            "top_cities": [
                {
                    "city": r[0],
                    "count": r[1],
                    "share_pct": round(r[1] / total * 100, 1) if total > 0 else 0,
                }
                for r in top5
            ],
            "total_cities_count": len(results),
            "total_jobs": total,
        }

        existing = cached or {}
        existing["cr5"] = data
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return data

    def get_province_aggregation(self, filters: AnalysisFilters) -> list[dict]:
        """
        获取省份级别聚合统计。

        使用内置的 city_to_province 映射表，将城市聚合到省份。
        未在映射表中的城市归入"其他"。

        Args:
            filters: 查询筛选参数。

        Returns:
            [{province, count, percentage, cities_count}, ...] 按 count 降序。
        """
        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "province" in cached:
            return cached["province"]

        base_query = filters.apply_to_query(self.db.query(Job))
        total = base_query.count()

        results = (
            base_query.with_entities(
                Job.city,
                func.count(Job.job_id).label("count"),
            )
            .group_by(Job.city)
            .all()
        )

        # 聚合到省份
        province_counts: dict[str, dict] = {}
        for city, count in results:
            province = CITY_TO_PROVINCE.get(city, "其他")
            if province not in province_counts:
                province_counts[province] = {
                    "province": province,
                    "count": 0,
                    "cities": set(),
                }
            province_counts[province]["count"] += count
            province_counts[province]["cities"].add(city)

        data = []
        for prov_info in province_counts.values():
            data.append({
                "province": prov_info["province"],
                "count": prov_info["count"],
                "percentage": round(prov_info["count"] / total * 100, 1) if total > 0 else 0,
                "cities_count": len(prov_info["cities"]),
            })

        data.sort(key=lambda x: x["count"], reverse=True)

        existing = cached or {}
        existing["province"] = data
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return data

    def get_city_category_matrix(
        self, filters: AnalysisFilters, top_n_cities: int = 15
    ) -> dict:
        """
        获取城市×岗位大类交叉分布矩阵。

        Args:
            filters: 查询筛选参数。
            top_n_cities: 取前 N 个城市。

        Returns:
            {cities: [...], categories: [...], data: [[count, ...], ...]}
        """
        top_n_cities = min(max(top_n_cities, 1), 30)

        params_hash = filters.to_params_hash()
        cached = self.cache.get(self.CACHE_TYPE, params_hash)
        if cached and "city_category_matrix" in cached:
            return cached["city_category_matrix"]

        base_query = filters.apply_to_query(self.db.query(Job))

        # 前 N 城市
        top_cities = [
            r[0] for r in (
                base_query.with_entities(Job.city, func.count(Job.job_id))
                .group_by(Job.city)
                .order_by(func.count(Job.job_id).desc())
                .limit(top_n_cities)
                .all()
            )
        ]

        # 所有岗位大类
        cat_results = (
            base_query.with_entities(Job.job_category, func.count(Job.job_id))
            .filter(Job.job_category.isnot(None), Job.job_category != "")
            .group_by(Job.job_category)
            .order_by(func.count(Job.job_id).desc())
            .all()
        )
        categories = [r[0] for r in cat_results]

        # 构建交叉矩阵
        matrix_data = []
        for city in top_cities:
            row = []
            for cat in categories:
                count = (
                    base_query.filter(Job.city == city, Job.job_category == cat)
                    .count()
                )
                row.append(count)
            matrix_data.append(row)

        result = {
            "cities": top_cities,
            "categories": categories,
            "data": matrix_data,
        }

        existing = cached or {}
        existing["city_category_matrix"] = result
        self.cache.set(self.CACHE_TYPE, params_hash, existing)

        return result
