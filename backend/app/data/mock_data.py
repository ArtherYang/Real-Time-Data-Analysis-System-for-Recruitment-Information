"""
模拟数据生成器
==============
生成合理的招聘市场模拟数据（~200条岗位），覆盖30个中国主要城市、
8种岗位类型、5个平台。数据结构与 jobs 表一致。

城市数据源：app.data.city_metadata（30 城市 + 坐标 + 图标）

用途：
- 前端可视化开发调试
- API 接口联调
- 后续切换到 MySQL 时只需替换数据访问层

作者: 杨昱晨 (AI生成，待人工审查)
日期: 2026-07-03
"""

import random
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from .city_metadata import CITY_NAMES, CITY_METADATA, CITY_DISTRICTS, CITY_REGIONS

# ============================================================
# 数据池
# ============================================================

CITIES = CITY_NAMES  # 30 城市，来自 city_metadata

JOB_TITLES = {
    "技术": [
        "Python开发工程师", "Java开发工程师", "前端开发工程师",
        "数据分析师", "算法工程师", "测试工程师",
        "DevOps工程师", "Go开发工程师", "架构师",
        "全栈工程师",
    ],
    "产品": [
        "产品经理", "产品运营", "产品助理",
    ],
    "运营": [
        "运营经理", "内容运营", "用户运营",
        "活动运营", "新媒体运营",
    ],
    "市场": [
        "市场经理", "品牌策划", "商务拓展",
        "销售经理",
    ],
    "职能": [
        "人力资源专员", "财务专员", "行政专员",
        "法务专员",
    ],
    "设计": [
        "UI设计师", "UX设计师", "视觉设计师",
    ],
    "金融": [
        "金融分析师", "风控专员", "投资经理",
    ],
    "教育": [
        "课程设计师", "培训讲师", "教育产品经理",
    ],
}

COMPANIES = [
    "字节跳动", "阿里巴巴", "腾讯", "美团", "京东",
    "百度", "网易", "小米", "华为", "比亚迪",
    "小红书", "B站", "滴滴", "快手", "拼多多",
    "蔚来汽车", "理想汽车", "大疆", "商汤科技", "科大讯飞",
    "招商银行", "平安科技", "万科", "新东方", "好未来",
]

SKILLS_POOL = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust",
    "React", "Vue.js", "Angular", "Node.js", "Spring Boot", "Django",
    "MySQL", "Redis", "MongoDB", "PostgreSQL", "Elasticsearch",
    "Docker", "Kubernetes", "Jenkins", "Git", "Linux",
    "AWS", "Azure", "阿里云", "腾讯云",
    "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy",
    "Figma", "Sketch", "Adobe XD", "Photoshop",
    "数据分析", "项目管理", "团队管理", "沟通能力",
    "英语流利", "PPT制作", "SQL", "Tableau", "Power BI",
]

EXPERIENCE_LEVELS = ["应届生", "1-3年", "3-5年", "5-10年", "10年以上", "不限"]
EDUCATION_LEVELS = ["不限", "大专", "本科", "硕士", "博士"]
PLATFORMS = ["BOSS直聘", "智联招聘", "前程无忧", "猎聘", "其他"]
JOB_TYPES = ["全职", "兼职", "实习"]
COMPANY_SIZES = ["50-150人", "150-500人", "500-2000人", "2000人以上", "10000人以上"]
COMPANY_TYPES = ["民营", "国企", "外企", "上市公司", "合资"]
WELFARE_TAGS = [
    "五险一金", "补充公积金", "年终奖", "股票期权",
    "弹性工作", "远程办公", "免费三餐", "健身房",
    "年度旅游", "带薪年假", "节日福利", "定期体检",
]


def _random_date(days_back: int = 30) -> date:
    """生成过去 N 天内的随机日期"""
    return date.today() - timedelta(days=random.randint(0, days_back))


def _random_salary(exp: str) -> tuple:
    """根据经验生成合理的薪资范围 (月薪/元)"""
    base = {
        "应届生": (5000, 12000),
        "1-3年": (8000, 20000),
        "3-5年": (12000, 30000),
        "5-10年": (20000, 50000),
        "10年以上": (30000, 80000),
        "不限": (6000, 25000),
    }
    low, high = base.get(exp, (8000, 20000))
    # 城市系数
    tier1_cities = {"北京", "上海", "广州", "深圳", "杭州"}
    return (low, high)  # 城市系数在生成时处理


def generate_jobs(count: int = 200) -> list[dict]:
    """
    生成模拟岗位数据

    Args:
        count: 生成数量

    Returns:
        岗位字典列表，结构与 jobs 表一致
    """
    jobs = []
    for _ in range(count):
        category = random.choice(list(JOB_TITLES.keys()))
        title = random.choice(JOB_TITLES[category])
        city = random.choice(CITIES)
        exp = random.choice(EXPERIENCE_LEVELS)
        edu = random.choice(EDUCATION_LEVELS)
        platform = random.choice(PLATFORMS)
        company = random.choice(COMPANIES)

        # 薪资 (面议概率 15%)
        salary_type = "面议" if random.random() < 0.15 else "月薪"
        if salary_type == "面议":
            sal_min, sal_max = None, None
        else:
            base_low, base_high = _random_salary(exp)
            # 城市系数
            tier1_mult = random.uniform(1.1, 1.6) if city in {"北京", "上海", "广州", "深圳", "杭州"} else random.uniform(0.7, 1.1)
            sal_min = int(base_low * tier1_mult / 1000) * 1000
            sal_max = int(base_high * tier1_mult / 1000) * 1000 + random.choice([0, 2000, 5000])

        # 技能标签
        num_skills = random.randint(3, 8)
        skills = ",".join(random.sample(SKILLS_POOL, num_skills))

        # 福利
        num_welfare = random.randint(2, 6)
        welfare = ",".join(random.sample(WELFARE_TAGS, num_welfare))

        pub_date = _random_date(30)
        crawl_date = pub_date + timedelta(days=random.randint(0, 2))

        job = {
            "job_id": uuid.uuid4().hex,
            "title": title,
            "title_raw": title,
            "company": company,
            "salary_min": sal_min,
            "salary_max": sal_max,
            "salary_type": salary_type,
            "city": city,
            "district": random.choice(["朝阳区", "海淀区", "浦东新区", "天河区", "南山区", None]),
            "experience": exp,
            "education": edu,
            "description": f"{company}招聘{title}，要求{exp}经验，{edu}学历...",
            "skills": skills,
            "job_type": random.choice(JOB_TYPES),
            "recruit_number": random.choice([str(random.randint(1, 5)), "若干"]),
            "industry": random.choice(["互联网", "金融", "教育", "制造", "医疗", "电商", "游戏"]),
            "job_category": category,
            "company_size": random.choice(COMPANY_SIZES),
            "company_type": random.choice(COMPANY_TYPES),
            "welfare": welfare,
            "platform": platform,
            "platform_job_id": f"{platform}_{uuid.uuid4().hex[:12]}",
            "source_url": f"https://www.{platform}.com/jobs/{uuid.uuid4().hex[:8]}",
            "published_at": pub_date.isoformat(),
            "crawled_at": crawl_date.isoformat(),
            "status": "有效",
        }
        jobs.append(job)
    return jobs


# ============================================================
# 内存数据存储（单例）
# ============================================================

_jobs_cache: Optional[list[dict]] = None


def get_all_jobs() -> list[dict]:
    """获取全部岗位数据（懒加载+缓存）"""
    global _jobs_cache
    if _jobs_cache is None:
        _jobs_cache = generate_jobs(200)
    return _jobs_cache


def filter_jobs(
    city: Optional[str] = None,
    job_category: Optional[str] = None,
    platform: Optional[str] = None,
    experience: Optional[str] = None,
    education: Optional[str] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict]:
    """
    按条件筛选岗位数据

    Args:
        city: 城市名
        job_category: 岗位大类
        platform: 数据来源平台
        experience: 经验要求
        education: 学历要求
        salary_min: 最低薪资
        salary_max: 最高薪资
        date_from: 发布日期起始
        date_to: 发布日期结束

    Returns:
        筛选后的岗位列表
    """
    jobs = get_all_jobs()
    result = []

    for job in jobs:
        if city and job["city"] != city:
            continue
        if job_category and job["job_category"] != job_category:
            continue
        if platform and job["platform"] != platform:
            continue
        if experience and job["experience"] != experience:
            continue
        if education and job["education"] != education:
            continue
        if salary_min is not None:
            if job["salary_min"] is None or job["salary_min"] < salary_min:
                continue
        if salary_max is not None:
            if job["salary_max"] is None or job["salary_max"] > salary_max:
                continue
        if date_from:
            if job["published_at"] < date_from:
                continue
        if date_to:
            if job["published_at"] > date_to:
                continue
        result.append(job)
    return result


def get_filter_options() -> dict:
    """获取所有筛选器可选项"""
    jobs = get_all_jobs()
    cities = sorted(set(j["city"] for j in jobs))
    categories = sorted(set(j["job_category"] for j in jobs))
    platforms = sorted(set(j["platform"] for j in jobs))
    experiences = EXPERIENCE_LEVELS
    educations = EDUCATION_LEVELS

    # 薪资范围
    valid_salaries = [j for j in jobs if j["salary_min"] is not None]
    salary_range = {
        "min": min(j["salary_min"] for j in valid_salaries) if valid_salaries else 0,
        "max": max(j["salary_max"] for j in valid_salaries) if valid_salaries else 50000,
    }

    return {
        "cities": cities,
        "job_categories": categories,
        "platforms": platforms,
        "experiences": experiences,
        "educations": educations,
        "salary_range": salary_range,
    }
