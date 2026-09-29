"""
示例数据生成与入库脚本
======================
生成 500 条模拟招聘岗位数据，覆盖 15 个城市、8 种岗位类型、5 个平台。

使用方式：
    python backend/scripts/seed_data.py
"""

import sys
import os
import random
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import TestingConfig


class SQLiteFileConfig(TestingConfig):
    """SQLite 文件 —— 持久化保存到项目目录"""
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        db_path = os.path.join(os.path.dirname(__file__), "..", "rdas.db")
        return f"sqlite:///{db_path}"


from app import database as db_module
from app.models.job import Job

# ============================================================
# 数据池 — 大幅扩充
# ============================================================

PLATFORMS = ["BOSS直聘", "智联招聘", "前程无忧", "猎聘"]

# 30 城市，按真实招聘市场规模加权（一线城市权重高，二三线权重低）
CITIES = (
    ["北京"] * 8 + ["上海"] * 8 + ["深圳"] * 7 + ["广州"] * 7 +
    ["杭州"] * 6 + ["成都"] * 6 + ["武汉"] * 5 + ["南京"] * 5 +
    ["西安"] * 4 + ["重庆"] * 4 + ["苏州"] * 4 + ["长沙"] * 4 +
    ["天津"] * 3 + ["合肥"] * 3 + ["厦门"] * 3 + ["青岛"] * 3 +
    ["大连"] * 3 + ["济南"] * 3 + ["福州"] * 3 + ["郑州"] * 3 +
    ["沈阳"] * 2 + ["昆明"] * 2 + ["贵阳"] * 2 + ["南宁"] * 2 +
    ["哈尔滨"] * 2 + ["兰州"] * 2 + ["海口"] * 2 + ["乌鲁木齐"] * 2 +
    ["拉萨"] * 1 + ["呼和浩特"] * 1
)

# 30 城市经纬度（用于地图标记）
CITY_COORDS = {
    "北京": [116.40, 39.90], "上海": [121.47, 31.23], "深圳": [114.07, 22.62],
    "广州": [113.26, 23.13], "杭州": [120.15, 30.28], "成都": [104.07, 30.67],
    "武汉": [114.30, 30.60], "南京": [118.78, 32.07], "西安": [108.94, 34.26],
    "重庆": [106.55, 29.57], "苏州": [120.58, 31.30], "长沙": [112.97, 28.23],
    "天津": [117.20, 39.13], "合肥": [117.23, 31.82], "厦门": [118.09, 24.48],
    "青岛": [120.38, 36.07], "大连": [121.62, 38.92], "济南": [117.00, 36.67],
    "福州": [119.30, 26.08], "郑州": [113.62, 34.75], "沈阳": [123.43, 41.80],
    "昆明": [102.83, 24.88], "贵阳": [106.71, 26.65], "南宁": [108.37, 22.82],
    "哈尔滨": [126.53, 45.80], "兰州": [103.83, 36.07], "海口": [110.20, 20.02],
    "乌鲁木齐": [87.62, 43.82], "拉萨": [91.13, 29.65], "呼和浩特": [111.75, 40.84],
}

# 30 城市特色图标
CITY_ICONS = {
    "北京": "🏯", "上海": "🗼", "深圳": "💻", "广州": "🦐", "杭州": "🪷",
    "成都": "🐼", "武汉": "🍜", "南京": "🏯", "西安": "🏯", "重庆": "🍲",
    "苏州": "🏯", "长沙": "🌶️", "天津": "🥟", "合肥": "🔬", "厦门": "🏝️",
    "青岛": "🍺", "大连": "⚓", "济南": "⛲", "福州": "🍵", "郑州": "🛕",
    "沈阳": "🏮", "昆明": "🌺", "贵阳": "🍶", "南宁": "🍊", "哈尔滨": "❄️",
    "兰州": "🍜", "海口": "🌴", "乌鲁木齐": "🍇", "拉萨": "🏔️", "呼和浩特": "🐑",
}

DISTRICTS = {
    "北京": ["朝阳区", "海淀区", "西城区", "东城区", "丰台区", "大兴区"],
    "上海": ["浦东新区", "徐汇区", "静安区", "黄浦区", "杨浦区", "长宁区"],
    "深圳": ["南山区", "福田区", "罗湖区", "宝安区", "龙华区"],
    "广州": ["天河区", "海珠区", "越秀区", "白云区", "黄埔区"],
    "杭州": ["余杭区", "西湖区", "滨江区", "拱墅区", "萧山区"],
    "成都": ["高新区", "武侯区", "锦江区", "天府新区", "青羊区"],
    "武汉": ["武昌区", "洪山区", "江汉区", "东湖高新区"],
    "南京": ["江宁区", "鼓楼区", "建邺区", "雨花台区"],
    "西安": ["雁塔区", "高新区", "未央区"],
    "重庆": ["渝北区", "江北区", "南岸区"],
    "苏州": ["工业园区", "虎丘区"],
    "长沙": ["岳麓区", "开福区"],
    "天津": ["和平区", "滨海新区"],
    "合肥": ["蜀山区", "包河区"],
    "厦门": ["思明区", "湖里区"],
    "青岛": ["市南区", "崂山区"],
    "大连": ["中山区", "高新园区"],
    "济南": ["历下区", "高新区"],
    "福州": ["鼓楼区", "台江区"],
    "郑州": ["金水区", "郑东新区"],
    "沈阳": ["和平区", "浑南新区"],
    "昆明": ["五华区", "盘龙区"],
    "贵阳": ["南明区", "观山湖区"],
    "南宁": ["青秀区", "西乡塘区"],
    "哈尔滨": ["南岗区", "松北区"],
    "兰州": ["城关区", "安宁区"],
    "海口": ["龙华区", "美兰区"],
    "乌鲁木齐": ["天山区", "新市区"],
    "拉萨": ["城关区"],
    "呼和浩特": ["新城区", "赛罕区"],
}

JOB_TEMPLATES = [
    # (title, category, industry, skills)
    ("Python开发工程师", "技术", "互联网", "Python,Flask,Django,MySQL,Redis,Linux,Docker"),
    ("高级Python开发工程师", "技术", "互联网", "Python,FastAPI,PostgreSQL,Kubernetes,gRPC,微服务"),
    ("Python后端开发", "技术", "金融", "Python,Flask,MySQL,MongoDB,消息队列,分布式系统"),
    ("Java开发工程师", "技术", "互联网", "Java,SpringBoot,MyBatis,MySQL,Redis,微服务"),
    ("高级Java工程师", "技术", "金融", "Java,SpringCloud,Kafka,Redis,微服务架构"),
    ("前端开发工程师", "技术", "互联网", "JavaScript,TypeScript,React,Vue.js,CSS3,HTML5,Webpack"),
    ("前端开发（React方向）", "技术", "互联网", "React,TypeScript,Next.js,AntDesign,TailwindCSS"),
    ("前端开发（Vue方向）", "技术", "互联网", "Vue.js,JavaScript,TypeScript,ElementPlus,Vite,Sass"),
    ("全栈工程师", "技术", "互联网", "Python,JavaScript,React,Node.js,MySQL,Docker,AWS"),
    ("Go开发工程师", "技术", "互联网", "Go,Microservices,gRPC,Kubernetes,Docker,Redis"),
    ("C++开发工程师", "技术", "游戏", "C++,UnrealEngine,图形学,多线程,性能优化"),
    ("算法工程师", "技术", "人工智能", "Python,TensorFlow,PyTorch,深度学习,计算机视觉,NLP"),
    ("算法工程师（推荐方向）", "技术", "互联网", "Python,推荐系统,机器学习,Spark,Hive,AB实验"),
    ("数据分析师", "技术", "互联网", "SQL,Python,Pandas,Tableau,Excel,数据可视化"),
    ("高级数据分析师", "技术", "金融", "Python,R,SQL,机器学习,数据挖掘,Spark,Hive"),
    ("商业数据分析师", "技术", "互联网", "SQL,Excel,Python,PowerBI,业务分析,指标体系"),
    ("数据工程师", "技术", "互联网", "Spark,Flink,Hadoop,Python,Scala,数据仓库,ETL"),
    ("测试工程师", "技术", "互联网", "自动化测试,Selenium,JMeter,Python,CI/CD,性能测试"),
    ("高级测试开发", "技术", "互联网", "Python,Pytest,Selenium,CI/CD,测试左移,压测"),
    ("运维工程师", "技术", "互联网", "Linux,Docker,Kubernetes,CI/CD,Prometheus,Ansible,Terraform"),
    ("DevOps工程师", "技术", "互联网", "AWS,Kubernetes,Terraform,Docker,Jenkins,GitOps"),
    ("安全工程师", "技术", "互联网", "渗透测试,漏洞扫描,安全审计,Python,BurpSuite,Nmap"),
    ("产品经理", "产品", "互联网", "产品设计,需求分析,PRD,数据分析,用户研究,Axure"),
    ("高级产品经理", "产品", "互联网", "产品战略,商业分析,团队管理,数据分析,A/B测试"),
    ("产品运营", "运营", "互联网", "数据分析,活动策划,用户运营,内容运营,SQL"),
    ("用户运营", "运营", "互联网", "用户增长,社群运营,数据分析,活动策划,CRM"),
    ("内容运营", "运营", "互联网", "内容策划,文案撰写,数据分析,短视频,公众号"),
    ("运营经理", "运营", "互联网", "团队管理,运营策略,数据分析,KPI制定,活动策划"),
    ("市场经理", "市场", "互联网", "品牌策划,营销活动,数据分析,团队管理,渠道合作"),
    ("品牌策划", "市场", "互联网", "品牌定位,内容营销,社交媒体,活动策划,PR"),
    ("商务拓展", "市场", "互联网", "商务谈判,市场分析,合同管理,客户关系,方案撰写"),
    ("销售经理", "市场", "互联网", "销售策略,客户管理,方案演示,谈判,CRM,团队管理"),
    ("UI设计师", "设计", "互联网", "Figma,Sketch,用户研究,交互设计,视觉设计,设计系统"),
    ("UX设计师", "设计", "互联网", "用户研究,交互设计,可用性测试,信息架构,原型设计"),
    ("视觉设计师", "设计", "互联网", "Photoshop,Illustrator,AE,品牌设计,平面设计"),
    ("金融分析师", "金融", "金融", "财务分析,Excel,Python,风险管理,投资分析,Bloomberg"),
    ("风控专员", "金融", "金融", "风险评估,数据分析,SQL,Python,信用评级,合规审查"),
    ("人力资源专员", "职能", "综合", "招聘,员工关系,薪酬福利,劳动法,Excel,沟通能力"),
    ("HRBP", "职能", "互联网", "组织发展,人才招聘,绩效管理,员工关系,HR数据,SSC"),
    ("财务专员", "职能", "综合", "财务核算,税务申报,Excel,财务报表,金蝶,用友"),
    ("法务专员", "职能", "综合", "合同法,公司法,知识产权,法律文书,合规管理"),
    ("课程设计师", "教育", "教育", "课程设计,教学设计,课件制作,教育技术,学习评估"),
    ("培训讲师", "教育", "教育", "演讲表达,课程开发,教学评估,课件设计,普通话"),
    ("教育产品经理", "教育", "互联网", "产品设计,用户研究,教育理论,数据分析,项目推进"),
]

EXPERIENCE_LEVELS = ["应届生", "1-3年", "1-3年", "3-5年", "3-5年", "5-10年", "10年以上", "不限"]
EDUCATION_LEVELS = ["大专", "本科", "本科", "本科", "硕士", "硕士", "博士", "不限"]

COMPANY_POOL = [
    # 大厂
    ("字节跳动", "10000人以上", "民营", "互联网"),
    ("阿里巴巴", "10000人以上", "民营", "互联网"),
    ("腾讯", "10000人以上", "上市公司", "互联网"),
    ("美团", "10000人以上", "上市公司", "互联网"),
    ("京东", "10000人以上", "上市公司", "互联网"),
    ("百度", "10000人以上", "上市公司", "互联网"),
    ("网易", "10000人以上", "上市公司", "互联网"),
    ("小米", "10000人以上", "上市公司", "互联网"),
    ("华为", "10000人以上", "民营", "通信"),
    ("比亚迪", "10000人以上", "上市公司", "制造"),
    ("小红书", "2000人以上", "民营", "互联网"),
    ("B站", "500-2000人", "上市公司", "互联网"),
    ("快手", "10000人以上", "上市公司", "互联网"),
    ("拼多多", "10000人以上", "上市公司", "电商"),
    ("滴滴", "5000-10000人", "民营", "互联网"),
    ("蔚来汽车", "10000人以上", "上市公司", "新能源"),
    ("理想汽车", "10000人以上", "上市公司", "新能源"),
    ("大疆", "5000-10000人", "民营", "硬件"),
    ("商汤科技", "2000-5000人", "上市公司", "人工智能"),
    ("科大讯飞", "5000-10000人", "上市公司", "人工智能"),
    # 金融
    ("招商银行", "10000人以上", "上市公司", "金融"),
    ("平安科技", "10000人以上", "上市公司", "金融"),
    ("蚂蚁集团", "10000人以上", "民营", "金融"),
    ("微众银行", "2000-5000人", "民营", "金融"),
    # 综合
    ("万科", "10000人以上", "上市公司", "房地产"),
    ("新东方", "10000人以上", "上市公司", "教育"),
    ("好未来", "10000人以上", "上市公司", "教育"),
    ("恒瑞医药", "10000人以上", "上市公司", "医疗"),
    ("迈瑞医疗", "5000-10000人", "上市公司", "医疗"),
    # 中小企业
    ("星云数据", "150-500人", "民营", "大数据"),
    ("极光科技", "150-500人", "外企", "互联网"),
    ("创智软件", "50-150人", "民营", "软件"),
    ("领航科技", "150-500人", "合资", "互联网"),
    ("博睿智能", "50-150人", "民营", "人工智能"),
    ("明远信息", "500-2000人", "上市公司", "互联网"),
    ("鼎新云", "500-2000人", "民营", "云计算"),
    ("睿思科技", "150-500人", "外企", "软件"),
    ("云端互动", "150-500人", "民营", "互联网"),
    ("华胜天隆", "500-2000人", "国企", "IT服务"),
    ("恒信科技", "500-2000人", "上市公司", "金融科技"),
    ("远航软件", "150-500人", "民营", "软件"),
    ("通达信息", "500-2000人", "国企", "IT服务"),
    ("智联数据", "50-150人", "民营", "大数据"),
    ("星辰科技", "150-500人", "民营", "互联网"),
]

WELFARE_OPTIONS = [
    "五险一金,年终奖,带薪年假,定期体检",
    "五险一金,补充公积金,年终奖,弹性工作",
    "五险一金,弹性工作,餐补,免费健身房",
    "五险一金,股票期权,年终奖,免费三餐",
    "六险一金,年终奖,交通补贴,通讯补贴,团建",
    "五险一金,带薪年假,定期体检,节日福利,旅游",
    "五险一金,双休,年终奖,餐补,零食下午茶",
    "五险一金,年终奖,员工培训,晋升空间,团建",
    "五险一金,弹性工作,远程办公,免费三餐,健身房",
    "六险一金,股票期权,带薪年假,年度旅游,免费三餐",
    "五险一金,年终奖,租房补贴,餐补,弹性工作",
    "五险一金,补充医保,带薪年假,团建,节日福利",
]


def random_date(days_back: int = 30) -> datetime:
    days = random.randint(0, days_back)
    return datetime.utcnow() - timedelta(days=days)


def generate_salary(experience: str) -> tuple:
    if random.random() < 0.08:
        return (None, None, "面议")

    base_map = {
        "应届生": (5000, 15000),
        "1-3年": (8000, 22000),
        "3-5年": (15000, 35000),
        "5-10年": (25000, 55000),
        "10年以上": (35000, 80000),
        "不限": (7000, 25000),
    }

    base_min, base_max = base_map.get(experience, (8000, 20000))
    variation = random.uniform(0.75, 1.4)
    salary_min = int(base_min * variation // 500 * 500)
    salary_max = salary_min + random.randint(3000, 20000)
    return (salary_min, salary_max, "月薪")


def generate_job() -> Job:
    template = random.choice(JOB_TEMPLATES)
    title, category, industry, skills = template
    city = random.choice(CITIES)
    districts = DISTRICTS.get(city, ["市中心"])
    district = random.choice(districts)
    experience = random.choice(EXPERIENCE_LEVELS)
    education = random.choice(EDUCATION_LEVELS)
    salary_min, salary_max, salary_type = generate_salary(experience)

    company_info = random.choice(COMPANY_POOL)
    company, size, ctype, cindustry = company_info
    # 30% 用真实公司名，70% 随机组合避免全是知名公司
    if random.random() > 0.3:
        prefixes = ["华", "明", "睿", "鼎", "博", "星", "云", "极", "领", "创",
                    "智", "恒", "远", "达", "信", "通", "中", "天", "海", "汇"]
        suffix = random.choice(["科技", "信息技术", "数据", "云计算", "软件", "智能科技", "互联", "数字"])
        company = f"{random.choice(prefixes)}{random.choice(['', '远', '恒', '达', '智', '睿'])}{suffix}有限公司"
        size = random.choice(["50-150人", "150-500人", "500-2000人", "2000人以上"])
        ctype = random.choice(["民营", "国企", "外企", "上市公司", "合资"])

    published_at = (datetime.utcnow() - timedelta(days=random.randint(0, 28))).date()
    crawled_at = datetime.utcnow() - timedelta(hours=random.randint(0, 48))

    job = Job(
        job_id=uuid.uuid4().hex,
        title=title,
        title_raw=title,
        company=company,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_type=salary_type,
        city=city,
        district=district,
        experience=experience,
        education=education,
        description=f"【岗位职责】\n1. 负责{title}的设计、开发和维护；"
                    f"\n2. 参与系统架构设计和技术方案评审；"
                    f"\n3. 与团队协作完成产品迭代，保证代码质量。"
                    f"\n\n【任职要求】\n1. {education}及以上学历；"
                    f"\n2. {experience}相关工作经验；"
                    f"\n3. 熟练使用{skills.split(',')[0] if skills else '相关技术栈'}；"
                    f"\n4. 良好的沟通能力和团队协作精神。",
        skills=skills,
        job_type=random.choice(["全职", "全职", "全职", "全职", "实习", "兼职"]),
        recruit_number=str(random.choice([1, 2, 3, 5, 10, "若干"])),
        industry=industry,
        job_category=category,
        company_size=size,
        company_type=ctype,
        welfare=random.choice(WELFARE_OPTIONS),
        platform=random.choice(PLATFORMS),
        platform_job_id=uuid.uuid4().hex[:16],
        source_url=f"https://www.example.com/jobs/{uuid.uuid4().hex[:12]}",
        published_at=published_at,
        crawled_at=crawled_at,
        status="有效",
    )
    return job


def seed_jobs(count: int = 500):
    print(f"正在生成 {count} 条模拟岗位数据...")
    jobs = [generate_job() for _ in range(count)]

    session = db_module.SessionLocal()
    try:
        # 追加模式：不清空旧数据
        print(f"  追加模式（保留现有数据）")

        session.add_all(jobs)
        session.commit()
        print(f"  成功插入 {len(jobs)} 条新数据")
        return jobs
    except Exception as e:
        session.rollback()
        print(f"数据插入失败: {e}")
        raise
    finally:
        session.close()


def print_stats():
    from sqlalchemy import func
    session = db_module.SessionLocal()
    try:
        total = session.query(Job).filter(Job.status == "有效").count()
        print(f"\n{'='*50}")
        print(f"总记录数: {total}")
        print(f"{'='*50}")

        print(f"\n按城市分布 (Top 15):")
        city_stats = (
            session.query(Job.city, func.count(Job.job_id))
            .filter(Job.status == "有效")
            .group_by(Job.city).order_by(func.count(Job.job_id).desc()).limit(15).all()
        )
        for city, count in city_stats:
            bar = "█" * (count // 5)
            print(f"  {city:6s} │ {bar} {count}")

        print(f"\n按平台分布:")
        platform_stats = (
            session.query(Job.platform, func.count(Job.job_id))
            .filter(Job.status == "有效")
            .group_by(Job.platform).all()
        )
        for p, c in platform_stats:
            print(f"  {p}: {c}")

        print(f"\n按岗位大类分布:")
        cat_stats = (
            session.query(Job.job_category, func.count(Job.job_id))
            .filter(Job.status == "有效")
            .group_by(Job.job_category).order_by(func.count(Job.job_id).desc()).all()
        )
        for cat, c in cat_stats:
            print(f"  {cat}: {c}")

        print(f"\n按经验要求分布:")
        exp_stats = (
            session.query(Job.experience, func.count(Job.job_id))
            .filter(Job.status == "有效")
            .group_by(Job.experience).all()
        )
        for e, c in exp_stats:
            print(f"  {e}: {c}")

        salary_stats = session.query(
            func.avg(Job.salary_min), func.avg(Job.salary_max),
            func.min(Job.salary_min), func.max(Job.salary_max)
        ).filter(Job.status == "有效", Job.salary_type != "面议").first()
        print(f"\n薪资统计（不含面议）:")
        print(f"  平均范围: ¥{int(salary_stats[0]):,} - ¥{int(salary_stats[1]):,}")
        print(f"  最低: ¥{salary_stats[2]:,} / 最高: ¥{salary_stats[3]:,}")

    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 50)
    print("  RDAS 数据生成器 — 500 条岗位数据")
    print("=" * 50)

    config = SQLiteFileConfig()
    db_module.init_db(config)
    db_module.create_tables()

    seed_jobs(count=500)
    print_stats()
    print(f"\n数据入库完成！刷新仪表盘查看。")
