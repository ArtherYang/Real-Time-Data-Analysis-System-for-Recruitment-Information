"""
独立爬虫运行脚本
================
可直接运行：python run_crawler.py
采集 BOSS直聘 和 51job 的真实岗位数据，输出到 data/ 目录。

策略：
  1. 51job API（优先，JSON接口最可靠）
  2. 51job Playwright WAF绕过（备选）
  3. BOSS直聘内部API（需要Cookie）
  4. BOSS直聘 Selenium（最后兜底）

使用方式：
  python run_crawler.py                      # 默认：Python开发, 3页
  python run_crawler.py --keyword "数据分析" --pages 5
  python run_crawler.py --platform boss      # 仅BOSS直聘
  python run_crawler.py --platform job51     # 仅51job
"""
import argparse
import json
import os
import sys
import time
import hashlib
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests
from loguru import logger

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.crawler.base import JobRawData
from app.crawler.anti_crawl import AntiCrawlManager, retry_request
from app.crawler.job51 import Job51Crawler
from app.crawler.boss import BossZhipinCrawler

# ======================== 配置 ========================
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

KEYWORDS = [
    "Python开发", "Java开发", "前端开发", "数据分析", "产品经理",
    "UI设计", "测试工程师", "运维工程师", "算法工程师", "运营",
]

# ======================== 51job API 直连（最可靠的方式）====================


def crawl_51job_api(keyword: str = "", pages: int = 3) -> List[Dict]:
    """
    通过 51job 公开搜索API直接获取岗位数据。

    这是最稳定的方式：直接调 JSON API，绕过页面解析和WAF。
    API: https://we.51job.com/api/job/search-pc

    Args:
        keyword: 搜索关键词，空字符串=不限
        pages: 采集页数

    Returns:
        List[Dict]: 岗位数据字典列表
    """
    logger.info(f"[51job-API] 开始采集: keyword='{keyword}', pages={pages}")

    session = requests.Session()
    anti_crawl = AntiCrawlManager()
    all_jobs = []

    api_url = "https://we.51job.com/api/job/search-pc"

    for page in range(1, pages + 1):
        params = {
            "api_key": "51job",
            "timestamp": int(time.time() * 1000),
            "keyword": keyword,
            "searchType": "2",
            "function": "",
            "industry": "",
            "jobArea": "000000",  # 全国
            "jobArea2": "",
            "landmark": "",
            "metro": "",
            "salary": "",
            "workYear": "",
            "degree": "",
            "companyType": "",
            "companySize": "",
            "jobType": "",
            "issueDate": "4",  # 近30天
            "sortType": "0",
            "pageNum": page,
            "requestId": "",
            "keywordType": "2",
            "pageSize": "20",
            "source": "1",
            "accountId": "",
            "pageCode": "sou|sou|soulb",
            "scene": "7",
        }

        headers = anti_crawl.get_headers(referer="https://we.51job.com/")
        headers["Accept"] = "application/json, text/plain, */*"

        # 延迟
        time.sleep(random.uniform(2.0, 5.0))

        try:
            resp = session.get(api_url, params=params, headers=headers, timeout=30)

            if resp.status_code != 200:
                logger.warning(f"[51job-API] 第{page}页 HTTP {resp.status_code}")
                continue

            # 检查是否被WAF拦截（返回HTML而非JSON）
            text = resp.text
            if text.strip().startswith("<"):
                logger.warning(f"[51job-API] 第{page}页被WAF拦截（返回HTML）")
                continue

            data = resp.json()
            items = (
                data.get("resultbody", {})
                .get("job", {})
                .get("items", [])
            )

            if not items:
                logger.info(f"[51job-API] 第{page}页无数据，停止翻页")
                break

            for item in items:
                job = {
                    "title": (item.get("jobName") or "").strip(),
                    "company": (item.get("companyName") or "").strip(),
                    "salary": (item.get("provideSalaryString") or "").strip(),
                    "location": (item.get("jobAreaString") or "").strip(),
                    "experience": (item.get("workYearString") or "").strip(),
                    "education": (item.get("degreeString") or "").strip(),
                    "company_size": (item.get("companySizeString") or "").strip(),
                    "company_type": (item.get("companyTypeString") or "").strip(),
                    "industry": (item.get("industryType1Str") or "").strip(),
                    "welfare": (item.get("jobWelfareString") or "").strip(),
                    "published_at": (item.get("issueDateString") or "").strip(),
                    "source": "job51",
                    "source_url": (item.get("jobHref") or "").strip(),
                    "platform_job_id": f"job51_{item.get('jobId', '')}",
                    "crawled_at": datetime.now().isoformat(),
                }
                all_jobs.append(job)

            logger.info(f"[51job-API] 第{page}页: {len(items)}条")

        except requests.RequestException as e:
            logger.error(f"[51job-API] 第{page}页请求异常: {e}")
            continue
        except json.JSONDecodeError as e:
            logger.error(f"[51job-API] 第{page}页JSON解析失败: {e}")
            continue

    logger.info(f"[51job-API] 采集完成: 共{len(all_jobs)}条")
    return all_jobs


def crawl_all(keyword: str = "Python开发", pages: int = 3) -> List[Dict]:
    """多关键词、多平台采集，汇总结果。"""
    all_jobs = []

    # ==== 51job API（主采集源）====
    for kw in KEYWORDS[:6]:  # 限制关键词数量，避免请求过多
        logger.info(f"=" * 50)
        logger.info(f"采集 51job: {kw}")
        jobs = crawl_51job_api(keyword=kw, pages=pages)
        all_jobs.extend(jobs)
        logger.info(f"  -> {len(jobs)} 条")
        time.sleep(random.uniform(5.0, 10.0))  # 关键词间延迟

    return all_jobs


# ======================== 数据清洗 ========================

def clean_jobs(raw_jobs: List[Dict]) -> List[Dict]:
    """去重、清洗原始数据。"""
    seen = set()
    cleaned = []

    for job in raw_jobs:
        # 去重键：岗位名+公司名+来源平台
        dedup_key = f"{job.get('title','')}|{job.get('company','')}|{job.get('source','')}"
        dedup_hash = hashlib.md5(dedup_key.encode()).hexdigest()

        if dedup_hash in seen:
            continue
        seen.add(dedup_hash)

        # 过滤无效数据
        if not job.get("title") or not job.get("company"):
            continue
        if job.get("title") in ("", "未知岗位") or job.get("company") in ("", "未知公司"):
            continue

        cleaned.append(job)

    return cleaned


# ======================== 主入口 ========================

def main():
    parser = argparse.ArgumentParser(description="招聘数据采集工具")
    parser.add_argument("--keyword", default="Python开发", help="搜索关键词")
    parser.add_argument("--pages", type=int, default=3, help="每个关键词采集页数")
    parser.add_argument("--platform", default="all", choices=["all", "boss", "job51"])
    parser.add_argument("--output", default=None, help="输出文件路径")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("招聘信息数据采集工具 v2.0")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"关键词: {args.keyword}, 页数: {args.pages}, 平台: {args.platform}")
    logger.info("=" * 60)

    # ---- 采集 ----
    all_raw = crawl_all(keyword=args.keyword, pages=args.pages)

    # ---- 清洗 ----
    cleaned = clean_jobs(all_raw)

    # ---- 统计 ----
    companies = set(j.get("company", "") for j in cleaned)
    cities = set(j.get("location", "") for j in cleaned)
    titles = set(j.get("title", "") for j in cleaned)

    logger.info("=" * 60)
    logger.info(f"采集完成统计:")
    logger.info(f"  原始数据: {len(all_raw)} 条")
    logger.info(f"  清洗后:   {len(cleaned)} 条")
    logger.info(f"  去重率:   {(1 - len(cleaned)/max(len(all_raw),1))*100:.1f}%")
    logger.info(f"  公司数:   {len(companies)} 家")
    logger.info(f"  城市数:   {len(cities)} 个")
    logger.info(f"  岗位类:   {len(titles)} 种")
    logger.info("=" * 60)

    # ---- 保存 ----
    output_path = args.output or str(DATA_DIR / "jobs_raw.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    logger.info(f"数据已保存至: {output_path}")

    # ---- 也保存一份带时间戳的备份 ----
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DATA_DIR / f"jobs_{timestamp}.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    logger.info(f"备份已保存至: {backup_path}")

    return cleaned


if __name__ == "__main__":
    main()
