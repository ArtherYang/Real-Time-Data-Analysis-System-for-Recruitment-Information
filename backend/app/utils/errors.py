"""
统一错误处理
============
注册 Flask 应用的全局错误处理器，确保所有错误返回统一格式的 JSON 响应。
提供业务层异常类，方便 API 层抛出可被统一捕获的异常。

AI生成，待人工审查。
"""

from typing import Any
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


# ============================================================
# 自定义异常类
# ============================================================

class AppException(Exception):
    """应用层基础异常。

    所有业务异常统一抛出此类或其子类，由 register_error_handlers 中
    的 AppException handler 统一捕获并返回标准化 JSON 响应。

    Args:
        message: 错误描述信息（会返回给客户端）。
        code: HTTP 状态码。
        data: 附加错误数据（如字段校验详情）。
    """

    def __init__(self, message: str = "请求错误", code: int = 400, data: Any = None):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(self.message)


class AuthException(AppException):
    """认证/授权异常 (401/403)。

    用于认证失败（未登录、token无效/过期 → 401）和权限不足（403）场景。
    """

    def __init__(self, message: str = "未授权", code: int = 401):
        super().__init__(message, code)


class RateLimitException(AppException):
    """请求频率限制异常 (429)。

    用于登录失败次数超限、API调用频率限制等场景。
    """

    def __init__(self, message: str = "请求过于频繁，请稍后再试"):
        super().__init__(message, code=429)


class ValidationException(AppException):
    """请求参数校验异常 (422)。

    用于表单/JSON 请求参数校验失败时返回详细的错误信息。
    Args:
        message: 错误描述。
        data: 字段级别的错误详情（dict）。
    """

    def __init__(self, message: str = "参数校验失败", data: Any = None):
        super().__init__(message, code=422, data=data)


# ============================================================
# 错误处理器注册
# ============================================================

def register_error_handlers(app: Flask) -> None:
    """在 Flask 应用上注册所有自定义错误处理器。"""

    @app.errorhandler(AppException)
    def handle_app_exception(error: AppException):
        """统一处理所有业务异常。"""
        return jsonify({
            "code": error.code,
            "message": error.message,
            "data": error.data,
        }), error.code

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            "code": 400,
            "message": "请求参数错误",
            "data": str(error.description) if hasattr(error, "description") else None,
        }), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            "code": 401,
            "message": "未授权，请先登录",
            "data": None,
        }), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            "code": 403,
            "message": "权限不足",
            "data": None,
        }), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "code": 404,
            "message": "资源不存在",
            "data": str(error.description) if hasattr(error, "description") else None,
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "code": 405,
            "message": "请求方法不允许",
            "data": None,
        }), 405

    @app.errorhandler(409)
    def conflict(error):
        """资源冲突（如重复注册）。"""
        return jsonify({
            "code": 409,
            "message": "资源冲突",
            "data": str(error.description) if hasattr(error, "description") else None,
        }), 409

    @app.errorhandler(429)
    def too_many_requests(error):
        """请求频率限制。"""
        return jsonify({
            "code": 429,
            "message": "请求过于频繁，请稍后再试",
            "data": None,
        }), 429

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"服务器内部错误: {error}")
        return jsonify({
            "code": 500,
            "message": "服务器内部错误",
            "data": None,
        }), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """兜底处理器：捕获所有未显式处理的异常。"""
        if isinstance(error, HTTPException):
            return jsonify({
                "code": error.code,
                "message": error.description or "请求错误",
                "data": None,
            }), error.code

        app.logger.exception(f"未捕获的异常: {error}")
        return jsonify({
            "code": 500,
            "message": "服务器内部错误",
            "data": None,
        }), 500
