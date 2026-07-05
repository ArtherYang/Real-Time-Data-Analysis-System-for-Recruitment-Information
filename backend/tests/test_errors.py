"""
统一错误处理模块测试
====================
测试 utils/errors.py 中的自定义异常类和 Flask 错误处理器注册。

覆盖范围：
- AppException / AuthException / RateLimitException / ValidationException 异常类
- register_error_handlers 注册的所有 HTTP 错误处理器
"""

import json
import pytest
from flask import Flask

from app.utils.errors import (
    AppException,
    AuthException,
    RateLimitException,
    ValidationException,
    register_error_handlers,
)


class TestAppException:
    """基础应用异常测试"""

    def test_default_values(self):
        """默认构造参数"""
        e = AppException()
        assert e.message == "请求错误"
        assert e.code == 400
        assert e.data is None

    def test_custom_message_and_code(self):
        """自定义消息和状态码"""
        e = AppException("资源不存在", code=404, data={"id": "xxx"})
        assert e.message == "资源不存在"
        assert e.code == 404
        assert e.data == {"id": "xxx"}

    def test_inherits_from_exception(self):
        """是 Exception 的子类"""
        e = AppException()
        assert isinstance(e, Exception)

    def test_str_representation(self):
        """字符串表示"""
        e = AppException("错误信息")
        assert str(e) == "错误信息"


class TestAuthException:
    """认证异常测试"""

    def test_default_values(self):
        """默认未授权"""
        e = AuthException()
        assert e.code == 401
        assert "未授权" in e.message

    def test_custom_message(self):
        """自定义消息"""
        e = AuthException("令牌已过期")
        assert e.message == "令牌已过期"
        assert e.code == 401

    def test_forbidden_code(self):
        """权限不足(403)"""
        e = AuthException("权限不足", code=403)
        assert e.code == 403

    def test_inherits_from_app_exception(self):
        """继承自 AppException"""
        assert isinstance(AuthException(), AppException)


class TestRateLimitException:
    """频率限制异常测试"""

    def test_default_values(self):
        """默认 429"""
        e = RateLimitException()
        assert e.code == 429
        assert "频繁" in e.message

    def test_inherits_from_app_exception(self):
        """继承自 AppException"""
        assert isinstance(RateLimitException(), AppException)


class TestValidationException:
    """参数校验异常测试"""

    def test_default_values(self):
        """默认 422"""
        e = ValidationException()
        assert e.code == 422
        assert "校验" in e.message

    def test_with_field_errors(self):
        """带字段错误详情"""
        errors = {"email": "格式不正确", "password": "长度不足"}
        e = ValidationException("注册参数错误", data=errors)
        assert e.data == errors
        assert e.code == 422

    def test_inherits_from_app_exception(self):
        """继承自 AppException"""
        assert isinstance(ValidationException(), AppException)


class TestErrorHandlers:
    """Flask 错误处理器注册测试"""

    @pytest.fixture
    def error_app(self):
        """创建已注册错误处理器的测试 Flask 应用"""
        app = Flask(__name__)
        app.config["TESTING"] = True
        register_error_handlers(app)
        return app

    def test_app_exception_handler(self, error_app):
        """AppException 返回统一格式 JSON"""
        @error_app.route("/test_app_error")
        def raise_app_error():
            raise AppException("自定义业务错误", code=400)

        with error_app.test_client() as client:
            resp = client.get("/test_app_error")
            assert resp.status_code == 400
            body = json.loads(resp.data)
            assert body["code"] == 400
            assert "自定义业务错误" in body["message"]

    def test_auth_exception_handler(self, error_app):
        """AuthException 返回 401"""
        @error_app.route("/test_auth_error")
        def raise_auth_error():
            raise AuthException("请先登录", code=401)

        with error_app.test_client() as client:
            resp = client.get("/test_auth_error")
            assert resp.status_code == 401
            body = json.loads(resp.data)
            assert body["code"] == 401

    def test_404_handler(self, error_app):
        """404 错误返回统一格式"""
        with error_app.test_client() as client:
            resp = client.get("/nonexistent_path")
            assert resp.status_code == 404
            body = json.loads(resp.data)
            assert body["code"] == 404

    def test_405_handler(self, error_app):
        """405 错误返回统一格式"""
        @error_app.route("/post_only", methods=["POST"])
        def post_only():
            return "ok"

        with error_app.test_client() as client:
            resp = client.get("/post_only")
            assert resp.status_code == 405
            body = json.loads(resp.data)
            assert body["code"] == 405

    def test_500_handler(self, error_app):
        """500 错误返回统一格式"""
        @error_app.route("/test_500")
        def raise_500():
            1 / 0  # 触发 ZeroDivisionError

        with error_app.test_client() as client:
            resp = client.get("/test_500")
            assert resp.status_code == 500
            body = json.loads(resp.data)
            assert body["code"] == 500
            assert "服务器内部错误" in body["message"]

    def test_validation_exception_with_data(self, error_app):
        """ValidationException 附带字段错误详情"""
        @error_app.route("/test_validation")
        def raise_validation():
            raise ValidationException(
                "参数校验失败",
                data={"email": ["格式不正确"]},
            )

        with error_app.test_client() as client:
            resp = client.get("/test_validation")
            assert resp.status_code == 422
            body = json.loads(resp.data)
            assert body["data"] == {"email": ["格式不正确"]}

    def test_rate_limit_exception(self, error_app):
        """RateLimitException 返回 429"""
        @error_app.route("/test_rate_limit")
        def raise_rate_limit():
            raise RateLimitException("请求过于频繁")

        with error_app.test_client() as client:
            resp = client.get("/test_rate_limit")
            assert resp.status_code == 429
            body = json.loads(resp.data)
            assert body["code"] == 429
