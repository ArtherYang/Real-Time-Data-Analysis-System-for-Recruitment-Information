"""51job DOM 提取 - 已验证可用"""
import sys,os,time,json,uuid,re
from datetime import datetime
sys.path.insert(0,os.path.join(os.path.dirname(__file__),".."))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.config import TestingConfig
class FC(TestingConfig):
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return f"sqlite:///{os.path.join(os.path.dirname(__file__),'..','rdas.db')}"
from app import database as db
from app.models.job import Job

KWS = ["Python开发","Java开发","前端开发","数据分析","产品经理","测试工程师","算法工程师","运维","UI设计","运营","Go开发","架构师"]

def parse_salary(s):
    if not s or "面议" in s: return None,None,"面议"
    m=re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*月",s)
    if m: return int(float(m.group(1))*10000),int(float(m.group(2))*10000),"月薪"
    m=re.match(r"([\d.]+)\s*[-~至]\s*([\d.]+)\s*万\s*/\s*年",s)
    if m: return int(float(m.group(1))*10000/12),int(float(m.group(2))*10000/12),"月薪"
    m=re.match(r"([\d.]+)\s*[kK]\s*[-~至]\s*([\d.]+)\s*[kK]",s)
    if m: return int(float(m.group(1))*1000),int(float(m.group(2))*1000),"月薪"
    return None,None,"未识别"

EM={"在校生/应届生":"应届生","应届生":"应届生","无需经验":"应届生",
    "1年及以上":"1-3年","2年及以上":"1-3年","3年及以上":"3-5年",
    "5年及以上":"5-10年","10年以上":"10年以上"}
for y in ["1年","1-3年","2年","2-3年"]: EM[y]="1-3年"
for y in ["3年","3-5年","4年","3-4年"]: EM[y]="3-5年"
for y in ["5年","5-7年","5-10年","8-9年"]: EM[y]="5-10年"

if __name__=="__main__":
    print("51job DOM 真实数据采集")
    print("="*50)

    config=FC();db.init_db(config);db.create_tables()
    session=db.SessionLocal()

    opts=Options()
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches",["enable-automation"])
    d=webdriver.Chrome(options=opts)
    d.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

    total_saved=0
    for idx,kw in enumerate(KWS):
        pct=(idx+1)*100//len(KWS)
        bar="█"*(pct//5)+"░"*(20-pct//5)

        try:
            d.get(f"https://we.51job.com/pc/search?keyword={kw}&searchType=2")
            time.sleep(6)

            # 滚动加载更多
            for _ in range(2):
                d.execute_script("window.scrollTo(0,document.body.scrollHeight)")
                time.sleep(2)

            cards=d.find_elements(By.CSS_SELECTOR,".card.sensors_exposure")
            saved=0
            for c in cards:
                try:
                    s=c.get_attribute("sensorsdata")
                    if not s: continue
                    data=json.loads(s)
                    pid=str(data.get("jobId",""))
                    if session.query(Job).filter(Job.platform_job_id==pid).first(): continue

                    co=""
                    try: co=c.find_element(By.CSS_SELECTOR,".bottom .left span").text.strip()
                    except: pass

                    title=data.get("jobTitle","")
                    city=(data.get("jobArea","") or "").split("·")[0].strip()
                    exp=EM.get(data.get("jobYear",""),"不限")
                    edu=data.get("jobDegree","") or "不限"
                    sal_min,sal_max,sal_type=parse_salary(data.get("jobSalary",""))

                    tags=[]
                    try:
                        for t in c.find_elements(By.CSS_SELECTOR,".middle .tag"):
                            txt=t.text.strip()
                            if txt and txt not in ["本科","硕士","博士","大专","高中","中专","不限","应届生","1-3年","3-5年","5-10年","10年以上"]:
                                tags.append(txt)
                    except: pass

                    pub=data.get("jobTime","")[:10]
                    try: pub_dt=datetime.strptime(pub,"%Y-%m-%d").date() if pub else datetime.now().date()
                    except: pub_dt=datetime.now().date()

                    session.add(Job(
                        job_id=uuid.uuid4().hex,title=title,title_raw=title,company=co or "未知",
                        salary_min=sal_min,salary_max=sal_max,salary_type=sal_type,
                        city=city or "未知",experience=exp,education=edu,
                        skills=",".join(tags[:8]),platform="前程无忧",platform_job_id=pid,
                        source_url=f"https://jobs.51job.com/all/{pid}.html",
                        published_at=pub_dt,crawled_at=datetime.now(),status="有效"))
                    saved+=1; total_saved+=1
                except: pass
            session.commit()
            print(f"\r[{bar}] {pct:3d}% {kw}: {len(cards)}卡片→{saved}条入库 (累计{total_saved}条)",flush=True)
        except Exception as e:
            print(f"\r[{bar}] {pct:3d}% {kw}: ERR ({e})",flush=True)
        time.sleep(3)

    d.quit()
    from sqlalchemy import func
    t=session.query(Job).filter(Job.status=="有效").count()
    c=session.query(Job.city).filter(Job.status=="有效").distinct().count()
    print(f"\n{'='*50}")
    print(f"总计:{t}条 {c}城市")
    cities=session.query(Job.city,func.count(Job.job_id)).filter(Job.status=="有效").group_by(Job.city).order_by(func.count(Job.job_id).desc()).all()
    for cn,cc in cities: print(f"  {cn}:{cc}")
    session.close()
