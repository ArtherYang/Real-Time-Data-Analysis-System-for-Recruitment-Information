"""
浏览器自动化采集脚本
====================
使用 Selenium + Chrome 渲染 JS 页面，从 51job 和 BOSS直聘采集真实岗位数据。

原理：真实浏览器渲染后提取 DOM 中的岗位卡片，绕过所有反爬机制。

使用方法：
    python backend/scripts/crawl_browser.py

注意：
    - 需要已安装 Chrome 浏览器
    - 自动管理 chromedriver（Selenium 4 内置）
"""

import sys
import os
import time
import random
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from app.config import TestingConfig


class SQLiteFileConfig(TestingConfig):
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        db_path = os.path.join(os.path.dirname(__file__), "..", "rdas.db")
        return f"sqlite:///{db_path}"


from app import database as db_module


def create_driver():
    """创建 Chrome WebDriver（反检测模式）"""
    opts = Options()
    # 先用非 headless 试试看（绕过反自动化检测）
    # opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    # 注入 stealth 脚本
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ============================================================
# BOSS直聘 采集
# ============================================================

def crawl_boss(driver, keywords, save_callback):
    """从 BOSS直聘搜索页采集数据"""
    print(f"\n{'='*50}")
    print("  BOSS直聘 浏览器采集")
    print(f"{'='*50}")

    total = 0
    for kw in keywords:
        print(f"\n  [关键词] {kw}")
        for page in range(1, 4):  # 每个关键词取 3 页
            url = f"https://www.zhipin.com/web/geek/job?query={kw}&page={page}"
            try:
                driver.get(url)
                time.sleep(random.uniform(3, 5))

                # 等待岗位卡片加载
                wait = WebDriverWait(driver, 15)
                cards = wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, ".job-card-wrapper, .job-card-box, [class*='job-card']")
                    )
                )
                if not cards:
                    print(f"    第{page}页: 0 条")
                    break

                page_count = 0
                for card in cards:
                    try:
                        title_el = card.find_element(By.CSS_SELECTOR, ".job-name, [class*='job-title'], span.job-name")
                        title = title_el.text.strip()
                        if not title:
                            continue

                        salary = "薪资面议"
                        try:
                            salary_el = card.find_element(By.CSS_SELECTOR, ".salary, [class*='salary']")
                            salary = salary_el.text.strip() or "薪资面议"
                        except:
                            pass

                        city = ""
                        exp = "不限"
                        edu = "不限"
                        tags = card.find_elements(By.CSS_SELECTOR, ".tag-list li, [class*='tag'] li, .job-info .tag-item")
                        tag_texts = [t.text.strip() for t in tags if t.text.strip()]
                        for t in tag_texts:
                            if any(term in t for term in ["应届", "年经验", "1-3", "3-5", "5-10", "10年"]):
                                exp = t
                            elif any(term in t for term in ["本科", "硕士", "博士", "大专", "学历不限"]):
                                edu = t
                            elif t not in (exp, edu):
                                pass  # 这些是技能标签

                        try:
                            company_el = card.find_element(By.CSS_SELECTOR, ".company-name a, [class*='company'] a")
                            company = company_el.text.strip()
                        except:
                            company = "未知公司"

                        try:
                            loc_el = card.find_element(By.CSS_SELECTOR, ".job-area, [class*='area']")
                            city = loc_el.text.strip().split("·")[0].split("-")[0]
                        except:
                            pass

                        job = {
                            "title": title,
                            "title_raw": title,
                            "company": company,
                            "salary": salary,
                            "city": city or "未知",
                            "experience": exp,
                            "education": edu,
                            "platform": "BOSS直聘",
                            "status": "有效",
                        }
                        save_callback(job)
                        page_count += 1
                    except Exception as e:
                        continue

                total += page_count
                print(f"    第{page}页: {page_count} 条")
                time.sleep(random.uniform(2, 4))

            except Exception as e:
                print(f"    第{page}页失败: {e}")
                break

    print(f"\n  BOSS直聘 合计: {total} 条")
    return total


# ============================================================
# 51job 采集
# ============================================================

def crawl_51job(driver, keywords, save_callback):
    """从 51job 搜索页采集数据"""
    print(f"\n{'='*50}")
    print("  51job 浏览器采集")
    print(f"{'='*50}")

    total = 0
    for kw in keywords:
        print(f"\n  [关键词] {kw}")
        url = f"https://we.51job.com/pc/search?keyword={kw}&searchType=2&sortType=0"
        try:
            driver.get(url)
            time.sleep(random.uniform(4, 6))

            wait = WebDriverWait(driver, 15)
            # 新版 51job 可能用多种选择器
            cards = driver.find_elements(By.CSS_SELECTOR, ".joblist-item, .j-joblist .job-item, [class*='job-card'], .e ")

            page_count = 0
            for card in cards:
                try:
                    # 岗位名称
                    try:
                        title_el = card.find_element(By.CSS_SELECTOR, ".job-name, .jname, .jobinfo-name, [class*='job-title'] a")
                        title = title_el.text.strip() or title_el.get_attribute("title") or ""
                    except:
                        try:
                            title_el = card.find_element(By.TAG_NAME, "a")
                            title = title_el.text.strip() or title_el.get_attribute("title") or ""
                        except:
                            continue
                    if not title or len(title) < 2:
                        continue

                    # 公司
                    try:
                        company_el = card.find_element(By.CSS_SELECTOR, ".cname, .company-name, [class*='company'] a")
                        company = company_el.text.strip()
                    except:
                        company = "未知公司"

                    # 薪资
                    try:
                        salary_el = card.find_element(By.CSS_SELECTOR, ".sal, .salary, [class*='salary']")
                        salary = salary_el.text.strip() or "薪资面议"
                    except:
                        salary = "薪资面议"

                    # 工作地点+经验+学历 — 51job新版可能用不同的class
                    info_text = ""
                    try:
                        # 尝试多种选择器匹配新版51job
                        for selector in [
                            ".job-attribute span, .jobinfo-attribute span",
                            "[class*='attribute'] span, [class*='attr'] span",
                            "p.msg, .msg",
                            "[class*='info'] span, [class*='condition'] span",
                            "[class*='item-attr'] span"
                        ]:
                            els = card.find_elements(By.CSS_SELECTOR, selector)
                            if els:
                                info_text = "|".join(e.text.strip() for e in els if e.text.strip())
                                break
                        # 如果上面都没找到，拿卡片内全部文本
                        if not info_text:
                            info_text = card.text
                    except:
                        info_text = card.text if hasattr(card, 'text') else ""

                    # 从 info_text 解析地点/经验/学历
                    city = ""
                    exp = "不限"
                    edu = "不限"
                    # 常见城市列表
                    all_cities = ["北京", "上海", "深圳", "广州", "杭州", "成都", "武汉",
                                  "南京", "西安", "重庆", "苏州", "长沙", "天津", "合肥",
                                  "厦门", "郑州", "济南", "青岛", "大连", "沈阳", "东莞",
                                  "宁波", "福州", "无锡", "佛山", "珠海", "中山"]
                    if info_text:
                        # 按常见分隔符拆分
                        parts = [p.strip() for p in info_text.replace("|", "|").replace("/", "|").split("|")]
                        for p in parts:
                            # 城市识别（优先级最高）
                            for c in all_cities:
                                if p.startswith(c):
                                    city = c
                                    break
                            if city:
                                continue
                            # 经验
                            if any(t in p for t in ["年经验", "1-3", "3-5", "5-10", "10年", "应届", "不限经验"]):
                                exp = p
                            # 学历
                            elif any(t in p for t in ["本科", "硕士", "博士", "大专", "高中", "中专"]):
                                edu = p
                            # 已有全经验匹配
                            elif any(t == p for t in ["1-3年", "3-5年", "5-10年", "1年以下"]):
                                exp = p

                    job_title = title
                    job = {
                        "title": job_title,
                        "title_raw": job_title,
                        "company": company,
                        "salary": salary,
                        "city": city or "未知",
                        "experience": exp,
                        "education": edu,
                        "platform": "前程无忧",
                        "status": "有效",
                    }
                    save_callback(job)
                    page_count += 1
                except Exception as e:
                    continue

            total += page_count
            print(f"    {kw}: {page_count} 条")

        except Exception as e:
            print(f"    {kw} 失败: {e}")

    print(f"\n  51job 合计: {total} 条")
    return total


# ============================================================
# 数据存储
# ============================================================

def create_save_callback(session):
    """创建数据保存回调，负责解析+清洗+入库"""
    from app.models.job import Job
    from app.processor.cleaner import DataCleaner
    from app.processor.normalizer import FieldNormalizer
    from app.crawler.base import JobRawData
    import hashlib

    saved = [0]
    seen_ids = set()

    cleaner = DataCleaner()
    normalizer = FieldNormalizer()

    def save(raw_data):
        # 生成platform_job_id
        key_str = raw_data.get("title", "") + raw_data.get("company", "") + raw_data.get("city", "")
        pid = hashlib.md5(key_str.encode()).hexdigest()[:16]
        if pid in seen_ids:
            return
        seen_ids.add(pid)

        # 构建 JobRawData 用于清洗
        raw = JobRawData(
            title=raw_data.get("title", ""),
            company=raw_data.get("company", ""),
            source=raw_data.get("platform", ""),
            crawled_at=datetime.now().isoformat(),
            salary=raw_data.get("salary", ""),
            location=raw_data.get("city", ""),
            experience=raw_data.get("experience", ""),
            education=raw_data.get("education", ""),
            platform_job_id=pid,
        )

        # 清洗+标准化
        clean_records, _ = cleaner.clean([raw])
        if not clean_records:
            return
        normalized = normalizer.normalize(clean_records)
        if not normalized:
            return

        rec = normalized[0]
        job = Job(
            job_id=uuid.uuid4().hex,
            title=rec.get("title", "") or "",
            title_raw=raw_data.get("title_raw", "") or "",
            company=rec.get("company", "") or "",
            salary_min=rec.get("salary_min"),
            salary_max=rec.get("salary_max"),
            salary_type=rec.get("salary_type", "月薪"),
            city=rec.get("city", "") or "",
            district=rec.get("district"),
            experience=rec.get("experience", "不限"),
            education=rec.get("education", "不限"),
            description=raw_data.get("description", ""),
            skills="",
            job_type="全职",
            recruit_number="1",
            industry=raw_data.get("industry", ""),
            job_category=raw_data.get("job_category", ""),
            company_size=raw_data.get("company_size", ""),
            company_type=raw_data.get("company_type", ""),
            welfare="",
            platform=raw_data.get("platform", ""),
            platform_job_id=pid,
            source_url="",
            published_at=datetime.now().date(),
            crawled_at=datetime.now(),
            status="有效",
        )
        try:
            # 检查重复
            existing = session.query(Job).filter(Job.platform_job_id == pid).first()
            if existing:
                return
            session.add(job)
            session.commit()
            saved[0] += 1
        except:
            session.rollback()

    return save, saved


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  RDAS 浏览器自动化采集")
    print("=" * 50)

    # 初始化数据库
    config = SQLiteFileConfig()
    db_module.init_db(config)
    db_module.create_tables()

    session = db_module.SessionLocal()
    save_cb, saved_counter = create_save_callback(session)

    # 先清空旧模拟数据
    from app.models.job import Job
    old = session.query(Job).delete()
    session.commit()
    print(f"  清空旧数据 {old} 条\n")

    driver = create_driver()

    try:
        # 先试 BOSS直聘（JS渲染页面可提取）
        boss_kw = [
            "Python开发", "Java开发", "前端开发", "数据分析",
            "产品经理", "算法工程师", "测试工程师", "运维",
        ]
        boss_count = crawl_boss(driver, boss_kw, save_cb)

        # 再试 51job
        job51_kw = [
            "Python开发", "Java开发", "前端开发", "数据分析",
        ]
        job51_count = crawl_51job(driver, job51_kw, save_cb)

        total = saved_counter[0]
        print(f"\n{'='*50}")
        print(f"  采集完成！")
        print(f"  BOSS直聘: {boss_count} 条")
        print(f"  51job:    {job51_count} 条")
        print(f"  入库总计: {total} 条")
        print(f"{'='*50}")

        # 统计
        from sqlalchemy import func
        real_total = session.query(Job).filter(Job.status == "有效").count()
        real_cities = session.query(Job.city).filter(Job.status == "有效").distinct().count()
        print(f"\n  数据库状态: {real_total} 条有效岗位, {real_cities} 个城市")

    finally:
        driver.quit()
        session.close()
