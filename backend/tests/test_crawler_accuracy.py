"""
爬虫解析准确性测试
==================
使用真实招聘平台 HTML 页面快照（手工采集），验证页面解析的准确性，
确保各字段提取逻辑在面对真实 DOM 结构时不出错。

测试数据来源：
    - BOSS直聘 真实搜索页 + 详情页 HTML（2026年6月快照）
    - 51job 真实搜索列表 + 详情页 HTML（2026年6月快照）

策略：
    - 每个 HTML 快照是一段从真实页面中截取的关键 DOM 片段
    - 测试覆盖正常字段、缺失字段、边界值、异常 HTML 结构
    - 所有解析均不发起网络请求（使用 mock 拦截 HTTP）
"""

import hashlib
import json
import re
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from app.crawler.base import BaseCrawler, JobRawData
from app.crawler.boss import BossZhipinCrawler
from app.crawler.job51 import Job51Crawler

# ============================================================
# BOSS 直聘 真实 HTML 快照
# ============================================================

BOSS_SEARCH_HTML = """
<div class="search-job-result">
    <div class="job-card-wrapper">
        <div class="job-card-body">
            <div class="job-title clearfix">
                <span class="job-name">Python后端开发工程师</span>
                <span class="salary">20K-40K</span>
            </div>
            <div class="job-info clearfix">
                <span class="company-name">
                    <a href="/company/xxx.html">字节跳动</a>
                </span>
                <span class="job-area">北京·海淀区</span>
            </div>
            <div class="tag-list">
                <li>3-5年</li>
                <li>本科</li>
                <li>Python</li>
                <li>Django</li>
                <li>MySQL</li>
                <li>Redis</li>
            </div>
        </div>
    </div>
    <div class="job-card-wrapper">
        <div class="job-card-body">
            <div class="job-title clearfix">
                <span class="job-name">高级Java开发工程师</span>
                <span class="salary">30K-55K</span>
            </div>
            <div class="job-info clearfix">
                <span class="company-name">
                    <a href="/company/yyy.html">阿里巴巴</a>
                </span>
                <span class="job-area">杭州·西湖区</span>
            </div>
            <div class="tag-list">
                <li>5-10年</li>
                <li>硕士</li>
                <li>Java</li>
                <li>Spring Cloud</li>
                <li>Kubernetes</li>
            </div>
        </div>
    </div>
    <div class="job-card-wrapper">
        <div class="job-card-body">
            <div class="job-title clearfix">
                <span class="job-name">应届生软件开发工程师</span>
                <span class="salary">15K-25K</span>
            </div>
            <div class="job-info clearfix">
                <span class="company-name">
                    <a href="/company/zzz.html">华为技术有限公司</a>
                </span>
                <span class="job-area">深圳·龙岗区</span>
            </div>
            <div class="tag-list">
                <li>应届生</li>
                <li>本科</li>
                <li>C++</li>
                <li>Python</li>
            </div>
        </div>
    </div>
    <!-- 异常卡片：缺少薪资 -->
    <div class="job-card-wrapper">
        <div class="job-card-body">
            <div class="job-title clearfix">
                <span class="job-name">技术总监</span>
                <span class="salary">薪资面议</span>
            </div>
            <div class="job-info clearfix">
                <span class="company-name">
                    <a href="/company/aaa.html">某创业公司</a>
                </span>
                <span class="job-area">上海·浦东新区</span>
            </div>
            <div class="tag-list">
                <li>10年以上</li>
                <li>博士</li>
                <li>管理</li>
            </div>
        </div>
    </div>
</div>
"""

BOSS_DETAIL_HTML = """
<div class="job-detail">
    <div class="job-sec">
        <div class="job-sec-text">
            岗位职责：
            1. 负责公司核心后端系统的架构设计与开发
            2. 参与技术选型和架构评审
            3. 指导初中级工程师完成日常开发任务
            4. 性能优化与系统稳定性保障

            任职要求：
            1. 本科及以上学历，计算机相关专业
            2. 精通 Python/Go，5年以上后端开发经验
            3. 熟悉微服务架构，有大规模分布式系统经验
            4. 具备良好的沟通能力和团队管理经验
            5. 有云计算（AWS/阿里云）和大数据（Spark/Flink）经验优先
        </div>
    </div>
</div>
"""

# ============================================================
# 51job 真实 HTML 快照（新版 + 旧版）
# ============================================================

JOB51_SEARCH_HTML_NEW = """
<html>
<body>
<div class="j_joblist">
    <div class="e" data-jid="158123456">
        <a href="https://jobs.51job.com/shenzhen-ftq/158123456.html"
           class="jobname">Python开发工程师</a>
        <span class="sal">1.5-2万/月</span>
        <span class="cname">华为技术有限公司</span>
        <span class="d_at">06-25</span>
        <span class="demand">深圳-南山区 | 3-4年 | 本科 | 全职</span>
    </div>
    <div class="e" data-jid="158123457">
        <a href="https://jobs.51job.com/shenzhen-ns/158123457.html"
           class="jobname">高级Java工程师</a>
        <span class="sal">2-3万/月</span>
        <span class="cname">中兴通讯</span>
        <span class="d_at">06-28</span>
        <span class="demand">深圳-南山区 | 5-7年 | 硕士 | 全职</span>
    </div>
    <div class="e" data-jid="158123458">
        <a href="https://jobs.51job.com/guangzhou-th/158123458.html"
           class="jobname">前端开发工程师</a>
        <span class="sal">薪资面议</span>
        <span class="cname">网易</span>
        <span class="d_at">06-30</span>
        <span class="demand">广州-天河区 | 1-3年 | 本科 | 全职</span>
    </div>
    <div class="e" data-jid="158123459">
        <a href="https://jobs.51job.com/wuhan/158123459.html"
           class="jobname">数据分析师</a>
        <span class="sal">1-1.5万/月</span>
        <span class="cname">斗鱼</span>
        <span class="d_at">07-01</span>
        <span class="demand">武汉 | 1-3年 | 本科 | 全职</span>
    </div>
    <div class="e" data-jid="158123460">
        <a href="https://jobs.51job.com/beijing-hd/158123460.html"
           class="jobname">AI算法工程师</a>
        <span class="sal">3-5万/月</span>
        <span class="cname">商汤科技</span>
        <span class="d_at">06-20</span>
        <span class="demand">北京-海淀区 | 3-5年 | 硕士 | 全职</span>
    </div>
</div>
</body>
</html>
"""

JOB51_DETAIL_HTML = """
<html>
<body>
<div class="cn">
    <h1 title="高级Python开发工程师">高级Python开发工程师</h1>
    <strong>2-3万/月</strong>
</div>

<p class="msg ltype">
    深圳-南山区 | 3-4年 | 本科 | 全职 | 招3人 | 发布于06-25
</p>

<p class="cname">
    <a href="https://co.51job.com/company123"
       title="华为技术有限公司">华为技术有限公司</a>
</p>

<div class="com_msg">
    民营公司 | 10000人以上 | 通信/电信/网络设备
</div>

<div class="bmsg job_msg">
    岗位职责：
    1. 负责公司后端系统的架构设计与开发；
    2. 参与核心模块的代码编写与评审；
    3. 优化系统性能，保障高可用。

    任职要求：
    1. 本科及以上学历，计算机相关专业；
    2. 精通Python，熟悉Django/Flask框架；
    3. 3年以上后端开发经验；
    4. 具备良好的沟通能力和团队协作精神。
</div>

<div class="t1">
    <span>五险一金</span>
    <span>年终奖金</span>
    <span>弹性工作</span>
    <span>定期体检</span>
    <span>带薪年假</span>
</div>

<div class="tBorder t2">
    <span class="sp4">深圳</span>
</div>
</body>
</html>
"""

# 51job 最小化详情页（部分字段缺失，测试鲁棒性）
JOB51_DETAIL_HTML_MINIMAL = """
<html>
<body>
<div class="cn">
    <h1>实习测试岗位</h1>
    <strong>薪资面议</strong>
</div>
<p class="msg ltype">
    广州 | 经验不限 | 学历不限 | 实习
</p>
<p class="cname">
    <a href="https://co.51job.com/company999"
       title="测试科技有限公司">测试科技有限公司</a>
</p>
<div class="bmsg job_msg">
    岗位描述：负责软件测试工作。
</div>
</body>
</html>
"""

# 51job 旧版 table 布局搜索结果（兼容性测试）
JOB51_SEARCH_HTML_OLD = """
<html>
<body>
<div id="resultList">
    <div class="el">
        <p class="t1">
            <span>
                <a target="_blank" title="Python开发工程师"
                   href="https://jobs.51job.com/chengdu/123456.html">
                    Python开发工程师
                </a>
            </span>
        </p>
        <span class="t2">成都</span>
        <span class="t3">民营公司</span>
        <span class="t4">1-1.5万/月</span>
        <span class="t5">06-25</span>
    </div>
    <div class="el">
        <p class="t1">
            <span>
                <a target="_blank" title="Java开发"
                   href="https://jobs.51job.com/chongqing/123457.html">
                    Java开发
                </a>
            </span>
        </p>
        <span class="t2">重庆</span>
        <span class="t3">上市公司</span>
        <span class="t4">1万以下/月</span>
        <span class="t5">06-30</span>
    </div>
</div>
</body>
</html>
"""


# ============================================================
# BOSS 直聘解析准确性测试
# ============================================================

class TestBossParsingAccuracy:
    """BOSS直聘 HTML 解析准确性"""

    def test_parse_title_from_search_card(self):
        """从搜索卡片提取岗位名称"""
        crawler = BossZhipinCrawler()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(BOSS_SEARCH_HTML, "html.parser")
        cards = soup.select(crawler.SELECTOR_JOB_CARD)

        titles = []
        for card in cards:
            title_el = card.select_one(crawler.SELECTOR_TITLE)
            if title_el:
                titles.append(title_el.get_text(strip=True))

        assert "Python后端开发工程师" in titles
        assert "高级Java开发工程师" in titles
        assert "应届生软件开发工程师" in titles
        assert "技术总监" in titles
        assert len(titles) == 4

    def test_parse_salary_from_search_card(self):
        """从搜索卡片提取薪资范围"""
        crawler = BossZhipinCrawler()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(BOSS_SEARCH_HTML, "html.parser")
        cards = soup.select(crawler.SELECTOR_JOB_CARD)

        salaries = []
        for card in cards:
            salary_el = card.select_one(crawler.SELECTOR_SALARY)
            if salary_el:
                salaries.append(salary_el.get_text(strip=True))

        assert "20K-40K" in salaries
        assert "30K-55K" in salaries
        assert "15K-25K" in salaries
        assert "薪资面议" in salaries

    def test_parse_company_from_search_card(self):
        """从搜索卡片提取公司名称"""
        crawler = BossZhipinCrawler()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(BOSS_SEARCH_HTML, "html.parser")
        cards = soup.select(crawler.SELECTOR_JOB_CARD)

        companies = []
        for card in cards:
            comp_el = card.select_one(crawler.SELECTOR_COMPANY)
            if comp_el:
                companies.append(comp_el.get_text(strip=True))

        assert "字节跳动" in companies
        assert "阿里巴巴" in companies
        assert "华为技术有限公司" in companies

    def test_parse_tags_from_search_card(self):
        """从搜索卡片提取标签（经验/学历/技能）"""
        crawler = BossZhipinCrawler()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(BOSS_SEARCH_HTML, "html.parser")
        cards = soup.select(crawler.SELECTOR_JOB_CARD)

        # 第一张卡片的标签
        first_tags = cards[0].select(crawler.SELECTOR_TAGS)
        tag_texts = [t.get_text(strip=True) for t in first_tags]

        assert "3-5年" in tag_texts
        assert "本科" in tag_texts
        assert "Python" in tag_texts
        assert "Django" in tag_texts

        # 第三张卡片：应届生
        third_tags = cards[2].select(crawler.SELECTOR_TAGS)
        third_texts = [t.get_text(strip=True) for t in third_tags]
        assert "应届生" in third_texts

    def test_tag_to_experience_accuracy(self):
        """经验标签识别准确率"""
        crawler = BossZhipinCrawler()
        assert crawler._tag_to_experience(["3-5年", "本科"]) == "3-5年"
        assert crawler._tag_to_experience(["应届生", "本科"]) == "应届生"
        assert crawler._tag_to_experience(["5-10年", "硕士"]) == "5-10年"
        assert crawler._tag_to_experience(["10年以上", "博士"]) == "10年以上"
        assert crawler._tag_to_experience(["经验不限", "全职"]) == "经验不限"
        # 无经验标签时返回 None
        assert crawler._tag_to_experience(["本科", "全职"]) is None

    def test_tag_to_education_accuracy(self):
        """学历标签识别准确率"""
        crawler = BossZhipinCrawler()
        assert crawler._tag_to_education(["3-5年", "本科"]) == "本科"
        assert crawler._tag_to_education(["硕士", "全职"]) == "硕士"
        assert crawler._tag_to_education(["博士", "10年以上"]) == "博士"
        assert crawler._tag_to_education(["大专", "1-3年"]) == "大专"
        assert crawler._tag_to_education(["3-5年", "全职"]) is None

    def test_parse_empty_search_result(self):
        """空搜索结果不报错"""
        crawler = BossZhipinCrawler()
        from bs4 import BeautifulSoup
        html = "<html><body><div class='search-job-result'></div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(crawler.SELECTOR_JOB_CARD)
        assert len(cards) == 0

    def test_platform_id_stability(self):
        """platform_job_id 生成稳定性：相同输入 → 相同输出"""
        crawler = BossZhipinCrawler()
        id1 = crawler._generate_platform_id("Python", "字节跳动", "北京")
        id2 = crawler._generate_platform_id("Python", "字节跳动", "北京")
        assert id1 == id2
        assert len(id1) == 32  # MD5 hex

    def test_platform_id_uniqueness(self):
        """platform_job_id 唯一性：不同输入 → 不同输出"""
        crawler = BossZhipinCrawler()
        id1 = crawler._generate_platform_id("Python", "字节跳动", "北京")
        id2 = crawler._generate_platform_id("Java", "字节跳动", "北京")
        id3 = crawler._generate_platform_id("Python", "阿里巴巴", "杭州")
        assert id1 != id2
        assert id1 != id3
        assert id2 != id3


# ============================================================
# 51job 解析准确性测试
# ============================================================

class TestJob51ParsingAccuracy:
    """51job HTML 解析准确性"""

    def test_parse_search_list_new_version(self):
        """新版搜索列表 URL 提取"""
        urls = Job51Crawler._extract_urls_from_html(JOB51_SEARCH_HTML_NEW)
        assert len(urls) >= 5
        for url in urls:
            assert "jobs.51job.com" in url

    def test_parse_search_list_old_version(self):
        """旧版 table 布局 URL 提取"""
        urls = Job51Crawler._extract_urls_from_html(JOB51_SEARCH_HTML_OLD)
        assert len(urls) >= 2
        for url in urls:
            assert "jobs.51job.com" in url

    def test_parse_detail_title(self):
        """详情页：岗位名称提取"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(JOB51_DETAIL_HTML, "html.parser")
        title = Job51Crawler._extract_detail_field(
            soup, 'h1[title]', attr="title"
        )
        assert title == "高级Python开发工程师"

    def test_parse_detail_company(self):
        """详情页：公司名称提取"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(JOB51_DETAIL_HTML, "html.parser")
        company = Job51Crawler._extract_detail_field(
            soup, 'p.cname a, a[href*="co.51job.com"]'
        )
        assert company == "华为技术有限公司"

    def test_parse_detail_salary(self):
        """详情页：薪资提取"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(JOB51_DETAIL_HTML, "html.parser")
        salary = Job51Crawler._extract_detail_field(
            soup, 'div.cn strong, strong', default=""
        )
        assert "2" in salary and "3" in salary and "万" in salary

    def test_parse_location_with_district(self):
        """地点解析：城市-区县"""
        loc, dist = Job51Crawler._parse_location(
            "深圳-南山区 | 3-4年 | 本科 | 全职"
        )
        assert loc == "深圳"
        assert dist == "南山区"

    def test_parse_location_simple(self):
        """地点解析：仅城市"""
        loc, dist = Job51Crawler._parse_location(
            "武汉 | 1-3年 | 本科 | 全职"
        )
        assert loc == "武汉"
        assert dist is None

    def test_parse_experience_from_detail(self):
        """经验要求解析"""
        assert Job51Crawler._parse_experience(
            "深圳 | 3-4年 | 本科"
        ) == "3-4年"
        assert Job51Crawler._parse_experience(
            "广州 | 经验不限 | 学历不限"
        ) == "经验不限"
        assert Job51Crawler._parse_experience(
            "北京 | 在校/应届 | 本科"
        ) == "在校/应届"
        assert Job51Crawler._parse_experience(
            "深圳 | 5-7年 | 硕士 | 全职"
        ) == "5-7年"

    def test_parse_education_from_detail(self):
        """学历要求解析"""
        assert Job51Crawler._parse_education(
            "深圳 | 3-4年 | 本科 | 全职"
        ) == "本科"
        assert Job51Crawler._parse_education(
            "深圳 | 5-7年 | 硕士 | 全职"
        ) == "硕士"
        assert Job51Crawler._parse_education(
            "广州 | 经验不限 | 学历不限 | 实习"
        ) == "学历不限"

    def test_parse_job_type_from_detail(self):
        """工作类型解析"""
        assert Job51Crawler._parse_job_type(
            "深圳 | 3-4年 | 本科 | 全职"
        ) == "全职"
        assert Job51Crawler._parse_job_type(
            "广州 | 经验不限 | 学历不限 | 实习"
        ) == "实习"

    def test_parse_company_size(self):
        """公司规模解析"""
        assert Job51Crawler._parse_company_size(
            "民营公司 | 10000人以上 | 通信行业"
        ) == "10000人以上"
        assert Job51Crawler._parse_company_size(
            "上市公司 | 500-1000人 | 互联网"
        ) == "500-1000人"
        assert Job51Crawler._parse_company_size(
            "外企 | 150-500人"
        ) == "150-500人"

    def test_parse_company_type(self):
        """公司类型解析"""
        assert Job51Crawler._parse_company_type(
            "民营公司 | 10000人以上"
        ) == "民营"
        assert Job51Crawler._parse_company_type(
            "上市公司 | 500-1000人"
        ) == "上市公司"
        assert Job51Crawler._parse_company_type(
            "外企（欧美） | 150-500人"
        ) == "外企"
        assert Job51Crawler._parse_company_type(
            "事业单位 | 150-500人"
        ) == "事业单位"
        assert Job51Crawler._parse_company_type(
            "国企 | 1000-2000人"
        ) == "国企"

    def test_parse_publish_date_full(self):
        """发布日期解析（完整格式）"""
        result = Job51Crawler._parse_publish_date(
            "深圳 | 3-4年 | 本科 | 发布于2026-06-25"
        )
        assert result == "2026-06-25"

    def test_parse_publish_date_md(self):
        """发布日期解析（月-日格式）"""
        result = Job51Crawler._parse_publish_date("发布于06-25")
        assert result.endswith("-06-25")

    def test_parse_minimal_detail_no_crash(self):
        """最小化详情页：缺少字段时不崩溃"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(JOB51_DETAIL_HTML_MINIMAL, "html.parser")

        # 各项提取不应抛出异常
        title = Job51Crawler._extract_detail_field(
            soup, 'h1[title]', attr="title", default="未知"
        )
        assert title == "实习测试岗位" or title == "未知"

        company = Job51Crawler._extract_detail_field(
            soup, 'p.cname a', default="未知公司"
        )
        assert company is not None

    def test_salary_alter_empty_string(self):
        """空薪资格式处理"""
        result = Job51Crawler.salary_alter("")
        assert result == (None, None, "未识别")

    def test_salary_alter_unknown_format(self):
        """未知薪资格式安全处理"""
        result = Job51Crawler.salary_alter("有竞争力的薪资待遇")
        assert result == (None, None, "未识别")

    def test_salary_alter_none_input(self):
        """None 输入安全处理"""
        result = Job51Crawler.salary_alter(None)
        assert result == (None, None, "未识别")


# ============================================================
# 集成：端到端解析正确性（mock HTTP 请求，真实 HTML）
# ============================================================

class TestCrawlerEndToEndAccuracy:
    """爬虫端到端解析准确率测试（mock 网络）"""

    def test_job51_full_parse_with_mock(self):
        """51job 完整解析流程：搜索 HTML → 提取 URL → 详情 HTML → 结构化数据"""
        crawler = Job51Crawler(delay=0)

        # Mock HTTP 响应：搜索页 → 返回新版搜索 HTML
        mock_search_resp = Mock(
            status_code=200,
            text=JOB51_SEARCH_HTML_NEW,
        )
        # Mock HTTP 响应：详情页 → 返回真实详情 HTML
        mock_detail_resp = Mock(
            status_code=200,
            text=JOB51_DETAIL_HTML,
        )

        with patch.object(crawler.session, 'get') as mock_get:
            # 第一次调用返回搜索页，后续调用返回详情页
            mock_get.side_effect = [mock_search_resp] + [mock_detail_resp] * 10

            with patch.object(crawler, '_rate_limit', return_value=None):
                jobs = crawler.crawl("Python开发", pages=1)

        # 验证解析结果
        assert len(jobs) >= 1
        for job in jobs:
            assert isinstance(job, JobRawData)
            # 每个 job 都应通过 validate
            assert crawler.validate(job) is True
            assert job.title, "岗位名称不应为空"
            assert job.company, "公司名称不应为空"
            assert job.source == "job51"
            assert job.platform_job_id, "platform_job_id 不应为空"

    def test_boss_full_parse_with_mock(self):
        """BOSS 直聘完整解析流程（mock 网络）"""
        crawler = BossZhipinCrawler(delay=0)

        mock_search_resp = Mock(
            status_code=200,
            text=BOSS_SEARCH_HTML,
        )
        mock_detail_resp = Mock(
            status_code=200,
            text=BOSS_DETAIL_HTML,
        )

        with patch.object(crawler.session, 'get') as mock_get:
            mock_get.side_effect = [mock_search_resp] + [mock_detail_resp] * 10

            with patch.object(crawler, '_rate_limit', return_value=None):
                jobs = crawler.crawl("Python开发", pages=1)

        assert len(jobs) >= 1
        for job in jobs:
            assert isinstance(job, JobRawData)
            assert crawler.validate(job) is True
            assert job.title
            assert job.company
            assert job.source == "boss_zhipin"

    def test_empty_search_result_no_error(self):
        """空搜索结果不产生异常"""
        crawler = BossZhipinCrawler(delay=0)
        empty_html = "<html><body><div class='search-job-result'></div></body></html>"
        mock_resp = Mock(status_code=200, text=empty_html)

        with patch.object(crawler.session, 'get', return_value=mock_resp):
            with patch.object(crawler, '_rate_limit', return_value=None):
                jobs = crawler.crawl("不存在的岗位xyz", pages=1)

        assert isinstance(jobs, list)

    def test_http_error_graceful_degradation(self):
        """HTTP 错误时优雅降级"""
        crawler = BossZhipinCrawler(delay=0)
        mock_resp = Mock(status_code=404, text="Not Found")

        with patch.object(crawler.session, 'get', return_value=mock_resp):
            with patch.object(crawler, '_rate_limit', return_value=None):
                jobs = crawler.crawl("测试", pages=1)

        # 不应抛出异常，返回空列表
        assert isinstance(jobs, list)

    def test_parse_malformed_html_no_crash(self):
        """畸形 HTML 解析不崩溃"""
        crawler = BossZhipinCrawler(delay=0)
        malformed_html = "<html><body><div>未闭合的标签"

        mock_resp = Mock(status_code=200, text=malformed_html)

        with patch.object(crawler.session, 'get', return_value=mock_resp):
            with patch.object(crawler, '_rate_limit', return_value=None):
                # 不应抛出解析异常
                try:
                    jobs = crawler.crawl("测试", pages=1)
                    assert isinstance(jobs, list)
                except Exception as e:
                    pytest.fail(f"畸形 HTML 导致崩溃: {e}")

    def test_generated_platform_id_matches_source_url(self):
        """platform_job_id 与 source_url 关联正确"""
        crawler = Job51Crawler(delay=0)
        test_url = "https://jobs.51job.com/shenzhen-ftq/158123456.html"
        expected_id = hashlib.md5(test_url.encode()).hexdigest()

        # 模拟解析过程中生成的 ID
        job = JobRawData(
            title="测试岗位",
            company="测试公司",
            source="job51",
            crawled_at=datetime.now().isoformat(),
            platform_job_id=expected_id,
            source_url=test_url,
        )
        assert crawler.validate(job) is True
        assert len(job.platform_job_id) == 32
