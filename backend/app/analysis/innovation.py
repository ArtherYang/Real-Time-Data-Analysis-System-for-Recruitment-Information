"""
M3 数据分析引擎 — 创新功能服务
==============================
三个创新分析功能：
1. 跨平台薪资对比引擎 — 同一岗位在不同平台的薪资差异
2. 岗位竞争力评分   — 五维评分模型（薪资+公司+福利+经验友好度+需求热度）
3. 薪资预测小工具   — 基于历史数据的薪资区间预测

AI生成，待人工审查。
"""

import math
import numpy as np
from typing import Optional
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.job import Job
from .filters import AnalysisFilters


class PlatformComparisonService:
    """跨平台薪资对比引擎。"""

    def __init__(self, db: Session):
        self.db = db

    def compare(
        self,
        filters: AnalysisFilters,
        group_by: str = "job_category",
    ) -> dict:
        """
        跨平台薪资对比：同一维度下各平台的薪资差异。

        Args:
            filters: 查询筛选参数。
            group_by: 分组维度 (job_category / city / experience)。

        Returns:
            {
                "groups": [
                    {
                        "group_key": "技术",
                        "platforms": [
                            {"platform": "BOSS直聘", "count": 120, "avg_salary": 25000, "median_salary": 23000},
                            {"platform": "前程无忧", "count": 80, "avg_salary": 21000, "median_salary": 20000},
                        ],
                        "comparisons": [
                            {"pair": "BOSS直聘 vs 前程无忧", "diff_pct": 19.0, "winner": "BOSS直聘", "significant": true}
                        ]
                    }
                ],
                "summary": {
                    "highest_avg_platform": "BOSS直聘",
                    "overall_diff_max_pct": 25.0,
                    "overall_diff_max_pair": "BOSS直聘 vs 猎聘"
                }
            }
        """
        valid_groups = {"job_category", "city", "experience", "education"}
        if group_by not in valid_groups:
            group_by = "job_category"

        group_column = getattr(Job, group_by)

        # 基础查询：有效岗位、排除面议
        base_query = AnalysisFilters.exclude_negotiable_salary(
            filters.apply_to_query(self.db.query(Job))
        )

        # 获取所有 (分组, 平台) 组合的薪资统计
        results = (
            base_query.with_entities(
                group_column.label("group_key"),
                Job.platform,
                func.count(Job.job_id).label("count"),
                func.round(func.avg((Job.salary_min + Job.salary_max) / 2)).label("avg_salary"),
            )
            .filter(group_column.isnot(None), group_column != "")
            .group_by(group_column, Job.platform)
            .order_by(group_column, func.count(Job.job_id).desc())
            .all()
        )

        # 组织数据
        groups_map = defaultdict(list)
        for row in results:
            groups_map[row[0]].append({
                "platform": str(row[1]),
                "count": row[2],
                "avg_salary": int(row[3]) if row[3] else None,
            })

        # 计算中位数（需要额外查询）
        for group_key in groups_map:
            for pdata in groups_map[group_key]:
                midpoints = (
                    base_query.with_entities(
                        ((Job.salary_min + Job.salary_max) / 2).label("midpoint")
                    )
                    .filter(
                        group_column == group_key,
                        Job.platform == pdata["platform"],
                    )
                    .all()
                )
                mids = [float(r[0]) for r in midpoints if r[0] is not None]
                if mids:
                    pdata["median_salary"] = int(np.median(mids))
                    pdata["p25"] = int(np.percentile(mids, 25))
                    pdata["p75"] = int(np.percentile(mids, 75))

        # 构建对比数据
        groups_list = []
        for group_key, platforms in sorted(groups_map.items()):
            # 至少需要两个平台才能对比
            comparisons = []
            for i in range(len(platforms)):
                for j in range(i + 1, len(platforms)):
                    p1, p2 = platforms[i], platforms[j]
                    if p1["avg_salary"] and p2["avg_salary"] and p2["avg_salary"] > 0:
                        diff_pct = round(
                            (p1["avg_salary"] - p2["avg_salary"]) / p2["avg_salary"] * 100, 1
                        )
                        winner = p1["platform"] if diff_pct > 0 else p2["platform"]
                        # 显著性：差异>10%且样本量都>=5
                        significant = abs(diff_pct) > 10 and p1["count"] >= 5 and p2["count"] >= 5
                        comparisons.append({
                            "pair": f"{p1['platform']} vs {p2['platform']}",
                            "diff_pct": diff_pct,
                            "winner": winner,
                            "significant": significant,
                        })

            groups_list.append({
                "group_key": str(group_key),
                "platforms": platforms,
                "comparisons": comparisons,
            })

        # 全局汇总
        all_comparisons = []
        for g in groups_list:
            all_comparisons.extend(g["comparisons"])

        # 找差异最大的对比
        if all_comparisons:
            max_diff = max(all_comparisons, key=lambda c: abs(c["diff_pct"]))
            summary = {
                "overall_diff_max_pct": max_diff["diff_pct"],
                "overall_diff_max_pair": max_diff["pair"],
                "total_groups_compared": len(groups_list),
                "total_comparisons": len(all_comparisons),
            }
        else:
            summary = {
                "overall_diff_max_pct": 0,
                "overall_diff_max_pair": None,
                "total_groups_compared": len(groups_list),
                "total_comparisons": 0,
            }

        # 最高均薪平台
        platform_avgs = defaultdict(list)
        for g in groups_list:
            for p in g["platforms"]:
                if p["avg_salary"]:
                    platform_avgs[p["platform"]].append(p["avg_salary"])
        highest_platform = max(
            platform_avgs.items(),
            key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0,
        )[0] if platform_avgs else None
        summary["highest_avg_platform"] = highest_platform

        return {"groups": groups_list, "summary": summary}


class JobScoringService:
    """
    岗位竞争力评分引擎。

    五维评分模型（总分 0-100）：
    - 薪资分 (40%): 该岗位薪资 vs 同城市同岗位均薪
    - 公司分 (25%): 公司规模 + 公司类型
    - 福利分 (20%): 福利标签数量
    - 经验友好度 (15%): 经验要求越低越友好
    - 需求热度 (加分项): 该岗位大类近7天需求量
    """

    # 公司类型基础分
    COMPANY_TYPE_SCORE = {
        "上市公司": 25,
        "外企": 22,
        "国企": 20,
        "合资": 18,
        "民营": 15,
    }

    # 公司规模系数
    COMPANY_SIZE_MULTIPLIER = {
        "10000人以上": 1.0,
        "2000人以上": 0.95,
        "500-2000人": 0.85,
        "150-500人": 0.7,
        "50-150人": 0.5,
    }

    # 经验友好度基准
    EXPERIENCE_SCORE = {
        "不限": 15,
        "应届生": 15,
        "1-3年": 12,
        "3-5年": 8,
        "5-10年": 4,
        "10年以上": 2,
    }

    def __init__(self, db: Session):
        self.db = db

    def score_job(self, job_id: str) -> dict:
        """
        对单个岗位进行五维竞争力评分。

        Args:
            job_id: 岗位 UUID。

        Returns:
            {
                "job_id": "...",
                "title": "Python开发",
                "total_score": 78.5,
                "dimensions": {
                    "salary": {"score": 32.0, "max": 40, "detail": "..."},
                    "company": {"score": 20.0, "max": 25, "detail": "..."},
                    "welfare": {"score": 12.0, "max": 20, "detail": "..."},
                    "experience": {"score": 8.0, "max": 15, "detail": "..."},
                    "demand_bonus": {"score": 5.0, "max": 10, "detail": "..."}
                },
                "interpretation": "该岗位综合竞争力较高，薪资高于同城平均水平..."
            }
        """
        job = self.db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return None

        # 1. 薪资分 (40%)
        salary_score, salary_detail = self._calc_salary_score(job)

        # 2. 公司分 (25%)
        company_score, company_detail = self._calc_company_score(job)

        # 3. 福利分 (20%)
        welfare_score, welfare_detail = self._calc_welfare_score(job)

        # 4. 经验友好度 (15%)
        exp_score, exp_detail = self._calc_experience_score(job)

        # 5. 需求热度加分 (最高+10)
        demand_bonus, demand_detail = self._calc_demand_bonus(job)

        total = salary_score + company_score + welfare_score + exp_score + demand_bonus

        # 生成解读
        interpretation = self._generate_interpretation(
            total, salary_score, company_score, welfare_score, exp_score
        )

        return {
            "job_id": job.job_id,
            "title": job.title,
            "company": job.company,
            "city": job.city,
            "total_score": round(total, 1),
            "dimensions": {
                "salary": {"score": salary_score, "max": 40, "detail": salary_detail},
                "company": {"score": company_score, "max": 25, "detail": company_detail},
                "welfare": {"score": welfare_score, "max": 20, "detail": welfare_detail},
                "experience": {"score": exp_score, "max": 15, "detail": exp_detail},
                "demand_bonus": {"score": demand_bonus, "max": 10, "detail": demand_detail},
            },
            "interpretation": interpretation,
        }

    def _calc_salary_score(self, job: Job) -> tuple:
        """计算薪资分。"""
        if not job.salary_min or not job.salary_max or job.salary_type == "面议":
            return 0, "薪资面议，无法评分"

        job_mid = (job.salary_min + job.salary_max) / 2

        # 同城市同岗位均薪
        avg_result = (
            self.db.query(
                func.avg((Job.salary_min + Job.salary_max) / 2)
            )
            .filter(
                Job.status == "有效",
                Job.city == job.city,
                Job.job_category == job.job_category,
                Job.salary_type != "面议",
                Job.salary_min.isnot(None),
            )
            .first()
        )

        city_avg = float(avg_result[0]) if avg_result and avg_result[0] else job_mid

        if city_avg > 0:
            ratio = job_mid / city_avg
            score = min(round(ratio * 20, 1), 40)
        else:
            score = 20

        return score, f"岗位薪资 {job_mid:.0f}元/月, 同城同岗均薪 {city_avg:.0f}元/月, 比率 {job_mid/city_avg:.2f}"

    def _calc_company_score(self, job: Job) -> tuple:
        """计算公司分。"""
        type_score = self.COMPANY_TYPE_SCORE.get(job.company_type, 10)
        size_mult = self.COMPANY_SIZE_MULTIPLIER.get(job.company_size, 0.6)

        score = round(type_score * size_mult, 1)
        detail = f"公司类型: {job.company_type or '未知'} ({type_score}分), 规模: {job.company_size or '未知'} (系数{size_mult})"
        return score, detail

    def _calc_welfare_score(self, job: Job) -> tuple:
        """计算福利分。"""
        if not job.welfare or not job.welfare.strip():
            return 0, "无福利标签"

        tags = [t.strip() for t in job.welfare.split(",") if t.strip()]
        score = min(len(tags) * 4, 20)
        detail = f"福利标签 {len(tags)} 个: {', '.join(tags[:5])}{'...' if len(tags) > 5 else ''}"
        return score, detail

    def _calc_experience_score(self, job: Job) -> tuple:
        """计算经验友好度。"""
        score = self.EXPERIENCE_SCORE.get(job.experience, 8)
        detail = f"经验要求: {job.experience or '不限'} ({score}/15分)"
        return score, detail

    def _calc_demand_bonus(self, job: Job) -> tuple:
        """计算需求热度加分。"""
        from datetime import datetime, timedelta

        week_ago = (datetime.utcnow() - timedelta(days=7)).date()

        recent_count = (
            self.db.query(func.count(Job.job_id))
            .filter(
                Job.status == "有效",
                Job.job_category == job.job_category,
                Job.city == job.city,
                Job.published_at >= week_ago,
            )
            .scalar()
        )

        if recent_count > 50:
            score = 10
        elif recent_count > 20:
            score = 7
        elif recent_count > 5:
            score = 4
        elif recent_count > 0:
            score = 2
        else:
            score = 0

        detail = f"{job.city} · {job.job_category} 近7天发布 {recent_count} 个岗位"
        return score, detail

    def _generate_interpretation(self, total, salary, company, welfare, exp):
        """生成综合解读。"""
        parts = []
        if total >= 75:
            parts.append("该岗位综合竞争力优秀，强烈推荐投递。")
        elif total >= 55:
            parts.append("该岗位综合竞争力良好，值得考虑。")
        elif total >= 35:
            parts.append("该岗位综合竞争力一般，可酌情投递。")
        else:
            parts.append("该岗位综合竞争力偏低，建议谨慎评估。")

        if salary >= 30:
            parts.append("薪资水平显著高于同类岗位。")
        elif salary >= 15:
            parts.append("薪资处于行业平均水平。")
        else:
            parts.append("薪资偏低，可尝试谈薪。")

        if company >= 20:
            parts.append("公司背景优秀。")
        if welfare >= 12:
            parts.append("福利待遇较好。")
        if exp >= 12:
            parts.append("经验门槛低，适合新人。")

        return " ".join(parts)


class SalaryPredictionService:
    """薪资预测小工具。"""

    def __init__(self, db: Session):
        self.db = db

    def predict(self, city: str, job_category: str, experience: str) -> dict:
        """
        基于历史数据预测薪资范围。

        Args:
            city: 工作城市。
            job_category: 岗位大类。
            experience: 经验要求。

        Returns:
            {
                "city": "北京",
                "job_category": "技术",
                "experience": "3-5年",
                "predicted_range": {"min": 18000, "max": 32000},
                "confidence": "高",
                "sample_size": 150,
                "distribution": {"p10": 12000, "p25": 18000, "p50": 24000, "p75": 32000, "p90": 42000}
            }
        """
        # 查询匹配的薪资数据
        base_query = (
            self.db.query((Job.salary_min + Job.salary_max) / 2)
            .filter(
                Job.status == "有效",
                Job.salary_type != "面议",
                Job.salary_min.isnot(None),
                Job.salary_max.isnot(None),
            )
        )

        # 逐级放宽条件，确保有足够样本
        # Level 1: 精确匹配 city + category + experience
        midpoints = base_query.filter(
            Job.city == city,
            Job.job_category == job_category,
            Job.experience == experience,
        ).all()
        match_level = "精确匹配（城市+岗位+经验）"

        if len(midpoints) < 10:
            # Level 2: city + category
            midpoints = base_query.filter(
                Job.city == city,
                Job.job_category == job_category,
            ).all()
            match_level = "近似匹配（城市+岗位）"

        if len(midpoints) < 10:
            # Level 3: category + experience
            midpoints = base_query.filter(
                Job.job_category == job_category,
                Job.experience == experience,
            ).all()
            match_level = "近似匹配（岗位+经验）"

        if len(midpoints) < 5:
            # Level 4: category only
            midpoints = base_query.filter(
                Job.job_category == job_category,
            ).all()
            match_level = "模糊匹配（仅岗位类型）"

        values = [float(r[0]) for r in midpoints if r[0] is not None and r[0] > 0]
        sample_size = len(values)

        if sample_size < 3:
            return {
                "city": city,
                "job_category": job_category,
                "experience": experience,
                "predicted_range": {"min": None, "max": None},
                "confidence": "数据不足",
                "sample_size": sample_size,
                "match_level": match_level,
                "distribution": None,
                "message": f"样本量不足（仅 {sample_size} 条），无法给出可靠预测",
            }

        arr = np.array(values)
        p10 = round(float(np.percentile(arr, 10)), -2)  # 取整到百
        p25 = round(float(np.percentile(arr, 25)), -2)
        p50 = round(float(np.median(arr)), -2)
        p75 = round(float(np.percentile(arr, 75)), -2)
        p90 = round(float(np.percentile(arr, 90)), -2)

        # 置信度评估
        if sample_size >= 50:
            confidence = "高"
        elif sample_size >= 20:
            confidence = "中"
        elif sample_size >= 10:
            confidence = "较低"
        else:
            confidence = "低"

        # 预测范围：P25 ~ P75 作为建议薪资范围
        return {
            "city": city,
            "job_category": job_category,
            "experience": experience,
            "predicted_range": {"min": int(p25), "max": int(p75)},
            "median": int(p50),
            "confidence": confidence,
            "sample_size": sample_size,
            "match_level": match_level,
            "distribution": {
                "p10": int(p10),
                "p25": int(p25),
                "p50": int(p50),
                "p75": int(p75),
                "p90": int(p90),
            },
        }
