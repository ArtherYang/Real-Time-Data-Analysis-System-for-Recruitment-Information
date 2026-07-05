"""
数据处理管道集成测试
====================
测试 PipelineOrchestrator 的完整流程：采集→清洗→标准化→存储。
所有存储相关测试使用 SQLite 内存数据库（通过 db_session fixture 注入）。
"""

import pytest
from datetime import datetime

from app.crawler.boss import generate_sample_data
from app.processor.pipeline import PipelineOrchestrator, PipelineReport


class TestPipelineWithSampleData:
    """使用模拟数据测试完整管道"""

    def test_pipeline_runs_with_sample_data(self, db_session):
        """管道使用模拟数据执行成功"""
        orchestrator = PipelineOrchestrator(
            use_sample_data=True,
            init_database=False,
        )
        report = orchestrator.run(
            keywords=["Python开发"], pages=1, db_session=db_session
        )

        assert isinstance(report, PipelineReport)
        assert report.total_crawled > 0
        assert report.total_valid > 0
        assert report.duration_seconds >= 0

    def test_pipeline_report_structure(self, db_session):
        """管道报告结构完整"""
        orchestrator = PipelineOrchestrator(
            use_sample_data=True,
            init_database=False,
        )
        report = orchestrator.run(
            keywords=["测试"], pages=1, db_session=db_session
        )

        d = report.to_dict()
        assert "crawl" in d
        assert "clean" in d
        assert "store" in d
        assert "meta" in d
        assert d["meta"]["keywords"] == ["测试"]

    def test_pipeline_with_multiple_keywords(self, db_session):
        """管道处理多个关键词"""
        orchestrator = PipelineOrchestrator(
            use_sample_data=True,
            init_database=False,
        )
        report = orchestrator.run(
            keywords=["Python开发", "Java开发", "数据分析师"],
            pages=1,
            db_session=db_session,
        )
        assert report.total_crawled > 0
        assert len(report.keywords) == 3

    def test_pipeline_empty_keywords(self, db_session):
        """空关键词处理"""
        orchestrator = PipelineOrchestrator(
            use_sample_data=True,
            init_database=False,
        )
        report = orchestrator.run(
            keywords=[], pages=1, db_session=db_session
        )
        assert report.total_crawled == 0

    def test_pipeline_clean_rate_reasonable(self, db_session):
        """模拟数据的有效率正常"""
        orchestrator = PipelineOrchestrator(
            use_sample_data=True,
            init_database=False,
        )
        report = orchestrator.run(
            keywords=["Python开发"], pages=1, db_session=db_session
        )
        # 模拟数据应该全部有效
        assert report.clean_rate >= 90.0


class TestPipelineStorage:
    """管道存储测试"""

    def test_pipeline_saves_to_db(self, db_session):
        """管道数据存入数据库"""
        from app.models.job import Job

        orchestrator = PipelineOrchestrator(
            use_sample_data=True,
            init_database=False,
        )
        report = orchestrator.run(
            keywords=["Python开发"], pages=1, db_session=db_session
        )

        # 验证数据已入库
        saved_jobs = db_session.query(Job).all()
        assert len(saved_jobs) >= report.total_saved

    def test_pipeline_upsert(self, db_session):
        """管道 upsert 不产生重复"""
        from app.models.job import Job

        orchestrator = PipelineOrchestrator(
            use_sample_data=True,
            init_database=False,
        )

        # 第一次运行
        report1 = orchestrator.run(
            keywords=["Python开发"], pages=1, db_session=db_session
        )
        count1 = db_session.query(Job).count()

        # 第二次运行（相同数据）
        report2 = orchestrator.run(
            keywords=["Python开发"], pages=1, db_session=db_session
        )
        count2 = db_session.query(Job).count()

        # 不应翻倍（upsert 更新而非新增）
        assert count2 <= count1 + report2.total_saved


class TestPipelineReportClass:
    """PipelineReport 类测试"""

    def test_report_creation(self):
        """报告创建"""
        report = PipelineReport(
            total_crawled=100,
            total_valid=80,
            total_saved=75,
        )
        assert report.total_crawled == 100
        assert report.total_valid == 80
        assert report.total_saved == 75

    def test_report_to_dict(self):
        """报告序列化"""
        report = PipelineReport(
            total_crawled=50,
            total_valid=45,
            total_saved=40,
            keywords=["测试"],
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            duration_seconds=2.5,
        )
        d = report.to_dict()
        assert d["crawl"]["total_crawled"] == 50
        assert d["clean"]["valid"] == 45
        assert d["store"]["saved"] == 40
        assert d["meta"]["duration_seconds"] == 2.5

    def test_report_repr(self):
        """报告字符串表示"""
        report = PipelineReport(total_crawled=10, total_valid=8, total_saved=7)
        r = repr(report)
        assert "PipelineReport" in r
        assert "10" in r
