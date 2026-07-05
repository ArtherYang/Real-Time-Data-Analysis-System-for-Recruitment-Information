"""
BOSS直聘爬虫模块测试
====================
测试 BossZhipinCrawler 的数据解析、校验和模拟数据生成。
"""

import pytest
from datetime import datetime

from app.crawler.base import BaseCrawler, JobRawData
from app.crawler.boss import BossZhipinCrawler, generate_sample_data


class TestBossCrawlerBasic:
    """BOSS直聘爬虫基础测试"""

    def test_crawler_initialization(self):
        """爬虫初始化正确"""
        crawler = BossZhipinCrawler()
        assert crawler.name == "boss_zhipin"
        assert "zhipin.com" in crawler.base_url
        assert crawler.delay >= 3.0

    def test_crawler_inherits_base(self):
        """是 BaseCrawler 的子类"""
        crawler = BossZhipinCrawler()
        assert isinstance(crawler, BaseCrawler)

    def test_validate_rejects_missing_title(self):
        """校验拒绝缺少标题的记录"""
        crawler = BossZhipinCrawler()
        job = JobRawData(
            title="",
            company="某公司",
            source="boss_zhipin",
            crawled_at=datetime.now().isoformat(),
            platform_job_id="test_001",
        )
        assert crawler.validate(job) is False

    def test_validate_rejects_missing_platform_id(self):
        """校验拒绝缺少 platform_job_id 的记录"""
        crawler = BossZhipinCrawler()
        job = JobRawData(
            title="工程师",
            company="某公司",
            source="boss_zhipin",
            crawled_at=datetime.now().isoformat(),
            platform_job_id=None,
        )
        assert crawler.validate(job) is False

    def test_validate_accepts_valid_record(self):
        """校验接受有效记录"""
        crawler = BossZhipinCrawler()
        job = JobRawData(
            title="Python工程师",
            company="字节跳动",
            source="boss_zhipin",
            crawled_at=datetime.now().isoformat(),
            platform_job_id="boss_valid_001",
        )
        assert crawler.validate(job) is True

    def test_rate_limit_enforced(self):
        """请求频率控制生效"""
        import time
        crawler = BossZhipinCrawler(delay=0.1)
        start = time.time()
        crawler._rate_limit()
        elapsed = time.time() - start
        # 首次调用不会等待
        assert elapsed < 0.05

        start = time.time()
        crawler._rate_limit()
        elapsed = time.time() - start
        # 第二次调用会等待 >= delay
        assert elapsed >= 0.1


class TestSearchUrlConstruction:
    """搜索 URL 构造测试"""

    def test_build_search_url(self):
        """搜索 URL 正确构造"""
        crawler = BossZhipinCrawler()
        url = crawler._build_search_url("Python开发", 1)
        assert "query=" in url
        assert "page=1" in url
        assert "zhipin.com" in url

    def test_build_search_url_different_pages(self):
        """不同页码 URL 不同"""
        crawler = BossZhipinCrawler()
        url1 = crawler._build_search_url("Java", 1)
        url2 = crawler._build_search_url("Java", 3)
        assert url1 != url2
        assert "page=1" in url1
        assert "page=3" in url2


class TestSampleDataGeneration:
    """模拟数据生成测试"""

    def test_generate_sample_data_count(self):
        """生成指定数量的模拟数据"""
        jobs = generate_sample_data("Python开发", count=15)
        assert len(jobs) == 15

    def test_sample_data_has_required_fields(self):
        """模拟数据包含必填字段"""
        jobs = generate_sample_data("测试", count=5)
        for job in jobs:
            assert job.title
            assert job.company
            assert job.source == "boss_zhipin"
            assert job.crawled_at
            assert job.platform_job_id

    def test_sample_data_variety(self):
        """模拟数据包含多样性"""
        jobs = generate_sample_data("Python", count=30)
        titles = {j.title for j in jobs}
        cities = {j.location for j in jobs}
        assert len(titles) > 1, "所有岗位名称相同"
        assert len(cities) > 1, "所有城市相同"

    def test_sample_data_validates(self):
        """模拟数据通过 BaseCrawler.validate()"""
        crawler = BossZhipinCrawler()
        jobs = generate_sample_data("测试", count=10)
        valid_count = sum(1 for j in jobs if crawler.validate(j))
        assert valid_count == len(jobs)


class TestParseHelperMethods:
    """解析辅助方法测试"""

    def test_extract_text(self):
        """_extract_text 确实提取文本（静态测试）"""
        crawler = BossZhipinCrawler()
        # 加载一些实际的 HTML 时，此方法用于提取文本
        from bs4 import BeautifulSoup
        html = '<div class="test">Python工程师</div>'
        soup = BeautifulSoup(html, "html.parser")
        text = crawler._extract_text(soup, ".test")
        assert text == "Python工程师"

    def test_tag_to_experience(self):
        """经验标签识别"""
        crawler = BossZhipinCrawler()
        assert crawler._tag_to_experience(["3-5年", "本科"]) == "3-5年"
        assert crawler._tag_to_experience(["经验不限", "全职"]) == "经验不限"
        assert crawler._tag_to_experience(["本科", "全职"]) is None

    def test_tag_to_education(self):
        """学历标签识别"""
        crawler = BossZhipinCrawler()
        assert crawler._tag_to_education(["3-5年", "本科"]) == "本科"
        assert crawler._tag_to_education(["硕士", "全职"]) == "硕士"
        assert crawler._tag_to_education(["3-5年", "全职"]) is None

    def test_generate_platform_id(self):
        """平台ID生成稳定"""
        crawler = BossZhipinCrawler()
        id1 = crawler._generate_platform_id(
            "Python", "字节跳动", "北京"
        )
        id2 = crawler._generate_platform_id(
            "Python", "字节跳动", "北京"
        )
        assert id1 == id2, "相同输入应生成相同ID"
        assert len(id1) == 32, "应为32位hex哈希"
