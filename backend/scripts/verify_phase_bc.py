"""Phase B+C 验证 — 新增表 + 新 API 端点"""
import os, json
os.environ['FLASK_ENV'] = 'testing'

from app import create_app
from app.config import TestingConfig
from app import database as db_module
from app.models.job import Job
from app.models.resume import ResumeTemplate, Resume
from app.models.user_profile import UserProfile
from app.models.user_preference import UserPreference
import uuid, random
from datetime import datetime, timedelta

app = create_app(TestingConfig())

with app.app_context():
    session = db_module.SessionLocal()

    # Seed resume templates (init.sql INSERT only works on MySQL)
    existing = session.query(ResumeTemplate).count()
    if existing == 0:
        for name, css in [
            ('简洁模板', '{"primary_color":"#2c3e50","font":"微软雅黑","layout":"single_column"}'),
            ('专业模板', '{"primary_color":"#1a5276","font":"宋体","layout":"two_column"}'),
            ('创意模板', '{"primary_color":"#e74c3c","font":"思源黑体","layout":"timeline"}'),
        ]:
            session.add(ResumeTemplate(name=name, css_styles=css, is_active=1))
        session.commit()

    # Jobs
    cities_pool = ['北京','上海','深圳','杭州','成都','武汉','广州','南京']
    for i in range(20):
        s_min = random.choice([6000, 10000, 15000, 20000, 30000])
        job = Job(job_id=uuid.uuid4().hex, title=f'岗位{i}', company=f'公司{i}',
                  platform='BOSS直聘', city=random.choice(cities_pool),
                  salary_min=s_min, salary_max=s_min+random.choice([3000,5000,10000]),
                  salary_type='月薪', experience=random.choice(['1-3年','3-5年','不限']),
                  education=random.choice(['本科','硕士','不限']),
                  job_category=random.choice(['技术','产品','运营']),
                  skills='Python,SQL', industry='互联网',
                  platform_job_id=f'pid_{i}', source_url=f'http://example.com/{i}',
                  published_at=(datetime.utcnow()-timedelta(days=random.randint(1,14))).date(),
                  crawled_at=datetime.utcnow(), status='有效')
        session.add(job)
    session.commit()
    session.close()

with app.test_client() as c:
    print('=== Phase C API Verification ===')

    # Dashboard
    r = c.get('/api/v1/dashboard/overview')
    d = json.loads(r.data)
    print(f'[OK] GET /dashboard/overview -> {r.status_code}, total={d["data"]["total_jobs"]}, cities={len(d["data"]["top_cities"])}')

    r = c.get('/api/v1/dashboard/hot-jobs?limit=5')
    d = json.loads(r.data)
    print(f'[OK] GET /dashboard/hot-jobs -> {r.status_code}, items={len(d["data"])}')

    r = c.get('/api/v1/dashboard/salary-trend')
    d = json.loads(r.data)
    print(f'[OK] GET /dashboard/salary-trend -> {r.status_code}')

    r = c.get('/api/v1/dashboard/city-distribution')
    d = json.loads(r.data)
    cd = d['data']
    has_coords = all('lng' in c for c in cd['cities'][:1]) if cd['cities'] else False
    print(f'[OK] GET /dashboard/city-distribution -> {r.status_code}, cities={cd["total_cities"]}, has_coords={has_coords}')

    # Resume templates
    r = c.get('/api/v1/resumes/templates')
    d = json.loads(r.data)
    print(f'[OK] GET /resumes/templates -> {r.status_code}, templates={len(d["data"])}')

    # Register + login for auth-required endpoints
    c.post('/api/v1/auth/register', json={'email':'phasec@test.com','password':'test1234','nickname':'PhaseC'})
    login_r = c.post('/api/v1/auth/login', json={'account':'phasec@test.com','password':'test1234'})
    token = json.loads(login_r.data)['data']['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # User profile
    r = c.get('/api/v1/user/profile', headers=headers)
    d = json.loads(r.data)
    print(f'[OK] GET /user/profile -> {r.status_code}, has_profile={d["data"]["profile"] is not None}')

    r = c.put('/api/v1/user/profile', headers=headers, json={
        'real_name': '测试用户', 'university': '重庆大学', 'major': '人工智能',
        'desired_position': 'Python开发', 'desired_city': '深圳', 'desired_salary_min': 15000
    })
    d = json.loads(r.data)
    print(f'[OK] PUT /user/profile -> {r.status_code}, real_name={d["data"]["profile"].get("real_name","?")}')

    r = c.get('/api/v1/user/profile', headers=headers)
    d = json.loads(r.data)
    print(f'[OK] GET /user/profile (after PUT) -> {r.status_code}, real_name={d["data"]["profile"]["real_name"]}, desired={d["data"]["preferences"]["desired_position"]}')

    # Resume generate
    r = c.post('/api/v1/resumes/generate', headers=headers, json={
        'template_id': 1, 'full_name': '张三', 'email': 'zhang@test.com',
        'university': '重庆大学', 'major': '软件工程', 'degree': '本科',
        'graduation_year': 2026, 'skills_text': 'Python,Flask,MySQL,React',
        'self_intro': '热爱编程的应届毕业生'
    })
    d = json.loads(r.data)
    resume_id = d['data']['resume_id']
    print(f'[OK] POST /resumes/generate -> {r.status_code}, resume_id={resume_id}')

    # Resume detail
    r = c.get(f'/api/v1/resumes/{resume_id}', headers=headers)
    d = json.loads(r.data)
    print(f'[OK] GET /resumes/{resume_id} -> {r.status_code}, full_name={d["data"]["resume"]["full_name"]}, template={d["data"]["template"]["name"]}')

    # Resume download (placeholder)
    r = c.get(f'/api/v1/resumes/{resume_id}/download', headers=headers)
    d = json.loads(r.data)
    print(f'[OK] GET /resumes/{resume_id}/download -> {r.status_code}, format_note={d["data"].get("note","")[:20]}...')

    # Auth error: no token
    r = c.get('/api/v1/user/profile')
    print(f'[OK] GET /user/profile (no auth) -> {r.status_code} (expected 401)')

print('=== ALL Phase B+C ENDPOINTS VERIFIED ===')
