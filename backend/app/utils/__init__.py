"""
工具函数模块
============
提供 API 层通用的响应格式化、分页处理等工具函数。
"""

from typing import Any, Optional, Dict
from flask import jsonify


def success_response(
    data: Any = None,
    message: str = "success",
    code: int = 200,
    pagination: Optional[Dict] = None,
):
    """
    构造统一格式的成功响应。

    Args:
        data: 响应数据体。
        message: 提示信息。
        code: HTTP 状态码。
        pagination: 分页信息（可选）。

    Returns:
        Flask Response 对象。
    """
    body = {
        "code": code,
        "message": message,
        "data": data,
    }
    if pagination:
        body["pagination"] = pagination
    return jsonify(body), code


def error_response(
    message: str = "error",
    code: int = 400,
    data: Any = None,
):
    """
    构造统一格式的错误响应。

    Args:
        message: 错误描述。
        code: HTTP 状态码。
        data: 附加错误数据（可选）。

    Returns:
        Flask Response 对象。
    """
    body = {
        "code": code,
        "message": message,
        "data": data,
    }
    return jsonify(body), code


def pagination_info(page: int, per_page: int, total: int) -> Dict:
    """
    计算分页元数据。

    Args:
        page: 当前页码（1-based）。
        per_page: 每页条数。
        total: 总记录数。

    Returns:
        包含分页信息的字典。
    """
    pages = max(1, (total + per_page - 1) // per_page)
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }


def parse_pagination_args(request_args, max_per_page: int = 100) -> tuple:
    """
    从请求参数中解析分页参数。

    Args:
        request_args: Flask request.args 对象。
        max_per_page: 每页最大条数限制。

    Returns:
        (page, per_page) 元组。
    """
    try:
        page = max(1, int(request_args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(request_args.get("per_page", 20))
        per_page = max(1, min(per_page, max_per_page))
    except (ValueError, TypeError):
        per_page = 20

    return page, per_page
