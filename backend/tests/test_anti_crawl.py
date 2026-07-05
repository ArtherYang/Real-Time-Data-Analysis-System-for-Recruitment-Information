"""
反爬工具模块测试
================
测试 crawler/anti_crawl.py 中的 AntiCrawlManager 和 retry_request 函数。

覆盖范围：
- AntiCrawlManager: UA 轮换、请求头构造、Cookie 持久化、封锁检测
- retry_request: 重试逻辑、指数退避、错误处理
"""

import json
import os
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.crawler.anti_crawl import (
    AntiCrawlManager,
    retry_request,
    USER_AGENTS,
    DEFAULT_HEADERS,
)


class TestAntiCrawlManagerInit:
    """AntiCrawlManager 初始化测试"""

    def test_default_init(self):
        """默认初始化"""
        manager = AntiCrawlManager()
        assert manager._ua_index == 0
        assert manager.cookie_dir.exists()

    def test_custom_cookie_dir(self):
        """自定义 Cookie 目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = AntiCrawlManager(cookie_dir=tmpdir)
            assert str(manager.cookie_dir) == tmpdir


class TestUserAgentRotation:
    """User-Agent 轮换测试"""

    def test_get_random_ua_returns_string(self):
        """返回字符串"""
        manager = AntiCrawlManager()
        ua = manager.get_random_ua()
        assert isinstance(ua, str)
        assert len(ua) > 20

    def test_get_random_ua_is_valid_browser(self):
        """返回的是浏览器 UA"""
        manager = AntiCrawlManager()
        ua = manager.get_random_ua()
        assert "Mozilla" in ua or "Chrome" in ua or "Firefox" in ua or "Safari" in ua

    def test_multiple_calls_vary(self):
        """多次调用返回不同的 UA"""
        manager = AntiCrawlManager()
        ua_list = [manager.get_random_ua() for _ in range(10)]
        # 至少有两个不同的 UA
        unique_uas = set(ua_list)
        assert len(unique_uas) >= 2

    def test_user_agents_list_not_empty(self):
        """UA 池非空"""
        assert len(USER_AGENTS) >= 5


class TestGetHeaders:
    """请求头构造测试"""

    def test_get_headers_basic(self):
        """基本请求头"""
        manager = AntiCrawlManager()
        headers = manager.get_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "DNT" in headers

    def test_get_headers_with_referer(self):
        """带 Referer 的请求头"""
        manager = AntiCrawlManager()
        headers = manager.get_headers(referer="https://www.zhipin.com/")
        assert headers["Referer"] == "https://www.zhipin.com/"

    def test_get_headers_no_referer(self):
        """无 Referer"""
        manager = AntiCrawlManager()
        headers = manager.get_headers()
        assert "Referer" not in headers


class TestCookiePersistence:
    """Cookie 持久化测试"""

    def test_save_and_load_cookies(self):
        """保存和加载 Cookie 往返一致"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = AntiCrawlManager(cookie_dir=tmpdir)

            # 创建 session 并设置 Cookie
            import requests
            session = requests.Session()
            session.cookies.set("test_key", "test_value", domain="example.com")

            # 保存
            manager.save_cookies(session, "test_cookies.json")
            assert os.path.exists(os.path.join(tmpdir, "test_cookies.json"))

            # 新建一个 session 并加载
            new_session = requests.Session()
            result = manager.load_cookies(new_session, "test_cookies.json")
            assert result is True

    def test_load_nonexistent_file(self):
        """加载不存在的 Cookie 文件返回 False"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = AntiCrawlManager(cookie_dir=tmpdir)
            import requests
            session = requests.Session()
            result = manager.load_cookies(session, "nonexistent.json")
            assert result is False

    def test_load_invalid_json(self):
        """加载无效 JSON 文件返回 False"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = AntiCrawlManager(cookie_dir=tmpdir)
            filepath = os.path.join(tmpdir, "bad_cookies.json")
            with open(filepath, "w") as f:
                f.write("not valid json{{{")

            import requests
            session = requests.Session()
            result = manager.load_cookies(session, "bad_cookies.json")
            assert result is False


class TestDetectBlock:
    """封锁检测测试"""

    def test_http_403_blocked(self):
        """HTTP 403 检测为封锁"""
        manager = AntiCrawlManager()
        mock_resp = Mock(
            status_code=403, text="Forbidden"
        )
        result = manager.detect_block(mock_resp)
        assert result is not None
        assert "403" in result

    def test_http_429_rate_limited(self):
        """HTTP 429 检测为限流"""
        manager = AntiCrawlManager()
        mock_resp = Mock(status_code=429, text="Too Many Requests")
        result = manager.detect_block(mock_resp)
        assert result is not None
        assert "429" in result

    def test_http_200_no_block(self):
        """HTTP 200 不检测为封锁"""
        manager = AntiCrawlManager()
        mock_resp = Mock(status_code=200, text="<html>正常页面</html>")
        result = manager.detect_block(mock_resp)
        assert result is None

    def test_captcha_text_detected(self):
        """验证码页面被检测"""
        manager = AntiCrawlManager()
        mock_resp = Mock(
            status_code=200,
            text="请点击下方按钮进行验证，完成后即可访问",
        )
        result = manager.detect_block(mock_resp)
        assert result is not None
        assert "验证码" in result

    def test_blocked_ip_text_detected(self):
        """IP 封禁文字被检测"""
        manager = AntiCrawlManager()
        mock_resp = Mock(
            status_code=200,
            text="您的ip被禁止访问",
        )
        result = manager.detect_block(mock_resp)
        assert result is not None
        assert "IP" in result

    def test_abnormal_access_detected(self):
        """异常访问检测"""
        manager = AntiCrawlManager()
        mock_resp = Mock(
            status_code=200,
            text="系统检测到异常访问，请稍后再试",
        )
        result = manager.detect_block(mock_resp)
        assert result is not None
        assert "异常访问" in result

    def test_empty_response_text(self):
        """空响应不报错"""
        manager = AntiCrawlManager()
        mock_resp = Mock(status_code=200, text=None)
        result = manager.detect_block(mock_resp)
        assert result is None


class TestRetryRequest:
    """请求重试逻辑测试"""

    def test_successful_first_attempt(self):
        """首次尝试成功"""
        mock_func = Mock(return_value=Mock(status_code=200))
        resp, error = retry_request(mock_func, max_retries=2)
        assert resp is not None
        assert error is None
        assert mock_func.call_count == 1

    def test_retry_on_500_then_succeed(self):
        """500 后重试成功"""
        mock_func = Mock(side_effect=[
            Mock(status_code=500),
            Mock(status_code=200),
        ])
        resp, error = retry_request(mock_func, max_retries=3, backoff_factor=0.01)
        assert resp is not None
        assert resp.status_code == 200
        assert mock_func.call_count == 2

    def test_retry_on_429_then_succeed(self):
        """429 限流后重试成功"""
        mock_func = Mock(side_effect=[
            Mock(status_code=429),
            Mock(status_code=200),
        ])
        resp, error = retry_request(mock_func, max_retries=3, backoff_factor=0.01)
        assert resp is not None
        assert error is None

    def test_no_retry_on_404(self):
        """404 不重试"""
        mock_func = Mock(return_value=Mock(status_code=404))
        resp, error = retry_request(mock_func, max_retries=3)
        assert resp is None
        assert error is not None
        assert "404" in error
        assert mock_func.call_count == 1  # 不应重试

    def test_no_retry_on_403(self):
        """403 不重试"""
        mock_func = Mock(return_value=Mock(status_code=403))
        resp, error = retry_request(mock_func, max_retries=3)
        assert resp is None
        assert "403" in error
        assert mock_func.call_count == 1

    def test_retry_on_connection_error(self):
        """连接错误重试"""
        import requests as req
        mock_func = Mock(side_effect=[
            req.ConnectionError("连接被拒绝"),
            Mock(status_code=200),
        ])
        resp, error = retry_request(mock_func, max_retries=3, backoff_factor=0.01)
        assert resp is not None
        assert error is None

    def test_retry_on_timeout(self):
        """超时重试"""
        import requests as req
        mock_func = Mock(side_effect=[
            req.Timeout("请求超时"),
            Mock(status_code=200),
        ])
        resp, error = retry_request(mock_func, max_retries=3, backoff_factor=0.01)
        assert resp is not None
        assert error is None

    def test_all_retries_exhausted(self):
        """所有重试耗尽"""
        mock_func = Mock(return_value=Mock(status_code=500))
        resp, error = retry_request(mock_func, max_retries=2, backoff_factor=0.01)
        assert resp is None
        assert error is not None
        assert mock_func.call_count == 3  # 首次 + 2次重试

    def test_zero_retries(self):
        """零次重试：仅尝试一次"""
        mock_func = Mock(return_value=Mock(status_code=500))
        resp, error = retry_request(mock_func, max_retries=0, backoff_factor=0.01)
        assert resp is None
        assert mock_func.call_count == 1
