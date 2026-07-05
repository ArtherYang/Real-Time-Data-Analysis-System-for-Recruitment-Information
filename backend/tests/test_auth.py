"""
用户认证模块测试
================
测试用户注册、登录、令牌刷新和个人信息管理的完整流程。

运行方式：
    pytest backend/tests/test_auth.py -v

AI生成，待人工审查。
"""

import pytest
from app import create_app
from app.config import TestingConfig
from app.database import init_db, create_tables


@pytest.fixture
def app():
    """创建测试用 Flask 应用（SQLite 内存数据库）。"""
    config = TestingConfig()
    test_app = create_app(config)
    with test_app.app_context():
        create_tables()
    yield test_app


@pytest.fixture
def client(app):
    """Flask 测试客户端。"""
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    """注册一个测试用户并返回带有 Bearer token 的请求头。"""
    client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "test1234",
        "nickname": "测试用户",
    })
    resp = client.post("/api/v1/auth/login", json={
        "account": "test@example.com",
        "password": "test1234",
    })
    data = resp.get_json()
    token = data["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# 注册测试
# ============================================================

class TestRegister:
    """用户注册接口测试。"""

    def test_register_success_with_email(self, client):
        """使用邮箱注册成功，返回201和双token。"""
        resp = client.post("/api/v1/auth/register", json={
            "email": "user1@test.com",
            "password": "pass1234",
            "nickname": "用户一",
        })
        data = resp.get_json()
        assert resp.status_code == 201
        assert data["message"] == "注册成功"
        assert data["data"]["user"]["email"] == "user1@test.com"
        assert data["data"]["user"]["nickname"] == "用户一"
        assert "password_hash" not in data["data"]["user"]
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    def test_register_success_with_phone(self, client):
        """使用手机号注册成功。"""
        resp = client.post("/api/v1/auth/register", json={
            "phone": "13800138001",
            "password": "abcd1234",
            "nickname": "手机用户",
        })
        assert resp.status_code == 201

    def test_register_missing_account(self, client):
        """邮箱和手机号都未提供时返回422。"""
        resp = client.post("/api/v1/auth/register", json={
            "password": "pass1234",
            "nickname": "无账号用户",
        })
        assert resp.status_code == 422

    def test_register_weak_password(self, client):
        """密码强度不足时返回422。"""
        resp = client.post("/api/v1/auth/register", json={
            "email": "weak@test.com",
            "password": "123",  # 太短且无字母
            "nickname": "弱密码用户",
        })
        assert resp.status_code == 422

    def test_register_password_no_letter(self, client):
        """纯数字密码返回422。"""
        resp = client.post("/api/v1/auth/register", json={
            "email": "num@test.com",
            "password": "12345678",  # 无字母
            "nickname": "纯数字",
        })
        assert resp.status_code == 422

    def test_register_password_no_digit(self, client):
        """纯字母密码返回422。"""
        resp = client.post("/api/v1/auth/register", json={
            "email": "alpha@test.com",
            "password": "abcdefgh",  # 无数字
            "nickname": "纯字母",
        })
        assert resp.status_code == 422

    def test_register_duplicate_email(self, client):
        """重复邮箱注册返回409。"""
        client.post("/api/v1/auth/register", json={
            "email": "dup@test.com",
            "password": "pass1234",
            "nickname": "首次",
        })
        resp = client.post("/api/v1/auth/register", json={
            "email": "dup@test.com",
            "password": "pass9999",
            "nickname": "重复",
        })
        assert resp.status_code == 409

    def test_register_invalid_email(self, client):
        """邮箱格式不正确返回422。"""
        resp = client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "pass1234",
            "nickname": "错误邮箱",
        })
        assert resp.status_code == 422

    def test_register_invalid_phone(self, client):
        """手机号格式不正确返回422。"""
        resp = client.post("/api/v1/auth/register", json={
            "phone": "12345",  # 不足11位
            "password": "pass1234",
            "nickname": "错误手机",
        })
        assert resp.status_code == 422


# ============================================================
# 登录测试
# ============================================================

class TestLogin:
    """用户登录接口测试。"""

    @pytest.fixture
    def _register(self, client):
        """注册一个测试用户。"""
        client.post("/api/v1/auth/register", json={
            "email": "login@test.com",
            "password": "login123",
            "nickname": "登录测试",
        })

    def test_login_success_with_email(self, client, _register):
        """邮箱登录成功，返回200和双token。"""
        resp = client.post("/api/v1/auth/login", json={
            "account": "login@test.com",
            "password": "login123",
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["message"] == "登录成功"
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["user"]["email"] == "login@test.com"

    def test_login_wrong_password(self, client, _register):
        """密码错误返回401。"""
        resp = client.post("/api/v1/auth/login", json={
            "account": "login@test.com",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        """不存在的用户返回401（与密码错误相同，防枚举）。"""
        resp = client.post("/api/v1/auth/login", json={
            "account": "nobody@test.com",
            "password": "whatever",
        })
        assert resp.status_code == 401
        assert "账号或密码错误" in resp.get_json()["message"]

    def test_login_missing_fields(self, client):
        """缺少必填字段返回422。"""
        resp = client.post("/api/v1/auth/login", json={
            "account": "someone@test.com",
        })
        assert resp.status_code == 422

    def test_login_account_locked(self, client, app):
        """登录失败达到最大次数后账号锁定。"""
        # 注册
        client.post("/api/v1/auth/register", json={
            "email": "lock@test.com",
            "password": "lock1234",
            "nickname": "锁测试",
        })
        # 连续错误密码登录 MAX_LOGIN_ATTEMPTS 次
        max_attempts = app.config.get("MAX_LOGIN_ATTEMPTS", 5)
        for i in range(max_attempts):
            resp = client.post("/api/v1/auth/login", json={
                "account": "lock@test.com",
                "password": "wrongpass",
            })
        # 最后一次应该返回锁定
        assert resp.status_code == 423

        # 正确密码也无法登录
        resp = client.post("/api/v1/auth/login", json={
            "account": "lock@test.com",
            "password": "lock1234",
        })
        assert resp.status_code == 423


# ============================================================
# 刷新令牌测试
# ============================================================

class TestRefresh:
    """令牌刷新接口测试。"""

    def test_refresh_success(self, client, auth_headers):
        """使用refresh_token成功刷新access_token。"""
        # 先登录获取 refresh_token
        client.post("/api/v1/auth/register", json={
            "email": "refresh@test.com",
            "password": "refresh1",
            "nickname": "刷新测试",
        })
        login_resp = client.post("/api/v1/auth/login", json={
            "account": "refresh@test.com",
            "password": "refresh1",
        })
        refresh_token = login_resp.get_json()["data"]["refresh_token"]

        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert "access_token" in data["data"]
        # 刷新不应返回新的 refresh_token
        assert "refresh_token" not in data["data"]

    def test_refresh_invalid_token(self, client):
        """无效token返回401。"""
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "this.is.not.valid",
        })
        assert resp.status_code == 401

    def test_refresh_missing_token(self, client):
        """缺少token返回422。"""
        resp = client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 422


# ============================================================
# 个人信息测试
# ============================================================

class TestUserProfile:
    """个人信息管理接口测试。"""

    def test_get_me_authenticated(self, client, auth_headers):
        """已认证用户获取个人信息成功。"""
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["data"]["email"] == "test@example.com"
        assert data["data"]["nickname"] == "测试用户"

    def test_get_me_unauthenticated(self, client):
        """未认证用户获取个人信息返回401。"""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        """无效token获取个人信息返回401。"""
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": "Bearer invalid_token_here",
        })
        assert resp.status_code == 401

    def test_update_nickname(self, client, auth_headers):
        """更新昵称成功。"""
        resp = client.put("/api/v1/auth/me", headers=auth_headers, json={
            "nickname": "新昵称",
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["data"]["user"]["nickname"] == "新昵称"

    def test_update_avatar(self, client, auth_headers):
        """更新头像成功。"""
        resp = client.put("/api/v1/auth/me", headers=auth_headers, json={
            "avatar_url": "https://example.com/avatar.png",
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["user"]["avatar_url"] == "https://example.com/avatar.png"

    def test_update_empty_body(self, client, auth_headers):
        """空请求体更新返回422。"""
        resp = client.put("/api/v1/auth/me", headers=auth_headers, json={})
        assert resp.status_code == 422

    def test_update_unauthenticated(self, client):
        """未认证更新返回401。"""
        resp = client.put("/api/v1/auth/me", json={"nickname": "未认证"})
        assert resp.status_code == 401
