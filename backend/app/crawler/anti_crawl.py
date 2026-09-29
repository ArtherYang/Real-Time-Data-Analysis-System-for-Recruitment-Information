"""
反爬工具模块
============
功能：提供爬虫通用的反反爬虫工具，包括 User-Agent 轮换、请求头构造、
      Cookie 持久化、请求重试等。
输入：无（工具函数/类，供各平台爬虫调用）
输出：构造好的请求头、Session 配置等

使用方式：
    from app.crawler.anti_crawl import AntiCrawlManager

    manager = AntiCrawlManager()
    headers = manager.get_headers(referer="https://www.zhipin.com/")
"""

import os
import json
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from loguru import logger

# ======================== User-Agent 池 ========================
# 主流浏览器（Chrome / Firefox / Edge）在 Windows / macOS 上的最新 UA
USER_AGENTS: List[str] = [
    # Chrome 125 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome 124 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 125 — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Firefox 126 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Firefox 126 — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Edge 125 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    # Safari 17.5 — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Chrome 125 — Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# ======================== 默认请求头 ========================
DEFAULT_HEADERS: Dict[str, str] = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",  # Do Not Track
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class AntiCrawlManager:
    """反爬虫管理器。

    功能：
    - User-Agent 轮换（Round-Robin + 随机）
    - 请求头构造（含 Referer、Host 等）
    - Cookie 持久化（保存/加载 requests.Session）
    - 响应状态检测（识别验证码/封锁页面）

    使用示例:
        manager = AntiCrawlManager()
        session = requests.Session()
        manager.load_cookies(session, "boss_cookies.json")

        headers = manager.get_headers(referer="https://www.zhipin.com/")
        resp = session.get(url, headers=headers)
        manager.save_cookies(session, "boss_cookies.json")
    """

    def __init__(self, cookie_dir: Optional[str] = None):
        """初始化反爬管理器。

        Args:
            cookie_dir: Cookie 文件存储目录，默认为项目根目录下的 cookies/
        """
        if cookie_dir is None:
            cookie_dir = str(
                Path(__file__).resolve().parent.parent.parent / "cookies"
            )
        self.cookie_dir = Path(cookie_dir)
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self._ua_index = 0

    def get_random_ua(self) -> str:
        """获取一个 User-Agent 字符串（Round-Robin + 随机偏移）。

        采用加权轮询策略：顺序遍历UA列表，但加入随机偏移避免规律被检测。

        Returns:
            str: User-Agent 字符串
        """
        offset = random.randint(0, len(USER_AGENTS) - 1)
        self._ua_index = (self._ua_index + offset) % len(USER_AGENTS)
        return USER_AGENTS[self._ua_index]

    def get_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        """构造完整的 HTTP 请求头。

        Args:
            referer: 可选的 Referer URL

        Returns:
            dict: HTTP 请求头字典
        """
        headers = DEFAULT_HEADERS.copy()
        headers["User-Agent"] = self.get_random_ua()
        if referer:
            headers["Referer"] = referer
        return headers

    def save_cookies(self, session: requests.Session, filename: str) -> None:
        """将 Session 中的 Cookie 保存到 JSON 文件。

        Args:
            session: requests.Session 对象
            filename: 文件名（仅文件名，不含路径）
        """
        filepath = self.cookie_dir / filename
        try:
            cookies = session.cookies.get_dict()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.debug(f"Cookie 已保存至 {filepath}")
        except (OSError, IOError) as e:
            logger.warning(f"Cookie 保存失败 ({filename}): {e}")

    def load_cookies(self, session: requests.Session, filename: str) -> bool:
        """从 JSON 文件加载 Cookie 到 Session。

        Args:
            session: requests.Session 对象
            filename: 文件名（仅文件名，不含路径）

        Returns:
            bool: 是否加载成功
        """
        filepath = self.cookie_dir / filename
        if not filepath.exists():
            logger.debug(f"Cookie 文件不存在: {filepath}")
            return False
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            session.cookies.update(cookies)
            logger.debug(f"Cookie 已从 {filepath} 加载 ({len(cookies)} 条)")
            return True
        except (OSError, IOError, json.JSONDecodeError) as e:
            logger.warning(f"Cookie 加载失败 ({filename}): {e}")
            return False

    def detect_block(self, response: requests.Response) -> Optional[str]:
        """检测响应是否触发了反爬封锁。

        检查常见封锁特征：验证码页面、IP限制提示、登录重定向等。

        Args:
            response: HTTP 响应对象

        Returns:
            Optional[str]: 封锁类型描述，未封锁返回 None
        """
        text = response.text[:2000] if response.text else ""
        status = response.status_code

        # HTTP 状态码检测
        if status == 403:
            return "HTTP 403 Forbidden — IP/UA 被封"
        if status == 429:
            return "HTTP 429 Too Many Requests — 请求频率过高"
        if status == 503:
            return "HTTP 503 Service Unavailable — 服务暂时不可用"

        # 页面内容特征检测（常见验证码/拦截页面）
        block_signatures = [
            ("请点击下方按钮进行验证", "滑块验证码"),
            ("请您输入验证码", "输入验证码"),
            ("访问过于频繁", "频率限制页"),
            ("ip被禁止", "IP被封禁"),
            ("系统检测到异常访问", "异常访问检测"),
            ("请先登录", "登录重定向"),
            ("_AntiSpam", "反垃圾页面"),
        ]
        for keyword, block_type in block_signatures:
            if keyword in text:
                return f"检测到封锁特征: {block_type}"

        return None


def retry_request(
    request_func,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    *args,
    **kwargs,
) -> Tuple[Optional[requests.Response], Optional[str]]:
    """带指数退避的请求重试包装器。

    在遇到网络错误、5xx错误、429限流时自动重试。

    Args:
        request_func: 可调用对象（如 session.get），返回 requests.Response
        max_retries: 最大重试次数（不含首次）
        backoff_factor: 退避因子，延迟 = backoff_factor ** retry_num 秒
        *args: 传递给 request_func 的位置参数
        **kwargs: 传递给 request_func 的关键字参数

    Returns:
        Tuple[Optional[Response], Optional[str]]:
            - 成功: (response, None)
            - 失败: (None, error_message)

    使用示例:
        resp, err = retry_request(session.get, 3, 2.0, url, headers=headers)
        if err:
            logger.error(f"请求失败: {err}")
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = request_func(*args, **kwargs)

            # 检查 HTTP 状态码
            if response.status_code < 400:
                return response, None

            # 4xx 客户端错误（非429）不重试
            if (
                400 <= response.status_code < 500
                and response.status_code != 429
            ):
                return None, (
                    f"HTTP {response.status_code} — 客户端错误，不重试"
                )

            # 5xx 或 429 记录错误并重试
            last_error = f"HTTP {response.status_code}"
            logger.warning(
                f"请求返回 {response.status_code}，"
                f"第 {attempt + 1}/{max_retries + 1} 次尝试"
            )

        except requests.Timeout as e:
            last_error = f"请求超时: {e}"
            logger.warning(f"请求超时 (尝试 {attempt + 1}/{max_retries + 1})")
        except requests.ConnectionError as e:
            last_error = f"连接错误: {e}"
            logger.warning(f"连接错误 (尝试 {attempt + 1}/{max_retries + 1})")
        except requests.RequestException as e:
            last_error = f"请求异常: {e}"
            logger.warning(f"请求异常 (尝试 {attempt + 1}/{max_retries + 1}): {e}")

        # 最后一次尝试失败后不再等待
        if attempt < max_retries:
            delay = backoff_factor ** (attempt + 1)
            jitter = random.uniform(0, delay * 0.5)
            time.sleep(delay + jitter)

    return None, last_error


# ======================== 多 Cookie 池（BOSS直聘专用） ========================


class CookiePool:
    """多 Cookie 轮换池。

    管理多个预置 Cookie，在请求时随机轮换，避免单一 Cookie 被限流。
    适用于 BOSS直聘等有较强反爬机制的平台。

    参考 bosszp-master 开源项目的 Cookie 轮换思路。

    使用示例:
        pool = CookiePool([
            {"__zp_stoken__": "abc123..."},
            {"__zp_stoken__": "def456..."},
        ])
        session = requests.Session()
        pool.apply_random(session)  # 每次请求前调用
    """

    def __init__(self, cookies: Optional[List[Dict[str, str]]] = None):
        """初始化 Cookie 池。

        Args:
            cookies: Cookie 字典列表，每个字典是一组 cookie 键值对。
                     如果为 None，使用内置默认池。
        """
        self._cookies = cookies or self._default_cookies()
        self._index = 0
        logger.info(
            f"[CookiePool] 初始化完成, 共 {len(self._cookies)} 组 Cookie"
        )

    @staticmethod
    def _default_cookies() -> List[Dict[str, str]]:
        """内置默认 Cookie 池（BOSS直聘 __zp_stoken__ 占位值）。

        请替换为自己的真实 token；默认值为占位符，不含任何有效凭证。

        Returns:
            List[Dict[str, str]]: 默认 Cookie 列表
        """
        return [
            {
                "__zp_stoken__": "YOUR_ZP_STOKEN_1",
            },
            {
                "__zp_stoken__": "YOUR_ZP_STOKEN_2",
            },
            {
                "__zp_stoken__": "YOUR_ZP_STOKEN_3",
            },
            {
                "__zp_stoken__": "YOUR_ZP_STOKEN_4",
            },
            {
                "__zp_stoken__": "YOUR_ZP_STOKEN_5",
            },
        ]

    def get_random(self) -> Dict[str, str]:
        """随机获取一组 Cookie。

        Returns:
            Dict[str, str]: Cookie 字典
        """
        return random.choice(self._cookies)

    def get_next(self) -> Dict[str, str]:
        """轮询获取下一组 Cookie（Round-Robin）。

        Returns:
            Dict[str, str]: Cookie 字典
        """
        cookie = self._cookies[self._index % len(self._cookies)]
        self._index += 1
        return cookie

    def apply_random(self, session: requests.Session) -> None:
        """将随机一组 Cookie 应用到 Session。

        Args:
            session: requests.Session 对象
        """
        for key, value in self.get_random().items():
            session.cookies.set(key, value)

    def apply_next(self, session: requests.Session) -> None:
        """将下一组 Cookie（轮询）应用到 Session。

        Args:
            session: requests.Session 对象
        """
        for key, value in self.get_next().items():
            session.cookies.set(key, value)

    def add_cookie(self, cookie_dict: Dict[str, str]) -> None:
        """向池中添加一组新 Cookie。

        Args:
            cookie_dict: Cookie 字典
        """
        if cookie_dict not in self._cookies:
            self._cookies.append(cookie_dict)
            logger.debug(f"[CookiePool] 新增Cookie, 池大小: {len(self._cookies)}")

    @property
    def size(self) -> int:
        """Cookie 池大小。"""
        return len(self._cookies)
