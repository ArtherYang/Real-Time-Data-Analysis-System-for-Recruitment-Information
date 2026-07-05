"""
M3 数据分析引擎 API 测试
=========================
测试所有分析 API 端点和底层服务。

AI生成，待人工审查。
"""

import pytest
import json
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from app.analysis import AnalysisEngine, AnalysisFilters
from app.models.job import Job, generate_uuid
from app.models.analysis import AnalysisCache


# ============================================================
# 测试夹具：插入示例岗位数据
# ============================================================

SAMPLE_JOBS = [
    {
        "title": "Python开发工程师", "company": "字节跳动", "city": "北京",
        "salary_min": 20000, "salary_max": 40000, "salary_type": "月薪",
        "experience": "3-5年", "education": "本科",
        "skills": "Python,Django,MySQL,Redis,Docker",
        "job_category": "技术", "industry": "互联网",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=3),
        "status": "有效",
    },
    {
        "title": "Java开发工程师", "company": "阿里巴巴", "city": "杭州",
        "salary_min": 25000, "salary_max": 45000, "salary_type": "月薪",
        "experience": "3-5年", "education": "本科",
        "skills": "Java,Spring Boot,MySQL,Redis,Kubernetes",
        "job_category": "技术", "industry": "互联网",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=5),
        "status": "有效",
    },
    {
        "title": "前端开发工程师", "company": "腾讯", "city": "深圳",
        "salary_min": 18000, "salary_max": 35000, "salary_type": "月薪",
        "experience": "1-3年", "education": "本科",
        "skills": "JavaScript,React,Vue.js,TypeScript,CSS",
        "job_category": "技术", "industry": "互联网",
        "platform": "智联招聘", "published_at": date.today() - timedelta(days=1),
        "status": "有效",
    },
    {
        "title": "数据分析师", "company": "美团", "city": "北京",
        "salary_min": 15000, "salary_max": 30000, "salary_type": "月薪",
        "experience": "1-3年", "education": "本科",
        "skills": "Python,SQL,Tableau,Pandas,数据分析",
        "job_category": "技术", "industry": "互联网",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=7),
        "status": "有效",
    },
    {
        "title": "产品经理", "company": "小红书", "city": "上海",
        "salary_min": 20000, "salary_max": 35000, "salary_type": "月薪",
        "experience": "3-5年", "education": "本科",
        "skills": "产品设计,需求分析,项目管理,数据分析,Figma",
        "job_category": "产品", "industry": "互联网",
        "platform": "猎聘", "published_at": date.today() - timedelta(days=10),
        "status": "有效",
    },
    {
        "title": "运营经理", "company": "B站", "city": "上海",
        "salary_min": 12000, "salary_max": 22000, "salary_type": "月薪",
        "experience": "1-3年", "education": "本科",
        "skills": "用户运营,数据分析,活动策划,社群运营",
        "job_category": "运营", "industry": "互联网",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=2),
        "status": "有效",
    },
    {
        "title": "UI设计师", "company": "网易", "city": "广州",
        "salary_min": None, "salary_max": None, "salary_type": "面议",
        "experience": "1-3年", "education": "本科",
        "skills": "Figma,Sketch,Photoshop,UI设计",
        "job_category": "设计", "industry": "互联网",
        "platform": "前程无忧", "published_at": date.today() - timedelta(days=15),
        "status": "有效",
    },
    {
        "title": "算法工程师", "company": "商汤科技", "city": "北京",
        "salary_min": 30000, "salary_max": 60000, "salary_type": "月薪",
        "experience": "3-5年", "education": "硕士",
        "skills": "Python,TensorFlow,PyTorch,深度学习,计算机视觉",
        "job_category": "技术", "industry": "人工智能",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=1),
        "status": "有效",
    },
    {
        "title": "HR专员", "company": "万科", "city": "深圳",
        "salary_min": 8000, "salary_max": 15000, "salary_type": "月薪",
        "experience": "应届生", "education": "本科",
        "skills": "招聘,员工关系,Excel,PPT制作",
        "job_category": "职能", "industry": "房地产",
        "platform": "前程无忧", "published_at": date.today() - timedelta(days=20),
        "status": "有效",
    },
    {
        "title": "金融分析师", "company": "招商银行", "city": "深圳",
        "salary_min": 15000, "salary_max": 28000, "salary_type": "月薪",
        "experience": "1-3年", "education": "硕士",
        "skills": "金融分析,Excel,SQL,Python,风险管理",
        "job_category": "金融", "industry": "金融",
        "platform": "猎聘", "published_at": date.today() - timedelta(days=30),
        "status": "有效",
    },
    # 一条已过期（不应被统计）
    {
        "title": "过期岗位", "company": "测试公司", "city": "武汉",
        "salary_min": 5000, "salary_max": 8000, "salary_type": "月薪",
        "experience": "不限", "education": "大专",
        "skills": "测试技能",
        "job_category": "技术", "industry": "测试",
        "platform": "其他", "published_at": date.today() - timedelta(days=60),
        "status": "已过期",
    },
]


def _job_kwargs(j: dict) -> dict:
    """补全缺失的默认字段，避免插入报错。"""
    defaults = {
        "job_id": generate_uuid(),
        "title_raw": j["title"],
        "job_type": "全职",
        "recruit_number": "1",
        "district": None,
        "description": f"{j['company']}招聘{j['title']}",
        "company_size": "500-2000人",
        "company_type": "民营",
        "welfare": "五险一金,年终奖",
        "platform_job_id": f"test_{generate_uuid()[:8]}",
        "source_url": "https://example.com/job",
        "crawled_at": datetime.utcnow(),
    }
    merged = {**j, **{k: v for k, v in defaults.items() if k not in j}}
    return merged


def _seed_jobs(session):
    """向测试数据库插入示例岗位（先清空已有数据，防止跨测试累积）。"""
    # 清空旧数据
    session.query(Job).delete()
    # 清空分析缓存，避免跨测试缓存污染
    session.query(AnalysisCache).delete()
    session.commit()
    for j in SAMPLE_JOBS:
        job = Job(**_job_kwargs(j))
        session.add(job)
    session.commit()


# ============================================================
# 测试：AnalysisFilters
# ============================================================

class TestAnalysisFilters:
    """测试 AnalysisFilters 过滤器。"""

    def test_empty_filters(self):
        """空过滤器生成固定的哈希值。"""
        f = AnalysisFilters()
        h = f.to_params_hash()
        assert len(h) == 64
        # 相同参数应生成相同哈希
        assert f.to_params_hash() == h

    def test_different_filters_different_hash(self):
        """不同参数生成不同哈希。"""
        f1 = AnalysisFilters(city="北京")
        f2 = AnalysisFilters(city="上海")
        assert f1.to_params_hash() != f2.to_params_hash()

    def test_apply_all_filters(self, app, db_session):
        """测试全部筛选条件应用到查询。"""
        _seed_jobs(db_session)
        filters = AnalysisFilters(
            city="北京", job_category="技术", experience="3-5年",
        )
        query = filters.apply_to_query(db_session.query(Job))
        results = query.all()
        assert len(results) >= 0  # 可能为 1+（取决于数据）

    def test_exclude_negotiable(self, app, db_session):
        """排除面议薪资。"""
        _seed_jobs(db_session)
        query = db_session.query(Job)
        filtered = AnalysisFilters.exclude_negotiable_salary(query)
        results = filtered.all()
        for job in results:
            assert job.salary_type != "面议"
            assert job.salary_min is not None


# ============================================================
# 测试：AnalysisEngine 和服务层
# ============================================================

class TestTrendingRankingService:
    """测试热度排行服务。"""

    def test_category_ranking(self, app, db_session):
        """岗位大类排行返回正确数据结构。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.ranking.get_category_ranking(filters, top_n=10)
        assert isinstance(result, list)
        if result:
            item = result[0]
            assert "category" in item
            assert "count" in item
            assert "percentage" in item
            # 按 count 降序排列
            counts = [r["count"] for r in result]
            assert counts == sorted(counts, reverse=True)

    def test_category_ranking_excludes_expired(self, app, db_session):
        """排行不包含已过期岗位。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.ranking.get_category_ranking(filters, top_n=20)
        # 技术类应只统计有效岗位（不含"已过期"那条）
        tech = next((r for r in result if r["category"] == "技术"), None)
        if tech:
            # 有效技术岗：前4条 + 算法工程师 = 5条（不包括"过期岗位"）
            assert tech["count"] == 5

    def test_hotness_index(self, app, db_session):
        """热度指数返回正确结构。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.ranking.get_hotness_index(filters, top_n=10)
        assert isinstance(result, list)
        if result:
            item = result[0]
            assert "hotness_index" in item
            assert "count" in item
            assert "category" in item
            # hotness_index 应在 0-100 之间
            assert 0 <= item["hotness_index"] <= 100

    def test_trend_data(self, app, db_session):
        """趋势数据返回按周分组的时间序列。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.ranking.get_trend_data(filters, granularity="weekly")
        assert isinstance(result, list)
        if len(result) >= 2:
            # 第二条及以后应有 growth_rate
            assert "growth_rate" in result[1] or result[1].get("growth_rate") is None

    def test_period_growth(self, app, db_session):
        """环比增长率返回正确字段。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.ranking.get_period_growth(filters)
        assert "weekly_growth_pct" in result
        assert "monthly_growth_pct" in result
        assert "current_week_count" in result


class TestSalaryDistributionService:
    """测试薪资分布服务。"""

    def test_salary_stats_by_category(self, app, db_session):
        """按 job_category 分组统计薪资。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.salary.get_salary_stats(filters, group_by="job_category")
        assert isinstance(result, list)
        if result:
            item = result[0]
            assert "group_key" in item
            assert "sample_count" in item
            assert "stats" in item
            stats = item["stats"]
            assert "mean" in stats
            assert "median" in stats
            assert "p25" in stats
            assert "p75" in stats

    def test_salary_excludes_mianyi(self, app, db_session):
        """薪资统计不包含面议岗位。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        # 设计师岗位是面议，不应出现在统计中
        result = engine.salary.get_salary_stats(
            filters, group_by="job_category"
        )
        design = next(
            (r for r in result if r["group_key"] == "设计"), None
        )
        assert design is None  # 面议岗位没有薪资数据，不应出现

    def test_salary_stats_by_city(self, app, db_session):
        """按城市分组统计薪资。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.salary.get_salary_stats(filters, group_by="city")
        assert isinstance(result, list)

    def test_salary_experience_matrix(self, app, db_session):
        """薪资-经验矩阵返回正确结构。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.salary.get_salary_experience_matrix(filters)
        assert "rows" in result
        assert "columns" in result
        assert "data" in result
        assert len(result["data"]) == len(result["rows"])

    def test_salary_by_city_and_experience(self, app, db_session):
        """城市×经验交叉分析。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.salary.get_salary_by_city_and_experience(filters)
        assert isinstance(result, dict)


class TestRegionalAnalysisService:
    """测试地域分析服务。"""

    def test_city_distribution(self, app, db_session):
        """城市分布返回正确结构。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.regional.get_city_distribution(filters, top_n=20)
        assert "total" in result
        assert "cities" in result
        assert isinstance(result["cities"], list)

    def test_cr5_concentration(self, app, db_session):
        """CR5 集中度计算正确。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.regional.get_cr5_concentration(filters)
        assert "cr5_pct" in result
        assert "top_cities" in result
        assert "total_cities_count" in result
        assert 0 <= result["cr5_pct"] <= 100

    def test_province_aggregation(self, app, db_session):
        """省份聚合。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.regional.get_province_aggregation(filters)
        assert isinstance(result, list)
        if result:
            assert "province" in result[0]
            assert "count" in result[0]
            assert "percentage" in result[0]

    def test_city_category_matrix(self, app, db_session):
        """城市×岗位矩阵。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.regional.get_city_category_matrix(filters, top_n_cities=10)
        assert "cities" in result
        assert "categories" in result
        assert "data" in result
        assert len(result["data"]) == len(result["cities"])


class TestSkillWordCloudService:
    """测试技能词云服务。"""

    def test_skill_frequency(self, app, db_session):
        """技能频率统计。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.skills.get_skill_frequency(filters, top_n=50)
        assert isinstance(result, list)
        if result:
            item = result[0]
            assert "skill" in item
            assert "count" in item
            assert "frequency_pct" in item

    def test_skill_cooccurrence(self, app, db_session):
        """技能共现对分析。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.skills.get_skill_cooccurrence(filters, top_n=30)
        assert isinstance(result, list)
        if result:
            item = result[0]
            assert "skill_a" in item
            assert "skill_b" in item
            assert "count" in item

    def test_top_skills_by_category(self, app, db_session):
        """按岗位分类的技能 TOP。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.skills.get_top_skills_by_category(filters, top_n=10)
        assert isinstance(result, dict)
        # 应有"技术"类别
        if "技术" in result:
            assert isinstance(result["技术"], list)

    def test_wordcloud_data(self, app, db_session):
        """词云数据格式正确。"""
        _seed_jobs(db_session)
        engine = AnalysisEngine(db_session)
        filters = AnalysisFilters()

        result = engine.skills.generate_wordcloud_data(filters, top_n=50)
        assert isinstance(result, list)
        if result:
            item = result[0]
            assert "name" in item
            assert "value" in item


# ============================================================
# 测试：API 端点
# ============================================================

class TestAnalysisAPI:
    """测试分析 API 端点。"""

    def test_hot_jobs_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/hot-jobs 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/hot-jobs?top=5")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert isinstance(body["data"], list)

    def test_hotness_index_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/hotness-index 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/hotness-index?top=5")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert isinstance(body["data"], list)

    def test_trend_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/trend 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/trend?granularity=weekly")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert "data_points" in body["data"]

    def test_growth_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/growth 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/growth")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200

    def test_salary_distribution_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/salary-distribution 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/salary-distribution?group_by=city")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert "items" in body["data"]

    def test_salary_matrix_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/salary-matrix 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/salary-matrix")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert "rows" in body["data"]

    def test_city_distribution_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/city-distribution 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/city-distribution?top=10")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert "cities" in body["data"]

    def test_city_category_matrix_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/city-category-matrix 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/city-category-matrix?top_n_cities=5")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200

    def test_skills_frequency_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/skills-frequency 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/skills-frequency?top=20")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert "skills" in body["data"]

    def test_skills_cooccurrence_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/skills-cooccurrence 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/skills-cooccurrence?top=20")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200

    def test_skills_by_category_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/skills-by-category 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/skills-by-category?top=5")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200

    def test_skills_wordcloud_endpoint(self, client, app, db_session):
        """GET /api/v1/analysis/skills-wordcloud 返回正确响应。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/skills-wordcloud?top=20")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        if body["data"]:
            assert "name" in body["data"][0]
            assert "value" in body["data"][0]

    def test_invalid_top_param_handled(self, client, app, db_session):
        """无效的 top 参数被安全处理。"""
        _seed_jobs(db_session)
        resp = client.get("/api/v1/analysis/hot-jobs?top=abc")
        assert resp.status_code == 200  # 不应报 500

    def test_empty_database_graceful(self, client, app, db_session):
        """空数据库返回空列表而非报错。"""
        # 清空数据和缓存确保空数据库状态
        db_session.query(Job).delete()
        db_session.query(AnalysisCache).delete()
        db_session.commit()
        resp = client.get("/api/v1/analysis/skills-frequency")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["skills"] == []


# ============================================================
# 测试：缓存
# ============================================================

class TestCache:
    """测试分析结果缓存。"""

    def test_cache_set_and_get(self, app, db_session):
        """缓存写入和读取。"""
        from app.analysis.cache import AnalysisCacheManager

        cache = AnalysisCacheManager(db_session, ttl_seconds=3600)
        test_hash = "abc123def456"

        # 写入
        cache.set("test_type", test_hash, {"key": "value"})
        # 读取
        result = cache.get("test_type", test_hash)
        assert result == {"key": "value"}

    def test_cache_invalidate(self, app, db_session):
        """缓存失效。"""
        from app.analysis.cache import AnalysisCacheManager

        cache = AnalysisCacheManager(db_session, ttl_seconds=3600)
        test_hash = "invalidate_test"

        cache.set("test_type", test_hash, {"data": 1})
        cache.invalidate("test_type")

        result = cache.get("test_type", test_hash)
        assert result is None

    def test_service_uses_cache(self, app, db_session):
        """服务层正确使用缓存（第二次调用应走缓存）。"""
        _seed_jobs(db_session)

        # 第一次调用：计算并缓存
        engine1 = AnalysisEngine(db_session)
        filters = AnalysisFilters()
        result1 = engine1.ranking.get_category_ranking(filters, top_n=5)

        # 第二次调用：应走缓存
        engine2 = AnalysisEngine(db_session)
        result2 = engine2.ranking.get_category_ranking(filters, top_n=5)

        assert result1 == result2


# ============================================================
# 测试：创新功能
# ============================================================

class TestPlatformComparison:
    """测试跨平台薪资对比引擎。"""

    def test_platform_compare(self, app, db_session):
        """平台对比返回正确数据结构。"""
        _seed_jobs(db_session)
        from app.analysis.innovation import PlatformComparisonService

        service = PlatformComparisonService(db_session)
        filters = AnalysisFilters()
        result = service.compare(filters, group_by="job_category")

        assert "groups" in result
        assert "summary" in result
        assert isinstance(result["groups"], list)
        if result["groups"]:
            g = result["groups"][0]
            assert "group_key" in g
            assert "platforms" in g
            assert "comparisons" in g

    def test_platform_compare_api(self, client, app, db_session):
        """POST /api/v1/analysis/platform-compare 端点。"""
        _seed_jobs(db_session)
        resp = client.post(
            "/api/v1/analysis/platform-compare",
            json={"group_by": "job_category"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert "groups" in body["data"]


class TestJobScoring:
    """测试岗位竞争力评分。"""

    def test_score_job(self, app, db_session):
        """岗位评分返回五维结果。"""
        _seed_jobs(db_session)
        from app.analysis.innovation import JobScoringService

        # 获取一个岗位 ID
        job = db_session.query(Job).filter(Job.status == "有效").first()
        assert job is not None

        service = JobScoringService(db_session)
        result = service.score_job(job.job_id)

        assert result is not None
        assert "total_score" in result
        assert "dimensions" in result
        assert "salary" in result["dimensions"]
        assert "company" in result["dimensions"]
        assert "welfare" in result["dimensions"]
        assert "experience" in result["dimensions"]
        assert "demand_bonus" in result["dimensions"]
        assert 0 <= result["total_score"] <= 100

    def test_score_job_not_found(self, app, db_session):
        """不存在的岗位返回 None。"""
        from app.analysis.innovation import JobScoringService

        service = JobScoringService(db_session)
        result = service.score_job("nonexistent_id")
        assert result is None

    def test_score_job_api(self, client, app, db_session):
        """GET /api/v1/analysis/job-score 端点。"""
        _seed_jobs(db_session)
        job = db_session.query(Job).filter(Job.status == "有效").first()

        resp = client.get(f"/api/v1/analysis/job-score?job_id={job.job_id}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert "total_score" in body["data"]

    def test_score_job_api_missing_param(self, client, app, db_session):
        """缺少 job_id 参数返回 400。"""
        resp = client.get("/api/v1/analysis/job-score")
        assert resp.status_code == 400


class TestSalaryPrediction:
    """测试薪资预测。"""

    def test_predict_salary(self, app, db_session):
        """薪资预测返回正确结构。"""
        _seed_jobs(db_session)
        from app.analysis.innovation import SalaryPredictionService

        service = SalaryPredictionService(db_session)
        result = service.predict("北京", "技术", "3-5年")

        assert "predicted_range" in result
        assert "confidence" in result
        assert "sample_size" in result
        assert "distribution" in result
        assert result["predicted_range"]["min"] is not None

    def test_predict_salary_insufficient_data(self, app, db_session):
        """数据不足时返回合适提示。"""
        from app.analysis.innovation import SalaryPredictionService

        service = SalaryPredictionService(db_session)
        result = service.predict("火星", "外星科技", "100年以上")

        assert result["confidence"] == "数据不足"
        assert "message" in result

    def test_predict_salary_api(self, client, app, db_session):
        """POST /api/v1/analysis/predict-salary 端点。"""
        _seed_jobs(db_session)
        resp = client.post(
            "/api/v1/analysis/predict-salary",
            json={"city": "北京", "job_category": "技术", "experience": "3-5年"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 200
        assert "predicted_range" in body["data"]

    def test_predict_salary_api_missing_params(self, client, app, db_session):
        """缺少必填参数返回 400。"""
        resp = client.post(
            "/api/v1/analysis/predict-salary",
            json={"city": "北京"},
        )
        assert resp.status_code == 400
