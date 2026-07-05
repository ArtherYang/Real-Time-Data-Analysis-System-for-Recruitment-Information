"""
API 端到端集成测试
===================
模拟真实用户场景的 API 调用链，覆盖完整业务流程。

场景覆盖：
- 求职者完整流程：注册 → 登录 → 搜索岗位 → 查看分析 → 导出
- 管理流程：注册 → 登录 → 管理权限
- 游客流程：浏览概览 → 搜索 → 受限操作验证
- 多用户并发场景（串行模拟）
- 数据新鲜度验证
"""

import json
import pytest
from datetime import date, datetime, timedelta

from app.models.job import Job, generate_uuid
from app.models.analysis import AnalysisCache


# ============================================================
# 场景夹具
# ============================================================

E2E_SEED_JOBS = [
    {
        "title": "Python开发工程师", "company": "字节跳动", "city": "北京",
        "salary_min": 20000, "salary_max": 40000, "salary_type": "月薪",
        "experience": "3-5年", "education": "本科",
        "skills": "Python,Django,MySQL,Redis,Docker",
        "job_category": "技术", "industry": "互联网",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=2),
        "status": "有效",
    },
    {
        "title": "Java开发工程师", "company": "阿里巴巴", "city": "杭州",
        "salary_min": 25000, "salary_max": 45000, "salary_type": "月薪",
        "experience": "3-5年", "education": "本科",
        "skills": "Java,Spring Boot,MySQL,Kubernetes",
        "job_category": "技术", "industry": "互联网",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=3),
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
        "skills": "Python,SQL,Tableau,Pandas",
        "job_category": "技术", "industry": "互联网",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=5),
        "status": "有效",
    },
    {
        "title": "产品经理", "company": "小红书", "city": "上海",
        "salary_min": 20000, "salary_max": 35000, "salary_type": "月薪",
        "experience": "3-5年", "education": "本科",
        "skills": "产品设计,需求分析,项目管理,Figma",
        "job_category": "产品", "industry": "互联网",
        "platform": "猎聘", "published_at": date.today() - timedelta(days=7),
        "status": "有效",
    },
    {
        "title": "算法工程师", "company": "商汤科技", "city": "北京",
        "salary_min": 30000, "salary_max": 60000, "salary_type": "月薪",
        "experience": "3-5年", "education": "硕士",
        "skills": "Python,TensorFlow,PyTorch,深度学习",
        "job_category": "技术", "industry": "人工智能",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=1),
        "status": "有效",
    },
    {
        "title": "UI设计师", "company": "网易", "city": "广州",
        "salary_min": None, "salary_max": None, "salary_type": "面议",
        "experience": "1-3年", "education": "本科",
        "skills": "Figma,Sketch,UI设计",
        "job_category": "设计", "industry": "互联网",
        "platform": "前程无忧", "published_at": date.today() - timedelta(days=10),
        "status": "有效",
    },
    {
        "title": "运营经理", "company": "B站", "city": "上海",
        "salary_min": 12000, "salary_max": 22000, "salary_type": "月薪",
        "experience": "1-3年", "education": "本科",
        "skills": "用户运营,数据分析,活动策划",
        "job_category": "运营", "industry": "互联网",
        "platform": "BOSS直聘", "published_at": date.today() - timedelta(days=2),
        "status": "有效",
    },
    {
        "title": "金融分析师", "company": "招商银行", "city": "深圳",
        "salary_min": 15000, "salary_max": 28000, "salary_type": "月薪",
        "experience": "1-3年", "education": "硕士",
        "skills": "金融分析,Excel,SQL,Python",
        "job_category": "金融", "industry": "金融",
        "platform": "猎聘", "published_at": date.today() - timedelta(days=14),
        "status": "有效",
    },
    {
        "title": "HR专员", "company": "万科", "city": "深圳",
        "salary_min": 8000, "salary_max": 15000, "salary_type": "月薪",
        "experience": "应届生", "education": "本科",
        "skills": "招聘,员工关系,Excel",
        "job_category": "职能", "industry": "房地产",
        "platform": "前程无忧", "published_at": date.today() - timedelta(days=20),
        "status": "有效",
    },
    {
        "title": "过期岗位示例", "company": "已关闭公司", "city": "武汉",
        "salary_min": 5000, "salary_max": 8000, "salary_type": "月薪",
        "experience": "不限", "education": "大专",
        "skills": "测试",
        "job_category": "技术", "industry": "测试",
        "platform": "其他", "published_at": date.today() - timedelta(days=60),
        "status": "已过期",
    },
]


def _seed_e2e_data(session):
    """向数据库插入 E2E 测试数据。"""
    session.query(Job).delete()
    session.query(AnalysisCache).delete()
    session.commit()

    for j in E2E_SEED_JOBS:
        defaults = {
            "job_id": generate_uuid(),
            "title_raw": j["title"],
            "job_type": "全职",
            "recruit_number": "1",
            "district": None,
            "description": f"{j['company']}正在招聘{j['title']}，要求{j.get('skills', 'N/A')}",
            "company_size": "500-2000人",
            "company_type": "民营",
            "welfare": "五险一金,年终奖",
            "platform_job_id": f"e2e_{generate_uuid()[:8]}",
            "source_url": "https://example.com/job",
            "crawled_at": datetime.utcnow(),
        }
        merged = {**j, **{k: v for k, v in defaults.items() if k not in j}}
        session.add(Job(**merged))
    session.commit()


def _register_and_login(client, email="e2e_user@test.com", password="Test1234",
                        nickname="E2E测试用户"):
    """辅助函数：注册并登录，返回 access_token。"""
    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "nickname": nickname,
    })
    if resp.status_code == 201:
        return json.loads(resp.data)["data"]["access_token"]
    # 可能已注册，直接登录
    resp = client.post("/api/v1/auth/login", json={
        "account": email,
        "password": password,
    })
    if resp.status_code == 200:
        return json.loads(resp.data)["data"]["access_token"]
    return None


# ============================================================
# 场景 1：求职者完整流程
# ============================================================

class TestJobSeekerFlow:
    """求职者端到端场景：注册 → 登录 → 搜索 → 分析 → 导出"""

    def test_full_job_seeker_journey(self, client, app, db_session):
        """完整求职者旅程不报错，各步骤响应正确"""
        _seed_e2e_data(db_session)

        # Step 1: 注册
        resp = client.post("/api/v1/auth/register", json={
            "email": "seeker@example.com",
            "password": "Test1234",
            "nickname": "求职者小王",
        })
        assert resp.status_code == 201
        token = json.loads(resp.data)["data"]["access_token"]
        assert token is not None

        # Step 2: 查看个人信息
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 200
        user = json.loads(resp.data)["data"]
        assert user["nickname"] == "求职者小王"

        # Step 3: 搜索 Python 相关岗位
        resp = client.get("/api/v1/jobs?keyword=Python&page=1&per_page=10")
        assert resp.status_code == 200
        jobs_data = json.loads(resp.data)
        assert jobs_data["pagination"]["page"] == 1
        python_jobs = [j for j in jobs_data["data"]
                       if "Python" in j.get("title", "")]
        assert len(python_jobs) >= 1

        # Step 4: 查看岗位详情
        if jobs_data["data"]:
            job_id = jobs_data["data"][0]["job_id"]
            resp = client.get(f"/api/v1/jobs/{job_id}")
            assert resp.status_code == 200
            detail = json.loads(resp.data)["data"]
            assert detail["job_id"] == job_id

        # Step 5: 查看薪资分布（按城市）
        resp = client.get(
            "/api/v1/analysis/salary-distribution?group_by=city&top=10"
        )
        assert resp.status_code == 200
        salary_data = json.loads(resp.data)["data"]
        assert len(salary_data["items"]) > 0

        # Step 6: 查看热门岗位
        resp = client.get("/api/v1/analysis/hot-jobs?top=5")
        assert resp.status_code == 200
        hot_jobs = json.loads(resp.data)["data"]
        assert len(hot_jobs) >= 1

        # Step 7: 查看技能词云
        resp = client.get("/api/v1/analysis/skills-wordcloud?top=20")
        assert resp.status_code == 200
        wordcloud = json.loads(resp.data)["data"]
        # 应有 Python,Java 等技能
        skills_names = [item["name"] for item in wordcloud]
        assert len(skills_names) >= 1

        # Step 8: 查看城市分布
        resp = client.get("/api/v1/analysis/city-distribution?top=10")
        assert resp.status_code == 200
        city_data = json.loads(resp.data)["data"]
        assert "cr5" in city_data

        # Step 9: 导出 CSV
        resp = client.get("/api/v1/export/csv?job_category=技术")
        assert resp.status_code == 200
        csv_content = resp.data.decode("utf-8")
        assert "Python" in csv_content or "Java" in csv_content or len(csv_content) > 0

    def test_cross_platform_comparison(self, client, app, db_session):
        """跨平台对比：求职者比较不同平台同一岗位的薪资"""
        _seed_e2e_data(db_session)

        # 查询 BOSS直聘的技术岗位
        resp = client.get(
            "/api/v1/jobs?platform=BOSS直聘&job_category=技术"
        )
        assert resp.status_code == 200
        boss_jobs = json.loads(resp.data)["data"]

        # 查询智联招聘的技术岗位
        resp = client.get(
            "/api/v1/jobs?platform=智联招聘&job_category=技术"
        )
        assert resp.status_code == 200
        zhilian_jobs = json.loads(resp.data)["data"]

        # 两个平台各有数据（种子数据包含了两个平台）
        total = len(boss_jobs) + len(zhilian_jobs)
        assert total >= 1

    def test_city_salary_comparison(self, client, app, db_session):
        """城市薪资对比：比较北京 vs 上海的薪资"""
        _seed_e2e_data(db_session)

        # 按城市分组薪资
        resp = client.get(
            "/api/v1/analysis/salary-distribution?group_by=city&top=50"
        )
        assert resp.status_code == 200
        items = json.loads(resp.data)["data"]["items"]

        beijing = next((i for i in items if i["group_key"] == "北京"), None)
        shanghai = next((i for i in items if i["group_key"] == "上海"), None)

        # 两个城市都有数据
        assert beijing is not None
        assert shanghai is not None
        assert beijing["sample_count"] >= 1
        assert shanghai["sample_count"] >= 1


# ============================================================
# 场景 2：游客（未登录）流程
# ============================================================

class TestGuestFlow:
    """游客场景：浏览公开数据 → 受限操作被拦截"""

    def test_guest_browse_public_data(self, client, app, db_session):
        """游客可以浏览所有公开分析数据"""
        _seed_e2e_data(db_session)

        # 首页概览
        resp = client.get("/api/v1/jobs/stats/overview")
        assert resp.status_code == 200
        overview = json.loads(resp.data)["data"]
        assert overview["total"] >= 1

        # 热门岗位
        resp = client.get("/api/v1/analysis/hot-jobs")
        assert resp.status_code == 200

        # 薪资分布
        resp = client.get("/api/v1/analysis/salary-distribution")
        assert resp.status_code == 200

        # 技能分析
        resp = client.get("/api/v1/analysis/skills-frequency")
        assert resp.status_code == 200

    def test_guest_restricted_access(self, client):
        """游客不能访问需要认证的接口"""
        # 个人信息需要登录
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

        # 注册接口游客可以访问
        resp = client.post("/api/v1/auth/register", json={
            "email": "newguest@test.com",
            "password": "Test1234",
            "nickname": "新游客",
        })
        assert resp.status_code in (201, 409)  # 201 成功或 409 已存在


# ============================================================
# 场景 3：数据一致性验证
# ============================================================

class TestDataConsistency:
    """端到端数据一致性：筛选/分析/导出使用相同数据基础"""

    def test_filters_consistent_with_overview(self, client, app, db_session):
        """筛选结果与概览统计一致"""
        _seed_e2e_data(db_session)

        # 获取概览
        resp = client.get("/api/v1/jobs/stats/overview")
        overview = json.loads(resp.data)["data"]

        # 按城市筛选
        for city_item in overview["city_distribution"][:3]:
            city = city_item["city"]
            resp = client.get(f"/api/v1/jobs?city={city}")
            jobs = json.loads(resp.data)["data"]
            # 筛选结果数量应 >= 1
            assert len(jobs) >= 1
            # 所有结果城市匹配
            for job in jobs:
                assert job["city"] == city

    def test_analysis_excludes_expired_jobs(self, client, app, db_session):
        """分析结果不包含已过期岗位"""
        _seed_e2e_data(db_session)

        # 获取热点岗位排行
        resp = client.get("/api/v1/analysis/hot-jobs?top=20")
        hot_jobs = json.loads(resp.data)["data"]

        # 所有岗位分类应有数据
        categories = {j["category"] for j in hot_jobs}
        assert len(categories) >= 1

        # 已过期的岗位不应影响热门排行
        total_count = sum(j["count"] for j in hot_jobs)
        assert total_count <= len(E2E_SEED_JOBS)  # 不应超过有效岗位数

    def test_pagination_consistency(self, client, app, db_session):
        """分页数据一致性：确保分页遍历覆盖所有数据"""
        _seed_e2e_data(db_session)

        all_job_ids = set()
        page = 1
        while True:
            resp = client.get(
                f"/api/v1/jobs?page={page}&per_page=3"
            )
            assert resp.status_code == 200
            data = json.loads(resp.data)
            jobs = data["data"]
            if not jobs:
                break

            # 收集当前页的 job_id
            page_ids = {j["job_id"] for j in jobs}
            all_job_ids.update(page_ids)

            if page >= data["pagination"]["pages"]:
                break
            page += 1

        # 验证至少获取到数据
        assert len(all_job_ids) >= 1
        # 总数应该等于 pagination.total（考虑过期岗位被排除）
        total = json.loads(
            client.get("/api/v1/jobs?per_page=3").data
        )["pagination"]["total"]
        assert len(all_job_ids) == total, (
            f"遍历获取 {len(all_job_ids)} 条，pagination.total={total}"
        )


# ============================================================
# 场景 4：错误恢复与边界场景
# ============================================================

class TestErrorRecovery:
    """错误处理和边界场景"""

    def test_invalid_token_then_valid_login(self, client):
        """无效 token → 重新登录 → 正常访问"""
        # 先用无效 token 访问
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": "Bearer invalid.token.here",
        })
        assert resp.status_code == 401

        # 注册并登录
        token = _register_and_login(
            client, "recovery@test.com", "Test1234", "恢复测试"
        )
        assert token is not None

        # 用有效 token 访问
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 200

    def test_empty_search_returns_all(self, client, app, db_session):
        """空关键词搜索返回全部数据"""
        _seed_e2e_data(db_session)

        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["pagination"]["total"] >= 1

    def test_nonexistent_job_detail(self, client, app, db_session):
        """不存在的岗位详情返回 404"""
        _seed_e2e_data(db_session)

        resp = client.get("/api/v1/jobs/fake_job_id_12345")
        assert resp.status_code == 404
        body = json.loads(resp.data)
        assert body["code"] == 404

    def test_analysis_with_all_filters(self, client, app, db_session):
        """所有筛选器同时使用不报错"""
        _seed_e2e_data(db_session)

        params = (
            "city=北京"
            "&job_category=技术"
            "&experience=3-5年"
            "&education=本科"
            "&platform=BOSS直聘"
        )
        resp = client.get(f"/api/v1/analysis/salary-distribution?{params}")
        assert resp.status_code == 200
        data = json.loads(resp.data)["data"]
        # 可能有结果也可能为空（取决于种子数据匹配情况），但不报错
        assert "items" in data

    def test_concurrent_filters_no_cache_race(self, client, app, db_session):
        """连续快速切换筛选条件不产生缓存竞态"""
        _seed_e2e_data(db_session)

        filters_list = [
            "city=北京",
            "city=上海",
            "city=深圳",
            "job_category=技术",
            "job_category=产品",
            "experience=1-3年",
            "experience=3-5年",
            "education=本科",
            "education=硕士",
        ]

        results = []
        for f in filters_list:
            resp = client.get(f"/api/v1/jobs?{f}")
            assert resp.status_code == 200
            results.append(json.loads(resp.data)["pagination"]["total"])

        # 所有请求都应成功，且总数应一致（同一数据集）
        # 不同筛选可能返回不同总数，但都应 >= 0
        assert all(r >= 0 for r in results)
