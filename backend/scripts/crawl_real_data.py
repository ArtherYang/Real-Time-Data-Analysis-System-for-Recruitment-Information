"""
真实数据采集脚本
================
使用爬虫从招聘平台采集真实岗位数据并入库。

数据来源（按反爬难度递增）：
    1. 51job（前程无忧）— 反爬较弱，requests 可访问
    2. BOSS直聘 — CloudFlare 保护，需 Selenium

使用方式：
    python backend/scripts/crawl_real_data.py

作者: 杨昱晨
日期: 2026-07-04
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 使用 SQLite 文件存储（避免依赖 MySQL）
from app.config import TestingConfig


class SQLiteFileConfig(TestingConfig):
    """SQLite 文件配置 — 数据持久化到项目目录下的 rdas.db"""
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        db_path = os.path.join(os.path.dirname(__file__), "..", "rdas.db")
        return f"sqlite:///{db_path}"


from app import database as db_module
from app.models.job import Job
from app.processor.cleaner import DataCleaner
from app.processor.normalizer import FieldNormalizer


def try_crawl_51job(keywords, pages=2):
    """尝试从 51job 采集真实数据。反爬较弱，成功率较高。"""
    from app.crawler.job51 import Job51Crawler

    print(f"\n{'='*50}")
    print("  [1/2] 51job 真实数据采集")
    print(f"{'='*50}")
    print(f"关键词: {keywords}")
    print(f"页数/关键词: {pages}")

    all_raw_jobs = []
    crawler = Job51Crawler(delay=random.uniform(2.0, 4.0))

    for kw in keywords:
        print(f"\n  采集关键词: {kw}")
        try:
            raw_jobs = crawler.crawl(kw, pages=pages)
            print(f"    获取到 {len(raw_jobs)} 条原始记录")
            all_raw_jobs.extend(raw_jobs)
        except Exception as e:
            print(f"    采集失败: {e}")

    return all_raw_jobs


def try_crawl_boss(keywords, pages=1):
    """尝试从 BOSS直聘采集数据。可能因 CloudFlare 失败。"""
    from app.crawler.boss import BossZhipinCrawler

    print(f"\n{'='*50}")
    print("  [2/2] BOSS直聘 真实数据采集")
    print(f"{'='*50}")
    print(f"关键词: {keywords}")
    print(f"页数/关键词: {pages}")
    print("⚠️  BOSS直聘有 CloudFlare 保护，可能采集失败")

    all_raw_jobs = []
    crawler = BossZhipinCrawler(delay=random.uniform(3.0, 6.0))

    for kw in keywords:
        print(f"\n  采集关键词: {kw}")
        try:
            raw_jobs = crawler.crawl(kw, pages=pages)
            print(f"    获取到 {len(raw_jobs)} 条原始记录")
            all_raw_jobs.extend(raw_jobs)
        except Exception as e:
            print(f"    采集失败: {e}")

    return all_raw_jobs


def process_and_save(raw_jobs):
    """清洗 + 标准化 + 入库"""
    if not raw_jobs:
        print("\n⚠️  未获取到任何真实数据")
        return 0

    # 清洗
    cleaner = DataCleaner()
    clean_data, report = cleaner.clean(raw_jobs)
    print(f"\n  清洗: {report['total']} 条 → {report['valid']} 条有效 "
          f"(有效率 {report['clean_rate']:.1f}%)")

    # 标准化
    normalizer = FieldNormalizer()
    normalized = normalizer.normalize(clean_data)
    print(f"  标准化: {len(normalized)} 条")

    # 入库
    session = db_module.SessionLocal()
    saved = 0
    try:
        for record in normalized:
            # 去重：检查 platform_job_id 是否已存在
            pid = record.get("platform_job_id", "")
            if pid:
                existing = session.query(Job).filter(
                    Job.platform_job_id == pid
                ).first()
                if existing:
                    continue

            job = Job(
                job_id=record.get("job_id", ""),
                title=record.get("title", ""),
                title_raw=record.get("title_raw", ""),
                company=record.get("company", ""),
                salary_min=record.get("salary_min"),
                salary_max=record.get("salary_max"),
                salary_type=record.get("salary_type", "月薪"),
                city=record.get("city", ""),
                district=record.get("district"),
                experience=record.get("experience", "不限"),
                education=record.get("education", "不限"),
                description=record.get("description", ""),
                skills=record.get("skills", ""),
                job_type=record.get("job_type", "全职"),
                recruit_number=record.get("recruit_number", "1"),
                industry=record.get("industry", ""),
                job_category=record.get("job_category", ""),
                company_size=record.get("company_size", ""),
                company_type=record.get("company_type", ""),
                welfare=record.get("welfare", ""),
                platform=record.get("platform", ""),
                platform_job_id=record.get("platform_job_id", ""),
                source_url=record.get("source_url", ""),
                published_at=record.get("published_at"),
                crawled_at=record.get("crawled_at"),
                status="有效",
            )
            session.add(job)
            saved += 1
        session.commit()
        print(f"  入库: {saved} 条新数据（已去重）")
    except Exception as e:
        session.rollback()
        print(f"  入库失败: {e}")
        raise
    finally:
        session.close()

    return saved


if __name__ == "__main__":
    print("=" * 50)
    print("  RDAS 真实数据采集")
    print("=" * 50)

    # 初始化数据库
    config = SQLiteFileConfig()
    db_module.init_db(config)
    db_module.create_tables()

    # 搜索关键词列表（覆盖多个岗位类型以获取多样化数据）
    keywords = [
        "Python开发",
        "Java开发",
        "前端开发",
        "数据分析",
        "产品经理",
        "UI设计",
        "测试工程师",
        "运营",
        "算法工程师",
    ]

    # === 第 1 步：尝试 51job ===
    raw_51 = try_crawl_51job(keywords[:5], pages=2)
    saved_51 = process_and_save(raw_51)

    # === 第 2 步：尝试 BOSS直聘 ===
    raw_boss = try_crawl_boss(keywords[5:], pages=1)
    saved_boss = process_and_save(raw_boss)

    # === 统计 ===
    session = db_module.SessionLocal()
    try:
        from sqlalchemy import func
        total = session.query(Job).filter(Job.status == "有效").count()
        city_count = session.query(Job.city).filter(Job.status == "有效").distinct().count()
        platform_stats = (
            session.query(Job.platform, func.count(Job.job_id))
            .filter(Job.status == "有效")
            .group_by(Job.platform).all()
        )
        print(f"\n{'='*50}")
        print(f"  采集完成！数据库总计: {total} 条有效岗位")
        print(f"  覆盖城市: {city_count} 个")
        print(f"  平台分布: {dict(platform_stats)}")
        print(f"{'='*50}")
    finally:
        session.close()
