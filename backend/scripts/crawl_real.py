"""51job 真实数据采集 - 修复版"""
import sys,os,time,json,uuid,re
from datetime import datetime
sys.path.insert(0,os.path.join(os.path.dirname(__file__),".."))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from app.config import TestingConfig
class FC(TestingConfig):
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return f"sqlite:///{os.path.join(os.path.dirname(__file__),'..','rdas.db')}"
from app import database as db
from app.models.job import Job

AREAS = {
    "010000":"北京","020000":"上海","030200":"广州","040000":"深圳",
    "080200":"成都","070000":"杭州","180000":"武汉","060000":"南京",
    "110000":"西安","230000":"重庆","090000":"长沙","120000":"天津",
    "160000":"合肥","220000":"苏州","050000":"青岛",
}
KWS = ["Python开发","Java开发","前端开发","数据分析","产品经理","测试工程师","算法工程师","运营","UI设计"]

def go(driver):
    """启动/恢复浏览器窗口"""
    try:
        if driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])
            return True
    except: pass
    try:
        driver.get("https://we.51job.com/pc/search?keyword=Python开发&searchType=2")
        time.sleep(5)
        return True
    except: return False

def fetch(driver, kw, area, page=1):
    if not go(driver): return []
    try:
        result = driver.execute_script(f'''
          return fetch("/api/job/search-pc?api_key=51job&keyword={kw}&searchType=2&jobArea={area}&pageNum={page}&pageSize=20",{{
            headers:{{"From-Domain":"51job_web","Accept":"application/json"}}
          }}).then(r=>r.text())
        ''')
        data = json.loads(result)
        return data.get("resultbody",{}).get("job",{}).get("items",[])
    except: return []

def parse_salary(s):
    if not s or "面议" in s: return None,None,"面议"
    m=re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*月",s)
    if m: return int(float(m.group(1))*10000),int(float(m.group(2))*10000),"月薪"
    m=re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*年",s)
    if m: return int(float(m.group(1))*10000/12),int(float(m.group(2))*10000/12),"月薪"
    m=re.match(r"([\d.]+)\s*[kK]\s*[-~至]\s*([\d.]+)\s*[kK]",s)
    if m: return int(float(m.group(1))*1000),int(float(m.group(2))*1000),"月薪"
    m=re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*(元|千|万)",s)
    if m:
        l,h=float(m.group(1)),float(m.group(2));u=m.group(3)
        if u=="千": l*=1000;h*=1000
        elif u=="万": l*=10000;h*=10000
        return int(l),int(h),"月薪"
    return None,None,"未识别"

EM={"在校生/应届生":"应届生","应届生":"应届生","无需经验":"应届生",
    "1年":"1-3年","1年及以上":"1-3年","2年":"1-3年","2年及以上":"1-3年",
    "3年及以上":"3-5年","3-4年":"3-5年","5年及以上":"5-10年",
    "5-7年":"5-10年","8-9年":"5-10年","10年以上":"10年以上"}

def save(items, session):
    n=0
    for item in items:
        try:
            pid=str(item.get("jobId",""))
            if not pid or session.query(Job).filter(Job.platform_job_id==pid).first(): continue
            title=item.get("jobName","")
            co=item.get("fullCompanyName","") or item.get("companyName","") or "未知"
            city=item.get("workAreaName","") or item.get("cityName","") or ""
            exp_str=item.get("workYear","") or ""
            exp="不限"
            for k,v in EM.items():
                if k in exp_str: exp=v;break
            edu=item.get("degree","") or "不限"
            sal_min,sal_max,sal_type=parse_salary(item.get("provideSalaryString",""))
            tags=(item.get("jobTags","") or "")[:500]
            welfare=(item.get("jobWelfare","") or "")[:500]
            csize=item.get("companySize","") or ""
            ctype=item.get("companyType","") or ""
            pub=item.get("issueDateString","") or item.get("updateDateTime","") or ""
            try: pub_dt=datetime.strptime(pub[:10],"%Y-%m-%d").date()
            except: pub_dt=datetime.now().date()
            session.add(Job(
                job_id=uuid.uuid4().hex,title=title,title_raw=title,company=co,
                salary_min=sal_min,salary_max=sal_max,salary_type=sal_type,
                city=city or "未知",experience=exp,education=edu,
                skills=tags,welfare=welfare,company_size=csize,company_type=ctype,
                platform="前程无忧",platform_job_id=pid,
                source_url=item.get("jobHref",""),published_at=pub_dt,
                crawled_at=datetime.now(),status="有效"))
            n+=1
        except: pass
    session.commit()
    return n

if __name__=="__main__":
    total_cities = len(AREAS); total_kw = len(KWS)
    total_combos = total_cities * total_kw
    print(f"51job 真实数据采集 | {total_cities}城市 × {total_kw}关键词 = {total_combos}次搜索")
    print("="*50)

    config=FC();db.init_db(config);db.create_tables()
    session=db.SessionLocal()

    opts=Options()
    opts.add_argument("--window-size=1920,1080")
    opts.add_experimental_option("excludeSwitches",["enable-automation"])
    driver=webdriver.Chrome(options=opts)

    go(driver)
    saved=0; completed=0
    for area_code, city_name in AREAS.items():
        for kw in KWS:
            completed+=1
            pct=completed*100//total_combos
            bar="█"*(pct//4)+"░"*(25-pct//4)
            try:
                items=fetch(driver,kw,area_code)
                n=save(items,session)
                saved+=n
                print(f"\r[{bar}] {pct:3d}% {city_name}|{kw}: {n}条 (当前{saved}条)",end="",flush=True)
            except Exception as e:
                print(f"\r[{bar}] {pct:3d}% {city_name}|{kw}: ERR 重试中...",end="",flush=True)
                go(driver)
            time.sleep(1.5)

    print(f"\n{'='*50}")
    print(f"入库:{saved}条新数据")

    from sqlalchemy import func
    t=session.query(Job).filter(Job.status=="有效").count()
    c=session.query(Job.city).filter(Job.status=="有效").distinct().count()
    print(f"总计:{t}条 城市:{c}个")
    cities=session.query(Job.city,func.count(Job.job_id)).filter(Job.status=="有效").group_by(Job.city).order_by(func.count(Job.job_id).desc()).all()
    for cn,cc in cities: print(f"  {cn}:{cc}")
    session.close()
    driver.quit()
