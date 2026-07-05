"""
全自动真实数据采集
==================
遍历关键词×城市组合，从 51job 直接提取 sensorsdata 数据。
纯真实数据，不混种子数据。
"""

import sys, os, json, time, random, uuid, hashlib, re
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from app.config import TestingConfig

class SQLiteFileConfig(TestingConfig):
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return f"sqlite:///{os.path.join(os.path.dirname(__file__), '..', 'rdas.db')}"

from app import database as db
from app.models.job import Job

# 51job 城市代码 → 城市名
CITIES_PINYIN = [
    ("beijing","北京"),("shanghai","上海"),("guangzhou","广州"),("shenzhen","深圳"),
    ("chengdu","成都"),("hangzhou","杭州"),("wuhan","武汉"),("nanjing","南京"),
    ("xian","西安"),("chongqing","重庆"),("changsha","长沙"),("tianjin","天津"),
    ("hefei","合肥"),("suzhou","苏州"),("zhengzhou","郑州"),("jinan","济南"),
    ("qingdao","青岛"),("dalian","大连"),("fuzhou","福州"),("kunming","昆明"),
]

KEYWORDS = [
    "Python开发","Java开发","前端开发","数据分析",
    "产品经理","UI设计","测试工程师","算法工程师","运维",
]

EXP_MAP = {
    "在校生/应届生":"应届生","应届生":"应届生","无需经验":"应届生",
    "1年":"1-3年","1年及以上":"1-3年","1-3年":"1-3年",
    "2年":"1-3年","2年及以上":"1-3年",
    "3年及以上":"3-5年","3-4年":"3-5年","3-5年":"3-5年",
    "5年及以上":"5-10年","5-7年":"5-10年","5-10年":"5-10年",
    "8-9年":"5-10年","10年以上":"10年以上",
}

EDU_MAP = {"大专":"大专","本科":"本科","硕士":"硕士","博士":"博士","高中":"不限","中技/中专":"不限","学历不限":"不限"}

def parse_salary(s):
    if not s or "面议" in s: return None, None, "面议"
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*年", s)
    if m: return int(float(m.group(1))*10000/12), int(float(m.group(2))*10000/12), "月薪"
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*月", s)
    if m: return int(float(m.group(1))*10000), int(float(m.group(2))*10000), "月薪"
    m = re.match(r"([\d.]+)\s*[kK]\s*[-~至]\s*([\d.]+)\s*[kK]", s)
    if m: return int(float(m.group(1))*1000), int(float(m.group(2))*1000), "月薪"
    return None, None, "未识别"

def create_driver():
    opts = Options()
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    d = webdriver.Chrome(options=opts)
    d.execute_script("Object.defineProperty(navigator, 'webdriver', {get: ()=>undefined})")
    return d

def extract_jobs(driver):
    """从当前页面提取所有岗位"""
    jobs = []
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[sensorsdata]"))
        )
        time.sleep(2)
    except:
        pass

    cards = driver.find_elements(By.CSS_SELECTOR, ".card.sensors_exposure, [sensorsdata]")
    seen = set()

    for card in cards:
        try:
            s = card.get_attribute("sensorsdata")
            if not s: continue
            d = json.loads(s)
            pid = str(d.get("jobId",""))
            if pid in seen: continue
            seen.add(pid)

            # 公司名
            co = ""
            try:
                for sel in [".bottom .left span", "a[href*='all/co'] span", ".cname"]:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    if el.text.strip():
                        co = el.text.strip(); break
            except: pass

            # 标签（当 skills 用）
            tags = []
            try:
                tag_els = card.find_elements(By.CSS_SELECTOR, ".middle .tag")
                for t in tag_els:
                    txt = t.text.strip()
                    if txt and not any(x in txt for x in ["年","本科","硕士","博士","大专","高中","中专","不限"]):
                        tags.append(txt)
            except: pass

            sal_min, sal_max, sal_type = parse_salary(d.get("jobSalary",""))
            exp = EXP_MAP.get(d.get("jobYear",""), "不限")
            edu = EDU_MAP.get(d.get("jobDegree",""), "不限")
            city = (d.get("jobArea","") or "").split("·")[0].strip()

            jobs.append({
                "title": d.get("jobTitle",""),
                "company": co or "未知公司",
                "salary_raw": d.get("jobSalary",""),
                "salary_min": sal_min, "salary_max": sal_max, "salary_type": sal_type,
                "city": city, "experience": exp, "education": edu,
                "skills": ",".join(tags[:8]),
                "platform": "前程无忧",
                "platform_job_id": pid,
                "source_url": f"https://jobs.51job.com/all/{pid}.html",
                "published_at": (d.get("jobTime","") or "")[:10],
            })
        except: continue
    return jobs

def save_jobs(jobs):
    session = db.SessionLocal()
    saved = 0
    try:
        for j in jobs:
            pid = j.get("platform_job_id","")
            if not pid: continue
            if session.query(Job).filter(Job.platform_job_id == pid).first():
                continue

            pub = j.get("published_at","")
            try: pub = datetime.strptime(pub[:10], "%Y-%m-%d").date() if pub else datetime.now().date()
            except: pub = datetime.now().date()

            job = Job(
                job_id=uuid.uuid4().hex, title=j.get("title",""), title_raw=j.get("title",""),
                company=j.get("company",""), salary_min=j.get("salary_min"), salary_max=j.get("salary_max"),
                salary_type=j.get("salary_type","月薪"), city=j.get("city",""), experience=j.get("experience","不限"),
                education=j.get("education","不限"), skills=j.get("skills",""), platform=j.get("platform",""),
                platform_job_id=pid, source_url=j.get("source_url",""), published_at=pub,
                crawled_at=datetime.now(), status="有效",
            )
            session.add(job); saved += 1
        session.commit()
    except Exception as e:
        session.rollback(); print(f"  DB Error: {e}")
    finally: session.close()
    return saved

if __name__ == "__main__":
    print("=" * 50)
    print("  51job 全自动真实数据采集")
    print("=" * 50)

    config = SQLiteFileConfig()
    db.init_db(config); db.create_tables()

    # 清空所有旧数据（种子+之前的）
    s = db.SessionLocal()
    from app.models.job import Job
    old = s.query(Job).delete(); s.commit(); s.close()
    print(f"  清空 {old} 条旧数据\n")

    driver = create_driver()
    total_saved = 0

    try:
        for pinyin, city_name in CITIES_PINYIN:
            # 先进入城市专属搜索页（设置城市 cookie）
            city_search_url = f"https://www.51job.com/{pinyin}/"
            try:
                driver.get(city_search_url); time.sleep(3)
            except: pass

            for kw in KEYWORDS[:4]:
                # 用城市页面的搜索 API
                url = f"https://search.51job.com/list/{pinyin},000000,0000,00,9,99,{kw},2,1.html"
                print(f"  {city_name} | {kw} ...", end=" ", flush=True)
                try:
                    driver.get(url)
                    time.sleep(random.uniform(4, 6))
                    jobs = extract_jobs(driver)
                    n = save_jobs(jobs)
                    total_saved += n
                    print(f"{n}条")
                except Exception as e:
                    print(f"ERR: {e}")
                time.sleep(random.uniform(2, 3))

    finally:
        driver.quit()

    # 统计
    s2 = db.SessionLocal()
    from sqlalchemy import func
    t = s2.query(Job).filter(Job.status=="有效").count()
    c = s2.query(Job.city).filter(Job.status=="有效").distinct().count()
    print(f"\n{'='*50}")
    print(f"  总计: {t} 条真实数据, {c} 个城市")
    # 按城市分布
    cities = s2.query(Job.city, func.count(Job.job_id)).filter(Job.status=="有效").group_by(Job.city).order_by(func.count(Job.job_id).desc()).all()
    for city, cnt in cities:
        print(f"    {city}: {cnt}")
    s2.close()
