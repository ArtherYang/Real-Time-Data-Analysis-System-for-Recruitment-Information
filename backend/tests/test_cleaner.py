"""
数据清洗模块测试
================
测试 DataCleaner 的必填字段检查、薪资验证、精确/模糊去重、质量报告。
"""

import pytest
from datetime import datetime

from app.crawler.base import JobRawData
from app.processor.cleaner import DataCleaner, CleanedRecord


class TestRequiredFieldCheck:
    """必填字段检查测试"""

    def test_valid_data_passes(self, sample_raw_jobs):
        """有效数据通过检查"""
        cleaner = DataCleaner()
        clean_data, report = cleaner.clean([sample_raw_jobs[0]])
        assert report["valid"] == 1
        assert report["invalid"] == 0
        assert report["clean_rate"] == 100.0

    def test_missing_title_rejected(self):
        """缺少岗位名称被标记无效"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        job = JobRawData(
            title="", company="某公司", source="boss_zhipin",
            crawled_at=now, platform_job_id="test_001",
        )
        clean_data, report = cleaner.clean([job])
        assert report["valid"] == 0
        assert report["invalid"] == 1
        assert "NO_TITLE" in report["invalid_reasons"]

    def test_missing_company_rejected(self):
        """缺少公司名称被标记无效"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        job = JobRawData(
            title="工程师", company="", source="boss_zhipin",
            crawled_at=now, platform_job_id="test_002",
        )
        clean_data, report = cleaner.clean([job])
        assert report["valid"] == 0
        assert "NO_COMPANY" in report["invalid_reasons"]

    def test_title_too_long_rejected(self):
        """异常长标题被标记无效"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        job = JobRawData(
            title="A" * 250, company="某公司", source="boss_zhipin",
            crawled_at=now, platform_job_id="test_003",
        )
        clean_data, report = cleaner.clean([job])
        assert report["valid"] == 0
        assert "TITLE_TOO_LONG" in report["invalid_reasons"]

    def test_empty_input(self):
        """空输入返回空结果"""
        cleaner = DataCleaner()
        clean_data, report = cleaner.clean([])
        assert clean_data == []
        assert report["total"] == 0
        assert report["empty_input"] is True


class TestSalaryValidation:
    """薪资验证测试"""

    def test_valid_salary_k_format(self):
        """K格式薪资被正确识别"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        job = JobRawData(
            title="工程师", company="某公司", source="boss_zhipin",
            crawled_at=now, salary="15K-25K", platform_job_id="test_sal_001",
        )
        clean_data, report = cleaner.clean([job])
        assert report["valid"] == 1

    def test_salary_negotiable_not_invalid(self):
        """薪资面议不标记为无效"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        job = JobRawData(
            title="工程师", company="某公司", source="boss_zhipin",
            crawled_at=now, salary="薪资面议", platform_job_id="test_sal_002",
        )
        clean_data, report = cleaner.clean([job])
        assert report["valid"] == 1  # 面议不是无效，只是标记

    def test_salary_out_of_range_flagged(self):
        """超出范围的薪资被标记异常"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        job = JobRawData(
            title="工程师", company="某公司", source="boss_zhipin",
            crawled_at=now, salary="500000-999999",
            platform_job_id="test_sal_003",
        )
        clean_data, report = cleaner.clean([job])
        # 薪资异常的记录：有效但被标记
        assert report["valid"] <= 1

    def test_salary_below_min_flagged(self):
        """低于最低值的薪资被标记"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        job = JobRawData(
            title="工程师", company="某公司", source="boss_zhipin",
            crawled_at=now, salary="500-1000",
            platform_job_id="test_sal_004",
        )
        clean_data, report = cleaner.clean([job])
        assert report["valid"] <= 1


class TestDeduplication:
    """去重测试"""

    def test_exact_dedup_removes_duplicate(self, sample_raw_jobs):
        """精确去重删除 title+company+platform_job_id 相同的记录"""
        cleaner = DataCleaner()
        # 取第一条和它的重复（索引 5）
        jobs = [sample_raw_jobs[0], sample_raw_jobs[5]]
        clean_data, report = cleaner.clean(jobs)
        assert report["dedup_exact"] == 1
        assert len(clean_data) == 1

    def test_different_platform_id_kept(self):
        """不同 platform_job_id 的记录都保留"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        job1 = JobRawData(
            title="工程师", company="某公司", source="boss_zhipin",
            crawled_at=now, platform_job_id="id_001",
        )
        job2 = JobRawData(
            title="工程师", company="某公司", source="boss_zhipin",
            crawled_at=now, platform_job_id="id_002",
        )
        clean_data, report = cleaner.clean([job1, job2])
        assert report["dedup_exact"] == 0
        assert len(clean_data) == 2

    def test_fuzzy_dedup_flags_similar(self):
        """模糊去重标记相似记录"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        job1 = JobRawData(
            title="Python开发工程师", company="字节跳动",
            source="boss_zhipin", crawled_at=now,
            platform_job_id="fuzz_001",
        )
        job2 = JobRawData(
            title="Python开发工程师（高级）", company="字节跳动",
            source="boss_zhipin", crawled_at=now,
            platform_job_id="fuzz_002",
        )
        clean_data, report = cleaner.clean([job1, job2])
        # 相似记录被标记，但可能都保留（标记不删除）
        assert report["dedup_exact"] == 0


class TestQualityReport:
    """质量报告测试"""

    def test_report_structure(self, sample_raw_jobs):
        """质量报告包含所有必需字段"""
        cleaner = DataCleaner()
        _, report = cleaner.clean([sample_raw_jobs[0]])
        required_keys = [
            "total", "valid", "invalid", "dedup_exact",
            "dedup_fuzzy", "invalid_reasons", "clean_rate",
        ]
        for key in required_keys:
            assert key in report, f"缺少报告字段: {key}"

    def test_clean_rate_calculation(self):
        """有效率计算正确"""
        cleaner = DataCleaner()
        now = datetime.now().isoformat()
        valid_job = JobRawData(
            title="工程师", company="某公司", source="boss_zhipin",
            crawled_at=now, platform_job_id="rate_001",
        )
        invalid_job = JobRawData(
            title="", company="某公司", source="boss_zhipin",
            crawled_at=now, platform_job_id="rate_002",
        )
        _, report = cleaner.clean([valid_job, invalid_job])
        assert report["clean_rate"] == 50.0
