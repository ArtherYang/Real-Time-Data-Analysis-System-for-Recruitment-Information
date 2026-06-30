"""
API 接口层
==========
对外提供 RESTful API，包括：
- 岗位数据查询接口
- 分析结果接口
- 用户管理接口
"""

from flask import Blueprint

# 创建蓝图（后续在工厂函数中注册）
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# 各子模块路由将在对应文件中定义后注册
# from . import jobs      # 岗位数据接口
# from . import analysis  # 分析结果接口
# from . import users     # 用户管理接口
