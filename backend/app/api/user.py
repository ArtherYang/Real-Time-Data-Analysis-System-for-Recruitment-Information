"""
用户资料 API 接口
==================
提供用户扩展信息和求职意向的查询与更新。

端点：
- GET  /api/v1/user/profile  — 获取当前用户资料+偏好
- PUT  /api/v1/user/profile  — 更新用户资料+偏好

AI生成，待人工审查。
"""

from flask import request

from . import api_bp
from ..database import get_db
from ..models.user import User
from ..models.user_profile import UserProfile
from ..models.user_preference import UserPreference
from ..utils.auth import _extract_token, decode_token
from ..utils.errors import AuthException, ValidationException
from ..utils import success_response, error_response


def _get_current_user(db):
    """从请求头解析 JWT 并返回当前用户。"""
    token = _extract_token()
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthException("令牌无效", code=401)
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise AuthException("用户不存在", code=404)
    return user


# ============================================================
# GET /user/profile
# ============================================================

@api_bp.route("/user/profile", methods=["GET"])
def get_user_profile():
    """获取当前用户的扩展资料和求职意向。

    Headers: Authorization: Bearer <token>

    Returns:
        {user, profile, preferences}
    """
    db = next(get_db())
    try:
        user = _get_current_user(db)

        profile = db.query(UserProfile).filter(
            UserProfile.user_id == user.user_id
        ).first()

        preference = db.query(UserPreference).filter(
            UserPreference.user_id == user.user_id
        ).first()

        return success_response(data={
            "user": user.to_dict(),
            "profile": profile.to_dict() if profile else None,
            "preferences": preference.to_dict() if preference else None,
        })
    except AuthException as e:
        return error_response(message=e.message, code=e.code)
    finally:
        db.close()


# ============================================================
# PUT /user/profile
# ============================================================

@api_bp.route("/user/profile", methods=["PUT"])
def update_user_profile():
    """更新当前用户的扩展资料和求职意向。

    Headers: Authorization: Bearer <token>
    Body (JSON) — 所有字段可选:
        real_name, age, university, major, city, phone, avatar_url
        desired_position, desired_city, desired_salary_min, desired_salary_max,
        industry_pref, job_type_pref
    """
    db = next(get_db())
    try:
        user = _get_current_user(db)
        data = request.get_json(silent=True)
        if not data:
            raise ValidationException("请求体不能为空")

        # ---- 更新 user_profiles ----
        profile = db.query(UserProfile).filter(
            UserProfile.user_id == user.user_id
        ).first()

        profile_fields = [
            "real_name", "age", "university", "major", "city", "phone", "avatar_url",
        ]
        profile_updated = False
        for field in profile_fields:
            if field in data:
                if profile is None:
                    profile = UserProfile(user_id=user.user_id)
                    db.add(profile)
                setattr(profile, field, data[field])
                profile_updated = True

        # ---- 更新 user_preferences ----
        preference = db.query(UserPreference).filter(
            UserPreference.user_id == user.user_id
        ).first()

        pref_fields = [
            "desired_position", "desired_city", "desired_salary_min",
            "desired_salary_max", "industry_pref", "job_type_pref",
        ]
        for field in pref_fields:
            if field in data:
                if preference is None:
                    preference = UserPreference(user_id=user.user_id)
                    db.add(preference)
                setattr(preference, field, data[field])

        db.commit()

        return success_response(data={
            "profile": profile.to_dict() if profile else None,
            "preferences": preference.to_dict() if preference else None,
        }, message="更新成功")

    except AuthException as e:
        return error_response(message=e.message, code=e.code)
    except ValidationException as e:
        return error_response(message=e.message, code=e.code)
    except Exception as e:
        db.rollback()
        return error_response(message=str(e), code=500)
    finally:
        db.close()
