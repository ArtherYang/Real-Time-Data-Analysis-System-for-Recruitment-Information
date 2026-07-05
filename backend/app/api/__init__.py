"""
API 接口层
==========
对外提供 RESTful API，包括：
- 仪表盘接口 (/api/v1/dashboard/*)
- 岗位数据查询接口 (/api/v1/jobs/*)
- 分析结果接口 (/api/v1/analysis/*)
- 用户管理接口 (/api/v1/auth/*)
- 用户资料接口 (/api/v1/user/*)
- 简历接口 (/api/v1/resumes/*)
- 数据导出接口 (/api/v1/export/*)
"""

from flask import Blueprint

# 创建蓝图（在工厂函数中注册到 Flask app）
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# 导入各子模块以注册路由
from . import jobs       # noqa: E402, F401 — 岗位数据接口
from . import analysis   # noqa: E402, F401 — 分析结果接口
from . import auth       # noqa: E402, F401 — 用户认证接口
from . import export     # noqa: E402, F401 — 数据导出接口
from . import dashboard  # noqa: E402, F401 — 仪表盘接口
from . import user       # noqa: E402, F401 — 用户资料接口
from . import resume     # noqa: E402, F401 — 简历接口
