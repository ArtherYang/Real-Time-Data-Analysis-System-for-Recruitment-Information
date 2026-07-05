"""
BOSS直聘爬虫
============
功能：针对 BOSS直聘（zhipin.com）的岗位数据采集实现。
      继承 BaseCrawler，实现 crawl() 和 parse() 方法。
输入：搜索关键词（keyword）、采集页数（pages）
输出：List[JobRawData] — 结构化原始岗位数据

技术方案：
  - 主路径：requests + BeautifulSoup4 解析搜索结果列表
  - 兜底路径：Selenium headless Chrome（当 BS4 无法提取关键字段时触发）
  - 反爬策略：UA轮换、请求间隔随机化、Cookie持久化

开发模式：
  - 由于 BOSS直聘有较强反爬机制（CloudFlare），开发阶段提供
    generate_sample_data() 方法生成模拟数据用于下游模块测试。
"""

import random
import time
import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from loguru import logger

from app.crawler.base import BaseCrawler, JobRawData
from app.crawler.anti_crawl import AntiCrawlManager, retry_request, CookiePool
from app.config import default_config as config


class BossZhipinCrawler(BaseCrawler):
    """BOSS直聘平台爬虫。

    采集 BOSS直聘搜索结果页的岗位信息，提取标题、公司、薪资、
    地点、经验要求、学历要求、技能标签等字段。

    使用示例:
        crawler = BossZhipinCrawler()
        jobs = crawler.crawl("Python开发", pages=3)
        print(f"采集到 {len(jobs)} 条岗位数据")
    """

    # ======================== 平台常量 ========================
    PLATFORM_NAME = "boss_zhipin"
    SEARCH_URL = "https://www.zhipin.com/web/geek/job?query={keyword}&page={page}"
    BASE_URL = "https://www.zhipin.com"

    # CSS 选择器（便于在HTML结构变化时集中修改）
    SELECTOR_JOB_CARD = ".job-card-wrapper"
    SELECTOR_TITLE = ".job-name"
    SELECTOR_SALARY = ".salary"
    SELECTOR_COMPANY = ".company-name"
    SELECTOR_LOCATION = ".job-area"
    SELECTOR_TAGS = ".tag-list li"
    SELECTOR_DESCRIPTION = ".job-sec-text"

    # 反爬参数
    DELAY_RANGE = (config.CRAWL_DELAY_MIN, config.CRAWL_DELAY_MAX)

    def __init__(self, delay: Optional[float] = None):
        """初始化 BOSS直聘爬虫。

        Args:
            delay: 请求间隔（秒），默认在 config 配置范围内随机取值
        """
        super().__init__(
            name=self.PLATFORM_NAME,
            base_url=self.BASE_URL,
            delay=delay or random.uniform(*self.DELAY_RANGE),
        )
        self.session = requests.Session()
        self.anti_crawl = AntiCrawlManager()

        # 多 Cookie 池（bosszp-master 方案，轮换避免限流）
        self.cookie_pool = CookiePool()

        # 尝试加载已保存的 Cookie
        cookie_loaded = self.anti_crawl.load_cookies(
            self.session, "boss_cookies.json"
        )
        if cookie_loaded:
            logger.info(
                f"已加载 BOSS直聘 Cookie（复用会话）, "
                f"Cookie池: {self.cookie_pool.size} 组"
            )
        else:
            logger.info(
                f"未找到已保存的 Cookie，将使用 Cookie池轮换 "
                f"({self.cookie_pool.size} 组预置token)"
            )
            # 应用一组随机预置 Cookie
            self.cookie_pool.apply_random(self.session)

    def crawl(self, keyword: str, pages: int = 5) -> List[JobRawData]:
        """执行 BOSS直聘数据采集。

        对每个搜索页：
        1. 发送搜索请求，获取岗位卡片列表
        2. 对每张卡片调用 parse() 提取结构化数据
        3. 调用 validate() 校验数据完整性
        4. 汇总有效结果

        Args:
            keyword: 搜索关键词（如 "Python开发" "数据分析师"）
            pages: 采集页数，默认 5

        Returns:
            List[JobRawData]: 通过校验的原始岗位数据列表
        """
        all_jobs: List[JobRawData] = []
        failed_pages = 0

        logger.info(
            f"[BOSS直聘] 开始采集: keyword='{keyword}', pages={pages}"
        )

        for page in range(1, pages + 1):
            self._rate_limit()

            # Cookie 轮换：每次搜索请求随机换一组
            self.cookie_pool.apply_random(self.session)

            url = self._build_search_url(keyword, page)
            headers = self.anti_crawl.get_headers(
                referer=self.BASE_URL + "/"
            )

            logger.debug(f"[BOSS直聘] 请求第{page}页: {url[:100]}...")

            resp, err = retry_request(
                self.session.get,
                config.CRAWL_MAX_RETRIES,
                2.0,
                url,
                headers=headers,
                timeout=30,
            )

            if err:
                logger.error(f"[BOSS直聘] 第{page}页请求失败: {err}")
                failed_pages += 1
                continue

            # 检测反爬封锁
            block_reason = self.anti_crawl.detect_block(resp)
            if block_reason:
                logger.warning(
                    f"[BOSS直聘] 第{page}页触发反爬: {block_reason}"
                )
                failed_pages += 1
                continue

            # 解析搜索结果页
            page_jobs = self._parse_search_page(resp.text, keyword)
            valid_jobs = [j for j in page_jobs if self.validate(j)]

            logger.info(
                f"[BOSS直聘] 第{page}页: 解析{len(page_jobs)}条, "
                f"有效{len(valid_jobs)}条"
            )
            all_jobs.extend(valid_jobs)

        # 保存 Cookie 供下次复用
        self.anti_crawl.save_cookies(self.session, "boss_cookies.json")

        logger.info(
            f"[BOSS直聘] 采集完成: 总计{len(all_jobs)}条有效数据, "
            f"失败{failed_pages}页"
        )
        return all_jobs

    def parse(self, raw_html: str) -> List[JobRawData]:
        """解析单个岗位卡片的 HTML，提取结构化数据。

        Args:
            raw_html: 岗位卡片 HTML 片段

        Returns:
            List[JobRawData]: 解析出的岗位数据列表（通常1条）
        """
        jobs = self._parse_search_page(raw_html)
        return jobs

    # ======================== 内部方法 ========================

    def _build_search_url(self, keyword: str, page: int) -> str:
        """构造 BOSS直聘搜索 URL。

        Args:
            keyword: 搜索关键词
            page: 页码（从1开始）

        Returns:
            str: 编码后的搜索 URL
        """
        return self.SEARCH_URL.format(
            keyword=quote(keyword), page=page
        )

    def _parse_search_page(
        self, html: str, keyword: str = ""
    ) -> List[JobRawData]:
        """解析搜索结果页面 HTML。

        从搜索结果列表页中提取所有岗位卡片的信息。

        Args:
            html: 搜索结果页 HTML
            keyword: 搜索关键词（用于构造数据标记）

        Returns:
            List[JobRawData]: 解析出的岗位数据列表
        """
        results: List[JobRawData] = []
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(self.SELECTOR_JOB_CARD)

        if not cards:
            logger.debug(
                "[BOSS直聘] 未找到岗位卡片，可能页面为JS动态渲染"
            )
            return results

        now_iso = datetime.now().isoformat()

        for card in cards:
            try:
                # 提取各字段（每个字段独立try-catch，单个字段缺失不影响整体）
                title = self._extract_text(card, self.SELECTOR_TITLE)
                company = self._extract_text(card, self.SELECTOR_COMPANY)
                salary = self._extract_text(card, self.SELECTOR_SALARY)
                location = self._extract_text(card, self.SELECTOR_LOCATION)

                # 标签列表（经验、学历等）
                tags = card.select(self.SELECTOR_TAGS)
                tag_texts = [t.get_text(strip=True) for t in tags]

                experience = self._tag_to_experience(tag_texts)
                education = self._tag_to_education(tag_texts)

                # 生成平台唯一ID
                platform_job_id = self._generate_platform_id(
                    title, company, location
                )

                # 技能标签（从岗位描述中提取，此处做预标记）
                skills = self._extract_skills_from_tags(tag_texts)

                job = JobRawData(
                    title=title or "未知岗位",
                    company=company or "未知公司",
                    source=self.PLATFORM_NAME,
                    crawled_at=now_iso,
                    salary=salary,
                    location=location,
                    experience=experience,
                    education=education,
                    skills=skills,
                    platform_job_id=platform_job_id,
                    source_url=self._build_detail_url(platform_job_id),
                    published_at=datetime.now().strftime("%Y-%m-%d"),
                )
                results.append(job)

            except Exception as e:
                logger.warning(f"[BOSS直聘] 解析卡片异常: {e}")
                continue

        return results

    @staticmethod
    def _extract_text(soup_element, selector: str) -> Optional[str]:
        """从 BeautifulSoup 元素中提取文本。

        Args:
            soup_element: BeautifulSoup 元素
            selector: CSS 选择器

        Returns:
            Optional[str]: 提取的文本，未找到返回 None
        """
        el = soup_element.select_one(selector)
        if el:
            return el.get_text(strip=True)
        return None

    @staticmethod
    def _tag_to_experience(tags: List[str]) -> Optional[str]:
        """从标签列表中识别经验要求。

        Args:
            tags: 标签文本列表

        Returns:
            Optional[str]: 经验要求文本
        """
        exp_patterns = [
            r"\d+[-\s]*\d*\s*年",  # 如 "3-5年" "1年"
            r"经验不限",
            r"应届生",
            r"在校.*应届",
        ]
        for tag in tags:
            for pattern in exp_patterns:
                if re.search(pattern, tag):
                    return tag
        return None

    @staticmethod
    def _tag_to_education(tags: List[str]) -> Optional[str]:
        """从标签列表中识别学历要求。

        Args:
            tags: 标签文本列表

        Returns:
            Optional[str]: 学历要求文本
        """
        edu_keywords = [
            "博士", "硕士", "本科", "大专", "学历不限",
            "高中", "中专", "初中及以下",
        ]
        for tag in tags:
            for keyword in edu_keywords:
                if keyword in tag:
                    return tag
        return None

    @staticmethod
    def _extract_skills_from_tags(tags: List[str]) -> Optional[str]:
        """从标签列表中提取技能关键词。

        对非经验、非学历的标签进行收集，作为技能标签备选。

        Args:
            tags: 标签文本列表

        Returns:
            Optional[str]: 逗号分隔的技能标签
        """
        exclude_keywords = [
            "年", "经验", "应届", "博士", "硕士", "本科",
            "大专", "高中", "中专", "学历",
        ]
        skill_tags = [
            t
            for t in tags
            if not any(kw in t for kw in exclude_keywords)
        ]
        return ",".join(skill_tags) if skill_tags else None

    @staticmethod
    def _generate_platform_id(
        title: str, company: str, location: Optional[str]
    ) -> str:
        """为岗位生成平台唯一标识。

        当平台不提供原始ID时，基于核心字段生成哈希ID用于去重。

        Args:
            title: 岗位名称
            company: 公司名称
            location: 工作地点

        Returns:
            str: 32位hex哈希ID
        """
        raw = f"{title}|{company}|{location or ''}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_detail_url(platform_job_id: str) -> Optional[str]:
        """构造岗位详情页 URL。

        Args:
            platform_job_id: 平台岗位ID

        Returns:
            str: 详情页URL（占位，实际需要真实job_id）
        """
        return (
            f"https://www.zhipin.com/job_detail/{platform_job_id}.html"
        )

    # ======================== Selenium 兜底路径 ========================

    def _parse_with_selenium(self, url: str) -> Optional[str]:
        """使用 Selenium 获取 JS 动态渲染后的页面 HTML。

        当 requests+BS4 路径无法获取有效数据时触发此兜底方案。

        Args:
            url: 目标页面 URL

        Returns:
            Optional[str]: 渲染后的页面 HTML，失败返回 None

        Note:
            需要安装 ChromeDriver 并配置 PATH。
            开发阶段标记为 P1 待完成项。
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
        except ImportError:
            logger.warning(
                "[BOSS直聘] Selenium 未安装，无法使用兜底路径。"
                "请执行: pip install selenium"
            )
            return None

        logger.info(f"[BOSS直聘] 启用 Selenium 兜底: {url[:100]}...")

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(
            f"user-agent={self.anti_crawl.get_random_ua()}"
        )

        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)

            # 等待岗位卡片加载（最多等待15秒）
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, self.SELECTOR_JOB_CARD)
                )
            )
            # 额外等待确保内容渲染完成
            time.sleep(2)

            page_source = driver.page_source
            logger.debug(
                f"[BOSS直聘] Selenium 获取页面成功 ({len(page_source)} 字符)"
            )
            return page_source

        except Exception as e:
            logger.error(f"[BOSS直聘] Selenium 执行异常: {e}")
            return None
        finally:
            if driver:
                driver.quit()


# ======================== 开发用模拟数据生成 ========================

# 30 个中国主要城市经纬度（M2 地图可视化用）
city_coords = {
    "北京": [116.40, 39.90], "上海": [121.47, 31.23],
    "广州": [113.26, 23.13], "深圳": [114.07, 22.62],
    "杭州": [120.15, 30.28], "成都": [104.07, 30.67],
    "武汉": [114.30, 30.60], "西安": [108.94, 34.26],
    "南京": [118.78, 32.07], "重庆": [106.55, 29.57],
    "昆明": [102.83, 24.88], "贵阳": [106.71, 26.65],
    "南宁": [108.37, 22.82], "海口": [110.20, 20.02],
    "乌鲁木齐": [87.62, 43.82], "青岛": [120.38, 36.07],
    "大连": [121.62, 38.92], "厦门": [118.09, 24.48],
    "长沙": [112.97, 28.23], "郑州": [113.62, 34.75],
    "苏州": [120.58, 31.30], "天津": [117.20, 39.13],
    "合肥": [117.23, 31.82], "福州": [119.30, 26.08],
    "济南": [117.00, 36.67], "沈阳": [123.43, 41.80],
    "哈尔滨": [126.53, 45.80], "兰州": [103.83, 36.07],
    "拉萨": [91.13, 29.65], "呼和浩特": [111.75, 40.84],
}

# 30 个中国主要城市特色图标（M2 地图标注用）
city_icons = {
    "北京": "🏯", "上海": "🗼", "广州": "🦐", "深圳": "💻",
    "杭州": "🪷", "成都": "🐼", "武汉": "🍜", "西安": "🏯",
    "南京": "🏯", "重庆": "🍲", "昆明": "🌺", "贵阳": "🍶",
    "南宁": "🍊", "海口": "🌴", "乌鲁木齐": "🍇", "青岛": "🍺",
    "大连": "⚓", "厦门": "🏝️", "长沙": "🌶️", "郑州": "🛕",
    "苏州": "🏯", "天津": "🥟", "合肥": "🔬", "福州": "🍵",
    "济南": "⛲", "沈阳": "🏮", "哈尔滨": "❄️", "兰州": "🍜",
    "拉萨": "🏔️", "呼和浩特": "🐑",
}


def generate_sample_data(
    keyword: str = "Python开发", count: int = 20
) -> List[JobRawData]:
    """生成模拟招聘数据，用于开发阶段下游模块测试。

    当爬虫因反爬机制无法正常工作时，使用此函数生成接近真实的数据
    以供 cleaner、normalizer、pipeline 等模块的开发和测试。

    Args:
        keyword: 模拟的搜索关键词
        count: 生成数据条数

    Returns:
        List[JobRawData]: 模拟的原始岗位数据
    """
    # 模拟数据模板
    companies = [
        "字节跳动", "阿里巴巴", "腾讯科技", "美团", "京东",
        "百度", "网易", "滴滴出行", "小红书", "哔哩哔哩",
        "华为技术", "小米科技", "拼多多", "快手", "商汤科技",
    ]
    titles = [
        f"{keyword}工程师", f"高级{keyword}工程师", f"{keyword}架构师",
        f"{keyword}开发", f"{keyword}技术专家", f"资深{keyword}",
        f"{keyword}负责人", f"{keyword}实习生",
    ]
    # 30 个中国主要城市（含经纬度 + 特色图标，用于 M2 可视化地图标注）
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
    salary_ranges = [
        "15K-25K", "20K-35K", "25K-40K", "30K-50K",
        "10K-15K", "12K-20K", "35K-60K", "40K-70K",
        "薪资面议", "8K-12K",
    ]
    experiences = [
        "经验不限", "1-3年", "3-5年", "5-10年", "应届生",
    ]
    educations = [
        "本科及以上", "大专及以上", "硕士及以上", "学历不限",
    ]
    skills_list = [
        "Python,Django,Flask,MySQL",
        "Python,FastAPI,Redis,PostgreSQL",
        "Python,TensorFlow,PyTorch,机器学习",
        "Python,Spark,Hadoop,数据仓库",
        "Python,Linux,Docker,Kubernetes",
    ]

    random.seed(42)  # 固定种子，保证可复现
    now = datetime.now()
    results = []

    for i in range(count):
        city = random.choice(cities)
        district = random.choice(districts_map.get(city, ["-"]))

        title = random.choice(titles)
        company = random.choice(companies)
        published_days_ago = random.randint(1, 14)

        job = JobRawData(
            title=title,
            company=company,
            source="boss_zhipin",
            crawled_at=now.isoformat(),
            salary=random.choice(salary_ranges),
            location=city,
            district=district,
            experience=random.choice(experiences),
            education=random.choice(educations),
            job_type=random.choice(["全职", "全职", "全职", "实习"]),
            recruit_number=str(random.randint(1, 5)),
            industry=random.choice(
                ["互联网", "金融", "教育", "医疗", "制造"]
            ),
            job_category=random.choice(
                ["技术", "产品", "运营", "市场", "职能"]
            ),
            skills=random.choice(skills_list),
            company_size=random.choice(
                ["100-499人", "500-2000人", "2000人以上", "50-100人"]
            ),
            company_type=random.choice(
                ["民营", "上市公司", "外企", "国企"]
            ),
            welfare=random.choice(
                [
                    "五险一金,年终奖,弹性工作",
                    "五险一金,带薪年假,节日福利",
                    "六险一金,股票期权,免费三餐",
                ]
            ),
            description=(
                f"岗位职责：负责{keyword}相关系统的设计、开发与维护；"
                f"参与技术方案评审与代码审查；优化系统性能与稳定性。"
                f"任职要求：熟悉{random.choice(skills_list)}；"
                f"具备良好的沟通能力和团队协作精神。"
            ),
            platform_job_id=f"boss_sample_{keyword}_{i:04d}",
            source_url=f"https://www.zhipin.com/job_detail/sample_{i}.html",
            published_at=(
                now - timedelta(days=published_days_ago)
            ).strftime("%Y-%m-%d"),
        )
        results.append(job)

    logger.info(
        f"生成 {count} 条模拟数据 (keyword='{keyword}')，"
        f"覆盖 {len(set(cities))} 个城市, {len(companies)} 家公司"
    )
    return results
