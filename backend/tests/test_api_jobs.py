"""
岗位 API 测试
=============
测试岗位相关的 RESTful API 端点。
"""

import json


class TestJobsAPI:
    """岗位列表和详情接口测试"""

    def test_get_jobs_empty(self, client):
        """测试获取空岗位列表。"""
        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["code"] == 200
        assert data["message"] == "success"
        assert isinstance(data["data"], list)
        assert "pagination" in data

    def test_get_jobs_with_pagination(self, client):
        """测试分页参数。"""
        response = client.get("/api/v1/jobs?page=1&per_page=10")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 10

    def test_get_jobs_invalid_page_params(self, client):
        """测试无效分页参数时的降级处理。"""
        response = client.get("/api/v1/jobs?page=abc&per_page=999")
        assert response.status_code == 200
        data = json.loads(response.data)
        # 无效参数应降级为默认值：page=1
        assert data["pagination"]["page"] == 1

    def test_get_jobs_with_filters(self, client):
        """测试带筛选参数的查询。"""
        response = client.get(
            "/api/v1/jobs?city=北京&experience=1-3年&platform=BOSS直聘"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["code"] == 200
        # 所有返回岗位应满足筛选条件（列表可能为空，但不报错）
        for job in data["data"]:
            assert job["city"] == "北京"

    def test_get_jobs_with_keyword_search(self, client):
        """测试关键词搜索。"""
        response = client.get("/api/v1/jobs?keyword=Python")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["code"] == 200

    def test_get_job_detail_not_found(self, client):
        """测试获取不存在的岗位详情。"""
        response = client.get("/api/v1/jobs/nonexistent_id")
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["code"] == 404
        assert "不存在" in data["message"]

    def test_get_overview(self, client):
        """测试岗位概览统计接口。"""
        response = client.get("/api/v1/jobs/stats/overview")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["code"] == 200
        overview = data["data"]
        assert "total" in overview
        assert "this_week_new" in overview
        assert "city_distribution" in overview
        assert "platform_distribution" in overview


class TestAnalysisAPI:
    """分析接口测试"""

    def test_get_hot_jobs(self, client):
        """测试热门岗位排行接口。"""
        response = client.get("/api/v1/analysis/hot-jobs")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["code"] == 200
        assert isinstance(data["data"], list)

    def test_get_hot_jobs_with_top_param(self, client):
        """测试热门岗位排行 top 参数。"""
        response = client.get("/api/v1/analysis/hot-jobs?top=5")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]) <= 5

    def test_get_salary_distribution(self, client):
        """测试薪资分布接口。"""
        response = client.get("/api/v1/analysis/salary-distribution")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["code"] == 200
        assert "group_by" in data["data"]

    def test_get_salary_dist_by_experience(self, client):
        """测试按经验维度分组薪资分布。"""
        response = client.get(
            "/api/v1/analysis/salary-distribution?group_by=experience"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["group_by"] == "experience"

    def test_get_salary_dist_education(self, client):
        """测试按学历维度分组薪资分布。"""
        response = client.get(
            "/api/v1/analysis/salary-distribution?group_by=education"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"]["group_by"] == "education"

    def test_get_city_distribution(self, client):
        """测试城市分布接口。"""
        response = client.get("/api/v1/analysis/city-distribution")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["code"] == 200
        assert "cr5" in data["data"]
        assert "cities" in data["data"]
