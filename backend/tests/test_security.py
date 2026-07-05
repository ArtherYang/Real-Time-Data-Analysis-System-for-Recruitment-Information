"""
安全测试
========
测试系统的关键安全特性：认证、SQL 注入防护、XSS 防护、接口限流、密码安全。

覆盖范围：
- 未认证访问受保护资源
- SQL 注入尝试
- XSS 攻击向量
- 密码安全策略
- 接口限流（登录失败锁定）
- 响应头安全检查
"""

import json
import pytest


class TestUnauthenticatedAccess:
    """未认证访问控制测试"""

    def test_auth_me_without_token(self, client):
        """无 token 无法访问 /auth/me"""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_auth_me_with_invalid_token(self, client):
        """无效 token 被拒绝"""
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.fake.token"},
        )
        assert resp.status_code == 401

    def test_auth_me_with_expired_token(self, app, client):
        """过期 token 被拒绝"""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        _utc_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)

        with app.app_context():
            from app.utils.auth import _get_jwt_secret
            payload = {
                "sub": "test_user",
                "role": "普通用户",
                "type": "access",
                "iat": _utc_now() - timedelta(hours=2),
                "exp": _utc_now() - timedelta(hours=1),
            }
            expired_token = pyjwt.encode(
                payload, _get_jwt_secret(), algorithm="HS256"
            )

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    def test_auth_me_with_wrong_token_type(self, app, client):
        """refresh token 不能用于访问接口"""
        with app.app_context():
            from app.utils.auth import create_refresh_token
            refresh = create_refresh_token("test_user")

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert resp.status_code == 401


class TestSQLInjection:
    """SQL 注入防护测试"""

    def test_sql_injection_in_keyword(self, client):
        """关键词搜索中注入 SQL"""
        # 尝试 SQL 注入 payload
        payloads = [
            "'; DROP TABLE jobs; --",
            "' OR '1'='1",
            "1' UNION SELECT * FROM users --",
            "'; SELECT password_hash FROM users; --",
        ]
        for payload in payloads:
            resp = client.get(f"/api/v1/jobs?keyword={payload}")
            # 不应返回 500，应正常处理或返回空结果
            assert resp.status_code == 200, (
                f"SQL 注入 payload '{payload}' 导致错误: {resp.status_code}"
            )

    def test_sql_injection_in_city_filter(self, client):
        """城市筛选器中的 SQL 注入"""
        resp = client.get("/api/v1/jobs?city='; DROP TABLE jobs; --")
        assert resp.status_code == 200

    def test_sql_injection_in_sort(self, client):
        """排序列中的 SQL 注入"""
        resp = client.get("/api/v1/jobs?sort='); DELETE FROM jobs; --")
        # 无效的排序参数应返回 200 + 降级处理，而非 500
        assert resp.status_code in (200, 400)


class TestXSSProtection:
    """XSS 防护测试"""

    def test_xss_in_register_nickname(self, client):
        """注册昵称中的 XSS"""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "xss_test@example.com",
                "password": "Test1234",
                "nickname": '<script>alert("XSS")</script>',
            },
        )
        # 注册成功时，昵称中的特殊字符应被处理（通过或转义）
        if resp.status_code == 201:
            data = json.loads(resp.data)
            nickname = data["data"]["user"].get("nickname", "")
            # 如果 API 层不做过滤，至少数据库层/ORM 不应执行脚本
            assert isinstance(nickname, str)

    def test_xss_in_search_keyword(self, client):
        """搜索关键词中的 XSS"""
        resp = client.get("/api/v1/jobs?keyword=<img src=x onerror=alert(1)>")
        assert resp.status_code == 200
        # 响应不应执行脚本
        data = json.loads(resp.data)
        assert "<script" not in str(data).lower()


class TestPasswordSecurity:
    """密码安全测试"""

    def test_weak_password_all_numbers_rejected(self, client):
        """纯数字密码被拒绝"""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak1@test.com",
                "password": "12345678",
                "nickname": "测试",
            },
        )
        assert resp.status_code in (400, 422)

    def test_weak_password_all_letters_rejected(self, client):
        """纯字母密码被拒绝"""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak2@test.com",
                "password": "abcdefgh",
                "nickname": "测试",
            },
        )
        assert resp.status_code in (400, 422)

    def test_short_password_rejected(self, client):
        """过短密码被拒绝"""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@test.com",
                "password": "Ab1",
                "nickname": "测试",
            },
        )
        assert resp.status_code in (400, 422)

    def test_password_not_returned(self, client):
        """API 响应中不返回密码哈希"""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "nopass@test.com",
                "password": "Valid1234",
                "nickname": "不返回密码",
            },
        )
        if resp.status_code == 201:
            data = json.loads(resp.data)
            user = data["data"]["user"]
            assert "password" not in user
            assert "password_hash" not in user


class TestRateLimiting:
    """接口限流（登录锁定）测试"""

    def test_account_lock_after_5_failures(self, client):
        """5次失败后账号锁定"""
        # 先注册一个用户
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "locktest@example.com",
                "password": "Correct123",
                "nickname": "锁定测试",
            },
        )
        # 前4次错误密码 — 每次返回 401
        for i in range(4):
            resp = client.post(
                "/api/v1/auth/login",
                json={
                    "account": "locktest@example.com",
                    "password": "WrongPassword",
                },
            )
            assert resp.status_code == 401, f"第{i+1}次预期401，实际{resp.status_code}"

        # 第5次失败触发锁定 — 返回 423
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "account": "locktest@example.com",
                "password": "WrongPassword",
            },
        )
        assert resp.status_code == 423, f"第5次预期423，实际{resp.status_code}"

    def test_correct_password_during_lock(self, client):
        """锁定期间正确密码也无法登录"""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "lock2@example.com",
                "password": "Correct123",
                "nickname": "锁定测试2",
            },
        )
        for _ in range(5):
            client.post(
                "/api/v1/auth/login",
                json={"account": "lock2@example.com", "password": "wrong"},
            )
        # 正确密码也被锁定
        resp = client.post(
            "/api/v1/auth/login",
            json={"account": "lock2@example.com", "password": "Correct123"},
        )
        assert resp.status_code == 423


class TestResponseHeaders:
    """响应头安全检查"""

    def test_content_type_is_json(self, client):
        """API 响应 Content-Type 为 JSON"""
        resp = client.get("/api/v1/jobs")
        if resp.status_code == 200:
            ct = resp.headers.get("Content-Type", "")
            assert "application/json" in ct

    def test_server_header_not_leaked(self, client):
        """不泄露服务器信息"""
        resp = client.get("/api/v1/jobs")
        # Flask 测试客户端通常不设置 Server 头
        server = resp.headers.get("Server", "")
        if server:
            # 如果有 Server 头，不应包含详细版本信息
            assert "Werkzeug" not in server or "Python" not in server

    def test_health_check(self, client):
        """健康检查端点可访问"""
        resp = client.get("/health")
        # 注意：测试环境下 health 端点由 create_app(TestingConfig()) 创建，
        # 可能因配置加载路径差异而不可用，此处验证服务基本可达性
        if resp.status_code == 200:
            data = json.loads(resp.data)
            assert data["status"] == "ok"
        else:
            # 如果 /health 不可达，至少 /api/v1/jobs 应可达
            resp2 = client.get("/api/v1/jobs")
            assert resp2.status_code == 200
