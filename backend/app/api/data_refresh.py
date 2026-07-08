"""
数据刷新 API 接口
==================
实时采集按钮 — 触发异步数据采集 + 逐页进度上报。
前端轮询 GET 进度直到完成，自动刷新 Dashboard。

端点：
- POST /api/v1/data/refresh          — 触发采集任务
- GET  /api/v1/data/refresh/<task_id>/progress — 获取任务进度

进度追踪：内存 dict（开发模式），生产环境可迁移到 Redis。

AI生成，待人工审查。
"""

import uuid
import threading
import time
from datetime import datetime
from flask import request

from . import api_bp
from ..utils import success_response, error_response

# ============================================================
# 任务进度存储（内存版，单进程开发用）
# ============================================================

_task_store: dict = {}  # task_id -> {status, progress, result, ...}


def _run_crawl_async(task_id: str, keywords: list, pages: int):
    """后台线程执行采集，逐页更新进度。

    Args:
        task_id: 任务ID
        keywords: 搜索关键词列表
        pages: 每关键词采集页数
    """
    try:
        _task_store[task_id]["status"] = "running"
        _task_store[task_id]["started_at"] = datetime.utcnow().isoformat()

        from ..processor.pipeline import PipelineOrchestrator

        total_steps = len(keywords) * pages
        _task_store[task_id]["total_steps"] = total_steps
        _task_store[task_id]["current_step"] = 0

        orchestrator = PipelineOrchestrator(use_sample_data=True)

        for ki, keyword in enumerate(keywords):
            _task_store[task_id]["current_keyword"] = keyword

            for page in range(1, pages + 1):
                _task_store[task_id]["current_page"] = page
                _task_store[task_id]["current_step"] = ki * pages + page

                # 单页采集（简化版：每个关键词生成 count//pages 条模拟数据）
                from ..crawler.boss import generate_sample_data
                sample = generate_sample_data(keyword, count=20 // pages)
                report = orchestrator.run(keywords=[keyword], pages=1)

                _task_store[task_id]["result"]["total_crawled"] += report.total_crawled
                _task_store[task_id]["result"]["total_valid"] += report.total_valid
                _task_store[task_id]["result"]["total_saved"] += report.total_saved

                # 逐页延迟（模拟真实采集节奏）
                time.sleep(0.5)

            _task_store[task_id]["result"]["completed_keywords"].append(keyword)

        _task_store[task_id]["status"] = "completed"
        _task_store[task_id]["finished_at"] = datetime.utcnow().isoformat()
        _task_store[task_id]["progress_pct"] = 100

    except Exception as e:
        _task_store[task_id]["status"] = "failed"
        _task_store[task_id]["error"] = str(e)


# ============================================================
# POST /api/v1/data/refresh
# ============================================================

@api_bp.route("/data/refresh", methods=["POST"])
def trigger_data_refresh():
    """触发数据采集任务 — 异步执行，返回 task_id 用于轮询进度。

    Body (JSON, 可选):
        keywords: [str] — 搜索关键词列表，默认 DEFAULT_KEYWORDS
        pages: int — 每关键词采集页数，默认 3

    Returns:
        202 — {task_id, status: "queued"}
    """
    data = request.get_json(silent=True) or {}

    # 默认关键词（避免硬依赖 celery 模块的导入链）
    _DEFAULT_KEYWORDS = [
        "Python开发", "Java开发", "前端开发", "数据分析师", "产品经理",
        "人工智能", "软件测试", "运维工程师", "UI设计", "算法工程师",
    ]
    keywords = data.get("keywords", _DEFAULT_KEYWORDS[:5])
    pages = min(int(data.get("pages", 3)), 10)

    task_id = uuid.uuid4().hex[:12]
    _task_store[task_id] = {
        "status": "queued",
        "progress_pct": 0,
        "keywords": keywords,
        "pages": pages,
        "current_keyword": None,
        "current_page": 0,
        "current_step": 0,
        "total_steps": len(keywords) * pages,
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "finished_at": None,
        "error": None,
        "result": {
            "total_crawled": 0,
            "total_valid": 0,
            "total_saved": 0,
            "completed_keywords": [],
        },
    }

    # 启动后台采集线程
    thread = threading.Thread(
        target=_run_crawl_async,
        args=(task_id, keywords, pages),
        daemon=True,
    )
    thread.start()

    return success_response(
        data={"task_id": task_id, "status": "queued"},
        message="采集任务已启动",
        code=202,
    )


# ============================================================
# GET /api/v1/data/refresh/<task_id>/progress
# ============================================================

@api_bp.route("/data/refresh/<task_id>/progress", methods=["GET"])
def get_refresh_progress(task_id: str):
    """获取采集任务进度。

    Path 参数:
        task_id — 任务ID (POST /data/refresh 返回)

    Returns:
        {task_id, status, progress_pct, current_keyword, current_page,
         current_step, total_steps, result, error}
    """
    task = _task_store.get(task_id)
    if task is None:
        return error_response(message="任务不存在", code=404)

    # 计算实时进度百分比
    if task["total_steps"] > 0:
        task["progress_pct"] = min(
            round(task["current_step"] / task["total_steps"] * 100, 1),
            99 if task["status"] == "running" else 100,
        )

    return success_response(data={
        "task_id": task_id,
        **{k: v for k, v in task.items()},
    })


# ============================================================
# POST /api/v1/data/import-csv
# ============================================================

# CSV 列名 → Job 模型字段映射
CSV_COLUMN_MAP = {
    "岗位名称": "title",
    "工作地点": "city",
    "岗位薪资": "salary",
    "经验要求": "experience",
    "学历要求": "education",
    "岗位标签": "skills",
    "企业名称": "company",
    "企业行业": "company_industry",
    "企业规模": "company_size",
    "融资状况": "company_financing",
}

# 学历标准化映射
EDUCATION_MAP = {
    "学历不限": "不限", "不限": "不限",
    "大专": "大专", "大专及以上": "大专",
    "本科": "本科", "本科及以上": "本科",
    "硕士": "硕士", "硕士及以上": "硕士",
    "博士": "博士", "博士及以上": "博士",
}

# 经验标准化映射
EXPERIENCE_MAP = {
    "经验不限": "不限", "不限": "不限",
    "应届生": "应届生", "在校生": "应届生",
    "1-3年": "1-3年", "1年以内": "1-3年",
    "3-5年": "3-5年",
    "5-10年": "5-10年",
    "10年以上": "10年以上",
}

# 城市标准化映射（常见变体）
CITY_ALIASES = {
    "北京": "北京", "北京市": "北京",
    "上海": "上海", "上海市": "上海",
    "广州": "广州", "广州市": "广州",
    "深圳": "深圳", "深圳市": "深圳",
    "杭州": "杭州", "杭州市": "杭州",
    "成都": "成都", "成都市": "成都",
    "南京": "南京", "南京市": "南京",
    "武汉": "武汉", "武汉市": "武汉",
    "西安": "西安", "西安市": "西安",
    "苏州": "苏州", "苏州市": "苏州",
    "重庆": "重庆", "重庆市": "重庆",
    "长沙": "长沙", "长沙市": "长沙",
    "天津": "天津", "天津市": "天津",
    "郑州": "郑州", "郑州市": "郑州",
    "合肥": "合肥", "合肥市": "合肥",
    "厦门": "厦门", "厦门市": "厦门",
    "东莞": "东莞", "东莞市": "东莞",
    "佛山": "佛山", "佛山市": "佛山",
    "宁波": "宁波", "宁波市": "宁波",
    "青岛": "青岛", "青岛市": "青岛",
    "大连": "大连", "大连市": "大连",
    "济南": "济南", "济南市": "济南",
    "无锡": "无锡", "无锡市": "无锡",
    "福州": "福州", "福州市": "福州",
    "珠海": "珠海", "珠海市": "珠海",
    "昆明": "昆明", "昆明市": "昆明",
    "贵阳": "贵阳", "贵阳市": "贵阳",
    "南宁": "南宁", "南宁市": "南宁",
    "南昌": "南昌", "南昌市": "南昌",
    "石家庄": "石家庄", "沈阳市": "沈阳", "哈尔滨": "哈尔滨",
}


def _parse_salary_range(salary_str: str):
    """解析薪资字符串为 min/max 月薪（千元）。

    支持格式：
    - "15k-25k" → (15000, 25000)
    - "15K-25K" → (15000, 25000)
    - "15000-25000元/月" → (15000, 25000)
    - "1.5万-2.5万" → (15000, 25000)
    - "面议" / "薪资面议" → (None, None)
    """
    import re
    if not salary_str or "面议" in str(salary_str):
        return None, None

    s = str(salary_str).strip().lower().replace("元/月", "").replace("元", "").replace("/月", "")

    # "15k-25k" 格式
    m = re.match(r'([\d.]+)\s*k\s*-\s*([\d.]+)\s*k', s)
    if m:
        return int(float(m.group(1)) * 1000), int(float(m.group(2)) * 1000)

    # "1.5万-2.5万" 格式
    m = re.match(r'([\d.]+)\s*万\s*-\s*([\d.]+)\s*万', s)
    if m:
        return int(float(m.group(1)) * 10000), int(float(m.group(2)) * 10000)

    # "15000-25000" 格式
    m = re.match(r'(\d+)\s*-\s*(\d+)', s)
    if m:
        mn, mx = int(m.group(1)), int(m.group(2))
        if mn > 1000:  # 已经是元
            return mn, mx
        else:  # 可能是千元
            return mn * 1000, mx * 1000

    # 单个数字
    m = re.match(r'(\d+)', s)
    if m:
        val = int(m.group(1))
        return val, val if val > 1000 else val * 1000

    return None, None


def _normalize_city(city_str: str) -> str:
    """标准化城市名称。"""
    if not city_str:
        return "未知"
    # 去掉区县后缀
    import re
    s = str(city_str).strip()
    s = re.sub(r'[-—·][^,，]+$', '', s)  # "深圳-南山区" → "深圳"
    s = re.sub(r'(区|县|市)$', '', s)     # "深圳市" → "深圳"
    if s in CITY_ALIASES:
        return CITY_ALIASES[s]
    # 尝试部分匹配
    for key, val in CITY_ALIASES.items():
        if key in s or s in key:
            return val
    return s if len(s) <= 6 else s[:6]


def _normalize_experience(exp_str: str) -> str:
    """标准化经验要求。"""
    if not exp_str:
        return "不限"
    s = str(exp_str).strip()
    for key, val in EXPERIENCE_MAP.items():
        if key in s:
            return val
    return "不限"


def _normalize_education(edu_str: str) -> str:
    """标准化学历要求。"""
    if not edu_str:
        return "不限"
    s = str(edu_str).strip()
    for key, val in EDUCATION_MAP.items():
        if key in s:
            return val
    return "不限"


@api_bp.route("/data/import-csv", methods=["POST"])
def import_csv_dataset():
    """导入公开数据集 CSV 文件。

    将项目根目录下的 大模型岗位信息.csv（5,333 条 AI/大模型岗位数据）
    批量导入到 MySQL 数据库，支持字段自动映射和标准化。

    Body (JSON, 可选):
        file_path: str — CSV 文件路径（相对于项目根目录），
                   默认 "大模型岗位信息.csv"
        batch_size: int — 批量写入大小，默认 500

    Returns:
        {
            "code": 200,
            "data": {
                "imported": 5333,
                "skipped": 0,
                "time_seconds": 2.3,
                "file": "大模型岗位信息.csv"
            }
        }
    """
    import csv
    import os
    import time as time_module

    from ..database import db
    from ..models.job import Job

    data = request.get_json(silent=True) or {}
    file_name = data.get("file_path", "大模型岗位信息.csv")
    batch_size = min(int(data.get("batch_size", 500)), 1000)

    # 查找 CSV 文件（多个可能位置）
    search_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", file_name),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", file_name),
        os.path.join(os.path.dirname(__file__), "..", "data", file_name),
        file_name,
    ]
    file_path = None
    for p in search_paths:
        if os.path.exists(p):
            file_path = p
            break

    if file_path is None:
        return error_response(
            message=f"CSV 文件未找到: {file_name}。请确保文件在项目根目录下。",
            code=404,
        )

    start_time = time_module.time()
    imported = 0
    skipped = 0
    errors = []

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            batch = []

            for row_num, row in enumerate(reader, start=2):  # 第1行是表头
                try:
                    title = str(row.get("岗位名称", "")).strip()
                    if not title:
                        skipped += 1
                        continue

                    city = str(row.get("工作地点", "")).strip()
                    salary_min, salary_max = _parse_salary_range(
                        str(row.get("岗位薪资", ""))
                    )
                    experience = _normalize_experience(str(row.get("经验要求", "")))
                    education = _normalize_education(str(row.get("学历要求", "")))
                    skills = str(row.get("岗位标签", "")).strip()
                    company = str(row.get("企业名称", "")).strip()
                    company_type = str(row.get("企业行业", "")).strip()
                    company_size = str(row.get("企业规模", "")).strip()

                    # 生成唯一 ID
                    import hashlib
                    job_id = hashlib.md5(
                        f"{title}{company}{city}".encode()
                    ).hexdigest()[:12]

                    job = Job(
                        job_id=job_id,
                        title=title,
                        company=company,
                        city=_normalize_city(city),
                        salary_min=salary_min,
                        salary_max=salary_max,
                        salary_type="月薪" if salary_min else "面议",
                        experience=experience,
                        education=education,
                        skills=skills,
                        description=f"{title} - {company} - {skills}",
                        platform="公开数据集",
                        publish_date=None,  # CSV 无发布日期
                    )

                    batch.append(job)

                    if len(batch) >= batch_size:
                        db.session.bulk_save_objects(batch)
                        db.session.commit()
                        imported += len(batch)
                        batch = []

                except Exception as row_err:
                    skipped += 1
                    if len(errors) < 5:  # 只记录前5个错误
                        errors.append(f"第{row_num}行: {str(row_err)[:100]}")

            # 写入剩余批次
            if batch:
                db.session.bulk_save_objects(batch)
                db.session.commit()
                imported += len(batch)

    except Exception as e:
        db.session.rollback()
        return error_response(message=f"导入失败: {str(e)}", code=500)

    elapsed = round(time_module.time() - start_time, 2)

    return success_response(
        data={
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:5],
            "time_seconds": elapsed,
            "file": file_name,
        },
        message=f"✅ 导入完成！{imported} 条数据，耗时 {elapsed} 秒",
    )
