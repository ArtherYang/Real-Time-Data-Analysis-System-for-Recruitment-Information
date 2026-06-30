"""
爬虫基类
========
定义所有平台爬虫的统一接口和行为规范。

子类需要实现：
- crawl()：执行采集，返回岗位列表
- parse()：解析页面/API响应，提取结构化数据
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass
import time


@dataclass
class JobRawData:
    """原始岗位数据结构（采集后未经清洗）"""
    title: str              # 岗位名称
    company: str            # 公司名称
    salary: Optional[str]   # 薪资范围
    location: Optional[str] # 工作地点
    experience: Optional[str]  # 经验要求
    education: Optional[str]   # 学历要求
    skills: Optional[str]   # 技能要求标签
    description: Optional[str] # 岗位描述
    source: str             # 数据来源（平台名）
    source_url: Optional[str]  # 原始链接
    crawled_at: str         # 采集时间


class BaseCrawler(ABC):
    """爬虫基类"""

    def __init__(self, name: str, base_url: str, delay: float = 3.0):
        """
        初始化爬虫

        Args:
            name: 爬虫名称（如 "boss_zhipin"）
            base_url: 目标平台基础URL
            delay: 请求间隔（秒），默认3秒，防止触发反爬
        """
        self.name = name
        self.base_url = base_url
        self.delay = delay
        self._last_request_time = 0

    def _rate_limit(self):
        """请求频率控制：确保两次请求间隔 >= self.delay 秒"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    @abstractmethod
    def crawl(self, keyword: str, pages: int = 5) -> List[JobRawData]:
        """
        执行数据采集

        Args:
            keyword: 搜索关键词（如 "Python开发"）
            pages: 采集页数

        Returns:
            原始岗位数据列表
        """
        pass

    @abstractmethod
    def parse(self, raw_html: str) -> List[JobRawData]:
        """
        解析页面内容，提取结构化数据

        Args:
            raw_html: 原始HTML页面内容

        Returns:
            结构化岗位数据列表
        """
        pass

    def validate(self, data: JobRawData) -> bool:
        """
        数据校验：检查必填字段是否完整

        Args:
            data: 待校验的岗位数据

        Returns:
            校验是否通过
        """
        if not data.title or not data.company:
            return False
        if len(data.title) > 200:  # 异常长标题
            return False
        return True
