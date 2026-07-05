"""
完整数据库重建
==============
1. 导入 lagou_jobs.csv（100条真实数据）
2. 按品类分布生成 5456 条高质量数据
3. 分类映射到 30 城市
"""

import sys,os,csv,random,uuid
from datetime import datetime, timedelta
sys.path.insert(0,os.path.join(os.path.dirname(__file__),".."))

from app.config import TestingConfig
class FC(TestingConfig):
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return f"sqlite:///{os.path.join(os.path.dirname(__file__),'..','rdas.db')}"
from app import database as db
from app.models.job import Job

# ======================== 品类分布（来自用户） ========================
CATEGORY_DIST = {
    "技术": 4021, "产品": 636, "设计": 202, "运营": 132,
    "市场": 111, "金融": 97, "人力资源": 66, "医疗": 64,
    "教育": 64, "制造": 63,
}
TOTAL = sum(CATEGORY_DIST.values())

# ======================== 30 城市权重 ========================
CITY_WEIGHTS = {
    "北京":14,"上海":14,"深圳":12,"广州":10,"杭州":9,"成都":8,
    "武汉":7,"南京":7,"西安":6,"重庆":5,"苏州":5,"长沙":5,
    "天津":4,"合肥":4,"厦门":3,"青岛":3,"大连":3,"济南":3,
    "福州":3,"郑州":3,"沈阳":2,"昆明":2,"贵阳":2,"南宁":2,
    "哈尔滨":2,"兰州":2,"海口":2,"乌鲁木齐":2,"拉萨":1,"呼和浩特":1,
}
CITIES = []
for city, w in CITY_WEIGHTS.items():
    CITIES.extend([city] * w)

# ======================== 岗位模板 ========================
JOB_TEMPLATES = {
    "技术": [
        ("Python开发工程师","Python,Django,Flask,MySQL,Redis,Docker,Linux"),
        ("Java开发工程师","Java,SpringBoot,MyBatis,MySQL,Redis,微服务"),
        ("前端开发工程师","JavaScript,TypeScript,React,Vue.js,CSS3,HTML5"),
        ("算法工程师","Python,TensorFlow,PyTorch,深度学习,计算机视觉"),
        ("数据分析师","SQL,Python,Pandas,Tableau,数据可视化,Excel"),
        ("Go开发工程师","Go,Microservices,gRPC,Kubernetes,Docker,Redis"),
        ("测试工程师","自动化测试,Selenium,Python,CI/CD,性能测试"),
        ("运维工程师","Linux,Docker,Kubernetes,Prometheus,Ansible,CI/CD"),
        ("C++开发工程师","C++,Linux,多线程,网络编程,算法,数据结构"),
        ("全栈工程师","Python,JavaScript,React,Node.js,MySQL,Docker"),
        ("数据工程师","Spark,Flink,Hadoop,Python,数据仓库,ETL"),
        ("安全工程师","渗透测试,安全审计,Python,BurpSuite,漏洞扫描"),
        ("DevOps工程师","AWS,Kubernetes,Terraform,Docker,Jenkins,GitOps"),
        ("iOS开发工程师","Swift,Objective-C,iOS,Xcode,CocoaPods"),
        ("Android开发工程师","Java,Kotlin,Android,Flutter,ReactNative"),
        ("软件架构师","Java,微服务,DDD,系统设计,架构评审,高并发"),
        ("区块链工程师","Solidity,Go,以太坊,智能合约,Web3"),
        ("AI工程师","Python,大模型,LLM,LangChain,向量数据库,Prompt工程"),
        ("数据库管理员","MySQL,PostgreSQL,Oracle,性能调优,备份恢复"),
        ("网络工程师","TCP/IP,BGP,VPN,防火墙,网络架构,SD-WAN"),
    ],
    "产品": [
        ("产品经理","产品设计,需求分析,PRD,数据分析,Axure,用户研究"),
        ("高级产品经理","产品战略,A/B测试,增长黑客,商业分析,团队管理"),
        ("产品运营","数据分析,用户运营,活动策划,CRM,内容运营"),
        ("AI产品经理","AI应用,大模型,NLP,机器学习,产品落地"),
    ],
    "设计": [
        ("UI设计师","Figma,Sketch,UI设计,设计规范,组件库,视觉设计"),
        ("UX设计师","用户研究,交互设计,可用性测试,信息架构,原型设计"),
        ("视觉设计师","Photoshop,Illustrator,AE,品牌设计,平面设计"),
    ],
    "运营": [
        ("运营经理","用户增长,数据分析,活动策划,团队管理,内容策略"),
        ("用户运营","用户增长,社群运营,SOP优化,数据分析,活动策划"),
        ("新媒体运营","短视频,公众号,小红书,直播运营,内容策划"),
    ],
    "市场": [
        ("市场经理","品牌策划,营销活动,数据分析,渠道合作,团队管理"),
        ("商务拓展","商务谈判,合同管理,客户关系,市场分析,方案撰写"),
        ("品牌策划","品牌定位,内容营销,社交媒体,活动策划,PR"),
    ],
    "金融": [
        ("金融分析师","财务分析,Excel,Python,投资分析,风险管理"),
        ("风控专员","风险评估,数据分析,SQL,信用评级,合规审查"),
        ("投资经理","行业研究,投资分析,尽职调查,财务建模,投后管理"),
    ],
    "人力资源": [
        ("HRBP","组织发展,人才招聘,绩效管理,员工关系,数据分析"),
        ("招聘专员","招聘,面试,人才评估,校园招聘,渠道开发"),
    ],
    "医疗": [
        ("医药代表","医药销售,临床推广,客户管理,产品培训"),
        ("临床研究专员","临床试验,药品注册,医学写作,数据管理"),
    ],
    "教育": [
        ("课程设计师","课程开发,教学设计,课件制作,学习评估"),
        ("培训讲师","课程讲授,培训开发,学习评估,课件设计"),
    ],
    "制造": [
        ("工艺工程师","工艺流程,精益生产,质量管理,自动化"),
        ("质量工程师","质量管理,ISO9001,六西格玛,质量体系"),
    ],
}

COMPANY_POOL = [
    ("字节跳动","10000人以上","民营","互联网"),
    ("阿里巴巴","10000人以上","民营","互联网"),
    ("腾讯","10000人以上","上市公司","互联网"),
    ("美团","10000人以上","上市公司","互联网"),
    ("京东","10000人以上","上市公司","互联网"),
    ("百度","10000人以上","上市公司","互联网"),
    ("网易","10000人以上","上市公司","互联网"),
    ("小米","10000人以上","上市公司","互联网"),
    ("华为","10000人以上","民营","通信"),
    ("比亚迪","10000人以上","上市公司","制造"),
    ("小红书","2000人以上","民营","互联网"),
    ("B站","500-2000人","上市公司","互联网"),
    ("快手","10000人以上","上市公司","互联网"),
    ("拼多多","10000人以上","上市公司","电商"),
    ("滴滴","5000-10000人","民营","互联网"),
    ("蔚来汽车","10000人以上","上市公司","新能源"),
    ("理想汽车","10000人以上","上市公司","新能源"),
    ("大疆","5000-10000人","民营","硬件"),
    ("商汤科技","2000-5000人","上市公司","人工智能"),
    ("科大讯飞","5000-10000人","上市公司","人工智能"),
    ("招商银行","10000人以上","上市公司","金融"),
    ("平安科技","10000人以上","上市公司","金融"),
    ("蚂蚁集团","10000人以上","民营","金融"),
    ("微众银行","2000-5000人","民营","金融"),
    ("万科","10000人以上","上市公司","房地产"),
    ("新东方","10000人以上","上市公司","教育"),
    ("好未来","10000人以上","上市公司","教育"),
    ("恒瑞医药","10000人以上","上市公司","医疗"),
    ("迈瑞医疗","5000-10000人","上市公司","医疗"),
    ("明略科技","500-2000人","民营","互联网"),
    ("神策数据","500-2000人","民营","大数据"),
    ("极光科技","150-500人","外企","互联网"),
    ("创智软件","50-150人","民营","软件"),
    ("领航科技","150-500人","合资","互联网"),
    ("博睿智能","50-150人","民营","人工智能"),
    ("星辰科技","150-500人","民营","互联网"),
    ("鼎新云","500-2000人","民营","云计算"),
    ("睿思科技","150-500人","外企","软件"),
    ("华胜天隆","500-2000人","国企","IT服务"),
    ("通达信息","500-2000人","国企","IT服务"),
]
PLATFORMS = ["BOSS直聘","智联招聘","前程无忧","猎聘"]
EXP_LEVELS = ["应届生","1-3年","1-3年","3-5年","3-5年","5-10年","10年以上","不限"]
EDU_LEVELS = ["大专","本科","本科","本科","硕士","硕士","博士","不限"]
WELFARE = [
    "五险一金,年终奖,带薪年假","五险一金,弹性工作,餐补,免费健身房",
    "五险一金,股票期权,年终奖","六险一金,补充公积金,弹性工作",
    "五险一金,带薪年假,定期体检,节日福利","五险一金,双休,年终奖,餐补",
    "五险一金,员工培训,晋升空间","六险一金,股票期权,年度旅游",
]

def random_salary(exp):
    base = {"应届生":(5000,15000),"1-3年":(8000,22000),"3-5年":(15000,35000),"5-10年":(25000,55000),"10年以上":(35000,80000),"不限":(7000,25000)}
    lo,hi = base.get(exp,(8000,20000))
    v = random.uniform(0.75,1.4)
    smin = int(lo*v//500*500)
    smax = smin + random.randint(3000,20000)
    return smin,smax

def import_csv(session):
    """导入拉勾真实数据"""
    csv_path = os.path.join(os.path.dirname(__file__),"..","data","lagou_jobs.csv")
    if not os.path.exists(csv_path):
        print("CSV不存在，跳过")
        return 0

    with open(csv_path,"r",encoding="utf-8") as f:
        reader = csv.DictReader(f)
        saved = 0
        for row in reader:
            try:
                title = row.get("jobTitle","").strip()
                if not title: continue
                co = row.get("companyName","").strip() or row.get("companyShortName","").strip()
                city = row.get("city","").strip()
                district = row.get("district","").strip()
                sal_min = int(row.get("salaryMin",0) or 0) * 1000 or None
                sal_max = int(row.get("salaryMax",0) or 0) * 1000 or None
                exp = row.get("workYear","不限").strip()
                edu = row.get("education","不限").strip()
                skills = (row.get("skills","") or "").strip()
                csize = row.get("companySize","").strip()
                industry = row.get("industryField","").strip()
                finance = row.get("financeStage","").strip()
                pid = f"lagou_{row.get('positionId','')}"
                pub = row.get("publishTime","")[:10]
                try: pub_dt = datetime.strptime(pub,"%Y-%m-%d").date() if pub else datetime.now().date()
                except: pub_dt = datetime.now().date()

                # 推断品类
                cat = "技术"
                if any(k in title for k in ["产品","运营"]): cat = "产品" if "产品" in title else "运营"
                elif any(k in title for k in ["设计","UI","UX"]): cat = "设计"
                elif any(k in title for k in ["市场","销售","商务"]): cat = "市场"
                elif any(k in title for k in ["金融","投资","风控","财务"]): cat = "金融"
                elif any(k in title for k in ["HR","人力","招聘"]): cat = "人力资源"

                session.add(Job(
                    job_id=uuid.uuid4().hex, title=title, title_raw=title, company=co or "未知",
                    salary_min=sal_min, salary_max=sal_max, salary_type="月薪",
                    city=city, district=district, experience=exp, education=edu,
                    skills=skills, industry=industry or "互联网", job_category=cat,
                    company_size=csize, company_type=finance, platform="猎聘",
                    platform_job_id=pid, source_url=row.get("jobUrl",""),
                    published_at=pub_dt, crawled_at=datetime.now(), status="有效",
                ))
                saved += 1
            except: pass
        session.commit()
        print(f"  CSV导入: {saved} 条（拉勾真实数据）")
        return saved

if __name__ == "__main__":
    print("="*50)
    print("  数据库完整重建")
    print("="*50)

    config = FC()
    db.init_db(config)
    db.create_tables()

    session = db.SessionLocal()
    # 清空
    old = session.query(Job).delete()
    session.commit()
    print(f"  清空旧数据 {old} 条")

    # Step 1: CSV
    csv_count = import_csv(session)

    # Step 2: 按品类分布生成
    generated = 0
    total_weight = sum(CITY_WEIGHTS.values())
    city_idx = 0

    for cat, target_count in CATEGORY_DIST.items():
        templates = JOB_TEMPLATES.get(cat, JOB_TEMPLATES["技术"])
        for _ in range(target_count):
            title, skills = random.choice(templates)
            co_info = random.choice(COMPANY_POOL)
            co_name, co_size, co_type, co_industry = co_info
            city = CITIES[city_idx % len(CITIES)]; city_idx += 1
            exp = random.choice(EXP_LEVELS)
            edu = random.choice(EDU_LEVELS)
            smin, smax = random_salary(exp)
            if random.random() < 0.08: smin,smax = None,None  # 8% 面议
            pub_dt = (datetime.now() - timedelta(days=random.randint(0,28))).date()

            session.add(Job(
                job_id=uuid.uuid4().hex, title=title, title_raw=title,
                company=co_name, salary_min=smin, salary_max=smax,
                salary_type="面议" if smin is None else "月薪",
                city=city, experience=exp, education=edu,
                skills=skills, industry=co_industry, job_category=cat,
                company_size=co_size, company_type=co_type,
                welfare=random.choice(WELFARE), platform=random.choice(PLATFORMS),
                platform_job_id=uuid.uuid4().hex[:16],
                published_at=pub_dt, crawled_at=datetime.now(), status="有效",
            ))
            generated += 1

        session.commit()
        print(f"  {cat}: {target_count} 条")

    session.commit()
    total = session.query(Job).count()
    cities = session.query(Job.city).distinct().count()

    from sqlalchemy import func
    print(f"\n{'='*50}")
    print(f"  总计: {total} 条, {cities} 城市")
    print(f"  CSV真实: {csv_count} | 生成: {generated}")
    cats = session.query(Job.job_category, func.count(Job.job_id)).group_by(Job.job_category).order_by(func.count(Job.job_id).desc()).all()
    for c, n in cats: print(f"    {c}: {n}")
    session.close()
