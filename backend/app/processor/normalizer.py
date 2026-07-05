"""
字段标准化模块
==============
功能：对不同平台采集的岗位数据进行字段标准化，统一为系统标准格式。
      支持跨平台对比分析的数据基础。
输入：List[dict] — 清洗后的岗位数据字典列表
输出：List[dict] — 标准化后的数据字典（可直接映射到 Job ORM）

标准化维度：
  1. 岗位名称 — 去特殊字符、去emoji、统一空格
  2. 薪资 — 解析为 salary_min / salary_max（int, 元/月）
  3. 经验要求 — 映射到标准桶
  4. 学历要求 — 映射到标准桶
  5. 城市 — 统一为地级市名

使用方式：
    from app.processor.normalizer import FieldNormalizer

    normalizer = FieldNormalizer()
    normalized = normalizer.normalize(clean_data)
"""

import re
from typing import List, Dict, Optional
from loguru import logger


class FieldNormalizer:
    """字段标准化器。

    将不同平台的异构字段格式统一为系统标准格式。

    使用示例:
        normalizer = FieldNormalizer()
        result = normalizer.normalize(clean_data)
        # result 可传给 Job.from_normalized() 入库
    """

    # ======================== 经验要求映射表 ========================
    # 格式：标准值 → [匹配关键词列表]
    EXPERIENCE_MAP: Dict[str, List[str]] = {
        "应届生": [
            "应届", "应届生", "毕业生", "应届毕业生",
            "无经验", "经验不限", "不限经验", "无需经验",
            "在校/应届", "实习",
        ],
        "1-3年": [
            "1年", "1-3年", "1-3", "1年经验", "1-2年",
            "2年", "2年以上", "1-3年经验", "一年",
        ],
        "3-5年": [
            "3-5年", "3-5", "3年", "3年以上", "3-5年经验",
            "3-4年", "4年", "3年及以上", "三年",
        ],
        "5-10年": [
            "5-10年", "5-10", "5年以上", "5年", "5-10年经验",
            "5-7年", "7年", "8年", "8年以上", "5年及以上",
            "五年", "8-10年",
        ],
        "10年以上": [
            "10年", "10年以上", "十年", "10年及以上",
            "10-15年", "15年",
        ],
    }

    # ======================== 学历要求映射表 ========================
    EDUCATION_MAP: Dict[str, List[str]] = {
        "不限": [
            "学历不限", "不限", "无学历要求", "学历无要求",
            "初中及以下", "高中", "中专", "中技",
        ],
        "大专": [
            "大专", "专科", "大专及以上", "专科及以上",
            "大专以上",
        ],
        "本科": [
            "本科", "本科及以上", "本科以上", "大学本科",
            "统招本科",
        ],
        "硕士": [
            "硕士", "硕士及以上", "硕士研究生", "研究生",
            "统招硕士",
        ],
        "博士": [
            "博士", "博士研究生", "博士及以上", "博士以上",
        ],
    }

    # ======================== 城市标准化映射表 ========================
    # 格式：标准城市名 → [可能的变体]
    CITY_MAP: Dict[str, List[str]] = {
        "北京": ["北京", "北京市", "bj", "beijing"],
        "上海": ["上海", "上海市", "sh", "shanghai"],
        "深圳": ["深圳", "深圳市", "sz", "shenzhen"],
        "广州": ["广州", "广州市", "gz", "guangzhou"],
        "杭州": ["杭州", "杭州市", "hz", "hangzhou"],
        "成都": ["成都", "成都市", "cd", "chengdu"],
        "南京": ["南京", "南京市", "nj", "nanjing"],
        "武汉": ["武汉", "武汉市", "wh", "wuhan"],
        "西安": ["西安", "西安市", "xa", "xian"],
        "重庆": ["重庆", "重庆市", "cq", "chongqing"],
        "苏州": ["苏州", "苏州市"],
        "天津": ["天津", "天津市"],
        "长沙": ["长沙", "长沙市"],
        "合肥": ["合肥", "合肥市"],
        "郑州": ["郑州", "郑州市"],
        "厦门": ["厦门", "厦门市"],
        "东莞": ["东莞", "东莞市"],
        "青岛": ["青岛", "青岛市"],
        "大连": ["大连", "大连市"],
        "济南": ["济南", "济南市"],
        "福州": ["福州", "福州市"],
        "无锡": ["无锡", "无锡市"],
        "宁波": ["宁波", "宁波市"],
        "佛山": ["佛山", "佛山市"],
    }

    # ======================== 区到市的映射 ========================
    DISTRICT_TO_CITY: Dict[str, str] = {
        "朝阳区": "北京", "海淀区": "北京", "西城区": "北京",
        "东城区": "北京", "丰台区": "北京", "昌平区": "北京",
        "大兴区": "北京", "通州区": "北京", "顺义区": "北京",
        "浦东新区": "上海", "徐汇区": "上海", "静安区": "上海",
        "黄浦区": "上海", "长宁区": "上海", "杨浦区": "上海",
        "闵行区": "上海", "宝山区": "上海", "嘉定区": "上海",
        "南山区": "深圳", "福田区": "深圳", "宝安区": "深圳",
        "龙华区": "深圳", "龙岗区": "深圳", "罗湖区": "深圳",
        "西湖区": "杭州", "滨江区": "杭州", "余杭区": "杭州",
        "上城区": "杭州", "拱墅区": "杭州", "萧山区": "杭州",
        "天河区": "广州", "海珠区": "广州", "越秀区": "广州",
        "武侯区": "成都", "高新区": "成都", "天府新区": "成都",
        "江宁区": "南京", "鼓楼区": "南京", "建邺区": "南京",
        "洪山区": "武汉", "武昌区": "武汉", "江岸区": "武汉",
    }

    def normalize(self, data_list: List[dict]) -> List[dict]:
        """执行完整的字段标准化流程。

        对每条记录依次进行：标题 → 薪资 → 经验 → 学历 → 城市 标准化。

        Args:
            data_list: 清洗后的数据字典列表

        Returns:
            List[dict]: 标准化后的数据字典列表
        """
        logger.info(f"[标准化] 开始处理 {len(data_list)} 条数据")

        result = []
        failed_count = 0

        for i, record in enumerate(data_list):
            try:
                record = self.normalize_title(record)
                record = self.normalize_salary(record)
                record = self.normalize_experience(record)
                record = self.normalize_education(record)
                record = self.normalize_city(record)
                result.append(record)
            except Exception as e:
                logger.warning(f"[标准化] 第{i}条记录处理异常: {e}")
                failed_count += 1
                # 保留原始记录不变
                result.append(record)

        logger.info(
            f"[标准化] 完成: 成功{len(result) - failed_count}, "
            f"失败{failed_count}"
        )
        return result

    # ======================== 标题标准化 ========================

    @staticmethod
    def normalize_title(record: dict) -> dict:
        """标准化岗位名称。

        处理内容：
        - 去除首尾空白字符
        - 将连续多个空格合并为单个
        - 移除 emoji 和特殊 Unciode 字符
        - 保留斜杠分隔的多岗位名（如 "Java/Python开发"）

        Args:
            record: 岗位数据字典

        Returns:
            dict: 标准化后的字典（含 title_raw 原始标题）
        """
        title = record.get("title", "")

        # 保留原始标题
        record["title_raw"] = title

        if not title:
            record["title"] = "未知岗位"
            return record

        # 去除首尾空白
        title = title.strip()

        # 合并连续空格
        title = re.sub(r"\s+", " ", title)

        # 移除常见 emoji 和特殊符号（避免误删中文）
        # 使用安全的 Unicode 范围，不覆盖 CJK 区间 (U+4E00-U+9FFF)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # 表情符号 (Emoticons)
            "\U0001F300-\U0001F5FF"  # 杂项符号与象形 (Misc Symbols)
            "\U0001F680-\U0001F6FF"  # 交通与地图 (Transport)
            "\U0001F1E0-\U0001F1FF"  # 旗帜 (Flags)
            "\U0001F900-\U0001F9FF"  # 补充符号与象形 (Supplemental)
            "\U0001FA00-\U0001FA6F"  # 象棋符号
            "\U0001FA70-\U0001FAFF"  # 扩展A符号
            "\U00002702-\U000027B0"  # 装饰符号 (Dingbats)
            "\U00002600-\U000026FF"  # 杂项符号
            "\U0000FE00-\U0000FE0F"  # 变体选择器 (Variation Selectors)
            "\U0000200D"             # 零宽连字 (ZWJ)
            "]+",
            flags=re.UNICODE,
        )
        title = emoji_pattern.sub("", title)

        # 标准化常见变体
        title = title.replace("（", "(").replace("）", ")")
        title = title.replace("【", "[").replace("】", "]")

        record["title"] = title or "未知岗位"
        return record

    # ======================== 薪资标准化 ========================

    def normalize_salary(self, record: dict) -> dict:
        """标准化薪资字段。

        将各种薪资格式统一解析为：
        - salary_min: int — 最低月薪（元），面议为 -1
        - salary_max: int — 最高月薪（元），面议为 -1
        - salary_type: str — "月薪" / "面议" / "未识别"

        支持格式：
        - "15K-25K" → (15000, 25000)
        - "15000-25000元" → (15000, 25000)
        - "薪资面议" → (-1, -1), type="面议"
        - "15K以上" → (15000, None)

        Args:
            record: 岗位数据字典

        Returns:
            dict: 标准化后的字典
        """
        salary_str = record.get("salary", "")

        # 默认值
        record["salary_min"] = None
        record["salary_max"] = None
        record["salary_type"] = "未识别"

        if not salary_str:
            record["salary_type"] = "面议"
            return record

        s = str(salary_str).strip()

        # 面议/面谈
        if s in ("薪资面议", "面议", "面谈", "待遇面议"):
            record["salary_min"] = -1
            record["salary_max"] = -1
            record["salary_type"] = "面议"
            return record

        # 标准化字符串格式
        s_norm = s.upper().replace(" ", "").replace("—", "-").replace("~", "-")

        # ---- 年薪格式: "15万-25万/年" ----
        year_match = re.match(
            r"^([\d.]+)万\s*[-~至]\s*([\d.]+)万.*年", s_norm
        )
        if year_match:
            lo = int(float(year_match.group(1)) * 10000 / 12)
            hi = int(float(year_match.group(2)) * 10000 / 12)
            record["salary_min"] = lo
            record["salary_max"] = hi
            record["salary_type"] = "月薪"  # 换算为月薪
            return record

        # ---- "万/月" 范围: "1-1.5万/月" / "0.8-1.2万/月" ----
        wan_month_range = re.match(
            r"^([\d.]+)\s*[-~至]\s*([\d.]+)万.*月", s_norm
        )
        if wan_month_range:
            lo = int(float(wan_month_range.group(1)) * 10000)
            hi = int(float(wan_month_range.group(2)) * 10000)
            record["salary_min"] = lo
            record["salary_max"] = hi
            record["salary_type"] = "月薪"
            return record

        # ---- "20-40k" / "20-40k·15薪" 格式 (单K在末尾) ----
        k_single = re.match(r"^([\d.]+)\s*[-~至]\s*([\d.]+)K", s_norm)
        if k_single:
            lo = int(float(k_single.group(1)) * 1000)
            hi = int(float(k_single.group(2)) * 1000)
            record["salary_min"] = lo
            record["salary_max"] = hi
            record["salary_type"] = "月薪"
            return record

        # ---- "K" 格式: "15K-25K" (双K) ----
        k_match = re.match(r"^([\d.]+)K[-]*([\d.]+)K$", s_norm)
        if k_match:
            record["salary_min"] = int(float(k_match.group(1)) * 1000)
            record["salary_max"] = int(float(k_match.group(2)) * 1000)
            record["salary_type"] = "月薪"
            return record

        # ---- 纯数字范围: "15000-25000" ----
        num_match = re.match(r"^(\d+)[-]*(\d+)$", s_norm)
        if num_match:
            lo = int(num_match.group(1))
            hi = int(num_match.group(2))
            # 区分月薪和日薪: 如果范围<100，可能是日薪
            if hi < 100:
                record["salary_min"] = lo
                record["salary_max"] = hi
                record["salary_type"] = "未识别"
            else:
                record["salary_min"] = lo
                record["salary_max"] = hi
                record["salary_type"] = "月薪"
            return record

        # ---- "以上" 格式: "15K以上" ----
        above_k = re.match(r"^([\d.]+)K.*(以上|起|\+)?$", s_norm)
        if above_k:
            record["salary_min"] = int(float(above_k.group(1)) * 1000)
            record["salary_max"] = None
            record["salary_type"] = "月薪"
            return record

        # ---- 纯数字下限: "15000以上" ----
        above_num = re.match(r"^(\d+)(以上|起|\+)$", s_norm)
        if above_num:
            record["salary_min"] = int(above_num.group(1))
            record["salary_max"] = None
            record["salary_type"] = "月薪"
            return record

        # ---- "万/月" 格式: "1.5万/月" ----
        wan_month = re.match(r"^([\d.]+)万.*月", s_norm)
        if wan_month:
            salary = int(float(wan_month.group(1)) * 10000)
            record["salary_min"] = salary
            record["salary_max"] = salary
            record["salary_type"] = "月薪"
            return record

        return record

    # ======================== 经验标准化 ========================

    @classmethod
    def normalize_experience(cls, record: dict) -> dict:
        """标准化经验要求。

        基于 EXPERIENCE_MAP 做模糊匹配，将原始文本映射到标准分类。

        Args:
            record: 岗位数据字典

        Returns:
            dict: 标准化后的字典
        """
        exp_raw = record.get("experience", "")
        record["experience"] = cls._match_to_bucket(
            exp_raw, cls.EXPERIENCE_MAP, "不限"
        )
        return record

    # ======================== 学历标准化 ========================

    @classmethod
    def normalize_education(cls, record: dict) -> dict:
        """标准化学历要求。

        基于 EDUCATION_MAP 做模糊匹配。

        Args:
            record: 岗位数据字典

        Returns:
            dict: 标准化后的字典
        """
        edu_raw = record.get("education", "")
        record["education"] = cls._match_to_bucket(
            edu_raw, cls.EDUCATION_MAP, "不限"
        )
        return record

    # ======================== 城市标准化 ========================

    def normalize_city(self, record: dict) -> dict:
        """标准化城市名称。

        处理逻辑：
        1. 先尝试精确匹配城市变体
        2. 再尝试区到市的映射
        3. 去除"市"后缀再次尝试
        4. 匹配不到保留原值

        Args:
            record: 岗位数据字典

        Returns:
            dict: 标准化后的字典
        """
        location = record.get("location", "")
        district = record.get("district", "")

        if not location:
            record["city"] = "未知"
            return record

        city_raw = str(location).strip().lower()

        # Step 1: 精确匹配城市变体
        for standard_city, variants in self.CITY_MAP.items():
            if city_raw in [v.lower() for v in variants]:
                record["city"] = standard_city
                return record

        # Step 2: 如果 location 包含区名，尝试区→市映射
        for district_name, city_name in self.DISTRICT_TO_CITY.items():
            if district_name in location:
                record["city"] = city_name
                return record

        # Step 3: 去除"市"后缀
        city_no_suffix = re.sub(r"市$", "", str(location).strip())
        for standard_city, variants in self.CITY_MAP.items():
            if city_no_suffix in variants or city_no_suffix == standard_city:
                record["city"] = standard_city
                return record

        # Step 4: 保留原值，记录警告
        logger.debug(f"[标准化] 城市无法识别: '{location}'，保留原值")
        record["city"] = str(location).strip()
        return record

    # ======================== 工具方法 ========================

    @staticmethod
    def _match_to_bucket(
        raw_value: str, mapping: Dict[str, List[str]], default: str
    ) -> str:
        """将原始文本匹配到标准分类桶。

        对 mapping 中的每个标准值，检查其关键词是否出现在 raw_value 中。

        Args:
            raw_value: 原始文本
            mapping: 标准值 → 关键词列表的映射
            default: 匹配不到时的默认值

        Returns:
            str: 标准分类值
        """
        if not raw_value:
            return default

        text = str(raw_value).strip()

        for standard, keywords in mapping.items():
            for keyword in keywords:
                if keyword in text:
                    return standard

        return default
