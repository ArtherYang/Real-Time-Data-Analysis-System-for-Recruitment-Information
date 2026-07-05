"""
51job 真实数据采集脚本
======================
从网页 DOM 的 sensorsdata 属性提取岗位数据。

原理：
    51job 的每个岗位卡片都有一个 sensorsdata 属性，内含完整 JSON：
    {jobTitle, jobSalary, jobArea, jobYear, jobDegree, jobTime, companyId, ...}
    直接解析这个 JSON 即可，无需逆向 API。

使用方法：
    第一种（自动）：
        python backend/scripts/crawl_51job.py

    第二种（手动批量导出，推荐）：
        在浏览器 Console 中运行下方代码，把输出 JSON 保存为文件，
        然后 python backend/scripts/crawl_51job.py --from-file data.json

作者: 杨昱晨
日期: 2026-07-04
"""

import sys
import os
import json
import time
import random
import uuid
import hashlib
import re
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from app.config import TestingConfig


class SQLiteFileConfig(TestingConfig):
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        db_path = os.path.join(os.path.dirname(__file__), "..", "rdas.db")
        return f"sqlite:///{db_path}"


from app import database as db_module
from app.models.job import Job

# 经验映射
EXP_MAP = {
    "在校生/应届生": "应届生", "应届生": "应届生", "无需经验": "应届生",
    "1年": "1-3年", "1年及以上": "1-3年", "1-3年": "1-3年",
    "2年": "1-3年", "2年及以上": "1-3年",
    "3年及以上": "3-5年", "3-4年": "3-5年", "3-5年": "3-5年",
    "5年及以上": "5-10年", "5-7年": "5-10年", "5-10年": "5-10年",
    "8-9年": "5-10年",
    "10年以上": "10年以上",
}

# 学历映射
EDU_MAP = {
    "初中及以下": "不限", "高中": "不限", "中技/中专": "不限",
    "大专": "大专", "本科": "本科", "硕士": "硕士", "博士": "博士",
    "学历不限": "不限", "招残疾人": "不限",
}

# 薪资解析（万/年 → 月薪）
def parse_salary_51job(salary_str):
    """解析 51job 薪资格式: '30-60万/年' | '1.5-2万/月' | '0.8-1万'"""
    if not salary_str or "面议" in salary_str:
        return None, None, "面议"

    # 万/年
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*年", salary_str)
    if m:
        low = int(float(m.group(1)) * 10000 / 12)
        high = int(float(m.group(2)) * 10000 / 12)
        return low, high, "月薪"

    # 万/月
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*月", salary_str)
    if m:
        return int(float(m.group(1)) * 10000), int(float(m.group(2)) * 10000), "月薪"

    # K格式: 15K-25K
    m = re.match(r"([\d.]+)\s*[kK]\s*[-~至]\s*([\d.]+)\s*[kK]", salary_str)
    if m:
        return int(float(m.group(1)) * 1000), int(float(m.group(2)) * 1000), "月薪"

    # 千/月: 8-10千/月
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*千\s*/\s*月", salary_str)
    if m:
        return int(float(m.group(1)) * 1000), int(float(m.group(2)) * 1000), "月薪"

    return None, None, "未识别"


def extract_from_dom(driver):
    """从浏览器 DOM 提取所有岗位卡片的 sensorsdata + company"""
    cards = driver.find_elements(By.CSS_SELECTOR, ".card.sensors_exposure, [sensorsdata]")
    jobs = []

    for card in cards:
        try:
            sensors_str = card.get_attribute("sensorsdata")
            if not sensors_str:
                continue
            data = json.loads(sensors_str)

            # 公司名称 — 尝试多种选择器
            company = ""
            try:
                for sel in [".bottom .left span", ".cname", "[class*='company'] span",
                           "a[href*='coU'] span", "a[href*='all/co'] span"]:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    txt = el.text.strip()
                    if txt and len(txt) >= 2:
                        company = txt
                        break
            except:
                pass

            # 福利标签
            try:
                tag_els = card.find_elements(By.CSS_SELECTOR, ".middle .tag, .tag")
                welfare_tags = [t.text.strip() for t in tag_els
                               if t.text.strip() and not any(x in t.text for x in ["年", "本科", "硕士", "博士", "大专"])]
                welfare = ",".join(welfare_tags[:8]) if welfare_tags else ""
            except:
                welfare = ""

            # 解析经验/学历
            raw_exp = data.get("jobYear", "不限")
            raw_edu = data.get("jobDegree", "不限")
            exp = EXP_MAP.get(raw_exp, "不限")
            edu = EDU_MAP.get(raw_edu, "不限")

            salary_min, salary_max, salary_type = parse_salary_51job(
                data.get("jobSalary", "")
            )

            job = {
                "title": data.get("jobTitle", ""),
                "company": company or "未知公司",
                "salary": data.get("jobSalary", ""),
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_type": salary_type,
                "city": data.get("jobArea", ""),
                "experience": exp,
                "education": edu,
                "welfare": welfare,
                "platform": "前程无忧",
                "platform_job_id": str(data.get("jobId", "")),
                "source_url": f"https://jobs.51job.com/all/{data.get('jobId', '')}.html",
                "published_at": (data.get("jobTime", "") or "")[:10],
                "status": "有效",
            }
            jobs.append(job)
        except Exception as e:
            continue

    return jobs


def save_to_db(jobs):
    """清洗并入库"""
    session = db_module.SessionLocal()
    saved = 0
    try:
        for j in jobs:
            pid = j.get("platform_job_id", "")
            if not pid:
                continue
            # 去重
            if session.query(Job).filter(Job.platform_job_id == pid).first():
                continue

            # 解析日期
            pub_at = j.get("published_at")
            if isinstance(pub_at, str):
                try:
                    pub_at = datetime.strptime(pub_at[:10], "%Y-%m-%d").date()
                except:
                    pub_at = datetime.now().date()
            elif pub_at is None:
                pub_at = datetime.now().date()

            # 城市名去掉区县后缀
            city = (j.get("city") or "").split("·")[0].split(" ")[0].strip()

            job = Job(
                job_id=uuid.uuid4().hex,
                title=j.get("title", ""),
                title_raw=j.get("title", ""),
                company=j.get("company", ""),
                salary_min=j.get("salary_min"),
                salary_max=j.get("salary_max"),
                salary_type=j.get("salary_type", "月薪"),
                city=city or "未知",
                experience=j.get("experience", "不限"),
                education=j.get("education", "不限"),
                skills=j.get("skills", ""),
                welfare=j.get("welfare", ""),
                platform=j.get("platform", ""),
                platform_job_id=pid,
                source_url=j.get("source_url", ""),
                published_at=pub_at,
                crawled_at=datetime.now(),
                status="有效",
            )
            session.add(job)
            saved += 1
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"  入库失败: {e}")
    finally:
        session.close()
    return saved


def crawl_from_browser():
    """自动模式：启动 Chrome 采集"""
    print("=" * 50)
    print("  51job 真实数据采集 (自动模式)")
    print("=" * 50)

    config = SQLiteFileConfig()
    db_module.init_db(config)
    db_module.create_tables()

    opts = Options()
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    keywords = [
        ("Python开发", "040000"), ("Java开发", "040000"), ("前端开发", "040000"),
        ("数据分析", "040000"), ("产品经理", "040000"), ("UI设计", "040000"),
        ("测试工程师", "040000"), ("运维工程", "040000"), ("算法工程师", "040000"),
        ("运营", "040000"),
        # 不同城市搜索
        ("Java开发", "010000"), ("前端开发", "030200"), ("数据分析", "080200"),
        ("产品经理", "070000"), ("测试工程师", "050000"),
    ]

    all_jobs = []
    try:
        for kw, area_code in keywords:
            url = f"https://we.51job.com/pc/search?keyword={kw}&searchType=2&area={area_code}"
            city_name = {
                "040000": "深圳", "010000": "北京", "030200": "广州",
                "080200": "成都", "070000": "杭州", "050000": "武汉",
            }.get(area_code, "默认")
            print(f"\n  关键词: {kw} (城市: {city_name})")
            try:
                driver.get(url)
                time.sleep(random.uniform(5, 8))
                # 等待卡片加载
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".card, .sensors_exposure, [sensorsdata]"))
                )
                # 滚动加载更多
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)

                jobs = extract_from_dom(driver)
                print(f"    提取到 {len(jobs)} 条")
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"    失败: {e}")
                continue

            time.sleep(random.uniform(3, 6))
    finally:
        driver.quit()

    saved = save_to_db(all_jobs)
    print(f"\n  入库: {saved} 条（去重后）")

    # 统计
    session = db_module.SessionLocal()
    from sqlalchemy import func
    total = session.query(Job).filter(Job.status == "有效").count()
    cities = session.query(Job.city).filter(Job.status == "有效").distinct().count()
    print(f"  数据库: {total} 条, {cities} 个城市")
    session.close()


def import_from_json(filepath):
    """手动模式：从 JSON 文件导入"""
    print(f"  从 {filepath} 导入数据...")
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    config = SQLiteFileConfig()
    db_module.init_db(config)
    db_module.create_tables()

    jobs = []
    for item in raw:
        salary_min, salary_max, salary_type = parse_salary_51job(
            item.get("salary", "")
        )
        exp = EXP_MAP.get(item.get("exp", ""), "不限")
        edu = EDU_MAP.get(item.get("edu", ""), "不限")

        jobs.append({
            "title": item.get("title", ""),
            "company": item.get("company", ""),
            "salary": item.get("salary", ""),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_type": salary_type,
            "city": item.get("city", ""),
            "experience": exp,
            "education": edu,
            "platform": "前程无忧",
            "platform_job_id": str(item.get("jobId", uuid.uuid4().hex[:16])),
            "source_url": item.get("source_url", ""),
            "published_at": (item.get("time", "") or "")[:10],
            "status": "有效",
        })

    saved = save_to_db(jobs)
    print(f"  入库: {saved} 条")


# ============================================================
# 手动导出脚本（在浏览器 Console 运行）
# ============================================================

COPY_SCRIPT = """
// ====== 在 51job 搜索结果页的浏览器 Console 中运行以下代码 ======
// 把输出的 JSON 保存为文件，然后:
//   python backend/scripts/crawl_51job.py --from-file 导出的文件.json

(function() {
  const cards = document.querySelectorAll('.card.sensors_exposure, [sensorsdata]');
  const result = [];
  cards.forEach(card => {
    try {
      const raw = card.getAttribute('sensorsdata');
      if (!raw) return;
      const d = JSON.parse(raw);
      const companyEl = card.querySelector('.bottom .left span, [class*="company"] span');
      result.push({
        jobId: d.jobId,
        title: d.jobTitle,
        salary: d.jobSalary,
        city: d.jobArea,
        exp: d.jobYear,
        edu: d.jobDegree,
        company: companyEl ? companyEl.textContent.trim() : '',
        time: d.jobTime
      });
    } catch(e) {}
  });
  console.log(JSON.stringify(result, null, 2));
  console.log('共 ' + result.length + ' 条记录');
})();
"""


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--from-file":
        import_from_json(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == "--copy-script":
        print(COPY_SCRIPT)
    else:
        crawl_from_browser()
