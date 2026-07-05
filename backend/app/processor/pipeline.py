"""
数据处理管道
============
功能：连接爬虫→清洗→标准化→存储的完整数据管道调度器。
      是 M1 数据采集与处理模块的统一入口。
输入：配置对象（Settings）、爬虫实例列表、搜索关键词列表
输出：PipelineReport — 包含采集/清洗/存储各阶段统计的执行摘要

使用方式（直接调用，无需 Celery）：
    from app.processor.pipeline import PipelineOrchestrator
    from app.crawler.boss import BossZhipinCrawler, generate_sample_data

    # 方式1: 使用真实爬虫
    orchestrator = PipelineOrchestrator()
    report = orchestrator.run(keywords=["Python开发", "数据分析师"], pages=3)

    # 方式2: 使用模拟数据（开发/测试）
    orchestrator = PipelineOrchestrator(use_sample_data=True)
    report = orchestrator.run(keywords=["Python开发"])
"""

import time
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field

from loguru import logger

from app.config import default_config as config
from app.crawler.base import BaseCrawler, JobRawData
from app.crawler.boss import BossZhipinCrawler, generate_sample_data
from app.processor.cleaner import DataCleaner
from app.processor.normalizer import FieldNormalizer
from app.models.job import Job
from app.models.company import Company
from app.models.database import get_session, init_db


@dataclass
class PipelineReport:
    """管道执行摘要报告。

    包含采集、清洗、标准化、存储各阶段的统计数据。
    """

    # 采集阶段
    total_crawled: int = 0
    crawl_errors: int = 0

    # 清洗阶段
    total_valid: int = 0
    total_invalid: int = 0
    dedup_exact: int = 0
    dedup_fuzzy: int = 0
    clean_rate: float = 0.0

    # 存储阶段
    total_saved: int = 0
    total_updated: int = 0
    store_errors: int = 0

    # 元数据
    keywords: List[str] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "crawl": {
                "total_crawled": self.total_crawled,
                "errors": self.crawl_errors,
            },
            "clean": {
                "valid": self.total_valid,
                "invalid": self.total_invalid,
                "dedup_exact": self.dedup_exact,
                "dedup_fuzzy": self.dedup_fuzzy,
                "clean_rate": self.clean_rate,
            },
            "store": {
                "saved": self.total_saved,
                "updated": self.total_updated,
                "errors": self.store_errors,
            },
            "meta": {
                "keywords": self.keywords,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "duration_seconds": round(self.duration_seconds, 1),
            },
        }

    def __repr__(self) -> str:
        return (
            f"<PipelineReport crawled={self.total_crawled}, "
            f"valid={self.total_valid}, saved={self.total_saved}, "
            f"duration={self.duration_seconds:.1f}s>"
        )


class PipelineOrchestrator:
    """数据处理管道调度器。

    编排数据从采集到存储的完整生命周期：
    crawl → clean → normalize → store

    支持两种数据源：
    1. 真实爬虫（BossZhipinCrawler 等）
    2. 模拟数据（generate_sample_data，用于开发测试）

    使用示例:
        orchestrator = PipelineOrchestrator()
        report = orchestrator.run(
            keywords=["Python开发", "Java开发"],
            pages=3
        )
        print(f"采集{report.total_crawled}条，入库{report.total_saved}条")
    """

    def __init__(
        self,
        crawlers: Optional[List[BaseCrawler]] = None,
        use_sample_data: bool = False,
        init_database: bool = True,
    ):
        """初始化管道调度器。

        Args:
            crawlers: 爬虫实例列表，默认使用 BossZhipinCrawler
            use_sample_data: 是否使用模拟数据（开发模式，跳过爬虫）
            init_database: 是否自动初始化数据库表
        """
        self.crawlers = crawlers or [BossZhipinCrawler()]
        self.use_sample_data = use_sample_data
        self.cleaner = DataCleaner()
        self.normalizer = FieldNormalizer()

        # 初始化数据库
        if init_database:
            try:
                init_db()
                logger.info("[管道] 数据库表初始化完成")
            except Exception as e:
                logger.warning(f"[管道] 数据库初始化失败（可能已存在）: {e}")

    def run(
        self,
        keywords: List[str],
        pages: int = None,
        db_session=None,
    ) -> PipelineReport:
        """执行完整的数据管道。

        Args:
            keywords: 搜索关键词列表
            pages: 每个关键词的采集页数，默认使用 config 配置
            db_session: 可选的数据库会话（用于测试注入 SQLite 会话）

        Returns:
            PipelineReport: 执行摘要报告
        """
        pages = pages or config.CRAWL_MAX_PAGES
        report = PipelineReport(
            keywords=keywords,
            start_time=datetime.now().isoformat(),
        )
        start = time.time()

        logger.info(
            f"[管道] 开始执行: keywords={keywords}, pages={pages}, "
            f"sample_mode={self.use_sample_data}"
        )

        # ========== 阶段1: 数据采集 ==========
        raw_data = self._collect(keywords, pages, report)

        if not raw_data:
            logger.warning("[管道] 未采集到任何数据，管道终止")
            report.end_time = datetime.now().isoformat()
            report.duration_seconds = time.time() - start
            return report

        report.total_crawled = len(raw_data)

        # ========== 阶段2: 数据清洗 ==========
        clean_data, quality_report = self.cleaner.clean(raw_data)
        report.total_valid = quality_report["valid"]
        report.total_invalid = quality_report["invalid"]
        report.dedup_exact = quality_report["dedup_exact"]
        report.dedup_fuzzy = quality_report["dedup_fuzzy"]
        report.clean_rate = quality_report["clean_rate"]

        logger.info(
            f"[管道] 清洗完成: 有效{report.total_valid}, "
            f"有效率{report.clean_rate:.1f}%"
        )

        if not clean_data:
            logger.warning("[管道] 清洗后无有效数据，管道终止")
            report.end_time = datetime.now().isoformat()
            report.duration_seconds = time.time() - start
            return report

        # ========== 阶段3: 字段标准化 ==========
        normalized_data = self.normalizer.normalize(clean_data)
        logger.info(f"[管道] 标准化完成: {len(normalized_data)} 条")

        # ========== 阶段4: 数据存储 ==========
        saved, updated, errors = self._store(normalized_data, report, db_session)
        report.total_saved = saved
        report.total_updated = updated
        report.store_errors = errors

        # ========== 完成 ==========
        report.end_time = datetime.now().isoformat()
        report.duration_seconds = time.time() - start

        logger.info(
            f"[管道] 执行完成: 采集{report.total_crawled}条, "
            f"入库{report.total_saved}条(新增), "
            f"更新{report.total_updated}条, "
            f"耗时{report.duration_seconds:.1f}秒"
        )
        return report

    def _collect(
        self,
        keywords: List[str],
        pages: int,
        report: PipelineReport,
    ) -> List[JobRawData]:
        """阶段1: 执行数据采集。

        Args:
            keywords: 搜索关键词列表
            pages: 采集页数
            report: 报告对象（用于记录错误）

        Returns:
            List[JobRawData]: 汇总的原始数据
        """
        all_data: List[JobRawData] = []

        if self.use_sample_data:
            # 开发模式：使用模拟数据
            for keyword in keywords:
                sample = generate_sample_data(keyword, count=20)
                all_data.extend(sample)
            logger.info(
                f"[管道-采集] 生成 {len(all_data)} 条模拟数据"
            )
            return all_data

        # 生产模式：使用真实爬虫
        for crawler in self.crawlers:
            for keyword in keywords:
                try:
                    jobs = crawler.crawl(keyword, pages)
                    all_data.extend(jobs)
                    logger.info(
                        f"[管道-采集] {crawler.name} "
                        f"'{keyword}': {len(jobs)} 条"
                    )
                except Exception as e:
                    logger.error(
                        f"[管道-采集] {crawler.name} "
                        f"'{keyword}' 采集异常: {e}"
                    )
                    report.crawl_errors += 1

        return all_data

    def _store(
        self,
        data: List[dict],
        report: PipelineReport,
        db_session=None,
    ) -> tuple:
        """阶段4: 将标准化数据批量写入数据库。

        使用 session.merge() 实现 upsert：
        - 新记录（新 platform_job_id）→ INSERT
        - 已存在记录（同 platform_job_id）→ UPDATE

        Args:
            data: 标准化后的数据字典列表
            report: 报告对象
            db_session: 可选的数据库会话（注入则使用，否则自建）

        Returns:
            tuple: (新增数, 更新数, 错误数)
        """
        saved = 0
        updated = 0
        errors = 0

        session = db_session if db_session is not None else get_session()
        close_on_exit = db_session is None  # 仅自建 session 需要关闭
        try:
            for record in data:
                try:
                    job = Job.from_normalized(record)

                    # 检查是否已存在（基于 platform_job_id）
                    existing = None
                    if job.platform_job_id:
                        existing = (
                            session.query(Job)
                            .filter_by(
                                platform_job_id=job.platform_job_id
                            )
                            .first()
                        )

                    if existing:
                        # 更新现有记录
                        for key, value in job.to_dict().items():
                            if key not in ("job_id",):
                                setattr(existing, key, value)
                        updated += 1
                    else:
                        # 新增记录
                        session.add(job)
                        saved += 1

                    # 同步写 Company 表
                    self._upsert_company(session, record)

                except Exception as e:
                    logger.warning(f"[管道-存储] 记录保存失败: {e}")
                    errors += 1
                    continue

            session.commit()
            logger.info(
                f"[管道-存储] 新增{saved}条, 更新{updated}条, "
                f"失败{errors}条"
            )

        except Exception as e:
            session.rollback()
            logger.error(f"[管道-存储] 事务提交失败: {e}")
            errors = len(data)  # 标记全部失败
        finally:
            if close_on_exit:
                session.close()

        return saved, updated, errors

    @staticmethod
    def _upsert_company(session, record: dict) -> None:
        """同步更新公司信息表。

        如果公司名不存在则创建，存在则跳过。

        Args:
            session: 数据库会话
            record: 标准化后的岗位数据字典
        """
        company_name = record.get("company")
        if not company_name:
            return

        existing = (
            session.query(Company)
            .filter_by(name=company_name)
            .first()
        )

        if not existing:
            company = Company(
                name=company_name,
                size=record.get("company_size"),
                company_type=record.get("company_type"),
                industry=record.get("industry"),
            )
            session.add(company)
