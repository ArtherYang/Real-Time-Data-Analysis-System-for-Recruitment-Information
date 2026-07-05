# ============================================================
# 招聘信息实时数据分析系统 (RDAS) — 前端 Docker 镜像
# ============================================================
# 多阶段构建：
#   阶段1 (build): Node.js 20 Alpine → npm install → vite build
#   阶段2 (run):   Nginx Alpine → 复制构建产物 + nginx 配置
#
# AI生成，待人工审查。
# ============================================================

# ---- 阶段1：构建 ----
FROM node:20-alpine AS build

WORKDIR /app

# 复制 package 文件（利用 Docker 缓存层）
COPY package.json ./

# 安装依赖
RUN npm install --registry=https://registry.npmmirror.com

# 复制源码并构建
COPY . .
RUN npm run build

# ---- 阶段2：运行 ----
FROM nginx:1.27-alpine

# 安装 curl 用于健康检查
RUN apk add --no-cache curl

# 移除默认配置
RUN rm -f /etc/nginx/conf.d/default.conf

# 复制自定义 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
