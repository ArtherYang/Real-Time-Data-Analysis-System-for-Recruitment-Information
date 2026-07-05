"""
Locust 性能压测脚本
====================
对 RDAS 系统核心 API 进行负载测试，验证性能指标。

使用方式：
    1. 启动 Flask 应用:
       cd backend && python run.py

    2. 启动 Locust（Web UI）:
       locust -f tests/locustfile.py --host=http://localhost:5000

    3. 打开浏览器访问 http://localhost:8089
       - 设置并发用户数（推荐 10-50）
       - 设置 spawn rate（推荐 5/s）
       - 设置测试域名

    4. 无 UI 命令行模式:
       locust -f tests/locustfile.py --host=http://localhost:5000 \\
         --headless --users 50 --spawn-rate 10 --run-time 60s \\
         --html=reports/locust_report.html

压测场景：
    - 游客浏览（70% 流量）：首页概览、岗位搜索、分析图表
    - 注册/登录（15% 流量）：注册、登录、查看个人信息
    - 数据导出（10% 流量）：CSV 导出
    - 健康检查（5% 流量）：/health 探针

性能目标（来自需求规格说明书 第4节）：
    - API 响应时间 P95 ≤ 500ms（简单查询）
    - API 响应时间 P95 ≤ 2s（复杂分析）
    - 支持 ≥ 50 并发用户
"""

import random
import string
from locust import HttpUser, task, between, events


class RDASUser(HttpUser):
    """
    模拟 RDAS 系统用户行为。

    权重分配：
        - 70% 浏览行为（搜索、查看分析）
        - 15% 认证行为（注册、登录）
        - 10% 导出行为
        - 5%  健康检查
    """

    # 请求间隔：模拟真实用户 1-5 秒操作间隔
    wait_time = between(1, 5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_token = None
        self._registered_emails = set()

    def on_start(self):
        """用户初始化：可选登录获取 token。"""
        # 30% 用户以登录状态开始
        if random.random() < 0.3:
            self._login()

    # ======================== 数据浏览（权重 7） ========================

    @task(7)
    def browse_jobs(self):
        """浏览岗位列表和概览"""
        # 随机选择浏览行为
        action = random.choice(["list", "overview", "detail_search"])

        if action == "list":
            page = random.randint(1, 5)
            per_page = random.choice([10, 20, 50])
            self.client.get(
                f"/api/v1/jobs?page={page}&per_page={per_page}",
                name="/api/v1/jobs [list]",
            )

        elif action == "overview":
            self.client.get(
                "/api/v1/jobs/stats/overview",
                name="/api/v1/jobs/stats/overview",
            )

        elif action == "detail_search":
            keyword = random.choice([
                "Python", "Java", "前端", "数据分析", "产品经理",
                "算法", "运营", "设计", "金融", "HR",
            ])
            city = random.choice([
                "北京", "上海", "深圳", "杭州", "广州",
                "", "",  # 30% 不筛选城市
            ])
            params = f"?keyword={keyword}"
            if city:
                params += f"&city={city}"
            self.client.get(
                f"/api/v1/jobs{params}",
                name="/api/v1/jobs [search]",
            )

    # ======================== 分析查看（权重 6） ========================

    @task(6)
    def view_analytics(self):
        """查看各类分析图表数据"""
        endpoint = random.choice([
            ("/api/v1/analysis/hot-jobs?top=10",
             "/api/v1/analysis/hot-jobs"),
            ("/api/v1/analysis/salary-distribution?group_by=job_category",
             "/api/v1/analysis/salary-distribution"),
            ("/api/v1/analysis/salary-distribution?group_by=city",
             "/api/v1/analysis/salary-distribution [city]"),
            ("/api/v1/analysis/city-distribution?top=20",
             "/api/v1/analysis/city-distribution"),
            ("/api/v1/analysis/skills-frequency?top=30",
             "/api/v1/analysis/skills-frequency"),
            ("/api/v1/analysis/skills-wordcloud?top=50",
             "/api/v1/analysis/skills-wordcloud"),
            ("/api/v1/analysis/trend?granularity=weekly",
             "/api/v1/analysis/trend"),
            ("/api/v1/analysis/salary-matrix?job_category=技术",
             "/api/v1/analysis/salary-matrix"),
            ("/api/v1/analysis/growth",
             "/api/v1/analysis/growth"),
        ])
        self.client.get(endpoint[0], name=endpoint[1])

    # ======================== 认证操作（权重 1.5） ========================

    @task(1)
    def auth_register(self):
        """用户注册"""
        suffix = "".join(random.choices(string.ascii_lowercase, k=8))
        email = f"loadtest_{suffix}@example.com"
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Test1234",
                "nickname": f"压测用户{suffix[:4]}",
            },
            name="/api/v1/auth/register",
        )

    @task(1)
    def auth_login(self):
        """用户登录"""
        # 使用固定的测试账号（需预先注册）
        self.client.post(
            "/api/v1/auth/login",
            json={
                "account": "loadtest_fixed@example.com",
                "password": "Test1234",
            },
            name="/api/v1/auth/login",
        )

    @task(2)
    def auth_me(self):
        """查看个人信息（需登录）"""
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        self.client.get(
            "/api/v1/auth/me",
            headers=headers,
            name="/api/v1/auth/me",
        )

    # ======================== 数据导出（权重 1） ========================

    @task(1)
    def export_data(self):
        """导出 CSV / Excel"""
        export_type = random.choice(["csv", "excel"])
        params = ""
        if random.random() < 0.5:
            city = random.choice(["北京", "上海", "深圳"])
            params = f"?city={city}"
        self.client.get(
            f"/api/v1/export/{export_type}{params}",
            name=f"/api/v1/export/{export_type}",
        )

    # ======================== 健康检查（权重 0.5） ========================

    @task(1)
    def health_check(self):
        """健康检查探针"""
        self.client.get("/health", name="/health")

    # ======================== 辅助方法 ========================

    def _login(self):
        """静默登录获取 token。"""
        resp = self.client.post(
            "/api/v1/auth/login",
            json={
                "account": "loadtest_fixed@example.com",
                "password": "Test1234",
            },
            name="/api/v1/auth/login [silent]",
        )
        if resp.status_code == 200:
            try:
                self.access_token = resp.json()["data"]["access_token"]
            except (KeyError, TypeError, AttributeError):
                pass


# ============================================================
# 自定义事件：记录性能指标
# ============================================================

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Locust 启动时输出提示信息。"""
    print("\n" + "=" * 60)
    print("  RDAS API 性能压测")
    print("  目标：验证 50 并发下 API 响应时间")
    print("  性能目标：P95 ≤ 500ms（简单查询）/ ≤ 2s（复杂分析）")
    print("=" * 60 + "\n")


# ============================================================
# Locust 配置建议（在 Web UI 中设置或命令行参数）
# ============================================================
#
# 轻量测试（冒烟）：
#   --users 10 --spawn-rate 5 --run-time 30s
#
# 中等压力（功能验证）：
#   --users 50 --spawn-rate 10 --run-time 2m
#
# 高压测试（极限探测）：
#   --users 200 --spawn-rate 20 --run-time 5m
#
# ============================================================
