"""
统一爬虫调度
============
合并所有可用数据源，按可靠性自动选择最优采集路径。

数据源（按优先级排序）：
  1. 已有真实 SQLite DB 直接导入 — real_30cities(600条) + jobSpider(491条) + lagou(100条)
  2. Playwright 浏览器 JS fetch 绕过 WAF — 51job 实时采集（已证明可绕过阿里云 WAF）
  3. BOSS 直聘模拟数据生成 — 开发测试用
  4. requests 传统爬虫 — 兜底（大概率被 WAF 拦截）

使用方式：
    from app.crawler.unified import UnifiedCrawler
    crawler = UnifiedCrawler()
    jobs, report = crawler.crawl(keyword="Python开发", max_pages=3)

AI生成，待人工审查。
"""

import os
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from loguru import logger

from app.crawler.base import JobRawData


@dataclass
class CrawlReport:
    """采集报告"""
    total_collected: int = 0
    total_saved: int = 0
    sources_used: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_collected": self.total_collected,
            "total_saved": self.total_saved,
            "sources_used": self.sources_used,
            "errors": self.errors[:5],
            "duration_seconds": round(self.duration_seconds, 1),
        }


class UnifiedCrawler:
    """统一爬虫 — 合并所有数据源。"""

    def __init__(self):
        self._data_dir = os.path.join(
            os.path.dirname(__file__), "..", "data"
        )

    # ============================================================
    # 数据源 1：直接导入已有真实 SQLite 数据库
    # ============================================================

    def import_real_db(self) -> Tuple[int, str]:
        """从工程内已有的真实 SQLite 数据库导入 jobs。

        数据文件：
          - real_30cities.db  : 600 条 51job 真实数据（30 城市）
          - jobSpider_real.db : 491 条 jobSpider 真实数据
          - lagou_real.db     : 100 条拉勾网真实数据

        Returns:
            (imported_count, status_message)
        """
        import sqlite3
        from ..models.database import get_session
        from ..models.job import Job

        db_files = [
            ("real_30cities.db", "51job 30城市"),
            ("jobSpider_real.db", "jobSpider"),
            ("lagou_real.db", "拉勾网"),
        ]

        app_db = get_session()
        total_imported = 0
        sources_used = []

        for filename, label in db_files:
            filepath = os.path.join(self._data_dir, filename)
            if not os.path.exists(filepath):
                logger.debug(f"跳过 {label}（文件不存在: {filepath}）")
                continue

            src = sqlite3.connect(filepath)
            src.row_factory = sqlite3.Row
            rows = src.execute("SELECT * FROM jobs").fetchall()
            src.close()

            if not rows:
                continue

            imported = 0
            for row in rows:
                d = dict(row)
                pid = d.get("platform_job_id", "")
                if not pid:
                    continue
                existing = app_db.query(Job).filter(
                    Job.platform_job_id == pid
                ).first()
                if existing:
                    continue

                job = Job(
                    job_id=d.get("job_id", ""),
                    title=d.get("title", ""),
                    title_raw=d.get("title_raw"),
                    company=d.get("company", ""),
                    salary_min=d.get("salary_min"),
                    salary_max=d.get("salary_max"),
                    salary_type=d.get("salary_type", "月薪"),
                    city=d.get("city", ""),
                    district=d.get("district"),
                    experience=d.get("experience", "不限"),
                    education=d.get("education", "不限"),
                    description=d.get("description"),
                    skills=d.get("skills"),
                    industry=d.get("industry"),
                    job_category=d.get("job_category"),
                    company_size=d.get("company_size"),
                    company_type=d.get("company_type"),
                    welfare=d.get("welfare"),
                    platform=d.get("platform", "job51"),
                    platform_job_id=pid,
                    source_url=d.get("source_url"),
                    published_at=d.get("published_at"),
                    status="有效",
                )
                app_db.add(job)
                imported += 1

            app_db.commit()
            total_imported += imported
            sources_used.append(f"{label}({imported}条)")
            logger.info(f"[统爬] {label}: {len(rows)}条 → 新增入库{imported}条")

        app_db.close()
        return total_imported, f"真实DB: {', '.join(sources_used)} → 共{total_imported}条"

    # ============================================================
    # 数据源 2：Playwright 浏览器内 fetch 绕过 WAF
    # ============================================================

    def crawl_playwright(
        self, keyword: str = "", pages: int = 1, cities: List[str] = None
    ) -> List[JobRawData]:
        """用 Playwright 绕过 51job WAF，浏览器内 JS fetch 调内部 API 采集。

        Args:
            keyword: 搜索关键词（暂不支持关键词搜索，仅城市范围）
            pages: 每个城市采集页数
            cities: 目标城市列表，默认 5 个一线城市

        Returns:
            原始岗位数据列表
        """
        if cities is None:
            cities = ["北京", "上海", "深圳", "杭州", "广州"]

        try:
            from .job51 import Job51Crawler
            crawler = Job51Crawler()
            logger.info(f"[统爬] Playwright: {len(cities)}城市×{pages}页")
            return crawler.crawl_with_playwright(cities=cities, pages_per_city=pages)
        except ImportError:
            logger.warning("Playwright 未安装")
            return []
        except Exception as e:
            logger.error(f"Playwright 采集异常: {e}")
            return []

    # ============================================================
    # 数据源 3：BOSS 直聘模拟数据（开发用）
    # ============================================================

    def crawl_boss_sample(self, keyword: str = "Python开发", count: int = 20) -> List[JobRawData]:
        """BOSS 直聘模拟数据生成（CloudFlare 封锁导致无真实数据）。"""
        from .boss import generate_sample_data
        logger.info(f"[统爬] BOSS 模拟数据: keyword={keyword}, count={count}")
        return generate_sample_data(keyword, count)

    # ============================================================
    # 数据源 4：requests 传统爬虫（兜底，大概率失败）
    # ============================================================

    def crawl_requests(self, keyword: str = "", pages: int = 1) -> List[JobRawData]:
        """传统 requests 爬虫 — 大概率被 WAF 拦截，快速失败。"""
        try:
            from .job51 import Job51Crawler
            crawler = Job51Crawler()
            logger.info(f"[统爬] requests: keyword={keyword}, pages={pages}")
            return crawler.crawl(keyword, pages)
        except Exception as e:
            logger.warning(f"requests 爬虫失败: {e}")
            return []

    # ============================================================
    # 主调度：自动选择最优数据源
    # ============================================================

    def crawl(
        self,
        keyword: str = "Python开发",
        platform: str = "job51",
        pages: int = 2,
        city: str = None,
    ) -> Tuple[List[JobRawData], CrawlReport]:
        """统一采集入口 — 自动选择最优数据源组合。

        策略：
          1. 始终先导入已有真实 DB（秒级）
          2. 如果 platform=job51，追加 Playwright 实时采集
          3. 如果 platform=boss_zhipin，用模拟数据
          4. 兜底用 requests（大概率失败，仅作尝试）

        Returns:
            (all_raw_jobs, CrawlReport)
        """
        start = time.time()
        report = CrawlReport()
        all_jobs = []

        # ---- Step 1: 导入已有真实 DB（最快，最可靠） ----
        imported, msg = self.import_real_db()
        report.total_saved += imported
        report.sources_used.append(msg)

        # ---- Step 2: 按平台选择实时采集方案 ----
        if platform == "job51":
            target_cities = [city] if city else ["北京", "上海", "深圳", "杭州", "广州"]
            pw_jobs = self.crawl_playwright(keyword, pages, target_cities)
            if pw_jobs:
                all_jobs.extend(pw_jobs)
                report.sources_used.append(f"Playwright({len(pw_jobs)}条)")
            else:
                report.errors.append("Playwright返回空（WAF可能升级）")

        elif platform == "boss_zhipin":
            sample = self.crawl_boss_sample(keyword, count=40)
            all_jobs.extend(sample)
            report.sources_used.append(f"BOSS模拟({len(sample)}条)")

        elif platform == "all":
            # 尝试所有可用渠道
            requests_jobs = self.crawl_requests(keyword, pages)
            if requests_jobs:
                all_jobs.extend(requests_jobs)

        report.total_collected = len(all_jobs)
        report.duration_seconds = time.time() - start

        logger.info(
            f"[统爬] 完成: collected={report.total_collected}, "
            f"saved={report.total_saved}, sources={report.sources_used}, "
            f"duration={report.duration_seconds:.1f}s"
        )
        return all_jobs, report


# 模块级便捷函数
_default_crawler = None


def get_unified_crawler() -> UnifiedCrawler:
    global _default_crawler
    if _default_crawler is None:
        _default_crawler = UnifiedCrawler()
    return _default_crawler


def quick_crawl(keyword: str = "Python开发") -> CrawlReport:
    """快速采集：导入真实 DB + 尝试 Playwright。"""
    crawler = get_unified_crawler()
    _, report = crawler.crawl(keyword=keyword)
    return report
