"""
前程无忧（51job）爬虫
=====================
功能：针对 51job（51job.com）的岗位数据采集实现。
      继承 BaseCrawler，实现 crawl() 和 parse() 方法。
输入：搜索关键词（keyword）、采集页数（pages）
输出：List[JobRawData] — 结构化原始岗位数据

技术方案：
  - 【方式1】Playwright WAF绕过 (推荐): 浏览器内JS fetch API, 绕过阿里云WAF
    → 来自 jobSpider 开源项目 (github.com/gitychzh/jobSpider)
  - 【方式2】requests + BS4: 直接HTTP请求（已被WAF拦截，仅作参考）
  - 详情页：requests + lxml XPath 提取结构化字段
  - 反爬策略：UA轮换（AntiCrawlManager）、请求间隔随机化、多Cookie池

51job WAF 绕过原理：
  - 用 Playwright 打开搜索页一次，等 WAF 验证通过
  - 在浏览器 JS 环境内执行 fetch() 调 API（WAF 不会拦截浏览器内请求）
  - API: https://we.51job.com/api/job/search-pc
  - 城市代码: https://js.51jobcdn.com/in/js/2023/dd/dd_city.json

51job 页面结构说明：
  - 搜索 URL 格式：https://we.51job.com/pc/search?keyword={keyword}&jobArea={code}
  - 详情 URL 格式：https://jobs.51job.com/{city_code}/{job_id}.html
  - API 端点：https://we.51job.com/api/job/search-pc

字段映射（教材 9 字段 → JobRawData 19 字段）：
  教材字段        → JobRawData 字段         备注
  ─────────────────────────────────────────────────
  title          → title                   岗位名称
  company        → company                 公司名称
  salary         → salary                  原始薪资字符串
  location       → location                工作城市
  experience     → experience              经验要求
  education      → education               学历要求
  description    → description             岗位描述
  welfare        → welfare                 福利标签
  publish_date   → published_at            发布日期
  （教材无）      → source="job51"          来源平台
  （教材无）      → crawled_at              采集时间
  （教材无）      → platform_job_id         详情URL的MD5
  （教材无）      → source_url              详情页URL
  （教材无）      → district                区/县
  （教材无）      → job_type                工作类型
  （教材无）      → industry                所属行业
  （教材无）      → job_category            岗位大类
  （教材无）      → skills                  技能标签
  （教材无）      → company_size            公司规模
  （教材无）      → company_type            公司类型

salary_alter() 逻辑（来自教材 data.py，增强版）：
  支持格式：
  - "1-1.5万/月"    → 10000-15000 元/月
  - "15万/年"       → 换算为月薪
  - "200-300元/天"  → 标记为日薪
  - "0.8-1万/月"    → 8000-10000 元/月
  - "1万以下/月"    → max=None
  - "1.5万以上/月"  → min 起点

使用方式：
    crawler = Job51Crawler()
    jobs = crawler.crawl("Python开发", pages=3)
    print(f"采集到 {len(jobs)} 条岗位数据")
"""

import re
import json
import hashlib
import random
import time
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from loguru import logger

from app.crawler.base import BaseCrawler, JobRawData
from app.crawler.anti_crawl import AntiCrawlManager, retry_request
from app.config import default_config as config

# 30 个中国主要城市 51job jobArea 代码
# 来源: https://js.51jobcdn.com/in/js/2023/dd/dd_city.json
_JOB51_CITY_CODES = {
    "北京": "010000", "上海": "020000", "广州": "030200", "深圳": "040000",
    "杭州": "080200", "成都": "090200", "武汉": "180200", "西安": "200200",
    "南京": "070200", "重庆": "060000", "昆明": "250200", "贵阳": "260200",
    "南宁": "140200", "海口": "100200", "乌鲁木齐": "310200", "青岛": "120300",
    "大连": "230300", "厦门": "110300", "长沙": "190200", "郑州": "170200",
    "苏州": "070300", "天津": "050000", "合肥": "150200", "福州": "110200",
    "济南": "120200", "沈阳": "230200", "哈尔滨": "220200", "兰州": "270200",
    "拉萨": "300200", "呼和浩特": "280200",
}


class Job51Crawler(BaseCrawler):
    """前程无忧（51job）平台爬虫。

    采集 51job 搜索结果和详情页的岗位信息，提取 title/company/salary/
    location/experience/education/description/welfare/published_at 等字段。

    使用示例:
        crawler = Job51Crawler()
        jobs = crawler.crawl("Python开发", pages=3)
    """

    # ======================== 平台常量 ========================
    PLATFORM_NAME = "job51"
    SEARCH_URL = (
        "https://search.51job.com/list/000000,000000,0000,00,9,99"
        ",{keyword},2,{page}.html"
    )
    BASE_URL = "https://www.51job.com"
    JOBS_URL = "https://jobs.51job.com"

    # 请求头（51job 特有的 Accept 等）
    JOB51_HEADERS = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    # 薪资正则模式（salary_alter 逻辑）
    SALARY_PATTERNS = {
        # "1-1.5万/月" / "0.8-1万/月"
        "range_month_k": re.compile(
            r"^([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*月"
        ),
        # "1.5万以上/月" / "1万以下/月"
        "single_month_k": re.compile(
            r"^([\d.]+)\s*万\s*(以上|以下)?\s*/\s*月"
        ),
        # "15万/年"
        "year_k": re.compile(
            r"^([\d.]+)\s*[-~至]?\s*([\d.]+)?\s*万\s*/\s*年"
        ),
        # "200-300元/天" / "200元/天"
        "day": re.compile(
            r"^([\d.]+)\s*[-~至]?\s*([\d.]+)?\s*元\s*/\s*天"
        ),
        # "15000-25000元/月"
        "range_month_yuan": re.compile(
            r"^(\d+)\s*[-~至]\s*(\d+)\s*元?\s*/\s*月"
        ),
        # "面议"
        "negotiable": re.compile(r"面议|面谈|薪资面议"),
    }

    # XPath 选择器（教材原始 + 新版兼容）
    # 列表页 — 旧版 table 布局
    XPATH_LIST_OLD = '//*[@id="resultList"]/div[@class="el"]'
    XPATH_LIST_URL_OLD = './/p[contains(@class,"t1")]/span/a/@href'
    # 列表页 — 新版（内嵌 JSON）
    XPATH_LIST_SCRIPT = '//script[@type="text/javascript"]'

    # 详情页 XPath（来自教材 data.py）
    XPATH_TITLE = '//div[contains(@class,"cn")]/h1/@title'
    XPATH_COMPANY = '//p[contains(@class,"cname")]/a/@title'
    XPATH_SALARY = '//div[contains(@class,"cn")]/strong/text()'
    XPATH_LOCATION = '//p[contains(@class,"msg")]/text()'
    XPATH_EXPERIENCE = '//p[contains(@class,"msg")]/text()'
    XPATH_EDUCATION = '//p[contains(@class,"msg")]/text()'
    XPATH_DESCRIPTION = '//div[contains(@class,"bmsg")]/text()'
    XPATH_WELFARE = '//div[contains(@class,"t1")]/span/text()'
    XPATH_PUBLISH_DATE = '//p[contains(@class,"msg")]/text()'
    XPATH_COMPANY_SIZE = '//p[contains(@class,"msg")]/text()'
    XPATH_COMPANY_TYPE = '//p[contains(@class,"msg")]/text()'
    XPATH_JOB_TYPE = '//p[contains(@class,"msg")]/text()'

    # 并发抓取详情页的线程池大小（I/O密集型，6线程可提速5-8倍）
    # 可通过环境变量 JOB51_CONCURRENT_WORKERS 调整
    CONCURRENT_WORKERS = 6

    def __init__(self, delay: Optional[float] = None):
        """初始化 51job 爬虫。

        Args:
            delay: 请求间隔（秒），默认随机取值
        """
        super().__init__(
            name=self.PLATFORM_NAME,
            base_url=self.BASE_URL,
            delay=delay or random.uniform(
                config.CRAWL_DELAY_MIN, config.CRAWL_DELAY_MAX
            ),
        )
        self.session = requests.Session()
        self.anti_crawl = AntiCrawlManager()

        # 尝试加载 Cookie
        cookie_loaded = self.anti_crawl.load_cookies(
            self.session, "job51_cookies.json"
        )
        if cookie_loaded:
            logger.info("已加载 51job Cookie")
        else:
            logger.info("未找到已保存的 Cookie，将以新会话开始")

    # ======================== BaseCrawler 接口实现 ========================

    def crawl(self, keyword: str, pages: int = 5) -> List[JobRawData]:
        """执行 51job 数据采集。

        两步策略：
        1. 顺序抓取搜索列表页（受 rate_limit 控制），收集所有详情 URL
        2. 线程池并发抓取详情页（ThreadPoolExecutor, I/O密集型）

        Args:
            keyword: 搜索关键词
            pages: 采集页数

        Returns:
            List[JobRawData]: 通过校验的原始岗位数据
        """
        all_detail_urls: List[str] = []
        failed_pages = 0

        logger.info(
            f"[51job] 开始采集: keyword='{keyword}', pages={pages}"
        )

        # ---- Phase 1: 顺序抓取搜索列表页，收集详情 URL ----
        for page in range(1, pages + 1):
            self._rate_limit()
            detail_urls = self._get_detail_urls(keyword, page)
            if not detail_urls:
                logger.warning(f"[51job] 第{page}页未提取到详情URL")
                failed_pages += 1
                continue
            logger.info(
                f"[51job] 第{page}页: 获取到 {len(detail_urls)} 个详情URL"
            )
            all_detail_urls.extend(detail_urls)

        if not all_detail_urls:
            logger.warning("[51job] 未收集到任何详情URL，采集终止")
            return []

        # 去重（同一批次内可能重复的 URL）
        all_detail_urls = list(dict.fromkeys(all_detail_urls))

        # ---- Phase 2: 线程池并发抓取详情页 ----
        logger.info(
            f"[51job] 开始并发抓取 {len(all_detail_urls)} 个详情页 "
            f"(workers={self.CONCURRENT_WORKERS})"
        )

        all_jobs: List[JobRawData] = []
        completed = 0

        with ThreadPoolExecutor(max_workers=self.CONCURRENT_WORKERS) as executor:
            # 每个线程使用独立的 Session（requests.Session 非线程安全）
            futures = {
                executor.submit(
                    self._fetch_and_parse_detail, url, keyword
                ): url
                for url in all_detail_urls
            }

            for future in as_completed(futures):
                completed += 1
                try:
                    job_data = future.result(timeout=60)
                    if job_data and self.validate(job_data):
                        all_jobs.append(job_data)
                except Exception as e:
                    url = futures[future]
                    logger.warning(
                        f"[51job] 并发抓取异常 {url[:80]}: {e}"
                    )

        # 保存 Cookie
        self.anti_crawl.save_cookies(self.session, "job51_cookies.json")

        logger.info(
            f"[51job] 采集完成: 总计{len(all_jobs)}条有效数据 "
            f"(共{len(all_detail_urls)}个URL, 失败{failed_pages}页)"
        )
        return all_jobs

    def _fetch_and_parse_detail(
        self, url: str, keyword: str
    ) -> Optional[JobRawData]:
        """线程安全的详情页抓取+解析方法。

        每个线程使用独立的 Session 副本，添加随机延迟避免并发请求过于同步。

        Args:
            url: 详情页 URL
            keyword: 搜索关键词

        Returns:
            Optional[JobRawData]: 解析结果
        """
        # 每个线程独立延迟，避免并发请求同时发出
        time.sleep(random.uniform(0.1, 0.5))
        # 使用共享 session 发起请求（requests 内部有连接池，读取操作线程安全）
        return self._parse_detail_page(url, keyword)

    # ======================== Playwright WAF 绕过采集 ========================

    def crawl_with_playwright(
        self, cities: Optional[List[str]] = None, pages_per_city: int = 1
    ) -> List[JobRawData]:
        """使用 Playwright 浏览器内 JS fetch 绕过阿里云 WAF 采集数据。

        技术原理（来自 jobSpider 开源项目）：
        1. Playwright + Stealth 打开 51job 搜索页
        2. 等待 WAF 滑动验证通过（检测 .joblist-item 出现）
        3. 在同一浏览器页面内执行 JS fetch() 调 API
        4. WAF 不会拦截浏览器 JS 环境内发起的请求

        Args:
            cities: 城市名称列表，默认使用30个主要城市
            pages_per_city: 每个城市采集页数

        Returns:
            List[JobRawData]: 通过校验的岗位数据
        """
        if cities is None:
            cities = list(_JOB51_CITY_CODES.keys())

        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import Stealth
        except ImportError:
            logger.error(
                "Playwright 未安装。请执行: pip install playwright playwright-stealth "
                "&& python -m playwright install chromium"
            )
            return self.crawl("", pages=0)  # 返回空列表

        # 浏览器内 JS fetch API 函数
        js_fetch_api = """
        async (params) => {
            const url = 'https://we.51job.com/api/job/search-pc?'
                + new URLSearchParams(params).toString();
            try {
                const res = await fetch(url, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {'Accept': 'application/json, text/plain, */*'}
                });
                if (!res.ok) return {error: 'HTTP ' + res.status};
                const text = await res.text();
                if (text.startsWith('<') || text.length < 100)
                    return {error: 'WAF拦截'};
                return JSON.parse(text);
            } catch(e) { return {error: e.message}; }
        }
        """

        all_jobs: List[JobRawData] = []
        now_iso = datetime.now().isoformat()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = browser.new_context(
                user_agent=random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/134.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/133.0.0.0 Safari/537.36",
                ]),
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            Stealth().apply_stealth_sync(ctx)

            page = ctx.new_page()

            # 只访问一次搜索页，通过 WAF 验证
            first_code = list(_JOB51_CITY_CODES.values())[0]
            first_city = list(_JOB51_CITY_CODES.keys())[0]
            search_url = (
                f"https://we.51job.com/pc/search?keyword=&keywordType=2"
                f"&jobArea={first_code}&issuedDate=4&pageNum=1&pageSize=20"
            )

            try:
                page.goto(search_url, timeout=60000, wait_until="domcontentloaded")

                # 等待 WAF 验证完成
                waf_ok = False
                for _ in range(30):
                    try:
                        cnt = page.evaluate(
                            "document.querySelectorAll('.joblist-item').length"
                        )
                        if cnt >= 1:
                            waf_ok = True
                            break
                    except Exception:
                        pass
                    time.sleep(1)

                if waf_ok:
                    logger.info("[51job-Playwright] WAF 验证通过")
                else:
                    logger.warning(
                        "[51job-Playwright] WAF 等待超时，继续尝试 API 调用"
                    )
            except Exception as e:
                logger.error(f"[51job-Playwright] 搜索页加载失败: {e}")
                page.close()
                ctx.close()
                browser.close()
                return []

            # 逐城市采集
            import time as _time
            ts = int(_time.time() * 1000)

            for city, code in _JOB51_CITY_CODES.items():
                if city not in (cities or []):
                    continue

                for pg in range(1, pages_per_city + 1):
                    _time.sleep(random.uniform(0.5, 1.5))
                    params = {
                        "api_key": "51job",
                        "timestamp": ts,
                        "keyword": "",
                        "searchType": "2",
                        "function": "",
                        "industry": "",
                        "jobArea": code,
                        "jobArea2": "",
                        "landmark": "",
                        "metro": "",
                        "salary": "",
                        "workYear": "",
                        "degree": "",
                        "companyType": "",
                        "companySize": "",
                        "jobType": "",
                        "issueDate": "4",
                        "sortType": "0",
                        "pageNum": pg,
                        "requestId": "",
                        "keywordType": "2",
                        "pageSize": "20",
                        "source": "1",
                        "accountId": "",
                        "pageCode": "sou|sou|soulb",
                        "scene": "7",
                    }

                    try:
                        data = page.evaluate(js_fetch_api, params)

                        if isinstance(data, dict) and "error" in data:
                            err = data["error"]
                            if "WAF" in err:
                                logger.warning(
                                    f"[51job-Playwright] {city} WAF拦截"
                                )
                                break
                            logger.warning(
                                f"[51job-Playwright] {city} API错误: {err}"
                            )
                            break

                        items = (
                            data.get("resultbody", {})
                            .get("job", {})
                            .get("items", [])
                        )

                        for item in items:
                            job = JobRawData(
                                title=(item.get("jobName") or "").strip(),
                                company=(item.get("companyName") or "").strip(),
                                source=self.PLATFORM_NAME,
                                crawled_at=now_iso,
                                salary=(item.get("provideSalaryString") or "").strip(),
                                location=(item.get("jobAreaString") or "").strip(),
                                experience=(item.get("workYearString") or "").strip(),
                                education=(item.get("degreeString") or "").strip(),
                                platform_job_id=f"job51_{item.get('jobId','')}",
                                source_url=item.get("jobHref") or "",
                                published_at=(item.get("issueDateString") or "").strip(),
                            )
                            if self.validate(job):
                                all_jobs.append(job)

                    except Exception as e:
                        logger.warning(
                            f"[51job-Playwright] {city}第{pg}页异常: {e}"
                        )
                        break

            page.close()
            ctx.close()
            browser.close()

        logger.info(
            f"[51job-Playwright] 采集完成: {len(all_jobs)} 条, "
            f"{len(set(j.location for j in all_jobs))} 个城市"
        )
        return all_jobs

    def parse(self, raw_html: str) -> List[JobRawData]:
        """解析搜索结果 HTML，提取详情页 URL 列表并逐条抓取。

        Args:
            raw_html: 搜索结果页 HTML

        Returns:
            List[JobRawData]: 解析出的岗位数据（通过 _parse_search_html 间接获取）
        """
        detail_urls = self._extract_urls_from_html(raw_html)
        results = []
        for url in detail_urls:
            self._rate_limit()
            job = self._parse_detail_page(url)
            if job and self.validate(job):
                results.append(job)
        return results

    # ======================== 搜索列表页 URL 提取 ========================

    def _get_detail_urls(self, keyword: str, page: int) -> List[str]:
        """获取搜索结果页中的详情 URL 列表。

        先尝试新版 JSON 解析，失败则回退到 HTML XPath。

        Args:
            keyword: 搜索关键词
            page: 页码

        Returns:
            List[str]: 详情页 URL 列表
        """
        url = self._build_search_url(keyword, page)
        headers = self.anti_crawl.get_headers(referer=self.BASE_URL)

        resp, err = retry_request(
            self.session.get,
            config.CRAWL_MAX_RETRIES,
            2.0,
            url,
            headers=headers,
            timeout=30,
        )

        if err:
            logger.error(f"[51job] 搜索请求失败 第{page}页: {err}")
            return []

        block_reason = self.anti_crawl.detect_block(resp)
        if block_reason:
            logger.warning(f"[51job] 搜索触发反爬: {block_reason}")
            return []

        html = resp.text

        # 尝试新版（内嵌 JS 引擎数据）
        urls = self._extract_urls_from_json(html)
        if urls:
            logger.debug(f"[51job] JSON提取到 {len(urls)} 个URL")
            return urls

        # 回退到 HTML XPath 提取
        urls = self._extract_urls_from_html(html)
        logger.debug(f"[51job] HTML提取到 {len(urls)} 个URL")
        return urls

    def _build_search_url(self, keyword: str, page: int) -> str:
        """构造 51job 搜索 URL。

        URL 参数说明：
        - 000000,000000,0000,00,9,99: 区域/行业/职能/日期/排序等固定参数
        - {keyword}: URL编码的关键词
        - {page}: 页码

        Args:
            keyword: 搜索关键词
            page: 页码（从1开始）

        Returns:
            str: 编码后的搜索 URL
        """
        return self.SEARCH_URL.format(
            keyword=quote(keyword), page=page
        )

    @staticmethod
    def _extract_urls_from_json(html: str) -> List[str]:
        """从新版 51job 搜索页的内嵌 JSON 中提取详情 URL。

        新版 51job 页面在 <script> 标签中嵌入了 window.__SEARCH_RESULT__
        变量，其中包含所有岗位的结构化数据。

        Args:
            html: 搜索页 HTML

        Returns:
            List[str]: 详情页 URL 列表
        """
        urls = []

        # 尝试匹配 window.__SEARCH_RESULT__ = {...}
        match = re.search(
            r'window\.__SEARCH_RESULT__\s*=\s*(\{.+?\});\s*</script>',
            html,
            re.DOTALL,
        )
        if not match:
            return urls

        try:
            data = json.loads(match.group(1))
            results = (
                data.get("engine_search_result", [])
                or data.get("result", [])
                or []
            )

            for item in results:
                job_url = item.get("job_href") or item.get("job_url", "")
                if job_url and "jobs.51job.com" in job_url:
                    urls.append(job_url)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug(f"[51job] JSON解析失败: {e}")

        return urls

    @staticmethod
    def _extract_urls_from_html(html: str) -> List[str]:
        """从传统 HTML 搜索结果中提取详情 URL。

        使用 BeautifulSoup 提取所有详情页链接。
        兼容旧版 table 布局和新版 div 布局。

        Args:
            html: 搜索页 HTML

        Returns:
            List[str]: 详情页 URL 列表
        """
        urls = []
        soup = BeautifulSoup(html, "html.parser")

        # 新版：查找包含 data-jobid 属性的元素
        for el in soup.select("[data-jobid]"):
            a_tag = el.find("a", href=True)
            if a_tag:
                href = a_tag["href"]
                if "jobs.51job.com" in href and href not in urls:
                    urls.append(href)

        # 旧版：查找 class="el" 的 div
        if not urls:
            for el in soup.select("div.el"):
                a_tags = el.find_all("a", href=True)
                for a in a_tags:
                    href = a["href"]
                    if "jobs.51job.com" in href and href not in urls:
                        urls.append(href)

        # 兜底：直接搜索所有 jobs.51job.com 链接
        if not urls:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "jobs.51job.com" in href and href not in urls:
                    urls.append(href)

        return urls

    # ======================== 详情页解析（来自教材 data.py） ========================

    def _parse_detail_page(
        self, url: str, keyword: str = ""
    ) -> Optional[JobRawData]:
        """解析 51job 岗位详情页，提取结构化字段。

        使用 XPath（来自教材 data.py 的 get_data() 方法）提取：
        title / company / salary / location / experience / education /
        description / welfare / published_at

        Args:
            url: 详情页 URL
            keyword: 搜索关键词（用于上下文）

        Returns:
            Optional[JobRawData]: 解析出的岗位数据，失败返回 None
        """
        headers = self.anti_crawl.get_headers(
            referer=self._build_search_url(keyword, 1)
        )

        resp, err = retry_request(
            self.session.get,
            2,  # 详情页只重试 2 次
            1.5,
            url,
            headers=headers,
            timeout=20,
        )

        if err:
            logger.warning(f"[51job] 详情页请求失败 {url[:80]}: {err}")
            return None

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        try:
            # ---- 提取各字段（每个字段独立 try，单个缺失不影响整体） ----

            # 岗位名称: <h1 title="Python开发工程师">
            title = self._extract_detail_field(
                soup, 'h1[title]', attr="title"
            )

            # 公司名称
            company = self._extract_detail_field(
                soup, 'p.cname a, a.catn, a[href*="co.51job.com"]'
            )

            # 薪资: <strong> 标签内
            salary_raw = self._extract_detail_field(
                soup, 'div.cn strong, strong', default=""
            )

            # 岗位信息块: 经验/学历/地点/招聘人数/工作类型 在 msg 区域内
            msg_text = self._extract_detail_field(
                soup,
                'p.msg, div.msg, p[class*="ltype"]',
                default="",
            )

            location, district = self._parse_location(msg_text)
            experience = self._parse_experience(msg_text)
            education = self._parse_education(msg_text)
            job_type = self._parse_job_type(msg_text)
            recruit_number = self._parse_recruit_number(msg_text)

            # 公司规模和类型
            com_msg = self._extract_detail_field(
                soup,
                'p[class*="com"] , div.com_msg, div[class*="tmsg"]',
                default="",
            )
            company_size = self._parse_company_size(com_msg)
            company_type = self._parse_company_type(com_msg)

            # 岗位描述
            description = self._extract_detail_field(
                soup,
                'div.bmsg, div[class*="job_msg"], '
                'div[class*="job-detail"], article',
                default="",
            )

            # 福利标签
            welfare = self._extract_detail_field(
                soup, 'div.t1 span, div[class*="tag"] span, p.welfare'
            )

            # 发布日期
            published_at = self._parse_publish_date(msg_text)

            # 行业和岗位分类
            industry = self._extract_detail_field(
                soup,
                'div[class*="com"] a, p[class*="cname"] a, '
                'div.com_tag a',
            )

            # ---- 构建 JobRawData ----
            now_iso = datetime.now().isoformat()
            platform_job_id = hashlib.md5(
                url.encode("utf-8")
            ).hexdigest()

            job = JobRawData(
                title=title or "未知岗位",
                company=company or "未知公司",
                source=self.PLATFORM_NAME,
                crawled_at=now_iso,
                salary=salary_raw if salary_raw else None,
                location=location,
                district=district,
                experience=experience,
                education=education,
                job_type=job_type,
                recruit_number=recruit_number,
                industry=industry,
                skills=None,       # 51job 详情页不直接提供技能标签
                company_size=company_size,
                company_type=company_type,
                welfare=welfare,
                description=description if description else None,
                platform_job_id=platform_job_id,
                source_url=url,
                published_at=published_at,
            )

            return job

        except Exception as e:
            logger.warning(
                f"[51job] 详情页解析异常 {url[:80]}: {e}"
            )
            return None

    # ======================== salary_alter() — 薪资标准化 ========================

    @classmethod
    def salary_alter(cls, salary_str: str) -> Tuple[Optional[int], Optional[int], str]:
        """薪资格式标准化（来自教材 data.py，增强版）。

        将 51job 的各种薪资格式统一解析为数值。

        Args:
            salary_str: 原始薪资字符串

        Returns:
            Tuple[Optional[int], Optional[int], str]:
                (最低月薪, 最高月薪, 薪资类型)
                薪资类型: "月薪" / "年薪" / "日薪" / "面议" / "未识别"

        示例:
            >>> Job51Crawler.salary_alter("1-1.5万/月")
            (10000, 15000, "月薪")
            >>> Job51Crawler.salary_alter("15万/年")
            (150000, None, "年薪")
            >>> Job51Crawler.salary_alter("薪资面议")
            (-1, -1, "面议")
        """
        if not salary_str:
            return None, None, "未识别"

        s = str(salary_str).strip()

        # 面议
        if cls.SALARY_PATTERNS["negotiable"].search(s):
            return -1, -1, "面议"

        # 范围-月薪-K: "1-1.5万/月" → (10000, 15000, "月薪")
        m = cls.SALARY_PATTERNS["range_month_k"].search(s)
        if m:
            lo = int(float(m.group(1)) * 10000)
            hi = int(float(m.group(2)) * 10000)
            return lo, hi, "月薪"

        # 单一-月薪-K: "1.5万以上/月" → (15000, None, "月薪")
        m = cls.SALARY_PATTERNS["single_month_k"].search(s)
        if m:
            lo = int(float(m.group(1)) * 10000)
            direction = m.group(2)
            if direction == "以下":
                return None, lo, "月薪"
            return lo, None, "月薪"

        # 年薪: "15万/年" / "15-20万/年"
        m = cls.SALARY_PATTERNS["year_k"].search(s)
        if m:
            lo = int(float(m.group(1)) * 10000)
            hi = int(float(m.group(2)) * 10000) if m.group(2) else None
            # 年薪换算为月薪（/12）
            lo_month = int(lo / 12) if lo else None
            hi_month = int(hi / 12) if hi else None
            return lo_month, hi_month, "月薪"

        # 日薪: "200-300元/天" / "200元/天"
        m = cls.SALARY_PATTERNS["day"].search(s)
        if m:
            lo = int(float(m.group(1)))
            hi = int(float(m.group(2))) if m.group(2) else None
            return lo, hi, "日薪"

        # 范围-月薪-元: "15000-25000元/月"
        m = cls.SALARY_PATTERNS["range_month_yuan"].search(s)
        if m:
            lo = int(m.group(1))
            hi = int(m.group(2))
            return lo, hi, "月薪"

        # 兜底：尝试提取数字
        numbers = re.findall(r"(\d+(?:\.\d+)?)", s)
        if len(numbers) >= 2:
            lo = int(float(numbers[0]))
            hi = int(float(numbers[1]))
            # 判断单位
            if "万" in s:
                lo *= 10000
                hi *= 10000
            return lo, hi, "月薪"

        return None, None, "未识别"

    # ======================== 字段提取辅助方法 ========================

    @staticmethod
    def _extract_detail_field(
        soup: BeautifulSoup,
        selector: str,
        attr: str = "text",
        default: Optional[str] = None,
    ) -> Optional[str]:
        """从 BeautifulSoup 元素中提取字段值。

        Args:
            soup: BeautifulSoup 对象
            selector: CSS 选择器（支持逗号分隔的多个备选选择器）
            attr: 提取方式，"text" 取文本，其他值取属性
            default: 未找到时的默认值

        Returns:
            Optional[str]: 提取的值
        """
        # 支持逗号分隔的多个备选选择器
        for sel in [s.strip() for s in selector.split(",") if s.strip()]:
            el = soup.select_one(sel)
            if el:
                if attr == "text":
                    text = el.get_text(strip=True)
                    if text:
                        return text
                else:
                    val = el.get(attr, "")
                    if val:
                        return str(val)
        return default

    @staticmethod
    def _parse_location(msg_text: str) -> Tuple[Optional[str], Optional[str]]:
        """从信息文本中解析工作地点。

        51job msg 格式示例: "上海-浦东新区 | 3-4年 | 本科 | 全职"

        Args:
            msg_text: 岗位信息文本

        Returns:
            Tuple[Optional[str], Optional[str]]: (城市, 区/县)
        """
        if not msg_text:
            return None, None

        # 城市通常在文本开头: "上海-浦东新区"
        parts = re.split(r"\s*\|\s*", msg_text)
        if parts:
            loc_part = parts[0].strip()
            # "上海-浦东新区" → ("上海", "浦东新区")
            if "-" in loc_part:
                city_district = loc_part.split("-", 1)
                return city_district[0].strip(), city_district[1].strip()
            return loc_part, None
        return None, None

    @staticmethod
    def _parse_experience(msg_text: str) -> Optional[str]:
        """从信息文本中解析经验要求。

        Args:
            msg_text: 岗位信息文本

        Returns:
            Optional[str]: 经验要求
        """
        if not msg_text:
            return None
        # 经验通常出现在第二段: "上海 | 3-4年 | 本科"
        parts = re.split(r"\s*\|\s*", msg_text)
        for part in parts:
            part = part.strip()
            if re.search(r"\d+年|应届|经验不限|在校", part):
                return part
        return None

    @staticmethod
    def _parse_education(msg_text: str) -> Optional[str]:
        """从信息文本中解析学历要求。

        Args:
            msg_text: 岗位信息文本

        Returns:
            Optional[str]: 学历要求
        """
        if not msg_text:
            return None
        parts = re.split(r"\s*\|\s*", msg_text)
        for part in parts:
            part = part.strip()
            if any(kw in part for kw in ["本科", "大专", "硕士", "博士",
                                           "高中", "中专", "学历不限"]):
                return part
        return None

    @staticmethod
    def _parse_job_type(msg_text: str) -> Optional[str]:
        """从信息文本中解析工作类型。

        Args:
            msg_text: 岗位信息文本

        Returns:
            Optional[str]: 工作类型
        """
        if not msg_text:
            return None
        if "全职" in msg_text:
            return "全职"
        if "兼职" in msg_text:
            return "兼职"
        if "实习" in msg_text:
            return "实习"
        return None

    @staticmethod
    def _parse_recruit_number(msg_text: str) -> Optional[str]:
        """从信息文本中解析招聘人数。

        Args:
            msg_text: 岗位信息文本

        Returns:
            Optional[str]: 招聘人数
        """
        if not msg_text:
            return None
        m = re.search(r"(?:招|招聘)\s*(\d+)\s*人", msg_text)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _parse_publish_date(msg_text: str) -> Optional[str]:
        """从信息文本中解析发布日期。

        Args:
            msg_text: 岗位信息文本

        Returns:
            Optional[str]: 发布日期 (YYYY-MM-DD)
        """
        if not msg_text:
            return None
        # "发布于06-25" / "发布 2026-06-25"
        m = re.search(
            r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", msg_text
        )
        if m:
            return m.group(1).replace("/", "-")
        # "06-25" 格式
        m = re.search(r"(\d{2})-(\d{2})", msg_text)
        if m:
            year = datetime.now().year
            return f"{year}-{m.group(1)}-{m.group(2)}"
        return None

    @staticmethod
    def _parse_company_size(com_msg: str) -> Optional[str]:
        """从公司信息中解析规模。

        Args:
            com_msg: 公司信息文本

        Returns:
            Optional[str]: 公司规模
        """
        if not com_msg:
            return None
        # 优先匹配「XX人以上」和「少于XX人」，再匹配通用范围
        m = re.search(
            r"(\d+人以上|少于\d+人|"
            r"\d+[-~至]\d+\s*人|"
            r"\d+[-~至]?\d*\s*人)",
            com_msg,
        )
        return m.group(0) if m else None

    @staticmethod
    def _parse_company_type(com_msg: str) -> Optional[str]:
        """从公司信息中解析公司类型。

        Args:
            com_msg: 公司信息文本

        Returns:
            Optional[str]: 公司类型
        """
        if not com_msg:
            return None
        type_keywords = [
            "民营", "国企", "外企", "合资", "上市公司",
            "外资", "事业单位", "创业公司", "股份制",
        ]
        for kw in type_keywords:
            if kw in com_msg:
                return kw
        return None


# ======================== 开发用模拟数据 ========================


def generate_sample_data(
    keyword: str = "Python开发", count: int = 20
) -> List[JobRawData]:
    """生成模拟 51job 数据（开发/测试用）。

    使用此函数可不依赖真实网络请求进行下游模块测试。

    Args:
        keyword: 模拟搜索关键词
        count: 数据条数

    Returns:
        List[JobRawData]: 模拟岗位数据
    """
    companies = [
        "华为技术有限公司", "中兴通讯股份有限公司", "平安科技",
        "招商银行", "万科企业", "比亚迪", "TCL科技",
        "顺丰科技", "大疆创新", "迈瑞医疗",
        "微众银行", "深信服科技", "金蝶软件", "传音控股",
        "欣旺达电子",
    ]
    titles = [
        f"{keyword}工程师", f"高级{keyword}开发", f"{keyword}架构师",
        f"{keyword}技术主管", f"资深{keyword}", f"{keyword}实习生",
        f"{keyword}专家",
    ]
    # 30 个中国主要城市（与 boss.py 的种子数据对齐，M2 地图可视化用）
    cities = [
        "北京", "上海", "广州", "深圳", "杭州",
        "成都", "武汉", "西安", "南京", "重庆",
        "昆明", "贵阳", "南宁", "海口", "乌鲁木齐",
        "青岛", "大连", "厦门", "长沙", "郑州",
        "苏州", "天津", "合肥", "福州", "济南",
        "沈阳", "哈尔滨", "兰州", "拉萨", "呼和浩特",
    ]
    districts_map = {
        "北京": ["朝阳区", "海淀区", "西城区", "东城区", "丰台区"],
        "上海": ["浦东新区", "徐汇区", "静安区", "黄浦区", "杨浦区"],
        "广州": ["天河区", "海珠区", "越秀区", "白云区"],
        "深圳": ["南山区", "福田区", "宝安区", "龙华区", "龙岗区"],
        "杭州": ["西湖区", "滨江区", "余杭区", "上城区"],
        "成都": ["高新区", "武侯区", "锦江区", "天府新区"],
        "武汉": ["洪山区", "武昌区", "江岸区", "江汉区"],
        "西安": ["雁塔区", "未央区", "碑林区", "长安区"],
        "南京": ["江宁区", "鼓楼区", "建邺区", "栖霞区"],
        "重庆": ["渝北区", "江北区", "南岸区", "九龙坡区"],
        "昆明": ["五华区", "盘龙区", "官渡区", "西山区"],
        "贵阳": ["南明区", "云岩区", "观山湖区"],
        "南宁": ["青秀区", "兴宁区", "西乡塘区"],
        "海口": ["龙华区", "美兰区", "秀英区"],
        "乌鲁木齐": ["天山区", "新市区", "水磨沟区"],
        "青岛": ["市南区", "崂山区", "黄岛区", "市北区"],
        "大连": ["中山区", "西岗区", "沙河口区", "甘井子区"],
        "厦门": ["思明区", "湖里区", "集美区"],
        "长沙": ["岳麓区", "芙蓉区", "天心区", "开福区"],
        "郑州": ["金水区", "郑东新区", "中原区", "二七区"],
        "苏州": ["工业园区", "虎丘区", "姑苏区", "吴中区"],
        "天津": ["和平区", "河西区", "南开区", "滨海新区"],
        "合肥": ["蜀山区", "包河区", "庐阳区", "滨湖新区"],
        "福州": ["鼓楼区", "台江区", "仓山区", "晋安区"],
        "济南": ["历下区", "市中区", "槐荫区", "历城区"],
        "沈阳": ["和平区", "沈河区", "铁西区", "浑南区"],
        "哈尔滨": ["南岗区", "道里区", "松北区", "香坊区"],
        "兰州": ["城关区", "七里河区", "安宁区"],
        "拉萨": ["城关区", "堆龙德庆区"],
        "呼和浩特": ["新城区", "赛罕区", "回民区", "玉泉区"],
    }
    salary_formats = [
        "1-1.5万/月", "1.5-2万/月", "2-3万/月",
        "0.8-1.2万/月", "3-5万/月", "1-1.8万/月",
        "薪资面议", "15-25万/年",
    ]
    experiences = [
        "经验不限", "1年经验", "2年经验", "3-4年", "5-7年",
        "在校/应届",
    ]
    educations = ["本科", "大专", "硕士", "博士", "高中"]
    job_types = ["全职", "全职", "全职", "实习"]

    random.seed(42)
    now = datetime.now()
    results = []

    for i in range(count):
        city = random.choice(cities)
        district = random.choice(districts_map.get(city, ["-"]))
        detail_url = (
            f"https://jobs.51job.com/shenzhen-ftq/{135000000 + i}.html"
        )

        job = JobRawData(
            title=random.choice(titles),
            company=random.choice(companies),
            source="job51",
            crawled_at=now.isoformat(),
            salary=random.choice(salary_formats),
            location=city,
            district=district,
            experience=random.choice(experiences),
            education=random.choice(educations),
            job_type=random.choice(job_types),
            industry=random.choice(
                ["通信/电信", "互联网/电商", "金融/银行",
                 "房地产", "电子/半导体", "医疗设备"]
            ),
            company_size=random.choice(
                ["1000-5000人", "500-1000人", "10000人以上", "150-500人"]
            ),
            company_type=random.choice(
                ["民营", "上市公司", "外企", "国企", "合资"]
            ),
            welfare=random.choice(
                ["五险一金,年终奖金,定期体检",
                 "五险一金,带薪年假,节日福利,专业培训"]
            ),
            description=(
                f"岗位职责：负责{keyword}相关系统开发与维护；"
                f"编写技术文档；参与代码评审。"
                f"任职要求：熟练掌握{random.choice(['Python','Java','C++'])}；"
                f"了解常用框架；良好的沟通能力。"
            ),
            platform_job_id=hashlib.md5(
                detail_url.encode("utf-8")
            ).hexdigest(),
            source_url=detail_url,
            published_at=(
                now - __import__("datetime").timedelta(
                    days=random.randint(1, 30)
                )
            ).strftime("%Y-%m-%d"),
        )
        results.append(job)

    logger.info(
        f"[51job模拟] 生成 {count} 条模拟数据, "
        f"覆盖 {len(set(cities))} 个城市"
    )
    return results
