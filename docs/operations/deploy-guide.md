# RDAS 部署指南

> **版本**: v1.0 | **日期**: 2026-07-03 | **作者**: 杨昱晨 (AI生成，待人工审查)

---

## 一、环境要求

### 硬件最低配置
| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 20 GB | 50 GB+ (SSD) |

### 软件要求
- Docker >= 24.0
- Docker Compose >= 2.20
- Git

---

## 二、快速部署（5 分钟）

```bash
# 1. 克隆项目
git clone <repo-url> rdas && cd rdas

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少修改：
#   - SECRET_KEY（python -c "import secrets; print(secrets.token_hex(32))"）
#   - JWT_SECRET_KEY
#   - DB_PASSWORD
#   - GRAFANA_ADMIN_PASSWORD

# 3. 启动全部服务
docker-compose up -d

# 4. 验证部署
docker-compose ps                    # 全部服务应为 healthy
curl http://localhost/health         # 返回 "ok"
curl http://localhost:3000           # Grafana 登录页
curl http://localhost:9090           # Prometheus UI
```

### 端口说明
| 端口 | 服务 | 用途 |
|------|------|------|
| 80 | Nginx | 统一入口（前端 + API） |
| 3000 | Grafana | 监控面板 |
| 9090 | Prometheus | 指标查询 |
| 3307 | MySQL | 数据库（调试用，生产应关闭） |
| 6380 | Redis | 缓存（调试用，生产应关闭） |

---

## 三、多环境部署

### 开发环境（Development）
```bash
ENV=development docker-compose up -d
# 特点：DEBUG 开启，MySQL/Redis 端口暴露到宿主机，日志级别 DEBUG
```

### 测试环境（Testing）
```bash
ENV=testing docker-compose up -d
# 特点：关闭 DEBUG，使用测试数据库，完整服务栈
```

### 生产环境（Production）
```bash
ENV=production docker-compose up -d
# 特点：关闭 DEBUG，仅暴露 80/3000 端口，日志级别 WARNING
# 注意：务必修改 .env 中所有密钥和密码！
```

---

## 四、常用操作

```bash
# 查看服务状态
docker-compose ps

# 查看所有日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f celery-worker

# 重启单个服务
docker-compose restart backend

# 更新镜像并重新部署
docker-compose pull
docker-compose up -d --force-recreate

# 停止全部服务
docker-compose down

# 停止并清理数据卷（危险！）
docker-compose down -v
```

---

## 五、数据备份

### 手动备份 MySQL
```bash
docker exec rdas-mysql mysqldump -u root -p${DB_PASSWORD} rdas > backup_$(date +%Y%m%d).sql
```

### 恢复 MySQL
```bash
docker exec -i rdas-mysql mysql -u root -p${DB_PASSWORD} rdas < backup_20260703.sql
```

### 定时备份（crontab）
```bash
# 每日凌晨 4:00 备份
0 4 * * * cd /opt/rdas && docker exec rdas-mysql mysqldump -u root -pYOUR_PASSWORD rdas | gzip > backups/rdas_$(date +\%Y\%m\%d).sql.gz
```

---

## 六、常见问题排查

| 问题 | 可能原因 | 解决方法 |
|------|---------|---------|
| 502 Bad Gateway | Backend 未启动 | `docker-compose logs backend` 查看错误 |
| 数据库连接失败 | MySQL 未就绪 | 等待 30s，MySQL 首次启动较慢 |
| 前端页面空白 | API 请求失败 | 检查浏览器控制台 network 面板 |
| 端口冲突 | 宿主机端口被占用 | 修改 `.env` 中的端口映射 |
| Celery 任务不执行 | Redis 未连接 | `docker exec rdas-redis redis-cli ping` |
| 容器反复重启 | 健康检查超时 | 增加资源限制或调整健康检查参数 |
| Grafana 无数据 | Prometheus 未抓取 | 检查 http://localhost:9090/targets |

---

## 七、安全加固清单

- [ ] 修改所有默认密码
- [ ] 生成随机 SECRET_KEY 和 JWT_SECRET_KEY
- [ ] 关闭非必要的外部端口（MySQL:3307、Redis:6380）
- [ ] 配置防火墙规则（仅开放 80 和 3000）
- [ ] 启用 HTTPS（Nginx 配置 SSL 证书）
- [ ] 设置 Grafana 强密码策略
