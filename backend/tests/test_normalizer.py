"""
字段标准化模块测试
==================
测试 FieldNormalizer 的标题、薪资、经验、学历、城市标准化。
"""

import pytest
from app.processor.normalizer import FieldNormalizer


class TestTitleNormalization:
    """标题标准化测试"""

    def test_strip_whitespace(self):
        """去除首尾空白"""
        normalizer = FieldNormalizer()
        record = {"title": "  Python开发  工程师  "}
        result = normalizer.normalize_title(record)
        assert result["title"] == "Python开发 工程师"

    def test_remove_emoji(self):
        """去除 emoji"""
        normalizer = FieldNormalizer()
        record = {"title": "AI工程师🎯🚀"}
        result = normalizer.normalize_title(record)
        assert "🎯" not in result["title"]
        assert "🚀" not in result["title"]
        assert "AI工程师" in result["title"]

    def test_normalize_brackets(self):
        """全角括号替换为半角"""
        normalizer = FieldNormalizer()
        record = {"title": "开发工程师（应届生）"}
        result = normalizer.normalize_title(record)
        assert "（" not in result["title"]
        assert "(" in result["title"]

    def test_preserve_raw_title(self):
        """保留原始标题"""
        normalizer = FieldNormalizer()
        original = "  Python工程师🎯  "
        record = {"title": original}
        result = normalizer.normalize_title(record)
        assert result["title_raw"] == original

    def test_empty_title_default(self):
        """空标题使用默认值"""
        normalizer = FieldNormalizer()
        record = {"title": ""}
        result = normalizer.normalize_title(record)
        assert result["title"] == "未知岗位"


class TestSalaryNormalization:
    """薪资标准化测试"""

    def test_k_format(self):
        """K格式解析: '15K-25K'"""
        normalizer = FieldNormalizer()
        record = {"salary": "15K-25K"}
        result = normalizer.normalize_salary(record)
        assert result["salary_min"] == 15000
        assert result["salary_max"] == 25000
        assert result["salary_type"] == "月薪"

    def test_numeric_range(self):
        """纯数字范围: '15000-25000'"""
        normalizer = FieldNormalizer()
        record = {"salary": "15000-25000"}
        result = normalizer.normalize_salary(record)
        assert result["salary_min"] == 15000
        assert result["salary_max"] == 25000
        assert result["salary_type"] == "月薪"

    def test_negotiable(self):
        """薪资面议标记"""
        normalizer = FieldNormalizer()
        record = {"salary": "薪资面议"}
        result = normalizer.normalize_salary(record)
        assert result["salary_min"] == -1
        assert result["salary_max"] == -1
        assert result["salary_type"] == "面议"

    def test_above_k(self):
        """K格式下限: '15K以上'"""
        normalizer = FieldNormalizer()
        record = {"salary": "15K以上"}
        result = normalizer.normalize_salary(record)
        assert result["salary_min"] == 15000
        assert result["salary_max"] is None
        assert result["salary_type"] == "月薪"

    def test_empty_salary(self):
        """空薪资"""
        normalizer = FieldNormalizer()
        record = {"salary": ""}
        result = normalizer.normalize_salary(record)
        assert result["salary_type"] == "面议"

    def test_year_salary_conversion(self):
        """年薪转换为月薪: '15万-25万/年'"""
        normalizer = FieldNormalizer()
        record = {"salary": "15万-25万/年"}
        result = normalizer.normalize_salary(record)
        # 15万/12 ≈ 12500, 25万/12 ≈ 20833
        assert result["salary_min"] == 12500
        assert result["salary_max"] == 20833
        assert result["salary_type"] == "月薪"

    def test_unparseable_salary(self):
        """无法解析的薪资标记未识别"""
        normalizer = FieldNormalizer()
        record = {"salary": "有竞争力的薪资"}
        result = normalizer.normalize_salary(record)
        assert result["salary_type"] == "未识别"


class TestExperienceNormalization:
    """经验标准化测试"""

    @pytest.mark.parametrize("raw,expected", [
        ("应届生", "应届生"),
        ("经验不限", "应届生"),  # "经验不限" 匹配 "应届生" 的 "经验不限" 关键词
        ("1-3年", "1-3年"),
        ("3-5年", "3-5年"),
        ("5-10年", "5-10年"),
        ("10年以上", "10年以上"),
        ("3年以上", "3-5年"),     # "3年以上" 匹配 "3年"
        ("无经验要求", "应届生"),  # "无经验" 匹配 "无经验"
    ])
    def test_experience_mapping(self, raw, expected):
        """经验要求映射正确"""
        normalizer = FieldNormalizer()
        record = {"experience": raw}
        result = normalizer.normalize_experience(record)
        assert result["experience"] == expected, (
            f"'{raw}' 应该映射为 '{expected}', 实际为 '{result['experience']}'"
        )

    def test_empty_experience_default(self):
        """空经验要求默认为不限"""
        normalizer = FieldNormalizer()
        record = {"experience": ""}
        result = normalizer.normalize_experience(record)
        assert result["experience"] == "不限"

    def test_unknown_experience_default(self):
        """无法匹配的经验要求默认为不限"""
        normalizer = FieldNormalizer()
        record = {"experience": "火星人"}
        result = normalizer.normalize_experience(record)
        assert result["experience"] == "不限"


class TestEducationNormalization:
    """学历标准化测试"""

    @pytest.mark.parametrize("raw,expected", [
        ("本科及以上", "本科"),
        ("硕士及以上", "硕士"),
        ("大专及以上", "大专"),
        ("博士", "博士"),
        ("学历不限", "不限"),
        ("中专", "不限"),  # 中专→不限
    ])
    def test_education_mapping(self, raw, expected):
        """学历要求映射正确"""
        normalizer = FieldNormalizer()
        record = {"education": raw}
        result = normalizer.normalize_education(record)
        assert result["education"] == expected


class TestCityNormalization:
    """城市标准化测试"""

    @pytest.mark.parametrize("location,district,expected", [
        ("北京", "", "北京"),
        ("北京市", "", "北京"),
        ("上海", "", "上海"),
        ("深圳", "", "深圳"),
        ("杭州", "", "杭州"),
    ])
    def test_city_variants(self, location, district, expected):
        """城市变体映射"""
        normalizer = FieldNormalizer()
        record = {"location": location, "district": district}
        result = normalizer.normalize_city(record)
        assert result["city"] == expected

    def test_district_to_city(self):
        """区名映射到城市"""
        normalizer = FieldNormalizer()
        record = {"location": "海淀区", "district": "海淀区"}
        result = normalizer.normalize_city(record)
        assert result["city"] == "北京"

    def test_unknown_city_preserved(self):
        """未知城市保留原值"""
        normalizer = FieldNormalizer()
        record = {"location": "火星", "district": ""}
        result = normalizer.normalize_city(record)
        assert result["city"] == "火星"

    def test_empty_city_default(self):
        """空城市使用默认值"""
        normalizer = FieldNormalizer()
        record = {"location": "", "district": ""}
        result = normalizer.normalize_city(record)
        assert result["city"] == "未知"


class TestFullNormalize:
    """全流程标准化测试"""

    def test_full_normalize_pipeline(self):
        """全流程标准化不报错"""
        normalizer = FieldNormalizer()
        records = [
            {
                "title": "  Python开发工程师🎯  ",
                "salary": "15K-25K",
                "experience": "3-5年",
                "education": "本科及以上",
                "location": "北京",
                "district": "海淀区",
                "company": "字节跳动",
            }
        ]
        results = normalizer.normalize(records)
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "Python开发工程师"
        assert r["salary_min"] == 15000
        assert r["salary_max"] == 25000
        assert r["experience"] == "3-5年"
        assert r["education"] == "本科"
        assert r["city"] == "北京"
