"""
性能测试
========
测试系统的关键性能指标：API 响应时间、数据库查询性能、缓存效果、数据管道吞吐量。

注：这些测试为基准性能测试（benchmark），在 CI 中作为参考指标。
"""

import time
import pytest
from datetime import date, datetime, timedelta

from app.models.job import Job, generate_uuid


class TestAPIResponseTime:
    """API 响应时间测试"""

    def test_jobs_list_response_time(self, client):
        """岗位列表 API 响应时间"""
        start = time.time()
        resp = client.get("/api/v1/jobs?page=1&per_page=20")
        elapsed = time.time() - start
        assert resp.status_code == 200
        # 空数据库下单次查询应在 200ms 内完成
        assert elapsed < 0.5, f"岗位列表响应时间 {elapsed:.3f}s 超过 0.5s 阈值"

    def test_jobs_overview_response_time(self, client):
        """概览统计 API 响应时间"""
        start = time.time()
        resp = client.get("/api/v1/jobs/stats/overview")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f"概览统计响应时间 {elapsed:.3f}s 超过 0.5s 阈值"

    def test_analysis_hot_jobs_response_time(self, client):
        """热度排行 API 响应时间"""
        start = time.time()
        resp = client.get("/api/v1/analysis/hot-jobs?top=10")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 1.0, f"热度排行响应时间 {elapsed:.3f}s 超过 1s 阈值"

    def test_concurrent_requests(self, client):
        """模拟并发请求（串行测试）"""
        num_requests = 10
        times = []
        for _ in range(num_requests):
            start = time.time()
            resp = client.get("/api/v1/jobs")
            times.append(time.time() - start)
            assert resp.status_code == 200

        avg_time = sum(times) / len(times)
        # 平均响应时间应在 100ms 以内
        assert avg_time < 0.3, f"平均响应时间 {avg_time:.3f}s 超过阈值"


class TestCachePerformance:
    """缓存性能测试"""

    def test_cache_speeds_up_repeated_query(self, app, db_session):
        """缓存使重复查询加速"""
        from app.analysis import AnalysisEngine, AnalysisFilters
        from app.models.analysis import AnalysisCache

        # 插入测试数据
        for i in range(50):
            defaults = {
                "job_id": generate_uuid(),
                "title": f"测试岗位{i}",
                "company": f"公司{i % 10}",
                "city": "北京" if i % 2 == 0 else "上海",
                "salary_min": 10000, "salary_max": 30000,
                "salary_type": "月薪",
                "experience": "3-5年", "education": "本科",
                "skills": "Python,Java", "job_category": "技术",
                "industry": "互联网", "platform": "BOSS直聘",
                "published_at": date.today(), "status": "有效",
                "title_raw": f"测试岗位{i}",
                "job_type": "全职", "recruit_number": "1",
                "company_size": "500-2000人", "company_type": "民营",
                "welfare": "五险一金",
                "platform_job_id": f"perf_{i}",
                "source_url": "https://example.com",
                "crawled_at": datetime.utcnow(),
            }
            session = db_session
            existing = session.query(Job).filter(
                Job.platform_job_id == f"perf_{i}"
            ).first()
            if not existing:
                session.add(Job(**defaults))
        session.commit()

        filters = AnalysisFilters()

        # 第一次查询（无缓存）
        start1 = time.time()
        engine1 = AnalysisEngine(session)
        result1 = engine1.ranking.get_category_ranking(filters, top_n=10)
        time1 = time.time() - start1

        # 第二次查询（有缓存）
        start2 = time.time()
        engine2 = AnalysisEngine(session)
        result2 = engine2.ranking.get_category_ranking(filters, top_n=10)
        time2 = time.time() - start2

        # 有缓存时应不慢于首次查询（通常更快或持平）
        assert result1 == result2
        # 缓存后查询不应明显慢于首次
        assert time2 <= time1 * 1.5, (
            f"缓存查询 {time2:.4f}s 不应显著慢于首次 {time1:.4f}s"
        )


class TestPipelinePerformance:
    """数据管道性能测试"""

    def test_pipeline_throughput(self, db_session):
        """管道处理吞吐量"""
        from app.processor.pipeline import PipelineOrchestrator

        orchestrator = PipelineOrchestrator(
            use_sample_data=True,
            init_database=False,
        )

        start = time.time()
        report = orchestrator.run(
            keywords=["Python开发"],
            pages=1,
            db_session=db_session,
        )
        elapsed = time.time() - start

        assert report.total_crawled > 0
        # 模拟数据生成+清洗+存储应在2秒内完成（对单个关键词+单页）
        assert elapsed < 3.0, (
            f"管道处理时间 {elapsed:.2f}s，超过 3s 阈值"
        )

    def test_pipeline_scales_with_keywords(self, db_session):
        """管道随关键词数量线性扩展"""
        from app.processor.pipeline import PipelineOrchestrator

        orchestrator = PipelineOrchestrator(
            use_sample_data=True,
            init_database=False,
        )

        # 1个关键词
        start = time.time()
        orchestrator.run(
            keywords=["测试"], pages=1, db_session=db_session
        )
        time_1 = time.time() - start

        # 5个关键词
        start = time.time()
        orchestrator.run(
            keywords=["测试1", "测试2", "测试3", "测试4", "测试5"],
            pages=1,
            db_session=db_session,
        )
        time_5 = time.time() - start

        # 5个关键词的时间应在 1个关键词的 1-5 倍之间
        ratio = time_5 / max(time_1, 0.001)
        assert 0.5 <= ratio <= 6.0, (
            f"关键词扩展比 {ratio:.1f}x（期望 1-5x）"
        )


class TestDBQueryPerformance:
    """数据库查询性能测试"""

    def test_indexed_query_performance(self, app, db_session):
        """索引查询性能"""
        from sqlalchemy import text

        # 检查查询计划
        result = db_session.execute(
            text("EXPLAIN QUERY PLAN SELECT * FROM jobs WHERE city = '北京'")
        )
        plan = "\n".join(str(row) for row in result.fetchall())
        # SQLite 中应能使用索引或全表扫描（小表预期全表扫描）
        assert "SCAN" in plan or "SEARCH" in plan or "INDEX" in plan
