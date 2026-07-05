"""
认证工具模块
============
提供密码哈希、JWT 令牌管理、登录安全控制和认证装饰器。

功能组：
- 密码安全：bcrypt 哈希加密与验证
- JWT 管理：access_token / refresh_token 的生成与解码
- 登录安全：失败计数与账号锁定
- 认证装饰器：require_auth（JWT 验证）、require_role（角色鉴权）

AI生成，待人工审查。
"""

import functools
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt
from flask import current_app, g, request

from ..database import get_db, SessionLocal
from ..models.user import User
from .errors import AppException, AuthException

# 兼容不同 Python 版本：统一使用 UTC 时间
_UTC_NOW = lambda: datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================
# 密码安全
# ============================================================

def hash_password(password: str) -> str:
    """使用 bcrypt 对明文密码进行哈希加密。

    Args:
        password: 明文密码（至少6位）。

    Returns:
        bcrypt 哈希字符串（可直接存入 password_hash 字段）。
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """验证明文密码是否与 bcrypt 哈希匹配。

    Args:
        password: 用户输入的明文密码。
        password_hash: 数据库中存储的 bcrypt 哈希。

    Returns:
        密码匹配返回 True，否则返回 False。
    """
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


# ============================================================
# JWT 令牌管理
# ============================================================

def _get_jwt_secret() -> str:
    """从 Flask 应用配置中获取 JWT 密钥。"""
    return current_app.config.get("JWT_SECRET_KEY", "default-jwt-secret")


def create_access_token(
    user_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """生成 JWT 访问令牌（access token）。

    Args:
        user_id: 用户唯一标识。
        role: 用户角色（用于权限判断）。
        expires_delta: 自定义过期时间，None 时使用配置的默认值（24小时）。

    Returns:
        编码后的 JWT 字符串。
    """
    if expires_delta is None:
        expires_seconds = current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES", 86400)
        expires_delta = timedelta(seconds=expires_seconds)

    now = _UTC_NOW()
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def create_refresh_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """生成 JWT 刷新令牌（refresh token）。

    Args:
        user_id: 用户唯一标识。
        expires_delta: 自定义过期时间，None 时使用配置的默认值（7天）。

    Returns:
        编码后的 JWT 字符串。
    """
    if expires_delta is None:
        expires_seconds = current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES", 604800)
        expires_delta = timedelta(seconds=expires_seconds)

    now = _UTC_NOW()
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    """解码并验证 JWT 令牌。

    Args:
        token: JWT 字符串。

    Returns:
        解码后的 payload 字典。

    Raises:
        AuthException: 令牌过期或无效时抛出（code=401）。
    """
    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=["HS256"],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthException("登录已过期，请重新登录", code=401)
    except jwt.InvalidTokenError:
        raise AuthException("令牌无效，请重新登录", code=401)


# ============================================================
# 登录安全
# ============================================================

def record_login_failure(user: User) -> None:
    """记录一次登录失败，达到阈值时锁定账号。

    应在密码验证失败后调用此函数。

    Args:
        user: 登录失败对应的用户对象。
    """
    max_attempts = current_app.config.get("MAX_LOGIN_ATTEMPTS", 5)
    lock_minutes = current_app.config.get("ACCOUNT_LOCK_MINUTES", 15)

    user.login_attempts += 1
    if user.login_attempts >= max_attempts:
        user.locked_until = _UTC_NOW() + timedelta(minutes=lock_minutes)


def reset_login_attempts(user: User) -> None:
    """登录成功后重置失败计数和锁定状态。

    Args:
        user: 登录成功的用户对象。
    """
    user.login_attempts = 0
    user.locked_until = None


# ============================================================
# 认证装饰器
# ============================================================

def _extract_token() -> str:
    """从请求头中提取 Bearer token。

    Returns:
        提取的 token 字符串。

    Raises:
        AuthException: 未提供 token 时抛出（code=401）。
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthException("未提供认证令牌，请先登录", code=401)
    return auth_header[7:]  # 去掉 "Bearer " 前缀（7个字符）


def require_auth(f):
    """认证装饰器：验证 JWT 并将用户注入 g.current_user。

    使用方式：
        @api_bp.route("/auth/me")
        @require_auth
        def get_current_user():
            user = g.current_user  # 当前登录用户
            ...

    验证流程：
    1. 从 Authorization 头提取 Bearer token
    2. 解码 JWT，验证签名和过期时间
    3. 校验 token 类型必须为 "access"
    4. 查询数据库确认用户存在且账号启用
    5. 将 User 对象注入 flask.g.current_user

    Raises:
        AuthException: 认证失败的各种情况（401/403）。
    """

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        payload = decode_token(token)

        # 校验 token 类型
        if payload.get("type") != "access":
            raise AuthException("令牌类型错误，请使用访问令牌", code=401)

        # 查询用户
        user_id = payload.get("sub")
        db = next(get_db())
        try:
            user = db.query(User).filter(
                User.user_id == user_id,
                User.is_active == True,
            ).first()

            if user is None:
                raise AuthException("用户不存在或账号已被禁用", code=401)

            if user.is_locked():
                raise AuthException("账号已被锁定，请稍后再试", code=423)

            # 注入到 flask.g
            g.current_user = user

            return f(*args, **kwargs)
        finally:
            db.close()

    return decorated


def require_role(*roles: str):
    """角色鉴权装饰器：检查当前用户是否具有指定角色。

    必须在 @require_auth 之后使用（依赖 g.current_user）。

    使用方式：
        @api_bp.route("/admin/users")
        @require_auth
        @require_role("管理员")
        def list_all_users():
            ...

    Args:
        *roles: 允许访问的角色列表（如 "管理员", "企业HR"）。

    Raises:
        AuthException: 未登录（401）或权限不足（403）。
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            current_user = getattr(g, "current_user", None)
            if current_user is None:
                raise AuthException("请先登录", code=401)

            if current_user.role not in roles:
                raise AuthException("权限不足，无法访问该资源", code=403)

            return f(*args, **kwargs)

        return decorated

    return decorator
