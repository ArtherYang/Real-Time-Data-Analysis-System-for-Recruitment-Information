"""
M3 数据分析引擎
===============
负责对清洗后的岗位数据进行多维度统计分析，为可视化展示提供数据支撑。

四个核心分析模块：
1. 热度排行 (TrendingRankingService)   — 岗位需求排行、热度指数、趋势
2. 薪资分布 (SalaryDistributionService) — 薪资统计、城市×经验交叉分析
3. 地域分析 (RegionalAnalysisService)   — 城市分布、省份聚合、集中度
4. 技能词云 (SkillWordCloudService)     — 技能频率、共现分析、词云数据

AI生成，待人工审查。
"""

from .engine import AnalysisEngine
from .filters import AnalysisFilters

__all__ = ["AnalysisEngine", "AnalysisFilters"]
