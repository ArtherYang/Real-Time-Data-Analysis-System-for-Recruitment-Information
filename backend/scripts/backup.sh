#!/bin/bash
# ============================================================
# RDAS MySQL 定时备份脚本
# ============================================================
# 用法：
#   ./backup.sh                  # 手动执行备份
#   ./backup.sh --list           # 列出已有备份
#   ./backup.sh --clean 30       # 清理 30 天前的旧备份
#
# 定时任务（crontab）：
#   0 4 * * * /opt/rdas/backend/scripts/backup.sh >> /var/log/rdas-backup.log 2>&1
#
# AI生成，待人工审查。
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKUP_DIR="${PROJECT_DIR}/backups"
CONTAINER_NAME="${MYSQL_CONTAINER:-rdas-mysql}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
DB_NAME="${DB_NAME:-rdas}"
DB_USER="${DB_USER:-root}"

# 从 docker-compose 环境或 .env 读取密码
DB_PASSWORD="${DB_PASSWORD:-rdas_dev_2026}"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# 备份
# ============================================================
do_backup() {
    mkdir -p "$BACKUP_DIR"

    local TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    local BACKUP_FILE="${BACKUP_DIR}/rdas_${TIMESTAMP}.sql.gz"

    log "开始备份数据库 ${DB_NAME}..."

    # 检查 MySQL 容器是否运行
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        err "MySQL 容器 ${CONTAINER_NAME} 未运行"
        exit 1
    fi

    # 执行 mysqldump（--single-transaction 不锁表，适合 InnoDB）
    docker exec "$CONTAINER_NAME" mysqldump \
        -u "$DB_USER" \
        -p"$DB_PASSWORD" \
        --single-transaction \
        --routines \
        --triggers \
        --events \
        --databases "$DB_NAME" \
        --default-character-set=utf8mb4 \
        | gzip > "$BACKUP_FILE"

    local SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

    if [ -s "$BACKUP_FILE" ]; then
        log "备份成功: ${BACKUP_FILE} (${SIZE})"
    else
        err "备份失败: 文件为空"
        rm -f "$BACKUP_FILE"
        exit 1
    fi

    # 清理过期备份
    do_cleanup "$RETENTION_DAYS"
}

# ============================================================
# 清理过期备份
# ============================================================
do_cleanup() {
    local DAYS=${1:-$RETENTION_DAYS}
    local COUNT=$(find "$BACKUP_DIR" -name "rdas_*.sql.gz" -mtime +"$DAYS" 2>/dev/null | wc -l)

    if [ "$COUNT" -gt 0 ]; then
        log "清理 ${DAYS} 天前的备份 (共 ${COUNT} 个)..."
        find "$BACKUP_DIR" -name "rdas_*.sql.gz" -mtime +"$DAYS" -delete
    fi
}

# ============================================================
# 列出备份
# ============================================================
do_list() {
    echo ""
    echo "============================================"
    echo "  RDAS 数据库备份列表"
    echo "  目录: ${BACKUP_DIR}"
    echo "============================================"
    echo ""

    if [ -d "$BACKUP_DIR" ] && [ "$(ls -1 "$BACKUP_DIR"/*.gz 2>/dev/null | wc -l)" -gt 0 ]; then
        echo "时间                    大小    文件"
        echo "----------------------  ------  ----"
        ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null | awk '{printf "%-22s  %6s  %s\n", $6" "$7, $5, $9}'
    else
        echo "  (暂无备份)"
    fi
    echo ""
}

# ============================================================
# 主入口
# ============================================================
case "${1:-backup}" in
    --list|-l)
        do_list
        ;;
    --clean|-c)
        do_cleanup "${2:-$RETENTION_DAYS}"
        log "清理完成"
        ;;
    backup|--backup|-b)
        do_backup
        ;;
    *)
        echo "用法: $0 [backup|--list|--clean DAYS]"
        echo ""
        echo "  backup (默认)  — 执行备份"
        echo "  --list, -l     — 列出已有备份"
        echo "  --clean N      — 清理 N 天前的备份 (默认 ${RETENTION_DAYS} 天)"
        exit 1
        ;;
esac
