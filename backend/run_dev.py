"""
开发环境启动脚本
================
使用 SQLite 文件数据库启动 Flask 开发服务器（无需 MySQL）。
包含种子数据：60 条岗位 + 测试用户。

测试账号: test@rdas.com / Test1234 (管理员)
"""

import os
import sys

# Ensure we're in the backend directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

os.environ['FLASK_ENV'] = 'testing'

# Patch TestingConfig to use absolute path to file-based SQLite
from app.config import TestingConfig

_DB_PATH = os.path.join(os.getcwd(), 'rdas.db')


def file_db_uri(self):
    return 'sqlite:///' + _DB_PATH


TestingConfig.SQLALCHEMY_DATABASE_URI = property(file_db_uri)

from app import create_app

app = create_app()
print(f"数据库: sqlite:///{_DB_PATH}")
print(f"测试账号: test@rdas.com / Test1234 (管理员)")
print(f"启动地址: http://127.0.0.1:5000")
app.run(host="0.0.0.0", port=5000, debug=False)
