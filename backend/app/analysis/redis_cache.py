"""
Redis 缓存加速层
================
双层缓存架构：L1 Redis（5分钟 TTL）+ L2 DB（1小时 TTL）。

读取流程：Redis 命中 → 直接返回；Redis 未命中 → 查 DB 缓存 → 回写 Redis。
写入流程：同时写入 Redis 和 DB。

需要 Redis 服务可用；不可用时自动降级到仅使用 DB 缓存。

AI生成，待人工审查。
"""

import json
import time
from typing import Optional

import redis as redis_lib

from app.config import default_config as config


class RedisCacheManager:
    """
    Redis 缓存管理器 — L1 加速层。

    使用方式：
        redis_cache = RedisCacheManager()
        if redis_cache.available:
            cached = redis_cache.get("hot_jobs", params_hash)
            if cached:
                return cached
        # 未命中，执行计算后写入
        redis_cache.set("hot_jobs", params_hash, result, ttl=300)
    """

    def __init__(self):
        """初始化 Redis 连接（不可用时标记为降级模式）。"""
        self._client = None
        self._available = None
        self._connect()

    def _connect(self):
        """尝试连接 Redis。"""
        try:
            self._client = redis_lib.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD or None,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            self._client.ping()
            self._available = True
        except Exception:
            self._client = None
            self._available = False

    @property
    def available(self) -> bool:
        """Redis 是否可用。"""
        return self._available is True

    def _key(self, cache_type: str, params_hash: str) -> str:
        """构造 Redis 键名。"""
        return f"rdas:analysis:{cache_type}:{params_hash}"

    def get(self, cache_type: str, params_hash: str) -> Optional[dict]:
        """
        从 Redis 读取缓存。

        Args:
            cache_type: 缓存类型（如 "hot_jobs"）。
            params_hash: 查询参数 SHA-256 哈希。

        Returns:
            命中返回 dict，未命中返回 None。
        """
        if not self.available:
            return None
        try:
            raw = self._client.get(self._key(cache_type, params_hash))
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def set(
        self, cache_type: str, params_hash: str, data: dict, ttl: int = 300
    ) -> bool:
        """
        写入 Redis 缓存。

        Args:
            cache_type: 缓存类型。
            params_hash: 查询参数哈希。
            data: 要缓存的数据（可 JSON 序列化）。
            ttl: 过期时间（秒），默认 300（5分钟）。

        Returns:
            写入成功返回 True。
        """
        if not self.available:
            return False
        try:
            key = self._key(cache_type, params_hash)
            self._client.setex(key, ttl, json.dumps(data, ensure_ascii=False))
            return True
        except Exception:
            return False

    def invalidate(self, cache_type: Optional[str] = None) -> int:
        """
        清除 Redis 缓存。

        Args:
            cache_type: 指定类型或全部。

        Returns:
            删除的键数量。
        """
        if not self.available:
            return 0
        try:
            pattern = f"rdas:analysis:{cache_type or '*'}:*"
            keys = list(self._client.scan_iter(match=pattern, count=100))
            if keys:
                return self._client.delete(*keys)
        except Exception:
            pass
        return 0


# 全局单例
redis_cache = RedisCacheManager()


def benchmark_analysis(func, *args, **kwargs):
    """
    执行分析函数并返回耗时和结果。

    Args:
        func: 分析函数。
        *args, **kwargs: 传递给 func 的参数。

    Returns:
        (result, elapsed_ms) 元组。
    """
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    return result, round(elapsed, 1)
