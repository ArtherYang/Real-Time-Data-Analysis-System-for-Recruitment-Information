"""
认证工具模块单元测试
====================
测试 utils/auth.py 中的密码哈希、JWT 令牌管理、登录安全控制和认证装饰器。

覆盖范围：
- hash_password / verify_password：bcrypt 密码哈希
- create_access_token / create_refresh_token / decode_token：JWT 令牌生命周期
- record_login_failure / reset_login_attempts：登录安全
- _extract_token / require_auth / require_role：认证装饰器
"""

import jwt
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

# UTC now helper
_utc_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)

from app.utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    record_login_failure,
    reset_login_attempts,
    _extract_token,
    require_auth,
    require_role,
)
from app.utils.errors import AuthException


# ============================================================
# 密码安全测试
# ============================================================

class TestPasswordHashing:
    """bcrypt 密码哈希测试"""

    def test_hash_returns_string(self):
        """哈希返回字符串"""
        result = hash_password("test1234")
        assert isinstance(result, str)
        assert len(result) > 20
        assert result.startswith("$2b$") or result.startswith("$2a$")

    def test_hash_is_deterministic_for_verification(self):
        """哈希可验证"""
        password = "MySecurePassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """错误密码验证失败"""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_case_sensitive(self):
        """密码验证区分大小写"""
        hashed = hash_password("CaseSensitive123")
        assert verify_password("casesensitive123", hashed) is False

    def test_hash_salt_is_unique(self):
        """每次哈希生成的盐值不同"""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # 不同盐值
        # 但两个哈希都能验证原始密码
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_unicode_password(self):
        """支持 Unicode 密码"""
        password = "密码测试123!@#"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


# ============================================================
# JWT 令牌管理测试
# ============================================================

class TestJWTAccessToken:
    """Access Token 测试"""

    def test_create_access_token_returns_string(self, app):
        """生成字符串格式的 JWT"""
        with app.app_context():
            token = create_access_token("user_001", "普通用户")
            assert isinstance(token, str)
            assert token.count(".") == 2  # JWT 三段结构

    def test_access_token_contains_claims(self, app):
        """JWT 包含正确的声明"""
        with app.app_context():
            token = create_access_token("user_002", "管理员")
            payload = decode_token(token)
            assert payload["sub"] == "user_002"
            assert payload["role"] == "管理员"
            assert payload["type"] == "access"
            assert "exp" in payload
            assert "iat" in payload

    def test_access_token_expiry(self, app):
        """token 过期时间正确"""
        with app.app_context():
            token = create_access_token(
                "user_003", "普通用户",
                expires_delta=timedelta(hours=1),
            )
            payload = decode_token(token)
            # 过期时间应在 59-61 分钟后
            iat = datetime.fromtimestamp(payload["iat"])
            exp = datetime.fromtimestamp(payload["exp"])
            delta = (exp - iat).total_seconds()
            assert 3590 <= delta <= 3610

    def test_expired_token_raises(self, app):
        """过期 token 抛出 AuthException"""
        with app.app_context():
            token = create_access_token(
                "user_004", "普通用户",
                expires_delta=timedelta(seconds=-1),
            )
            with pytest.raises(AuthException) as exc_info:
                decode_token(token)
            assert exc_info.value.code == 401

    def test_invalid_token_raises(self, app):
        """无效 token 抛出 AuthException"""
        with app.app_context():
            with pytest.raises(AuthException) as exc_info:
                decode_token("not.a.valid.token")
            assert exc_info.value.code == 401

    def test_wrong_secret_token_raises(self, app):
        """使用错误密钥签名的 token 被拒绝"""
        payload = {
            "sub": "user_hacker",
            "role": "管理员",
            "type": "access",
            "iat": _utc_now(),
            "exp": _utc_now() + timedelta(hours=1),
        }
        forged_token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")
        with app.app_context():
            with pytest.raises(AuthException):
                decode_token(forged_token)


class TestJWTRefreshToken:
    """Refresh Token 测试"""

    def test_create_refresh_token(self, app):
        """生成刷新令牌"""
        with app.app_context():
            token = create_refresh_token("user_005")
            payload = decode_token(token)
            assert payload["sub"] == "user_005"
            assert payload["type"] == "refresh"

    def test_refresh_token_longer_expiry(self, app):
        """刷新令牌有效期长于访问令牌"""
        with app.app_context():
            access = create_access_token("user_006", "普通用户")
            refresh = create_refresh_token("user_006")
            access_payload = decode_token(access)
            refresh_payload = decode_token(refresh)
            assert refresh_payload["exp"] >= access_payload["exp"]


# ============================================================
# 登录安全测试
# ============================================================

class TestLoginSecurity:
    """登录失败计数与账户锁定测试"""

    def test_record_login_failure_increments(self):
        """记录失败增加计数"""
        from app.models.user import User
        user = User(
            user_id="test_lock_001",
            password_hash="hash",
            nickname="测试",
            login_attempts=0,
        )
        assert user.login_attempts == 0

        with patch("flask.current_app") as mock_app:
            mock_app.config = {"MAX_LOGIN_ATTEMPTS": 5, "ACCOUNT_LOCK_MINUTES": 15}
            record_login_failure(user)
            assert user.login_attempts == 1

    def test_record_login_failure_locks_account(self):
        """失败次数达到阈值时锁定账号"""
        from app.models.user import User
        user = User(
            user_id="test_lock_002",
            password_hash="hash",
            nickname="测试",
            login_attempts=4,
        )
        assert user.is_locked() is False

        with patch("flask.current_app") as mock_app:
            mock_app.config = {"MAX_LOGIN_ATTEMPTS": 5, "ACCOUNT_LOCK_MINUTES": 15}
            record_login_failure(user)
            assert user.login_attempts == 5
            assert user.is_locked() is True

    def test_reset_login_attempts(self):
        """重置失败计数和锁定状态"""
        from app.models.user import User
        user = User(
            user_id="test_lock_003",
            password_hash="hash",
            nickname="测试",
            login_attempts=5,
            locked_until=_utc_now() + timedelta(minutes=15),
        )
        reset_login_attempts(user)
        assert user.login_attempts == 0
        assert user.locked_until is None


# ============================================================
# Token 提取测试
# ============================================================

class TestExtractToken:
    """从请求头提取 Bearer token 测试"""

    def test_extract_valid_bearer_token(self, app):
        """正确提取 Bearer token"""
        with app.test_request_context(
            headers={"Authorization": "Bearer my_token_123"}
        ):
            token = _extract_token()
            assert token == "my_token_123"

    def test_extract_missing_header_raises(self, app):
        """无 Authorization 头抛出异常"""
        with app.test_request_context():
            with pytest.raises(AuthException) as exc_info:
                _extract_token()
            assert exc_info.value.code == 401

    def test_extract_non_bearer_raises(self, app):
        """非 Bearer 类型抛出异常"""
        with app.test_request_context(
            headers={"Authorization": "Basic dXNlcjpwYXNz"}
        ):
            with pytest.raises(AuthException) as exc_info:
                _extract_token()
            assert exc_info.value.code == 401

    def test_extract_empty_header_raises(self, app):
        """空 Authorization 头抛出异常"""
        with app.test_request_context(
            headers={"Authorization": ""}
        ):
            with pytest.raises(AuthException):
                _extract_token()


# ============================================================
# require_role 装饰器测试
# ============================================================

class TestRequireRole:
    """角色鉴权装饰器测试"""

    def test_require_role_allows_matching_role(self, app):
        """匹配角色允许访问"""
        from flask import g

        @require_role("管理员")
        def admin_endpoint():
            return "OK"

        with app.test_request_context():
            g.current_user = MagicMock(role="管理员")
            result = admin_endpoint()
            assert result == "OK"

    def test_require_role_rejects_wrong_role(self, app):
        """不匹配角色拒绝访问"""
        from flask import g

        @require_role("管理员")
        def admin_endpoint():
            return "OK"

        with app.test_request_context():
            g.current_user = MagicMock(role="普通用户")
            with pytest.raises(AuthException) as exc_info:
                admin_endpoint()
            assert exc_info.value.code == 403

    def test_require_role_no_user_raises(self, app):
        """未登录用户拒绝访问"""
        from flask import g

        @require_role("管理员")
        def admin_endpoint():
            return "OK"

        with app.test_request_context():
            # 清除可能残留的 g.current_user
            if hasattr(g, "current_user"):
                del g.current_user
            with pytest.raises(AuthException) as exc_info:
                admin_endpoint()
            assert exc_info.value.code in (401, 403)

    def test_require_role_multiple_roles(self, app):
        """多角色任一匹配即可"""
        from flask import g

        @require_role("管理员", "企业HR")
        def privileged_endpoint():
            return "OK"

        with app.test_request_context():
            g.current_user = MagicMock(role="企业HR")
            result = privileged_endpoint()
            assert result == "OK"
