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
    """
    原始岗位数据结构（采集后未经清洗）

    字段来源：综合 BOSS直聘 / 智联招聘 / 前程无忧 三个平台
    必填字段（4个）：title, company, source, crawled_at
    可选字段（15个）：其余字段各平台覆盖度不同，采集不到则为 None
    """

    # ==== 必填字段 ====
    title: str                  # 岗位名称
    company: str                # 公司名称
    source: str                 # 数据来源平台标识（boss_zhipin / zhilian / job51）
    crawled_at: str             # 系统采集时间（ISO格式），注意区别于 published_at

    # ==== 岗位核心信息 ====
    salary: Optional[str] = None        # 薪资范围（如 "15K-25K"）
    location: Optional[str] = None      # 工作城市（如 "北京"）
    district: Optional[str] = None      # 区/县级别位置（如 "朝阳区"），用于城市内分布分析
    experience: Optional[str] = None    # 经验要求（如 "1-3年"）
    education: Optional[str] = None     # 学历要求（如 "本科及以上"）
    job_type: Optional[str] = None      # 工作类型（全职/兼职/实习）
    recruit_number: Optional[str] = None  # 招聘人数，反映岗位紧迫度

    # ==== 分类体系（数据分析核心维度）====
    industry: Optional[str] = None      # 所属行业（互联网/金融/教育/制造...）
    job_category: Optional[str] = None  # 岗位大类（技术/产品/运营/市场/职能...）
    skills: Optional[str] = None        # 技能标签（平台提供则直接用，否则从description中NLP提取）

    # ==== 公司信息 ====
    company_size: Optional[str] = None  # 公司规模（如 "500-2000人"）
    company_type: Optional[str] = None  # 公司类型（民营/国企/外企/上市公司...）

    # ==== 福利与描述 ====
    welfare: Optional[str] = None       # 福利标签（如 "五险一金,年终奖,弹性工作"）
    description: Optional[str] = None   # 岗位描述全文（NLP分析的主要文本源）

    # ==== 去重与溯源 ====
    platform_job_id: Optional[str] = None  # 平台原始职位ID（跨平台去重的关键）
    source_url: Optional[str] = None       # 职位详情页原始URL
    published_at: Optional[str] = None     # 岗位发布日期（来自平台，用于趋势分析）


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
        数据校验：检查必填字段完整性与数据合法性

        Args:
            data: 待校验的岗位数据

        Returns:
            校验是否通过
        """
        # 必填字段检查
        if not data.title or not data.company:
            return False
        if not data.source or not data.crawled_at:
            return False

        # 数据合法性检查
        if len(data.title) > 200:       # 异常长标题
            return False
        if len(data.company) > 100:     # 异常长公司名
            return False

        # 去重ID检查：各平台爬虫实现时必须提供
        if not data.platform_job_id:
            return False

        return True
