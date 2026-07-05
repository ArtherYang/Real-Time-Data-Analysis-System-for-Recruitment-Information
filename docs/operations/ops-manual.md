# RDAS 运维手册

> **版本**: v2.0 | **日期**: 2026-07-04 | **作者**: 杨昱晨 (AI生成，待人工审查)

---

## 一、环境配置说明

### 1.1 必需软件

| 软件 | 最低版本 | 说明 |
|------|---------|------|
| Docker | 24.0+ | 容器运行时 |
| Docker Compose | 2.20+ | 多服务编排 |
| Git | 2.x | 代码管理 |
| Bash | 4.x | 执行脚本 |

### 1.2 配置文件

```
recruitment-analytics/
├── .env              ← 环境变量（从 .env.example 复制）
├── docker-compose.yml ← 服务编排定义
├── nginx.conf         ← Nginx 入口配置
└── monitoring/        ← 监控配置文件
```

### 1.3 环境变量一览（.env）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_PASSWORD` | `rdas_dev_2026` | **生产务必修改** |
| `SECRET_KEY` | `change-...` | Flask 密钥，`secrets.token_hex(32)` 生成 |
| `JWT_SECRET_KEY` | `change-...` | JWT 签名密钥 |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Grafana 管理员密码 |
| `NGINX_PORT` | `80` | 对外 HTTP 端口 |
| `BACKEND_PORT` | `5000` | 后端端口 |
| `GRAFANA_PORT` | `3001` | Grafana 面板端口 |
| `PROMETHEUS_PORT` | `9090` | Prometheus 端口 |
| `DB_EXTERNAL_PORT` | `3307` | MySQL 宿主机端口 |
| `REDIS_EXTERNAL_PORT` | `6380` | Redis 宿主机端口 |

### 1.4 端口规划

```
宿主机 :80   → Nginx (前端 + API 统一入口)
宿主机 :5000 → Backend (调试用，生产可关闭)
宿主机 :3001 → Grafana (监控面板)
宿主机 :9090 → Prometheus (指标查询)
宿主机 :3307 → MySQL (调试用，生产应关闭)
宿主机 :6380 → Redis (调试用，生产应关闭)
```

---

## 二、启动步骤

### 2.1 首次启动

```bash
# 1. 进入项目目录
cd recruitment-analytics

# 2. 复制环境变量模板并编辑
cp .env.example .env
vim .env   # 至少修改 SECRET_KEY、JWT_SECRET_KEY、DB_PASSWORD

# 3. 启动全部服务（首次需构建镜像，约 3-5 分钟）
docker compose up -d

# 4. 等待健康检查通过（约 30 秒）
docker compose ps
# 预期：所有服务 Status 显示 "healthy"

# 5. 验证
curl http://localhost/health      # 应返回 "ok"
curl http://localhost/api/v1/jobs?page_size=1  # 应返回 JSON
```

### 2.2 日常启动/停止

```bash
# 启动（已构建过镜像，几秒完成）
docker compose up -d

# 停止（保留数据卷）
docker compose down

# 停止并删除数据卷（危险！会丢失数据库）
docker compose down -v

# 重启单个服务
docker compose restart backend
docker compose restart nginx

# 重新构建并启动（代码有变更时）
docker compose up -d --build backend
```

### 2.3 查看运行状态

```bash
# 一览所有容器
docker compose ps

# 查看资源占用
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep rdas

# 检查特定容器详情
docker inspect rdas-backend | grep -A5 Health
```

---

## 三、日志查看

### 3.1 实时追踪日志

```bash
# 后端 API 日志
docker compose logs -f backend

# 异步任务日志（爬虫执行情况）
docker compose logs -f celery-worker

# 定时调度日志
docker compose logs -f celery-beat

# Nginx 访问日志（请求来源、响应状态码）
docker compose logs -f nginx

# 前端容器日志
docker compose logs -f frontend
```

### 3.2 查看历史日志

```bash
# 查看最近 100 行
docker compose logs --tail=100 backend

# 查看最近 1 小时的日志
docker compose logs --since=1h backend

# 查看特定时间范围
docker compose logs --since="2026-07-04T08:00:00" --until="2026-07-04T09:00:00" backend

# 搜索错误
docker compose logs --tail=500 backend 2>&1 | grep -i error
docker compose logs --tail=500 celery-worker 2>&1 | grep -i "FAILED\|Error\|Exception"
```

### 3.3 通过 Grafana 查看日志

1. 浏览器打开 `http://localhost:3001`
2. 左侧菜单 → **Explore**
3. 数据源选择 **Loki**
4. 常用查询：
   ```
   {service="rdas-backend"} |= "ERROR"          # 后端错误日志
   {service="rdas-backend"} |= "500"             # 500 错误请求
   {service="rdas-celery-worker"} |= "FAILED"    # 采集失败
   {service="rdas-nginx"} | json                 # Nginx 结构化日志
   ```

### 3.4 日志保留策略

| 类型 | 保留时间 | 说明 |
|------|---------|------|
| 容器日志 (stdout) | Docker 默认无限制，建议配置 `max-size: 10m` | 通过 Loki 聚合 |
| Loki 聚合日志 | 30 天 | 在 `loki-config.yml` 中配置 |
| 数据库备份 | 30 天 | 备份脚本自动清理 |

---

## 四、常见故障排查

### 4.1 端口冲突

**现象**：`docker compose up -d` 报错 `port is already allocated`

**原因**：宿主机端口已被其他程序占用。

**排查**：
```bash
# 查看占用端口的进程（Windows PowerShell）
netstat -ano | findstr :80
netstat -ano | findstr :3001

# 或 Linux/macOS
lsof -i :80
```

**解决**：
1. 停止占用端口的程序
2. 或修改 `.env` 中的端口映射（如 `NGINX_PORT=8080`），然后 `docker compose up -d`

### 4.2 MySQL 连不上

**现象**：Backend 日志报 `Can't connect to MySQL server` 或 `/ready` 返回 `"database": false`

**排查**：
```bash
# 1. MySQL 容器是否运行
docker compose ps mysql

# 2. 查看 MySQL 日志
docker compose logs mysql --tail=30

# 3. 测试 MySQL 连接
docker exec rdas-mysql mysqladmin ping -u root -p${DB_PASSWORD}

# 4. 查看 Backend 能解析 MySQL 主机名
docker exec rdas-backend nslookup mysql
```

**常见原因与解决**：

| 原因 | 解决方法 |
|------|---------|
| MySQL 未完成初始化（首次启动） | 等待 30-60 秒，`docker compose logs mysql` 看到 `ready for connections` 即可 |
| 密码错误 | 检查 `.env` 中 `DB_PASSWORD` 是否与 `docker-compose.yml` 中一致 |
| 数据库文件损坏 | `docker compose down -v` 重建数据卷（会丢失数据！） |
| 端口冲突 | 修改 `DB_EXTERNAL_PORT` |

### 4.3 Redis 挂了

**现象**：Celery Worker 日志报 `Error connecting to Redis`，采集任务不执行

**排查**：
```bash
# 1. Redis 容器状态
docker compose ps redis

# 2. 测试 Redis 连接
docker exec rdas-redis redis-cli ping     # 应返回 PONG

# 3. 查看 Redis 内存
docker exec rdas-redis redis-cli INFO memory | grep used_memory_human

# 4. Redis 日志
docker compose logs redis --tail=30
```

**常见原因与解决**：

| 原因 | 解决方法 |
|------|---------|
| Redis 内存满 | `docker exec rdas-redis redis-cli FLUSHALL`（清空缓存）或增加 `maxmemory` |
| AOF 文件损坏 | `docker compose down -v` 重建（会丢失缓存数据） |
| 连接数过多 | 检查是否有连接泄漏，适当增加 `maxclients` |

### 4.4 Nginx 502 Bad Gateway

**现象**：浏览器访问 `http://localhost` 返回 502

**排查**：
```bash
# 1. Backend 是否健康
curl http://localhost:5000/health

# 2. Nginx 错误日志
docker compose logs nginx --tail=20 | grep error

# 3. 从 Nginx 容器内测试 Backend
docker exec rdas-nginx curl -s http://backend:5000/health

# 4. 如果容器内正常但宿主机 502 → DNS 缓存问题
docker exec rdas-nginx nginx -s reload
```

### 4.5 前端页面空白

**现象**：浏览器打开 `http://localhost` 显示空白页

**排查**：
```bash
# 1. 前端容器是否正常
docker compose ps frontend

# 2. 测试前端
curl http://localhost | head -20   # 应返回 HTML

# 3. 检查浏览器控制台（F12 → Network）
#    看 API 请求是否返回 200
```

**常见原因**：API 请求被浏览器跨域阻止或 API 返回 500 → 查看 Backend 日志。

### 4.6 采集任务不执行

**现象**：数据库没有新数据，采集监控面板数据为 0

**排查**：
```bash
# 1. Celery Worker 状态
docker compose logs celery-worker --tail=20

# 2. Celery Beat 是否在调度
docker compose logs celery-beat --tail=10

# 3. 手动触发采集（测试）
docker exec rdas-backend python -c "from app.tasks.crawl_tasks import daily_crawl; daily_crawl.delay()"

# 4. 查看 Celery 任务队列
docker exec rdas-redis redis-cli LLEN celery
```

### 4.7 磁盘空间不足

**现象**：多个容器异常退出、日志报 `no space left on device`

**解决**：
```bash
# 查看 Docker 占用
docker system df

# 清理无用资源（停止的容器、悬挂镜像、构建缓存）
docker system prune -a

# 清理所有未使用卷（危险！）
docker volume prune
```

---

## 五、备份与恢复

### 5.1 使用备份脚本

```bash
# 手动备份
cd recruitment-analytics
bash backend/scripts/backup.sh

# 列出已有备份
bash backend/scripts/backup.sh --list

# 清理 30 天前的备份
bash backend/scripts/backup.sh --clean 30
```

### 5.2 配置定时备份

```bash
# Linux/macOS: 添加 crontab（每日凌晨 4:00）
crontab -e
# 添加：
0 4 * * * cd /opt/rdas && bash backend/scripts/backup.sh >> logs/backup.log 2>&1

# Windows: 使用任务计划程序
# schtasks /create /tn "RDAS-Backup" /tr "bash C:\...\backup.sh" /sc daily /st 04:00
```

### 5.3 数据库恢复

```bash
# 1. 确保 MySQL 运行中
docker compose up -d mysql

# 2. 恢复
gunzip < backups/rdas_20260704_001348.sql.gz | \
  docker exec -i rdas-mysql mysql -u root -p${DB_PASSWORD} rdas

# 3. 重启后端
docker compose restart backend

# 4. 验证
curl http://localhost/api/v1/jobs?page_size=5
```

---

## 六、扩容指南

### 水平扩容

```bash
# 扩展后端实例（需配合 Nginx upstream 负载均衡）
docker compose up -d --scale backend=3

# 扩展 Celery Worker 应对采集高峰
docker compose up -d --scale celery-worker=3
```

### 垂直扩容（增加资源限制）

在 `docker-compose.yml` 中服务下添加：
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: '2G'
```

---

## 七、紧急回滚

```bash
# 1. 查看当前镜像
docker images | grep recruitment-analytics

# 2. 回滚：指定旧版本标签 rebuild
# git checkout <previous-tag>
# docker compose up -d --build backend frontend

# 3. 数据库回滚（如需要）
# docker exec -i rdas-mysql mysql -u root -p${DB_PASSWORD} rdas < rollback.sql
```

---

## 八、巡检清单

### 每日（5 分钟）
- [ ] `docker compose ps` — 全部 healthy
- [ ] `curl http://localhost/health` — 返回 ok
- [ ] `curl http://localhost:3001` — Grafana 可访问
- [ ] `df -h` — 磁盘 < 80%

### 每周（15 分钟）
- [ ] `docker compose logs --tail=500 backend | grep -i error` — 无异常
- [ ] 备份文件存在且大小正常
- [ ] `docker system df` — 清理旧镜像

### 每月（30 分钟）
- [ ] 备份恢复演练
- [ ] 安全更新检查
- [ ] 扩容评估
