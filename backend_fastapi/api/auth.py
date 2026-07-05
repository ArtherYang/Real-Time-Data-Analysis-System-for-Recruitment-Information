"""用户认证 API — FastAPI 版本"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.user import User, generate_uuid
from app.utils.auth import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, record_login_failure, reset_login_attempts,
)

router = APIRouter(tags=["用户认证"])

_UTC_NOW = lambda: datetime.now(timezone.utc).replace(tzinfo=None)


# ---- Pydantic Models ----

class RegisterBody(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    password: str
    nickname: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8 or len(v) > 20:
            raise ValueError("密码需8-20位")
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("密码需包含字母和数字")
        return v

    @field_validator("nickname")
    @classmethod
    def nickname_len(cls, v):
        if len(v.strip()) < 1:
            raise ValueError("昵称不能为空")
        return v.strip()


class LoginBody(BaseModel):
    account: str
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


class UpdateProfileBody(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None


# ---- Routes ----

@router.post("/auth/register")
def register(body: RegisterBody):
    if not body.email and not body.phone:
        return {"code": 400, "message": "邮箱和手机号至少填写一个", "data": None}

    session = next(get_db())
    try:
        user = User(
            user_id=generate_uuid(),
            email=body.email or None,
            phone=body.phone or None,
            password_hash=hash_password(body.password),
            nickname=body.nickname,
            role="普通用户",
            is_active=True,
            created_at=_UTC_NOW(),
        )
        session.add(user)
        session.commit()

        access_token = create_access_token(user.user_id, user.role)
        refresh_token = create_refresh_token(user.user_id)
        return {"code": 201, "message": "注册成功", "data": {
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }}
    except IntegrityError:
        session.rollback()
        return {"code": 409, "message": "邮箱或手机号已被注册", "data": None}
    finally:
        session.close()


@router.post("/auth/login")
def login(body: LoginBody):
    session = next(get_db())
    try:
        user = session.query(User).filter(
            (User.email == body.account) | (User.phone == body.account)
        ).first()

        if not user:
            return {"code": 401, "message": "账号或密码错误", "data": None}
        if not user.is_active:
            return {"code": 403, "message": "账号已被禁用", "data": None}
        if user.is_locked():
            return {"code": 423, "message": "账号已锁定，请15分钟后再试", "data": None}
        if not verify_password(body.password, user.password_hash):
            record_login_failure(user)
            return {"code": 401, "message": "账号或密码错误", "data": None}

        reset_login_attempts(user)
        access_token = create_access_token(user.user_id, user.role)
        refresh_token = create_refresh_token(user.user_id)
        return {"code": 200, "message": "登录成功", "data": {
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }}
    finally:
        session.close()


@router.post("/auth/refresh")
def refresh(body: RefreshBody):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        return {"code": 401, "message": "无效的刷新令牌", "data": None}

    user_id = payload.get("sub")
    session = next(get_db())
    try:
        user = session.query(User).filter(User.user_id == user_id, User.is_active == True).first()
        if not user:
            return {"code": 401, "message": "用户不存在", "data": None}

        new_access = create_access_token(user_id)
        return {"code": 200, "message": "success", "data": {"access_token": new_access}}
    finally:
        session.close()


@router.get("/auth/me")
def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return {"code": 401, "message": "未提供认证令牌", "data": None}

    payload = decode_token(authorization[7:])
    if not payload or payload.get("type") != "access":
        return {"code": 401, "message": "无效的访问令牌", "data": None}

    session = next(get_db())
    try:
        user = session.query(User).filter(User.user_id == payload["sub"]).first()
        if not user:
            return {"code": 404, "message": "用户不存在", "data": None}
        return {"code": 200, "message": "success", "data": {"user": user.to_dict()}}
    finally:
        session.close()


@router.put("/auth/me")
def update_profile(body: UpdateProfileBody, authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return {"code": 401, "message": "未提供认证令牌", "data": None}

    payload = decode_token(authorization[7:])
    if not payload:
        return {"code": 401, "message": "无效令牌", "data": None}

    session = next(get_db())
    try:
        user = session.query(User).filter(User.user_id == payload["sub"]).first()
        if not user:
            return {"code": 404, "message": "用户不存在", "data": None}
        if body.nickname:
            user.nickname = body.nickname
        if body.avatar_url:
            user.avatar_url = body.avatar_url
        session.commit()
        return {"code": 200, "message": "更新成功", "data": {"user": user.to_dict()}}
    finally:
        session.close()
