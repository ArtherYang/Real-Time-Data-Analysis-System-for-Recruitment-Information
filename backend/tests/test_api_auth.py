"""
认证 API 测试
=============
测试用户注册、登录和身份验证接口。

注：测试适配 linter 更新后的 auth.py，使用新的响应格式：
- 用户数据嵌套在 data.user 中
- 令牌字段为 access_token / refresh_token
"""

import json


class TestAuthRegister:
    """用户注册接口测试"""

    def test_register_success(self, client):
        """测试成功注册。"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "test1234",
                "nickname": "新用户",
            },
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["code"] == 201
        assert "注册成功" in data["message"]
        # 新格式：用户数据在 data.user 中
        assert data["data"]["user"]["email"] == "newuser@example.com"
        assert "access_token" in data["data"]

    def test_register_duplicate_email(self, client):
        """测试重复邮箱注册。"""
        # 第一次注册
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "test1234",
                "nickname": "用户A",
            },
        )
        # 第二次注册相同邮箱
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "abcd5678",
                "nickname": "用户B",
            },
        )
        assert response.status_code == 409

    def test_register_missing_fields(self, client):
        """测试缺少必填字段（新auth.py抛ValidationException → 422）。"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "password": "test1234",
            },
        )
        assert response.status_code in (400, 422)

    def test_register_weak_password(self, client):
        """测试弱密码拒绝。"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weakpw@example.com",
                "password": "12345678",  # 仅数字，无字母
                "nickname": "弱密码用户",
            },
        )
        assert response.status_code in (400, 422)

    def test_register_short_password(self, client):
        """测试短密码拒绝。"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@example.com",
                "password": "ab1",  # 只有3位
                "nickname": "短密码用户",
            },
        )
        assert response.status_code in (400, 422)

    def test_register_empty_body(self, client):
        """测试空请求体（新auth.py抛ValidationException → 422）。"""
        response = client.post("/api/v1/auth/register", data="not json")
        assert response.status_code in (400, 422)


class TestAuthLogin:
    """用户登录接口测试"""

    def test_login_success(self, client):
        """测试成功登录。"""
        # 先注册
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "logintest@example.com",
                "password": "pass1234",
                "nickname": "登录测试",
            },
        )
        # 登录
        response = client.post(
            "/api/v1/auth/login",
            json={
                "account": "logintest@example.com",
                "password": "pass1234",
            },
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["code"] == 200
        # 新格式：access_token 和 user 嵌套
        assert "access_token" in data["data"]
        assert data["data"]["user"]["email"] == "logintest@example.com"

    def test_login_wrong_password(self, client):
        """测试密码错误。"""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpw@example.com",
                "password": "correct1",
                "nickname": "密码测试",
            },
        )
        response = client.post(
            "/api/v1/auth/login",
            json={
                "account": "wrongpw@example.com",
                "password": "wrongone",
            },
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """测试不存在的用户。"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "account": "noone@example.com",
                "password": "pass1234",
            },
        )
        assert response.status_code == 401

    def test_login_empty_credentials(self, client):
        """测试空账号密码（新auth.py抛ValidationException → 422）。"""
        response = client.post(
            "/api/v1/auth/login",
            json={"account": "", "password": ""},
        )
        assert response.status_code in (400, 422)


class TestAuthMe:
    """获取当前用户信息接口测试"""

    def test_me_without_token(self, client):
        """测试无Token访问。"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self, client):
        """测试无效Token。"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert response.status_code == 401

    def test_me_with_valid_token(self, client):
        """测试使用有效Token获取用户信息。"""
        # 注册并登录获取Token
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "metest@example.com",
                "password": "pass1234",
                "nickname": "Me测试",
            },
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            json={
                "account": "metest@example.com",
                "password": "pass1234",
            },
        )
        # 新格式：access_token
        token = json.loads(login_resp.data)["data"]["access_token"]

        # 使用Token获取用户信息
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        # 新格式：用户数据在 data.user 中
        assert data["data"]["email"] == "metest@example.com"
