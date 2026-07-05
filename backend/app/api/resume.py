"""
简历 API 接口
=============
简历模板查询、简历生成、详情查看和下载。

端点：
- GET  /api/v1/resumes/templates         — 获取可用模板列表
- POST /api/v1/resumes/generate          — 生成简历
- GET  /api/v1/resumes/<resume_id>       — 获取简历详情
- GET  /api/v1/resumes/<resume_id>/download — 下载简历 PDF

AI生成，待人工审查。
"""

from flask import request, send_file
from io import BytesIO

from . import api_bp
from ..database import get_db
from ..models.user import User
from ..models.resume import Resume, ResumeTemplate
from ..utils.auth import _extract_token, decode_token
from ..utils.errors import AuthException, ValidationException
from ..utils import success_response, error_response


def _get_current_user_id(db) -> str:
    """从请求头解析 JWT 并返回 user_id。"""
    token = _extract_token()
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthException("未登录或令牌已过期", code=401)
    return user_id


# ============================================================
# GET /resumes/templates
# ============================================================

@api_bp.route("/resumes/templates", methods=["GET"])
def get_resume_templates():
    """获取所有可用的简历模板。

    Returns:
        [{template_id, name, preview_url, css_styles, is_active}, ...]
    """
    db = next(get_db())
    try:
        templates = (
            db.query(ResumeTemplate)
            .filter(ResumeTemplate.is_active == 1)
            .all()
        )
        return success_response(data=[t.to_dict() for t in templates])
    except Exception as e:
        return error_response(message=str(e), code=500)
    finally:
        db.close()


# ============================================================
# POST /resumes/generate
# ============================================================

@api_bp.route("/resumes/generate", methods=["POST"])
def generate_resume():
    """生成简历 — 需要登录。

    Headers: Authorization: Bearer <token>
    Body (JSON):
        template_id (必填), full_name (必填),
        email, phone, university, major, degree, graduation_year,
        skills_text, work_experience, project_experience, self_intro

    Returns:
        201 — {resume_id, ...}
    """
    db = next(get_db())
    try:
        user_id = _get_current_user_id(db)
        data = request.get_json(silent=True)
        if not data:
            raise ValidationException("请求体不能为空")

        template_id = data.get("template_id")
        full_name = data.get("full_name", "").strip()

        if not template_id:
            raise ValidationException("请选择简历模板")
        if not full_name:
            raise ValidationException("姓名不能为空")

        # 验证模板存在
        template = db.query(ResumeTemplate).filter(
            ResumeTemplate.template_id == template_id,
            ResumeTemplate.is_active == 1,
        ).first()
        if not template:
            raise ValidationException("所选模板不存在或已禁用")

        # 处理 JSON 字段
        import json
        work_exp = data.get("work_experience")
        project_exp = data.get("project_experience")
        if isinstance(work_exp, (list, dict)):
            work_exp = json.dumps(work_exp, ensure_ascii=False)
        if isinstance(project_exp, (list, dict)):
            project_exp = json.dumps(project_exp, ensure_ascii=False)

        resume = Resume(
            user_id=user_id,
            template_id=template_id,
            full_name=full_name,
            email=data.get("email", "").strip() or None,
            phone=data.get("phone", "").strip() or None,
            university=data.get("university", "").strip() or None,
            major=data.get("major", "").strip() or None,
            degree=data.get("degree", "").strip() or None,
            graduation_year=data.get("graduation_year"),
            skills_text=data.get("skills_text", "").strip() or None,
            work_experience=work_exp,
            project_experience=project_exp,
            self_intro=data.get("self_intro", "").strip() or None,
            status="draft",
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)

        return success_response(data=resume.to_dict(), message="简历生成成功", code=201)

    except AuthException as e:
        return error_response(message=e.message, code=e.code)
    except ValidationException as e:
        return error_response(message=e.message, code=e.code)
    except Exception as e:
        db.rollback()
        return error_response(message=str(e), code=500)
    finally:
        db.close()


# ============================================================
# GET /resumes/<resume_id>
# ============================================================

@api_bp.route("/resumes/<int:resume_id>", methods=["GET"])
def get_resume_detail(resume_id: int):
    """获取简历详情 — 需要登录且只能查看自己的简历。

    Headers: Authorization: Bearer <token>
    """
    db = next(get_db())
    try:
        user_id = _get_current_user_id(db)

        resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
        if not resume:
            return error_response(message="简历不存在", code=404)
        if resume.user_id != user_id:
            return error_response(message="无权查看此简历", code=403)

        # 附带模板信息
        template = db.query(ResumeTemplate).filter(
            ResumeTemplate.template_id == resume.template_id
        ).first()

        return success_response(data={
            "resume": resume.to_dict(),
            "template": template.to_dict() if template else None,
        })

    except AuthException as e:
        return error_response(message=e.message, code=e.code)
    finally:
        db.close()


# ============================================================
# GET /resumes/<resume_id>/download
# ============================================================

@api_bp.route("/resumes/<int:resume_id>/download", methods=["GET"])
def download_resume(resume_id: int):
    """下载简历 PDF — 需要登录且只能下载自己的简历。

    Query 参数:
        format — pdf / docx (默认 pdf)

    Note: PDF 生成需要 WeasyPrint 或 pdfkit。当前返回 JSON 格式的简历数据
          作为占位，P2 阶段集成真实的 PDF 渲染引擎。
    """
    db = next(get_db())
    try:
        user_id = _get_current_user_id(db)
        fmt = request.args.get("format", "pdf").strip()

        resume = db.query(Resume).filter(Resume.resume_id == resume_id).first()
        if not resume:
            return error_response(message="简历不存在", code=404)
        if resume.user_id != user_id:
            return error_response(message="无权下载此简历", code=403)

        # P2 占位: 返回 JSON 数据 + 提示
        return success_response(data={
            "resume": resume.to_dict(),
            "download_format": fmt,
            "note": "PDF 生成功能将在 P2 阶段集成 WeasyPrint/pdfkit。当前返回 JSON 格式数据。",
        })

    except AuthException as e:
        return error_response(message=e.message, code=e.code)
    finally:
        db.close()
