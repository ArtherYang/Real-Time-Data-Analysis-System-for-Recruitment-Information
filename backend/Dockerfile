# ============================================================
# 招聘信息实时数据分析系统 (RDAS) — 后端 Docker 镜像
# ============================================================
# 基于 Python 3.11 slim，使用 Gunicorn 运行 Flask 应用
# 注意：pymysql 是纯 Python 驱动，无需 gcc/libmysqlclient-dev
#
# AI生成，待人工审查。
# ============================================================

FROM python:3.11-slim

WORKDIR /app

# 仅安装 curl 用于健康检查（无需 gcc/pkg-config 等编译工具）
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 复制并安装 Python 依赖（使用清华镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用源码
COPY . .

# 创建非 root 用户运行应用
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/logs && chown -R appuser:appuser /app/logs
USER appuser

EXPOSE 5000

# 健康检查（每 15s 检查一次，超时 3s，最多重试 3 次）
HEALTHCHECK --interval=15s --timeout=3s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:5000/health || exit 1

# 使用 gunicorn 启动 Flask 应用（工厂模式）
# --preload 确保 create_app() 在所有 worker fork 之前执行一次
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "--preload", "app:create_app()"]
