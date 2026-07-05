"""
数据处理模块
============
负责对采集到的原始数据进行：
1. 数据清洗与去重
2. 字段标准化
3. NLP关键词提取（Jieba分词）
4. 缺失值处理
"""

# 数据清洗与去重
from .cleaner import DataCleaner, CleanedRecord

# 字段标准化
from .normalizer import FieldNormalizer

# 数据处理管道
from .pipeline import PipelineOrchestrator, PipelineReport

# NLP关键词提取（后续实现）
# from .extractor import KeywordExtractor

__all__ = [
    "DataCleaner",
    "CleanedRecord",
    "FieldNormalizer",
    "PipelineOrchestrator",
    "PipelineReport",
]
