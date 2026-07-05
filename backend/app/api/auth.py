"""
用户认证 API 路由
================
提供用户注册、登录、令牌刷新和个人信息管理接口。

端点列表：
- POST /api/v1/auth/register  — 用户注册
- POST /api/v1/auth/login     — 用户登录
- POST /api/v1/auth/refresh   — 刷新访问令牌
- GET  /api/v1/auth/me        — 获取当前用户信息（需认证）
- PUT  /api/v1/auth/me        — 更新个人资料（需认证）

安全设计：
- 密码使用 bcrypt 哈希加密存储
- JWT 双令牌机制（access_token 24h + refresh_token 7d）
- 登录失败次数限制（5次/15分钟锁定）
- 密码强度校验（8-20位，含字母和数字）

AI生成，待人工审查。
"""

from datetime import datetime, timezone

from flask import g, request
from sqlalchemy.exc import IntegrityError

from . import api_bp
from ..database import get_db
from ..models.user import User, generate_uuid
from ..utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    record_login_failure,
    reset_login_attempts,
    require_auth,
)
from ..utils.errors import AuthException, ValidationException
from ..utils import success_response, error_response

# 兼容：生成 UTC naive datetime（与数据库存储格式一致）
_UTC_NOW = lambda: datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================
# 输入校验
# ============================================================

def _validate_password(password: str) -> tuple:
    """
    校验密码强度。

    要求：8-20位，包含字母和数字。

    Args:
        password: 明文密码。

    Returns:
        (is_valid, error_message) 元组。
    """
    if not password:
        return False, "密码不能为空"
    if len(password) < 8 or len(password) > 20:
        return False, "密码长度需为8-20位"
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return False, "密码需包含字母和数字"
    return True, ""


def _validate_email(email: str) -> bool:
    """简单邮箱格式校验。"""
    return "@" in email and len(email) <= 100


def _validate_phone(phone: str) -> bool:
    """中国大陆手机号校验。"""
    return phone.isdigit() and len(phone) == 11


# ============================================================
# 辅助函数
# ============================================================

def _generate_token_pair(user: User) -> dict:
    """为指定用户生成 access_token 和 refresh_token。"""
    return {
        "access_token": create_access_token(user.user_id, user.role),
        "refresh_token": create_refresh_token(user.user_id),
    }


def _find_user_by_account(db, account: str):
    """通过邮箱或手机号查找用户。"""
    return db.query(User).filter(
        (User.email == account) | (User.phone == account)
    ).first()


# ============================================================
# 注册
# ============================================================

@api_bp.route("/auth/register", methods=["POST"])
def register():
    """用户注册。

    请求体 (JSON):
        email    — 邮箱地址（与 phone 至少提供一个）
        phone    — 手机号（与 email 至少提供一个）
        password — 密码（8-20位，需含字母和数字）
        nickname — 用户昵称

    成功响应 (201):
        {code: 201, message: "注册成功", data: {user: {...}, access_token, refresh_token}}
    """
    data = request.get_json(silent=True)
    if not data:
        raise ValidationException("请求体不能为空，请提供 JSON 数据")

    email = (data.get("email") or "").strip() or None
    phone = (data.get("phone") or "").strip() or None
    password = (data.get("password") or "").strip()
    nickname = (data.get("nickname") or "").strip()

    # 校验必填字段
    if not email and not phone:
        raise ValidationException("邮箱和手机号至少填写一项")
    if not nickname:
        raise ValidationException("昵称不能为空")

    # 校验密码强度
    valid, msg = _validate_password(password)
    if not valid:
        raise ValidationException(msg)

    # 校验邮箱格式
    if email and not _validate_email(email):
        raise ValidationException("邮箱格式不正确")

    # 校验手机号格式
    if phone and not _validate_phone(phone):
        raise ValidationException("手机号格式不正确，请输入11位手机号")

    db = next(get_db())
    try:
        # 检查唯一性
        if email and db.query(User).filter(User.email == email).first():
            return error_response("该邮箱已被注册", code=409)
        if phone and db.query(User).filter(User.phone == phone).first():
            return error_response("该手机号已被注册", code=409)

        # 创建用户
        user = User(
            user_id=generate_uuid(),
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            nickname=nickname,
            role="普通用户",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        tokens = _generate_token_pair(user)
        return success_response(
            data={"user": user.to_dict(), **tokens},
            message="注册成功",
            code=201,
        )

    except IntegrityError:
        db.rollback()
        return error_response("该邮箱或手机号已被注册", code=409)
    finally:
        db.close()


# ============================================================
# 登录
# ============================================================

@api_bp.route("/auth/login", methods=["POST"])
def login():
    """用户登录。

    请求体 (JSON):
        account  — 邮箱或手机号
        password — 密码

    成功响应 (200):
        {code: 200, message: "登录成功", data: {user: {...}, access_token, refresh_token}}
    """
    data = request.get_json(silent=True)
    if not data:
        raise ValidationException("请求体不能为空")

    account = (data.get("account") or "").strip()
    password = (data.get("password") or "").strip()

    if not account or not password:
        raise ValidationException("账号和密码不能为空")

    db = next(get_db())
    try:
        user = _find_user_by_account(db, account)

        # 安全：不区分"用户不存在"和"密码错误"
        if user is None:
            return error_response("账号或密码错误", code=401)

        # 检查账号状态
        if not user.is_active:
            return error_response("账号已被禁用，请联系管理员", code=403)

        if user.is_locked():
            remaining = (user.locked_until - _UTC_NOW()).seconds // 60 + 1
            return error_response(f"账号已被锁定，请{remaining}分钟后重试", code=423)

        # 验证密码
        if not verify_password(password, user.password_hash):
            record_login_failure(user)
            db.commit()
            remaining = 5 - user.login_attempts
            if remaining > 0:
                return error_response(f"账号或密码错误，还剩{remaining}次尝试机会", code=401)
            else:
                return error_response("登录失败次数过多，账号已锁定15分钟", code=423)

        # 登录成功
        reset_login_attempts(user)
        user.last_login = _UTC_NOW()
        db.commit()

        tokens = _generate_token_pair(user)
        return success_response(
            data={"user": user.to_dict(), **tokens},
            message="登录成功",
        )
    finally:
        db.close()


# ============================================================
# 刷新令牌
# ============================================================

@api_bp.route("/auth/refresh", methods=["POST"])
def refresh():
    """刷新访问令牌。

    请求体 (JSON):
        refresh_token — 刷新令牌

    成功响应 (200):
        {code: 200, message: "令牌刷新成功", data: {access_token}}
    """
    data = request.get_json(silent=True)
    if not data:
        raise ValidationException("请求体不能为空")

    token = (data.get("refresh_token") or "").strip()
    if not token:
        raise ValidationException("请提供刷新令牌")

    # 解码并验证
    payload = decode_token(token)

    if payload.get("type") != "refresh":
        raise AuthException("令牌类型错误，请使用刷新令牌", code=401)

    # 验证用户
    user_id = payload.get("sub")
    db = next(get_db())
    try:
        user = db.query(User).filter(
            User.user_id == user_id,
            User.is_active == True,
        ).first()

        if user is None:
            raise AuthException("用户不存在或账号已被禁用", code=401)

        access_token = create_access_token(user.user_id, user.role)
        return success_response(
            data={"access_token": access_token},
            message="令牌刷新成功",
        )
    finally:
        db.close()


# ============================================================
# 当前用户信息（需认证）
# ============================================================

@api_bp.route("/auth/me", methods=["GET"])
@require_auth
def get_current_user():
    """获取当前登录用户信息。

    请求头:
        Authorization: Bearer <access_token>

    成功响应 (200):
        {code: 200, message: "success", data: {user_id, email, phone, nickname, role, ...}}
    """
    return success_response(data=g.current_user.to_dict())


@api_bp.route("/auth/me", methods=["PUT"])
@require_auth
def update_profile():
    """更新当前用户个人资料（昵称、头像）。

    请求头:
        Authorization: Bearer <access_token>

    请求体 (JSON):
        nickname   — 新昵称（可选）
        avatar_url — 新头像URL（可选）

    成功响应 (200):
        {code: 200, message: "更新成功", data: {user: {...}}}
    """
    data = request.get_json(silent=True)
    if not data:
        raise ValidationException("请求体不能为空")

    nickname = (data.get("nickname") or "").strip() or None
    avatar_url = (data.get("avatar_url") or "").strip() or None

    if not nickname and not avatar_url:
        raise ValidationException("至少需要提供昵称或头像地址")

    # 重新查询用户（装饰器中的 session 已关闭）
    db = next(get_db())
    try:
        user = db.query(User).filter(User.user_id == g.current_user.user_id).first()
        if user is None:
            raise AuthException("用户不存在", code=401)

        if nickname:
            user.nickname = nickname
        if avatar_url:
            user.avatar_url = avatar_url

        db.commit()
        db.refresh(user)

        return success_response(
            data={"user": user.to_dict()},
            message="更新成功",
        )
    finally:
        db.close()
