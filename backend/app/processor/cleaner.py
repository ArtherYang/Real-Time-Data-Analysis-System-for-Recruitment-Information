"""
数据清洗与去重模块
==================
功能：对爬虫采集的原始岗位数据进行清洗、校验和去重。
      确保进入分析管道的数据达到基础质量标准。
输入：List[JobRawData] — 原始爬虫输出
输出：Tuple[List[dict], dict] — 清洗后数据 + 质量报告

清洗流程（按顺序执行）：
  1. 必填字段检查 → 标记无效记录（title/company/source/crawled_at）
  2. 薪资范围验证 → 标记异常薪资
  3. 精确去重 → 基于 (title + company + platform_job_id) 删除重复
  4. 模糊去重 → 基于 difflib 文本相似度标记疑似重复（不删除）

使用方式：
    from app.processor.cleaner import DataCleaner

    cleaner = DataCleaner()
    clean_data, report = cleaner.clean(raw_jobs)
    print(f"有效率: {report['clean_rate']:.1%}")
"""

import re
from difflib import SequenceMatcher
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field

from loguru import logger

from app.crawler.base import JobRawData
from app.config import default_config as config


@dataclass
class CleanedRecord:
    """清洗后的中间数据记录。

    保留原始字段，附加清洗状态标记。
    """

    data: dict  # 从 JobRawData 转换的字典
    is_valid: bool = True
    quality_flag: Optional[str] = None  # 质量标记: NO_TITLE / NO_COMPANY / SALARY_ANOMALY / FUZZY_DUP
    quality_note: Optional[str] = None  # 详细说明


class DataCleaner:
    """数据清洗器。

    对原始爬虫数据进行多阶段清洗，生成质量报告。

    使用示例:
        cleaner = DataCleaner()
        clean_data, report = cleaner.clean(raw_jobs)
        # clean_data: List[dict] — 有效且去重后的数据
        # report: dict — 包含 total, valid, invalid, dedup_exact 等统计
    """

    def __init__(self, salary_min: int = None, salary_max: int = None):
        """初始化清洗器。

        Args:
            salary_min: 合法最低月薪（元），默认从 config 读取
            salary_max: 合法最高月薪（元），默认从 config 读取
        """
        self.salary_min = salary_min or config.SALARY_MIN_VALID
        self.salary_max = salary_max or config.SALARY_MAX_VALID
        self.required_fields = ["title", "company", "source", "crawled_at"]
        self.fuzzy_threshold = config.FUZZY_DEDUP_THRESHOLD

    def clean(
        self, raw_data: List[JobRawData]
    ) -> Tuple[List[dict], dict]:
        """执行完整的数据清洗流程。

        流程顺序：
        1. JobRawData -> CleanedRecord 转换
        2. 必填字段校验
        3. 薪资范围验证
        4. 精确去重（删除重复项）
        5. 模糊去重（标记疑似重复）

        Args:
            raw_data: 原始爬虫数据列表

        Returns:
            Tuple[List[dict], dict]:
                - 清洗后的有效数据字典列表
                - 质量报告字典
        """
        total_count = len(raw_data)
        logger.info(f"[清洗] 开始处理 {total_count} 条原始数据")

        if total_count == 0:
            return [], {"total": 0, "valid": 0, "empty_input": True}

        # Step 1: 转换为中间记录
        records = [self._to_cleaned(r) for r in raw_data]

        # Step 2: 必填字段检查
        for rec in records:
            self._check_required_fields(rec)

        # Step 3: 薪资范围验证
        for rec in records:
            self._validate_salary(rec)

        # Step 4: 精确去重
        records, exact_dedup_count = self._exact_dedup(records)

        # Step 5: 模糊去重（仅对有效记录）
        valid_records = [r for r in records if r.is_valid]
        valid_records, fuzzy_dedup_count = self._fuzzy_dedup(valid_records)

        # 统计报告
        invalid_reasons = {}
        for rec in records:
            if rec.quality_flag and "DUP" not in rec.quality_flag:
                reason = rec.quality_flag
                invalid_reasons[reason] = invalid_reasons.get(reason, 0) + 1

        valid_data = [
            r.data for r in valid_records if r.is_valid
        ]
        report = {
            "total": total_count,
            "valid": len(valid_data),
            "invalid": total_count - len(valid_data),
            "dedup_exact": exact_dedup_count,
            "dedup_fuzzy": fuzzy_dedup_count,
            "invalid_reasons": invalid_reasons,
            "clean_rate": (
                round(len(valid_data) / total_count * 100, 2)
                if total_count > 0
                else 0.0
            ),
        }

        logger.info(
            f"[清洗] 完成: 总计{total_count}, 有效{report['valid']}, "
            f"精确去重{exact_dedup_count}, 模糊去重{fuzzy_dedup_count}, "
            f"有效率{report['clean_rate']:.1f}%"
        )
        return valid_data, report

    # ======================== 内部方法 ========================

    @staticmethod
    def _to_cleaned(raw: JobRawData) -> CleanedRecord:
        """将 JobRawData dataclass 转换为 CleanedRecord。

        Args:
            raw: 原始爬虫数据

        Returns:
            CleanedRecord: 中间记录
        """
        return CleanedRecord(data={
            "title": raw.title,
            "company": raw.company,
            "source": raw.source,
            "crawled_at": raw.crawled_at,
            "salary": raw.salary,
            "location": raw.location,
            "district": raw.district,
            "experience": raw.experience,
            "education": raw.education,
            "job_type": raw.job_type,
            "recruit_number": raw.recruit_number,
            "industry": raw.industry,
            "job_category": raw.job_category,
            "skills": raw.skills,
            "company_size": raw.company_size,
            "company_type": raw.company_type,
            "welfare": raw.welfare,
            "description": raw.description,
            "platform_job_id": raw.platform_job_id,
            "source_url": raw.source_url,
            "published_at": raw.published_at,
        })

    def _check_required_fields(self, record: CleanedRecord) -> None:
        """检查必填字段是否为空。

        标记规则：
        - title 为空 → NO_TITLE
        - company 为空 → NO_COMPANY
        - source 或 crawled_at 为空 → MISSING_META

        Args:
            record: 待检查的清洗记录
        """
        data = record.data

        if not data.get("title") or not str(data["title"]).strip():
            record.is_valid = False
            record.quality_flag = "NO_TITLE"
            record.quality_note = "岗位名称为空"
            return

        if not data.get("company") or not str(data["company"]).strip():
            record.is_valid = False
            record.quality_flag = "NO_COMPANY"
            record.quality_note = "公司名称为空"
            return

        if not data.get("source"):
            record.is_valid = False
            record.quality_flag = "MISSING_META"
            record.quality_note = "缺少数据来源标识"
            return

        if not data.get("crawled_at"):
            record.is_valid = False
            record.quality_flag = "MISSING_META"
            record.quality_note = "缺少采集时间"
            return

        # 标题长度异常检查
        title = str(data["title"])
        if len(title) > 200:
            record.is_valid = False
            record.quality_flag = "TITLE_TOO_LONG"
            record.quality_note = f"岗位名称过长 ({len(title)} 字符)"
            return

        # 公司名长度异常检查
        company = str(data["company"])
        if len(company) > 100:
            record.is_valid = False
            record.quality_flag = "COMPANY_TOO_LONG"
            record.quality_note = f"公司名称过长 ({len(company)} 字符)"
            return

    def _validate_salary(self, record: CleanedRecord) -> None:
        """验证薪资字段的合理性。

        只标记异常，不将记录设为无效（因为薪资面议等是合法场景）。

        标记规则：
        - salary 为空或"薪资面议" → SALARY_NEGOTIABLE（不标记无效）
        - 解析后超出合理范围 → SALARY_ANOMALY
        - 无法解析 → SALARY_UNPARSEABLE

        注意：如果记录已被 _check_required_fields 标记为无效，
        则跳过薪资验证（保留原始标记如 NO_TITLE/NO_COMPANY）。

        Args:
            record: 待检查的清洗记录
        """
        # 已被必填字段检查标记为无效的记录，不覆盖其标记
        if record.quality_flag:
            return

        salary = record.data.get("salary")
        if not salary:
            record.quality_flag = "SALARY_NEGOTIABLE"
            record.quality_note = "薪资未提供（可能为面议）"
            return

        salary_str = str(salary).strip()

        # 面议/薪资面议
        if salary_str in ("薪资面议", "面议", "面谈", "Negotiable"):
            record.quality_flag = "SALARY_NEGOTIABLE"
            record.quality_note = "薪资面议"
            return

        # 尝试解析薪资范围
        salary_min, salary_max = self._parse_salary(salary_str)

        if salary_min is None and salary_max is None:
            # 无法解析，标记但不设无效
            if not record.quality_flag:
                record.quality_flag = "SALARY_UNPARSEABLE"
                record.quality_note = f"无法解析薪资格式: '{salary_str}'"
            return

        # 范围合理性检查
        if salary_min is not None:
            if salary_min < self.salary_min:
                record.quality_flag = "SALARY_ANOMALY"
                record.quality_note = (
                    f"最低薪资 {salary_min}元 低于合理下限{self.salary_min}元"
                )
                return
            if salary_min > self.salary_max:
                record.quality_flag = "SALARY_ANOMALY"
                record.quality_note = (
                    f"最低薪资 {salary_min}元 超出合理上限{self.salary_max}元"
                )
                return

        if salary_max is not None:
            if salary_max > self.salary_max:
                record.quality_flag = "SALARY_ANOMALY"
                record.quality_note = (
                    f"最高薪资 {salary_max}元 超出合理上限{self.salary_max}元"
                )
                return

    @staticmethod
    def _parse_salary(salary_str: str) -> Tuple[Optional[int], Optional[int]]:
        """解析薪资字符串为数值范围。

        支持格式：
        - "15K-25K" / "15k-25k"
        - "15000-25000" / "15000-25000元"
        - "15K以上" / "15K起"
        - "15000以上" / "15000-"
        - "15万-25万/年"（暂不处理年薪，后续迭代）

        Args:
            salary_str: 薪资字符串

        Returns:
            Tuple[Optional[int], Optional[int]]: (最低月薪, 最高月薪)，
                                                  无法解析时返回 (None, None)
        """
        if not salary_str:
            return None, None

        s = salary_str.strip().upper().replace(" ", "")

        # 移除单位后缀: 元, /月, /年
        s = re.sub(r"元.*$", "", s)
        s = re.sub(r"/[月年].*$", "", s)

        # 处理 "万" 单位: "1.5万" -> 15000
        wan_pattern = re.match(
            r"^([\d.]+)万\s*[-~至]\s*([\d.]+)万", s
        )
        if wan_pattern:
            lo = int(float(wan_pattern.group(1)) * 10000)
            hi = int(float(wan_pattern.group(2)) * 10000)
            return lo, hi

        # 处理 "K" 单位: "15K-25K"
        k_pattern = re.match(r"^([\d.]+)K[-~至]+([\d.]+)K$", s)
        if k_pattern:
            lo = int(float(k_pattern.group(1)) * 1000)
            hi = int(float(k_pattern.group(2)) * 1000)
            return lo, hi

        # 处理纯数字范围: "15000-25000"
        num_pattern = re.match(r"^(\d+)[-~至]+(\d+)$", s)
        if num_pattern:
            lo = int(num_pattern.group(1))
            hi = int(num_pattern.group(2))
            return lo, hi

        # 处理 "15K以上" / "15K起"
        above_k = re.match(r"^([\d.]+)K(以上|起|\+)?$", s)
        if above_k:
            lo = int(float(above_k.group(1)) * 1000)
            return lo, None

        # 处理 "15000以上"
        above_num = re.match(r"^(\d+)(以上|起|\+)?$", s)
        if above_num:
            lo = int(above_num.group(1))
            return lo, None

        return None, None

    def _exact_dedup(
        self, records: List[CleanedRecord]
    ) -> Tuple[List[CleanedRecord], int]:
        """精确去重：基于 (title + company + platform_job_id) 复合键。

        规则：同一复合键保留第一条（crawled_at 最早的），其余标记删除。

        Args:
            records: 清洗记录列表

        Returns:
            Tuple[List[CleanedRecord], int]: 去重后的记录列表 + 删除数量
        """
        seen = {}
        deduped = []
        removed_count = 0

        for rec in records:
            title = rec.data.get("title", "")
            company = rec.data.get("company", "")
            pid = rec.data.get("platform_job_id", "")
            key = f"{title}|{company}|{pid}"

            if key in seen:
                removed_count += 1
                logger.debug(f"[去重-精确] 删除重复: {key}")
                continue

            seen[key] = True
            deduped.append(rec)

        if removed_count > 0:
            logger.info(f"[去重-精确] 删除 {removed_count} 条重复记录")

        return deduped, removed_count

    def _fuzzy_dedup(
        self, records: List[CleanedRecord]
    ) -> Tuple[List[CleanedRecord], int]:
        """模糊去重：使用 difflib.SequenceMatcher 检测相似记录。

        对 (title + company) 组合计算文本相似度。
        超过阈值（默认 0.85）的记录标记为 FUZZY_DUP，不删除。

        复杂度：O(n²)，对大批量数据建议分批处理。

        Args:
            records: 有效清洗记录列表

        Returns:
            Tuple[List[CleanedRecord], int]: 标记后的记录列表 + 疑似重复数
        """
        if len(records) < 2:
            return records, 0

        flagged_count = 0
        n = len(records)

        for i in range(n):
            if records[i].quality_flag == "FUZZY_DUP":
                continue  # 已被标记的跳过

            text_i = (
                f"{records[i].data.get('title', '')}"
                f"|{records[i].data.get('company', '')}"
            )

            for j in range(i + 1, n):
                if records[j].quality_flag == "FUZZY_DUP":
                    continue

                text_j = (
                    f"{records[j].data.get('title', '')}"
                    f"|{records[j].data.get('company', '')}"
                )

                similarity = SequenceMatcher(
                    None, text_i, text_j
                ).ratio()

                if similarity >= self.fuzzy_threshold:
                    # 标记后者为疑似重复
                    records[j].quality_flag = "FUZZY_DUP"
                    records[j].quality_note = (
                        f"与 '{records[i].data.get('title')}' "
                        f"({records[i].data.get('company')}) "
                        f"相似度 {similarity:.2%}，标记为疑似重复"
                    )
                    flagged_count += 1

        if flagged_count > 0:
            logger.info(
                f"[去重-模糊] 标记 {flagged_count} 条疑似重复 "
                f"(阈值={self.fuzzy_threshold})"
            )

        return records, flagged_count
