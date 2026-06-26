from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db.crud import delete_record_for_user, get_record_for_user, list_records_for_user
from db.database import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/history")
def get_report_history(
    userId: Optional[str] = None,
    db: Session = Depends(get_db),
):
    rows = list_records_for_user(db, userId, limit=50)
    return {
        "items": [
            {
                "id": r.id,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
                "titaiFb": r.titai_fb,
                "tixingFb": r.tixing_fb,
                "titaiLr": r.titai_lr,
                "tixingLr": r.tixing_lr,
                "postureAnalysisText": r.posture_analysis_text,
                "tongueAnalysisText": r.tongue_analysis_text,
                "comprehensiveAnalysisText": r.comprehensive_analysis_text,
                "historyChartData": r.history_chart_data,
                "trendData": (r.meta_json or {}).get("trendData") if isinstance(r.meta_json, dict) else [],
                "frontImagePath": r.front_image_path,
                "processedImagePath": r.processed_image_path,
                "meta": r.meta_json,
                "tcmTenQuestions": r.tcm_ten_questions,
            }
            for r in rows
        ]
    }


@router.get("/{record_id}/processed-image")
def get_processed_image(
    record_id: int,
    userId: Optional[str] = None,
    db: Session = Depends(get_db),
):
    rec = get_record_for_user(db, userId, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="record not found")

    p = (rec.processed_image_path or "").strip()
    if not p:
        raise HTTPException(status_code=404, detail="processed image not available")

    path = Path(p)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="processed image file missing")

    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(
        path=str(path),
        media_type=media_type or "image/jpeg",
        filename=path.name,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{record_id}/mosaic-image")
def get_mosaic_image(
    record_id: int,
    userId: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    返回仅做人脸马赛克、未绘制关键点与 mask 的“处理前底图”，用于前端对比滑动展示。
    该图应与 processed-image 尺寸一致（同一张校正后的底图生成）。
    """
    rec = get_record_for_user(db, userId, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="record not found")

    meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
    p = str(meta.get("mosaicFrontImagePath") or "").strip()
    if not p:
        raise HTTPException(status_code=404, detail="mosaic image not available")

    path = Path(p)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="mosaic image file missing")

    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(
        path=str(path),
        media_type=media_type or "image/jpeg",
        filename=path.name,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{record_id}/tongue-image")
def get_tongue_image(
    record_id: int,
    userId: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    返回“舌苔原图”：
    - 若 record_id 本身是舌苔记录（tongue_only），直接返回其 front_image_path；
    - 若 record_id 是联合报告/其他记录，则尝试从 meta.sourceTongueRecordId 回溯到舌苔记录并返回其 front_image_path。
    """
    rec = get_record_for_user(db, userId, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="record not found")

    meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
    analysis_type = str(meta.get("analysisType") or "").strip().lower()

    tongue_path = (rec.front_image_path or "").strip() if analysis_type == "tongue_only" else ""
    if not tongue_path:
        tixing_fb = rec.tixing_fb if isinstance(rec.tixing_fb, dict) else {}
        src_id = meta.get("sourceTongueRecordId") or tixing_fb.get("sourceTongueRecordId")
        try:
            src_id_int = int(src_id) if src_id is not None else None
        except Exception:
            src_id_int = None
        if src_id_int and src_id_int > 0:
            src = get_record_for_user(db, userId, src_id_int)
            if src is not None:
                tongue_path = (src.front_image_path or "").strip()

    if not tongue_path:
        raise HTTPException(status_code=404, detail="tongue image not available")

    path = Path(tongue_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="tongue image file missing")

    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(
        path=str(path),
        media_type=media_type or "image/jpeg",
        filename=path.name,
        headers={"Cache-Control": "no-store"},
    )


@router.delete("/{record_id}")
def delete_report_record(
    record_id: int,
    userId: Optional[str] = None,
    db: Session = Depends(get_db),
):
    ok = delete_record_for_user(db, userId, record_id)
    return {"success": ok, "recordId": record_id}
