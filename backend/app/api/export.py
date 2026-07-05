"""
数据导出 API
============
支持将筛选后的分析数据导出为 CSV 或 Excel 格式。

端点列表：
- GET /api/v1/export/csv   — 导出 CSV
- GET /api/v1/export/excel — 导出 Excel

作者: 杨昱晨 (AI生成，待人工审查)
日期: 2026-07-02
"""

import csv
import io
from datetime import date

from flask import jsonify, Response

from app.api import api_bp
from app.api.analysis import _parse_filters


def _get_filtered_jobs():
    """获取筛选后的岗位数据"""
    from app.analysis import AnalysisFilters
    from app.database import get_db
    from app.models.job import Job

    filters = _parse_filters()
    db = next(get_db())
    try:
        query = filters.apply_to_query(db.query(Job))
        # 只返回有效岗位
        query = query.filter(Job.status == "有效")
        return [job.to_dict() for job in query.all()]
    finally:
        db.close()


@api_bp.route("/export/csv")
def export_csv():
    """
    导出当前筛选结果为 CSV 文件

    Query: 同 analysis endpoints 的筛选参数
    """
    jobs = _get_filtered_jobs()

    output = io.StringIO()
    output.write("﻿")  # UTF-8 BOM (Excel 中文兼容)

    if jobs:
        # 字段顺序：重要的在前
        fields = [
            "title", "company", "city", "salary_min", "salary_max", "salary_type",
            "experience", "education", "job_category", "skills",
            "platform", "published_at", "company_type", "company_size", "welfare",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()

        for job in jobs:
            # 格式化薪资
            row = dict(job)
            if job["salary_min"] and job["salary_max"]:
                row["salary_display"] = f"{job['salary_min']/1000:.0f}K-{job['salary_max']/1000:.0f}K"
            writer.writerow(row)

    csv_content = output.getvalue()
    output.close()

    today_str = date.today().isoformat()
    return Response(
        csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=recruitment_data_{today_str}.csv",
            "Content-Type": "text/csv; charset=utf-8",
        },
    )


@api_bp.route("/export/excel")
def export_excel():
    """
    导出当前筛选结果为 Excel (.xlsx) 文件

    Query: 同 analysis endpoints 的筛选参数

    注意: 使用 openpyxl 生成 .xlsx。
          如未安装 openpyxl，返回提示。
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return jsonify({
            "code": -1,
            "msg": "请安装 openpyxl: pip install openpyxl",
        }), 500

    jobs = _get_filtered_jobs()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "招聘数据"

    # 表头样式
    header_font = Font(name="微软雅黑", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="409EFF", end_color="409EFF", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # 表头
    headers = [
        "岗位名称", "公司", "城市", "最低薪资(元)", "最高薪资(元)",
        "薪资类型", "经验要求", "学历要求", "岗位分类", "技能标签",
        "数据来源", "发布日期", "公司类型", "公司规模", "福利",
    ]
    fields = [
        "title", "company", "city", "salary_min", "salary_max",
        "salary_type", "experience", "education", "job_category", "skills",
        "platform", "published_at", "company_type", "company_size", "welfare",
    ]

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # 数据行
    for row_idx, job in enumerate(jobs, 2):
        for col_idx, field in enumerate(fields, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=job.get(field, ""))
            cell.alignment = Alignment(vertical="center")
            cell.border = thin_border

    # 列宽自适应
    col_widths = [22, 18, 8, 14, 14, 10, 10, 10, 12, 35, 12, 14, 12, 14, 30]
    for col_idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # 冻结首行
    ws.freeze_panes = "A2"

    # 自动筛选
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(jobs) + 1}"

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    today_str = date.today().isoformat()
    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=recruitment_data_{today_str}.xlsx",
        },
    )
