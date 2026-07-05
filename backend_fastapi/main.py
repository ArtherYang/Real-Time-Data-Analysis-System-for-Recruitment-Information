"""
RDAS FastAPI 应用入口
=====================
从 Flask 迁移到 FastAPI — 复用全部 SQLAlchemy 模型和分析引擎，
仅重写 API 路由层以使用 FastAPI 原生特性（Pydantic、async、自动文档）。

启动: uvicorn main:app --reload --port 8000
文档: http://localhost:8000/docs
"""

import os
import sys

# 原 Flask 后端优先（含 app.config / app.database / app.models 等），
# 当前目录补充 FastAPI 专用 api 路由
_FASTAPI = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_FASTAPI, "..", "backend")
sys.path.insert(0, _BACKEND)
sys.path.insert(1, _FASTAPI)  # FastAPI api/ 目录用独立 import

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import TestingConfig
from app.database import init_db, create_tables


class FileDBConfig(TestingConfig):
    """开发环境：SQLite 文件数据库"""
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        db_path = os.path.join(_BACKEND, "rdas.db")
        return f"sqlite:///{db_path}"


# 初始化数据库
config = FileDBConfig()
init_db(config)
create_tables()

app = FastAPI(
    title="RDAS — 招聘信息实时数据分析系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（FastAPI api/ 目录独立于 Flask app.api）
from api import jobs, analysis, auth, export, filters  # noqa: E402

app.include_router(jobs.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(filters.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "service": "RDAS FastAPI", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
