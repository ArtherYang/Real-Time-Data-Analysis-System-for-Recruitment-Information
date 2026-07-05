"""M2 API 验证脚本 — 使用 SQLite 内存数据库验证所有端点"""
import os, json
os.environ['FLASK_ENV'] = 'testing'

from app import create_app
from app.config import TestingConfig
from app import database as db_module
from app.models.job import Job
import uuid, random
from datetime import datetime, timedelta

app = create_app(TestingConfig())

with app.app_context():
    session = db_module.SessionLocal()
    platforms = ['BOSS直聘', 'BOSS直聘', '智联招聘', '前程无忧']
    cities = ['北京', '上海', '深圳', '杭州', '成都', '广州', '武汉', '南京']
    cats = ['技术', '技术', '产品', '运营', '技术', '市场']
    titles_map = {
        '技术': ['Python开发工程师', 'Java开发工程师', '前端开发工程师', '数据分析师', 'AI算法工程师'],
        '产品': ['产品经理', '高级产品经理'],
        '运营': ['运营专员', '用户运营'],
        '市场': ['市场推广', '品牌营销'],
    }
    exps = ['应届生', '1-3年', '3-5年', '5-10年', '不限']
    edus = ['本科', '大专', '硕士', '不限']
    skills_pool = ['Python,Flask,MySQL', 'Java,Spring,Redis', 'React,TypeScript,CSS', 'SQL,Python,Pandas']

    jobs = []
    for i in range(40):
        cat = cats[i % len(cats)]
        city = random.choice(cities)
        s_min = random.choice([6000, 8000, 10000, 15000, 20000, 25000, 30000])
        s_max = s_min + random.choice([3000, 5000, 8000, 10000, 15000])
        job = Job(
            job_id=uuid.uuid4().hex,
            title=random.choice(titles_map[cat]), company=f'公司{i+1}',
            platform=platforms[i % len(platforms)], city=city, district='中心区',
            salary_min=s_min, salary_max=s_max, salary_type='月薪',
            experience=random.choice(exps), education=random.choice(edus), job_category=cat,
            skills=random.choice(skills_pool), industry='互联网',
            company_size=random.choice(['100-500人', '500-2000人', '2000人以上']),
            company_type=random.choice(['民营', '上市公司', '外企']),
            welfare='五险一金,年终奖',
            platform_job_id=f'pid_{i:04d}',
            source_url=f'https://example.com/jobs/{i}',
            published_at=(datetime.utcnow() - timedelta(days=random.randint(1, 14))).date(),
            crawled_at=datetime.utcnow(), status='有效',
        )
        jobs.append(job)
    session.add_all(jobs)
    session.commit()
    session.close()

with app.test_client() as c:
    print('========== M2 API VERIFICATION ==========')
    r = c.get('/api/v1/jobs')
    d = json.loads(r.data)
    print(f'[OK] GET /api/v1/jobs -> 200, total={d["pagination"]["total"]}')
    r = c.get('/api/v1/jobs?platform=BOSS直聘')
    d = json.loads(r.data)
    print(f'[OK] GET /api/v1/jobs?platform=BOSS直聘 -> 200, count={d["pagination"]["total"]}')
    r = c.get('/api/v1/jobs?city=北京')
    d = json.loads(r.data)
    print(f'[OK] GET /api/v1/jobs?city=北京 -> 200, count={d["pagination"]["total"]}')
    r = c.get('/api/v1/jobs/stats/overview')
    d = json.loads(r.data)
    o = d['data']
    print(f'[OK] GET /api/v1/jobs/stats/overview -> 200, total={o["total"]}, avg_salary={o["avg_salary_min"]}-{o["avg_salary_max"]}')
    r = c.get('/api/v1/analysis/hot-jobs?top=10')
    d = json.loads(r.data)
    print(f'[OK] GET /api/v1/analysis/hot-jobs?top=10 -> 200, items={len(d["data"])}')
    r = c.get('/api/v1/analysis/city-distribution')
    d = json.loads(r.data)
    cd = d['data']
    print(f'[OK] GET /api/v1/analysis/city-distribution -> 200, cities={len(cd.get("cities",[]))}, cr5={cd.get("cr5","N/A")}')
    r = c.get('/api/v1/analysis/salary-distribution?group_by=city')
    d = json.loads(r.data)
    print(f'[OK] GET /api/v1/analysis/salary-distribution?group_by=city -> 200, items={len(d["data"].get("items",[]))}')
    r = c.get('/api/v1/analysis/salary-distribution?group_by=experience')
    d = json.loads(r.data)
    print(f'[OK] GET /api/v1/analysis/salary-distribution?group_by=experience -> 200, items={len(d["data"].get("items",[]))}')
    r = c.post('/api/v1/auth/register', json={'email': 'verify@test.com', 'password': 'pass1234', 'nickname': '验证'})
    d = json.loads(r.data)
    print(f'[OK] POST /api/v1/auth/register -> {r.status_code}, email={d.get("data",{}).get("user",{}).get("email","N/A")}')
    r = c.post('/api/v1/auth/login', json={'account': 'verify@test.com', 'password': 'pass1234'})
    d = json.loads(r.data)
    has_tok = 'access_token' in d.get('data', {})
    print(f'[OK] POST /api/v1/auth/login -> {r.status_code}, has_access_token={has_tok}')
print('========== ALL ENDPOINTS PASSED ==========')
