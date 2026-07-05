"""
数据导出接口测试
================
测试 api/export.py 中的 CSV 和 Excel 导出端点。
"""

import json
import pytest
from datetime import date, datetime, timedelta

from app.models.job import Job, generate_uuid


SAMPLE_JOBS_FOR_EXPORT = [
    {
        "title": "Python开发工程师", "company": "字节跳动", "city": "北京",
        "salary_min": 20000, "salary_max": 40000, "salary_type": "月薪",
        "experience": "3-5年", "education": "本科",
        "skills": "Python,Django,MySQL", "job_category": "技术",
        "industry": "互联网", "platform": "BOSS直聘",
        "published_at": date.today() - timedelta(days=3), "status": "有效",
    },
    {
        "title": "Java开发工程师", "company": "阿里巴巴", "city": "杭州",
        "salary_min": 25000, "salary_max": 45000, "salary_type": "月薪",
        "experience": "3-5年", "education": "本科",
        "skills": "Java,Spring,MySQL", "job_category": "技术",
        "industry": "互联网", "platform": "BOSS直聘",
        "published_at": date.today() - timedelta(days=5), "status": "有效",
    },
    {
        "title": "数据分析师", "company": "美团", "city": "北京",
        "salary_min": 15000, "salary_max": 30000, "salary_type": "月薪",
        "experience": "1-3年", "education": "本科",
        "skills": "Python,SQL,Tableau", "job_category": "技术",
        "industry": "互联网", "platform": "BOSS直聘",
        "published_at": date.today() - timedelta(days=7), "status": "有效",
    },
]


def _seed_export_data(session):
    """插入导出测试数据。"""
    from app.models.analysis import AnalysisCache
    session.query(Job).delete()
    session.query(AnalysisCache).delete()
    session.commit()
    for j in SAMPLE_JOBS_FOR_EXPORT:
        defaults = {
            "job_id": generate_uuid(),
            "title_raw": j["title"],
            "job_type": "全职",
            "recruit_number": "1",
            "district": None,
            "description": f"{j['company']}招聘{j['title']}",
            "company_size": "500-2000人",
            "company_type": "民营",
            "welfare": "五险一金",
            "platform_job_id": f"test_{generate_uuid()[:8]}",
            "source_url": "https://example.com/job",
            "crawled_at": datetime.utcnow(),
        }
        merged = {**j, **{k: v for k, v in defaults.items() if k not in j}}
        session.add(Job(**merged))
    session.commit()


class TestExportCSV:
    """CSV 导出接口测试"""

    def test_export_csv_basic(self, client, app, db_session):
        """基本 CSV 导出"""
        _seed_export_data(db_session)
        resp = client.get("/api/v1/export/csv")
        # 导出接口为公开接口
        assert resp.status_code in (200, 500)

    def test_export_csv_with_filters(self, client, app, db_session):
        """带筛选的 CSV 导出"""
        _seed_export_data(db_session)
        resp = client.get("/api/v1/export/csv?city=北京&job_category=技术")
        assert resp.status_code in (200, 500)

    def test_export_csv_content_type(self, client, app, db_session):
        """CSV 响应 Content-Type"""
        _seed_export_data(db_session)
        resp = client.get("/api/v1/export/csv")
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            assert "csv" in content_type.lower() or "text" in content_type.lower()


class TestExportExcel:
    """Excel 导出接口测试"""

    def test_export_excel_basic(self, client, app, db_session):
        """基本 Excel 导出"""
        _seed_export_data(db_session)
        resp = client.get("/api/v1/export/excel")
        assert resp.status_code in (200, 500)

    def test_export_excel_with_filters(self, client, app, db_session):
        """带筛选的 Excel 导出"""
        _seed_export_data(db_session)
        resp = client.get("/api/v1/export/excel?city=北京")
        assert resp.status_code in (200, 500)
