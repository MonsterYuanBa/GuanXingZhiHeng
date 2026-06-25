from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.crud import get_or_create_user, get_record_for_user, save_assessment
from db.database import SessionLocal, get_db
from db.models import AssessmentRecord
from routes.utils.api_helpers import save_uploaded_image
from .ask_AI_tongue import analyze_tongue_image, format_tongue_analysis_report

router = APIRouter(prefix='/api/tongue', tags=['tongue'])


def _run_tongue_ai_background(
    record_id: int,
    tongue_path: str,
    mime: str,
    tcm_ten: Optional[Dict[str, Any]],
    model: Optional[str],
    analysis_mode: str,
) -> None:
    db = SessionLocal()
    try:
        rec = db.execute(select(AssessmentRecord).where(AssessmentRecord.id == record_id)).scalars().first()
        if rec is None:
            return
        try:
            tongue_info = analyze_tongue_image(
                image_path=tongue_path,
                mime=mime,
                tcm_ten_questions=tcm_ten,
                analysis_mode=analysis_mode,
                model=model,
            )
            report_text = format_tongue_analysis_report(tongue_info)
            rec.tongue_analysis_text = report_text
            tx = rec.tixing_fb if isinstance(rec.tixing_fb, dict) else {}
            tx["tongueStructured"] = tongue_info
            rec.tixing_fb = tx
            meta = dict(rec.meta_json or {})
            meta["tongueInfo"] = tongue_info
            meta["aiStatus"] = "done"
            meta["aiFinishedAt"] = datetime.utcnow().isoformat()
            rec.meta_json = meta
        except Exception as e:
            meta = dict(rec.meta_json or {})
            meta["aiStatus"] = "failed"
            meta["aiError"] = str(e)
            meta["aiFinishedAt"] = datetime.utcnow().isoformat()
            rec.meta_json = meta
        db.commit()
    finally:
        db.close()


def _mime_for_tongue_image(image_info: Dict[str, Any], saved_path: str) -> str:
    ct = (image_info.get("contentType") or "").lower()
    if ct.startswith("image/"):
        return ct.split(";")[0].strip()
    ext = Path(saved_path).suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return "image/jpeg"


@router.post('/analyze')
async def analyze_tongue(
    background_tasks: BackgroundTasks,
    meta: UploadFile = File(...),
    userId: Optional[str] = Form(default=None),
    tongueImage: UploadFile = File(...),
    model: Optional[str] = Form(default=None),
    analysisMode: Optional[str] = Form(default="normal"),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    print("------waiting for AI response...------")
    meta_obj: Dict[str, Any] = {}
    try:
        raw = await meta.read()
        meta_obj = json.loads(raw)
    except Exception:
        meta_obj = {'_raw_meta': 'parse_failed'}

    merged = {'userId': meta_obj.get('userId') or userId}
    if isinstance(meta_obj, dict):
        merged['profileMeta'] = meta_obj

    tcm_ten = meta_obj.get('tcmTenQuestions') if isinstance(meta_obj, dict) else None
    if tcm_ten is not None and not isinstance(tcm_ten, dict):
        tcm_ten = None

    merged_user_id = merged.get('userId') or 'admin'
    user_row = get_or_create_user(db, merged_user_id)
    analysis_mode = "expert" if str(analysisMode or "").strip().lower() == "expert" else "normal"
    record = save_assessment(
        db,
        user=user_row,
        titai_fb=None,
        tixing_fb={
            'type': 'tongue_only',
            'imageInfo': None,
        },
        titai_lr=None,
        tixing_lr=None,
        posture_analysis_text=None,
        tongue_analysis_text=None,
        comprehensive_analysis_text=None,
        front_image_path=None,
        meta={
            'analysisType': 'tongue_only',
            'analysisMode': analysis_mode,
            'generatedAt': datetime.utcnow().isoformat(),
            'aiStatus': 'pending',
            'imageInfo': None,
        },
        tcm_ten_questions=tcm_ten,
    )
    tongue_path, image_info = await save_uploaded_image(
        tongueImage,
        preferred_stem=f"{record.id}_tongue",
        overwrite=True,
    )
    mime = _mime_for_tongue_image(image_info, tongue_path)
    record.front_image_path = tongue_path
    tixing_payload = dict(record.tixing_fb or {})
    tixing_payload['imageInfo'] = image_info
    record.tixing_fb = tixing_payload
    meta_payload = dict(record.meta_json or {})
    meta_payload['imageInfo'] = image_info
    record.meta_json = meta_payload
    db.commit()
    print("------waiting for AI response...------")
    background_tasks.add_task(
        _run_tongue_ai_background,
        record.id,
        tongue_path,
        mime,
        tcm_ten,
        model,
        analysis_mode,
    )

    return {
        'success': True,
        'msg': '舌苔数据已生成，智能体正在分析中',
        'authorization': authorization,
        'receivedMeta': meta_obj,
        'receivedFieldsMerged': merged,
        'aiReport': '',
        'aiPending': True,
        'tongueInfo': None,
        'imageInfo': image_info,
        'recordId': record.id,
        'createdAt': record.created_at.isoformat() if record.created_at else None,
    }


@router.get('/report-status')
def get_tongue_report_status(recordId: int = Query(...), userId: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    rec = get_record_for_user(db, userId, recordId)
    if rec is None:
        return {"success": False, "message": "record not found", "done": False}
    meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
    status = meta.get("aiStatus") or ("done" if (rec.tongue_analysis_text or "").strip() else "pending")
    return {
        "success": True,
        "done": status == "done",
        "status": status,
        "report": rec.tongue_analysis_text or "",
        "error": meta.get("aiError") or "",
    }
