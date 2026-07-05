"""
51job API 批量采集 - 100% 真实数据
=================================
通过浏览器内 fetch() 调用内部搜索 API，绕过 WAF。
每个关键词×城市组合独立查询，收集全国多城市数据。
"""

import sys, os, time, json, uuid, re
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from app.config import TestingConfig
class FC(TestingConfig):
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return f"sqlite:///{os.path.join(os.path.dirname(__file__), '..', 'rdas.db')}"

from app import database as db
from app.models.job import Job

# 51job 城市代码（6位：省2+市2+区2）
CITIES = {
    "010000":"北京","020000":"上海","030200":"广州","040000":"深圳",
    "080200":"成都","070000":"杭州","180000":"武汉","060000":"南京",
    "110000":"西安","230000":"重庆","090000":"长沙","120000":"天津",
    "160000":"合肥","220000":"苏州","130000":"郑州","140000":"济南",
    "050000":"青岛","170000":"大连","250000":"福州","100000":"昆明",
}

KEYWORDS = [
    "Python开发","Java开发","前端开发","数据分析",
    "产品经理","UI设计","测试工程师","算法工程师",
    "运维","运营","C++开发","Go开发",
]

EXP_MAP = {
    "在校生/应届生":"应届生","应届生":"应届生","无需经验":"应届生",
    "1年":"1-3年","1年及以上":"1-3年","2年":"1-3年","2年及以上":"1-3年",
    "3年及以上":"3-5年","3-4年":"3-5年","5年及以上":"5-10年",
    "5-7年":"5-10年","8-9年":"5-10年","10年以上":"10年以上",
}

def parse_salary(s):
    if not s or "面议" in s: return None, None, "面议"
    # 1.5-2万/月
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*月", s)
    if m: return int(float(m.group(1))*10000), int(float(m.group(2))*10000), "月薪"
    # 15-25万/年
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*年", s)
    if m: return int(float(m.group(1))*10000/12), int(float(m.group(2))*10000/12), "月薪"
    # 15K-25K
    m = re.match(r"([\d.]+)\s*[kK]\s*[-~至]\s*([\d.]+)\s*[kK]", s)
    if m: return int(float(m.group(1))*1000), int(float(m.group(2))*1000), "月薪"
    # 8000-15000元/月 / 8千-1.5万
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*(元|千|万)?\s*/\s*月", s)
    if m:
        low = float(m.group(1)); high = float(m.group(2))
        unit = m.group(3) or ""
        if unit == "千": low*=1000; high*=1000
        elif unit == "万": low*=10000; high*=10000
        return int(low), int(high), "月薪"
    return None, None, "未识别"

def fetch_jobs(driver, keyword, area_code, page=1):
    """在浏览器内 fetch API 获取岗位"""
    script = f'''
    return fetch("/api/job/search-pc?api_key=51job&keyword={keyword}&searchType=2&jobArea={area_code}&pageNum={page}&pageSize=20", {{
      headers: {{"From-Domain":"51job_web","Accept":"application/json"}}
    }}).then(r => r.text())
    '''
    result = driver.execute_script(script)
    try:
        data = json.loads(result)
        return data.get("resultbody", {}).get("job", {}).get("items", [])
    except:
        return []

def save_jobs(items, session):
    saved = 0
    for item in items:
        try:
            pid = str(item.get("jobId", ""))
            if not pid: continue
            if session.query(Job).filter(Job.platform_job_id == pid).first():
                continue

            title = item.get("jobName", "")
            company = item.get("fullCompanyName", "") or item.get("companyName", "") or "未知"
            city = item.get("workAreaName", "") or item.get("cityName", "") or item.get("areaName", "")
            if not city:
                # 从 jobTags/provideSalaryString 或其他字段推断
                href = item.get("jobHref", "") or ""
                for cname in CITIES.values():
                    if cname in href or cname in title:
                        city = cname; break
            if not city: city = "未知"

            salary_str = item.get("provideSalaryString", "")
            sal_min, sal_max, sal_type = parse_salary(salary_str)

            exp_str = item.get("workYear", "") or ""
            exp = "不限"
            for k, v in EXP_MAP.items():
                if k in exp_str: exp = v; break

            edu = item.get("degree", "") or "不限"

            # 公司规模/类型
            company_size = item.get("companySize", "") or ""
            company_type = item.get("companyType", "") or ""

            # 福利/标签
            tags = item.get("jobTags", "") or ""
            welfare = item.get("jobWelfare", "") or ""

            # 发布时间
            pub_time = item.get("issuedTime", "") or ""
            try: pub_dt = datetime.strptime(pub_time[:10], "%Y-%m-%d").date()
            except: pub_dt = datetime.now().date()

            job = Job(
                job_id=uuid.uuid4().hex, title=title, title_raw=title,
                company=company, salary_min=sal_min, salary_max=sal_max, salary_type=sal_type,
                city=city, experience=exp, education=edu,
                skills=tags, welfare=welfare,
                company_size=company_size, company_type=company_type,
                platform="前程无忧", platform_job_id=pid,
                source_url=item.get("jobHref", ""),
                published_at=pub_dt, crawled_at=datetime.now(), status="有效",
            )
            session.add(job); saved += 1
        except: continue
    session.commit()
    return saved

if __name__ == "__main__":
    print("=" * 50)
    print("  51job API 批量采集（真实数据）")
    print("=" * 50)

    config = FC(); db.init_db(config); db.create_tables()
    session = db.SessionLocal()

    # 不清空旧数据，增量添加

    opts = Options()
    opts.add_argument("--window-size=1920,1080")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Chrome(options=opts)

    # 先打开搜索页过 WAF
    driver.get("https://we.51job.com/pc/search?keyword=Python开发&searchType=2")
    time.sleep(5)

    total = 0
    for area_code, city_name in CITIES.items():
        for kw in KEYWORDS:
            try:
                items = fetch_jobs(driver, kw, area_code, page=1)
                if items:
                    n = save_jobs(items, session)
                    total += n
                    print(f"  {city_name} | {kw}: {n}条 (API返回{len(items)}条)")
                time.sleep(1)
            except Exception as e:
                print(f"  {city_name} | {kw}: ERR {e}")
                time.sleep(2)

    driver.quit()

    # 统计
    from sqlalchemy import func
    t = session.query(Job).filter(Job.status=="有效").count()
    c = session.query(Job.city).filter(Job.status=="有效").distinct().count()
    print(f"\n{'='*50}")
    print(f"  入库: {total} 条新数据")
    print(f"  数据库总计: {t} 条, {c} 个城市")
    cities = session.query(Job.city, func.count(Job.job_id)).filter(Job.status=="有效").group_by(Job.city).order_by(func.count(Job.job_id).desc()).limit(20).all()
    for city, cnt in cities:
        print(f"    {city}: {cnt}")
    session.close()
