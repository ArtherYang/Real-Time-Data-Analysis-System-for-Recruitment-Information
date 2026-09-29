"""
51job Playwright DOM 采集 — 第3次尝试
=====================================
使用 Playwright Chromium 有头模式 + 反检测注入 + DOM 提取 sensorsdata。
Selenium 两次都 0 条 (fetch API被WAF拦截、DOM选择器失效)。
"""
import sys, os, time, json, uuid, re, random
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from app.config import TestingConfig
class FC(TestingConfig):
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return f"sqlite:///{os.path.join(BASE, 'rdas.db')}"

from app import database as db_module
from app.models.job import Job
from sqlalchemy import func
from playwright.sync_api import sync_playwright

KEYWORDS = [
    "Python开发", "Java开发", "前端开发", "数据分析",
    "产品经理", "测试工程师", "算法工程师", "运维工程师",
    "UI设计", "运营", "Go开发", "架构师"
]
MAX_RETRIES = 3

def parse_salary(s):
    if not s or "面议" in s: return None, None, "面议"
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*月", s)
    if m: return int(float(m.group(1))*10000), int(float(m.group(2))*10000), "月薪"
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*年", s)
    if m: return int(float(m.group(1))*10000/12), int(float(m.group(2))*10000/12), "月薪"
    m = re.match(r"([\d.]+)\s*[kK]\s*[-~至]\s*([\d.]+)\s*[kK]", s)
    if m: return int(float(m.group(1))*1000), int(float(m.group(2))*1000), "月薪"
    m = re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*千\s*/\s*月", s)
    if m: return int(float(m.group(1))*1000), int(float(m.group(2))*1000), "月薪"
    return None, None, "未识别"

EM = {
    "在校生/应届生":"应届生","应届生":"应届生","无需经验":"应届生",
    "1年":"1-3年","1年及以上":"1-3年","1-3年":"1-3年",
    "2年":"1-3年","2年及以上":"1-3年","2-3年":"1-3年",
    "3年":"3-5年","3年及以上":"3-5年","3-4年":"3-5年","3-5年":"3-5年",
    "4年":"3-5年","5年":"5-10年","5年及以上":"5-10年",
    "5-7年":"5-10年","5-10年":"5-10年","8-9年":"5-10年",
    "10年以上":"10年以上",
}

print("=" * 55)
print("  51job Playwright DOM 采集 (第3次尝试)")
print(f"  {len(KEYWORDS)} 关键词 | WAF重试{MAX_RETRIES}次")
print("=" * 55)

config = FC()
db_module.init_db(config)
db_module.create_tables()
session = db_module.SessionLocal()

before_all = session.query(Job).filter(Job.status == "有效").count()
before_51 = session.query(Job).filter(Job.status == "有效", Job.platform == "前程无忧").count()
print(f"\n爬取前: 总计{before_all}条 | 前程无忧{before_51}条\n")

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en']});
        """)

        total_saved = 0
        retry_count = 0

        for idx, kw in enumerate(KEYWORDS):
            pct = (idx + 1) * 100 // len(KEYWORDS)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)

            saved_n = 0
            card_n = 0

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    url = f"https://we.51job.com/pc/search?keyword={kw}&searchType=2"
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(6)

                    # 检测拦截
                    title = page.title()
                    if any(w in title for w in ["验证", "安全", "拦截", "block", "captcha", "403", "502"]):
                        print(f"\r[{bar}] {pct:3d}% {kw}: ⚠ 拦截页(第{attempt}次重试){' '*20}",
                              flush=True)
                        retry_count += 1
                        time.sleep(random.uniform(5, 10))
                        continue

                    # 滚动
                    for _ in range(3):
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)

                    # 提取
                    cards = page.query_selector_all("[sensorsdata]")
                    card_n = len(cards)

                    for card in cards:
                        try:
                            s = card.get_attribute("sensorsdata")
                            if not s: continue
                            data = json.loads(s)
                            pid = str(data.get("jobId", ""))
                            if not pid: continue
                            if session.query(Job).filter(Job.platform_job_id == pid).first():
                                continue

                            co = ""
                            try:
                                el = card.query_selector(".bottom .left span, a[href*='coU'] span, [class*='cname']")
                                if el: co = el.inner_text().strip()
                            except: pass

                            tags = []
                            try:
                                for t in card.query_selector_all(".middle .tag, .tag"):
                                    txt = t.inner_text().strip()
                                    if txt and len(txt) < 20 and txt not in [
                                        "本科","硕士","博士","大专","高中","中专","不限",
                                        "应届生","1-3年","3-5年","5-10年","10年以上",
                                        "经验不限","学历不限"
                                    ]:
                                        tags.append(txt)
                            except: pass

                            title_v = data.get("jobTitle", "")
                            city_v = (data.get("jobArea", "") or "").split("·")[0].strip()
                            exp_v = EM.get(data.get("jobYear", ""), "不限")
                            edu_v = data.get("jobDegree", "") or "不限"
                            s_min, s_max, s_type = parse_salary(data.get("jobSalary", ""))

                            pub = (data.get("jobTime", "") or "")[:10]
                            try:
                                pub_dt = datetime.strptime(pub, "%Y-%m-%d").date() if pub else datetime.now().date()
                            except:
                                pub_dt = datetime.now().date()

                            session.add(Job(
                                job_id=uuid.uuid4().hex, title=title_v, title_raw=title_v,
                                company=co or "未知",
                                salary_min=s_min, salary_max=s_max, salary_type=s_type,
                                city=city_v or "未知", experience=exp_v, education=edu_v,
                                skills=",".join(tags[:8]), platform="前程无忧",
                                platform_job_id=pid,
                                source_url=f"https://jobs.51job.com/all/{pid}.html",
                                published_at=pub_dt, crawled_at=datetime.now(), status="有效"
                            ))
                            saved_n += 1
                        except:
                            continue

                    session.commit()
                    total_saved += saved_n
                    break  # 成功，跳出重试循环

                except Exception as e:
                    err_msg = str(e)[:50]
                    if attempt < MAX_RETRIES:
                        print(f"\r[{bar}] {pct:3d}% {kw}: ✗ {err_msg} (第{attempt}次重试){' '*20}",
                              flush=True)
                        retry_count += 1
                        time.sleep(random.uniform(5, 10))
                    else:
                        print(f"\r[{bar}] {pct:3d}% {kw}: ✗ 3次全失败 ({err_msg}){' '*20}",
                              flush=True)

            waf_note = " (WAF绕过)" if retry_count > 0 and saved_n > 0 else ""
            status = "✓" if saved_n > 0 else "✗ 0条"
            print(f"\r[{bar}] {pct:3d}% {kw}: {card_n}卡片→{saved_n}条 {status}{waf_note}{' '*20}",
                  flush=True)

            time.sleep(random.uniform(3, 6))

        browser.close()

except Exception as e:
    print(f"\n!!! 严重错误: {e}")

# === 最终统计 ===
print(f"\n{'='*55}")
print(f"  重试次数: {retry_count}")
print(f"  本次入库: {total_saved}条")

after_all = session.query(Job).filter(Job.status == "有效").count()
after_51 = session.query(Job).filter(Job.status == "有效", Job.platform == "前程无忧").count()
new_all = after_all - before_all
new_51 = after_51 - before_51
print(f"\n  数据库变化:")
print(f"    总有效岗位: {before_all} → {after_all} (+{new_all})")
print(f"    前程无忧:   {before_51} → {after_51} (+{new_51})")

if after_all > 0:
    cities = session.query(Job.city, func.count(Job.job_id)).filter(
        Job.status == "有效"
    ).group_by(Job.city).order_by(func.count(Job.job_id).desc()).limit(10).all()
    print(f"\n  Top 10 城市:")
    for cn, cc in cities:
        print(f"    {cn}: {cc}条")

session.close()
