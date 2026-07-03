from __future__ import annotations

import json
import mimetypes
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.crud import get_or_create_user, get_record_for_user, save_assessment
from db.database import get_db
from db.models import AssessmentRecord
from routes.joint_report_transfer.ask_AI_analyse import generate_joint_comprehensive_report
from routes.posture_transfer.ask_AI_pos import ask_ai_posture
from routes.tongue_transfer.ask_AI_tongue import analyze_tongue_image, format_tongue_analysis_report

router = APIRouter(prefix="/api/reports/test-mod", tags=["test-mod"])

_ROOT = Path(__file__).resolve().parents[1]
_TEST_MOD_ROOT = _ROOT / "4_test_mod"


def _sample_dir(sample_id: str) -> Path:
    sid = "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in (sample_id or "267"))
    return _TEST_MOD_ROOT / sid


def _manifest_path(sample_id: str) -> Path:
    return _sample_dir(sample_id) / "manifest.json"


def _read_manifest(sample_id: str) -> Dict[str, Any]:
    p = _manifest_path(sample_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"sample manifest not found: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"manifest parse failed: {e}") from e


def _copy_file(src: Optional[str], target_dir: Path, target_name: str) -> tuple[Optional[str], bool]:
    if not src:
        return None, False
    p = Path(src)
    if not p.is_absolute():
        p = (_ROOT / p).resolve()
    if (not p.exists()) or (not p.is_file()):
        return None, False
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = p.suffix or ".bin"
    dst = target_dir / f"{target_name}{ext}"
    shutil.copy2(p, dst)
    return str(dst), True


def _guess_posture_side(front_path: Optional[str], record_id: int) -> Optional[str]:
    if not front_path:
        return None
    fp = Path(front_path)
    side = fp.with_name(f"{record_id}_posture_side{fp.suffix}")
    return str(side) if side.exists() else None


def _build_file_url(sample_id: str, rel: Optional[str]) -> Optional[str]:
    if not rel:
        return None
    return f"/api/reports/test-mod/file?sampleId={sample_id}&relPath={rel}"


def _resolve_sample_image(sample_id: str, rel: Optional[str]) -> Optional[str]:
    if not rel:
        return None
    p = (_sample_dir(sample_id) / rel).resolve()
    try:
        p.relative_to(_sample_dir(sample_id).resolve())
    except Exception:
        return None
    if not p.exists():
        return None
    return str(p)


class ExportRecordPayload(BaseModel):
    userId: str
    recordId: int
    sampleId: str = "267"


@router.post("/export-record")
def export_record_to_test_mod(payload: ExportRecordPayload, db: Session = Depends(get_db)):
    rec = get_record_for_user(db, payload.userId, int(payload.recordId))
    if rec is None:
        raise HTTPException(status_code=404, detail="record not found")

    sample_dir = _sample_dir(payload.sampleId)
    files_dir = sample_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    posture_front_src = rec.front_image_path if isinstance(rec.meta_json, dict) and rec.meta_json.get("analysisType") == "posture_only" else None
    posture_side_src = _guess_posture_side(posture_front_src, rec.id)
    processed_src = rec.processed_image_path
    mosaic_src = (rec.meta_json or {}).get("mosaicFrontImagePath") if isinstance(rec.meta_json, dict) else None

    source_tongue_id = None
    if isinstance(rec.meta_json, dict):
        source_tongue_id = rec.meta_json.get("sourceTongueRecordId")
    tongue_rec = rec
    if source_tongue_id:
        src = get_record_for_user(db, payload.userId, int(source_tongue_id))
        if src is not None:
            tongue_rec = src
    tongue_src = tongue_rec.front_image_path

    copied: Dict[str, Any] = {}
    copied["postureFront"], _ = _copy_file(posture_front_src, files_dir, "posture_front")
    copied["postureSide"], side_ok = _copy_file(posture_side_src, files_dir, "posture_side")
    copied["postureProcessed"], _ = _copy_file(processed_src, files_dir, "posture_processed")
    copied["postureMosaic"], _ = _copy_file(mosaic_src, files_dir, "posture_mosaic")
    copied["tongueImage"], _ = _copy_file(tongue_src, files_dir, "tongue_upload")

    posture_source = rec if (rec.meta_json or {}).get("analysisType") == "posture_only" else None
    if posture_source is None and isinstance(rec.meta_json, dict) and rec.meta_json.get("sourcePostureRecordId"):
        src = get_record_for_user(db, payload.userId, int(rec.meta_json.get("sourcePostureRecordId")))
        if src is not None:
            posture_source = src
    if posture_source is None:
        posture_source = rec

    manifest = {
        "sampleId": payload.sampleId,
        "exportedAt": datetime.utcnow().isoformat(),
        "source": {
            "userId": payload.userId,
            "recordId": rec.id,
            "postureRecordId": posture_source.id if posture_source else None,
            "tongueRecordId": tongue_rec.id if tongue_rec else None,
        },
        "missingNotes": {
            "postureSideUploadMissing": not side_ok,
            "originalUploadUnknownHint": "若不知道用户上传原图，请手动补充 posture_front/posture_side/tongue_upload 文件。",
        },
        "posture": {
            "titai_fb": posture_source.titai_fb if posture_source else None,
            "tixing_fb": posture_source.tixing_fb if posture_source else None,
            "titai_lr": posture_source.titai_lr if posture_source else None,
            "tixing_lr": posture_source.tixing_lr if posture_source else None,
            "report": posture_source.posture_analysis_text if posture_source else "",
        },
        "tongue": {
            "report": tongue_rec.tongue_analysis_text if tongue_rec else "",
            "metaTongueInfo": ((tongue_rec.meta_json or {}).get("tongueInfo") if isinstance(tongue_rec.meta_json, dict) else None),
        },
        "joint": {
            "report": rec.comprehensive_analysis_text or "",
            "postureReport": rec.posture_analysis_text or (posture_source.posture_analysis_text if posture_source else ""),
            "tongueReport": rec.tongue_analysis_text or (tongue_rec.tongue_analysis_text if tongue_rec else ""),
        },
        "files": {
            k: (str(Path(v).relative_to(sample_dir)).replace("\\", "/") if v else None) for k, v in copied.items()
        },
        "profileMeta": (rec.meta_json or {}).get("profileMeta") if isinstance(rec.meta_json, dict) else None,
        "tcmTenQuestions": rec.tcm_ten_questions,
    }
    _manifest_path(payload.sampleId).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "sampleId": payload.sampleId, "manifestPath": str(_manifest_path(payload.sampleId))}


@router.get("/sample-ids")
def list_sample_ids():
    """列出 4_test_mod 下存在 manifest.json 的样本目录名。"""
    out: list[str] = []
    if not _TEST_MOD_ROOT.is_dir():
        return {"success": True, "sampleIds": out}
    for child in sorted(_TEST_MOD_ROOT.iterdir()):
        if not child.is_dir():
            continue
        sid = child.name
        if _manifest_path(sid).exists():
            out.append(sid)
    return {"success": True, "sampleIds": out}


@router.get("/sample")
def get_sample(sampleId: str = Query(default="267")):
    m = _read_manifest(sampleId)
    files = m.get("files") or {}
    return {
        "success": True,
        "sampleId": sampleId,
        "manifest": m,
        "posture": {
            "titai_fb": (m.get("posture") or {}).get("titai_fb"),
            "tixing_fb": (m.get("posture") or {}).get("tixing_fb"),
            "titai_lr": (m.get("posture") or {}).get("titai_lr"),
            "tixing_lr": (m.get("posture") or {}).get("tixing_lr"),
            "report": (m.get("posture") or {}).get("report") or "",
            "frontImageUrl": _build_file_url(sampleId, files.get("postureFront")),
            "sideImageUrl": _build_file_url(sampleId, files.get("postureSide")),
            "processedImageUrl": _build_file_url(sampleId, files.get("postureProcessed")),
            "mosaicImageUrl": _build_file_url(sampleId, files.get("postureMosaic")),
        },
        "tongue": {
            "report": (m.get("tongue") or {}).get("report") or "",
            "tongueImageUrl": _build_file_url(sampleId, files.get("tongueImage")),
            "tongueInfo": (m.get("tongue") or {}).get("metaTongueInfo"),
        },
        "joint": m.get("joint") or {},
        "profileMeta": m.get("profileMeta") or {},
        "tcmTenQuestions": m.get("tcmTenQuestions") or {},
        "missingNotes": m.get("missingNotes") or {},
    }


@router.get("/file")
def get_sample_file(sampleId: str = Query(default="267"), relPath: str = Query(...)):
    p = (_sample_dir(sampleId) / relPath).resolve()
    try:
        p.relative_to(_sample_dir(sampleId).resolve())
    except Exception:
        raise HTTPException(status_code=400, detail="invalid path")
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    media, _ = mimetypes.guess_type(str(p))
    return FileResponse(str(p), media_type=media or "application/octet-stream", filename=p.name)


class RunFromSamplePayload(BaseModel):
    userId: str
    sampleId: str = "267"
    model: Optional[str] = None
    analysisMode: Optional[str] = "normal"
    fakeAgent: bool = False


@router.post("/run-posture-agent")
def run_posture_agent_from_sample(payload: RunFromSamplePayload, db: Session = Depends(get_db)):
    m = _read_manifest(payload.sampleId)
    posture = m.get("posture") or {}
    files = m.get("files") or {}
    user_row = get_or_create_user(db, payload.userId)

    titai_fb = posture.get("titai_fb")
    tixing_fb = posture.get("tixing_fb")
    titai_lr = posture.get("titai_lr")
    tixing_lr = posture.get("tixing_lr")
    profile = m.get("profileMeta") if isinstance(m.get("profileMeta"), dict) else {}
    user_info = {
        "userId": payload.userId,
        "age": profile.get("age"),
        "gender": profile.get("gender"),
        "height": profile.get("height"),
        "weight": profile.get("weight"),
        "allergyHistory": profile.get("allergyHistory"),
    }
    posture_info = {
        "titaiFront": titai_fb,
        "tixingFront": tixing_fb,
        "titaiSide": titai_lr,
        "tixingSide": tixing_lr,
    }

    report = (posture.get("report") or "").strip()
    if (not payload.fakeAgent) or (not report):
        report = ask_ai_posture(
            user_info=user_info,
            posture_info=posture_info,
            analysis_mode="expert" if str(payload.analysisMode).lower() == "expert" else "normal",
            model=payload.model,
        )

    rec = save_assessment(
        db,
        user=user_row,
        titai_fb=titai_fb,
        tixing_fb=tixing_fb,
        titai_lr=titai_lr,
        tixing_lr=tixing_lr,
        posture_analysis_text=report,
        tongue_analysis_text=None,
        comprehensive_analysis_text=None,
        front_image_path=_resolve_sample_image(payload.sampleId, files.get("postureFront")),
        processed_image_path=_resolve_sample_image(payload.sampleId, files.get("postureProcessed")),
        meta={
            "analysisType": "posture_only",
            "analysisMode": "expert" if str(payload.analysisMode).lower() == "expert" else "normal",
            "aiStatus": "done",
            "testMode": True,
            "sampleId": payload.sampleId,
            "fakeAgent": bool(payload.fakeAgent),
            "mosaicFrontImagePath": _resolve_sample_image(payload.sampleId, files.get("postureMosaic")),
            "profileMeta": m.get("profileMeta") or {},
        },
        tcm_ten_questions=m.get("tcmTenQuestions"),
    )
    return {"success": True, "recordId": rec.id, "report": rec.posture_analysis_text or "", "fakeAgent": bool(payload.fakeAgent)}


@router.post("/run-tongue-agent")
def run_tongue_agent_from_sample(payload: RunFromSamplePayload, db: Session = Depends(get_db)):
    m = _read_manifest(payload.sampleId)
    tongue = m.get("tongue") or {}
    files = m.get("files") or {}
    user_row = get_or_create_user(db, payload.userId)
    tongue_path = _resolve_sample_image(payload.sampleId, files.get("tongueImage"))
    if not tongue_path:
        raise HTTPException(status_code=400, detail="sample tongue image missing")

    report = (tongue.get("report") or "").strip()
    tongue_struct = tongue.get("metaTongueInfo")
    if (not payload.fakeAgent) or (not report):
        mime, _ = mimetypes.guess_type(tongue_path)
        info = analyze_tongue_image(
            image_path=tongue_path,
            mime=(mime or "image/jpeg"),
            tcm_ten_questions=m.get("tcmTenQuestions"),
            analysis_mode="expert" if str(payload.analysisMode).lower() == "expert" else "normal",
            model=payload.model,
        )
        tongue_struct = info
        report = format_tongue_analysis_report(info)

    rec = save_assessment(
        db,
        user=user_row,
        titai_fb=None,
        tixing_fb={"type": "tongue_only", "tongueStructured": tongue_struct},
        titai_lr=None,
        tixing_lr=None,
        posture_analysis_text=None,
        tongue_analysis_text=report,
        comprehensive_analysis_text=None,
        front_image_path=tongue_path,
        meta={
            "analysisType": "tongue_only",
            "analysisMode": "expert" if str(payload.analysisMode).lower() == "expert" else "normal",
            "aiStatus": "done",
            "testMode": True,
            "sampleId": payload.sampleId,
            "fakeAgent": bool(payload.fakeAgent),
            "tongueInfo": tongue_struct,
        },
        tcm_ten_questions=m.get("tcmTenQuestions"),
    )
    return {"success": True, "recordId": rec.id, "report": rec.tongue_analysis_text or "", "fakeAgent": bool(payload.fakeAgent)}


@router.post("/run-joint-agent")
def run_joint_agent_from_sample(payload: RunFromSamplePayload, db: Session = Depends(get_db)):
    m = _read_manifest(payload.sampleId)
    joint = m.get("joint") or {}
    posture = m.get("posture") or {}
    tongue = m.get("tongue") or {}
    files = m.get("files") or {}
    posture_front_path = _resolve_sample_image(payload.sampleId, files.get("postureFront"))
    posture_processed_path = _resolve_sample_image(payload.sampleId, files.get("postureProcessed"))
    posture_mosaic_path = _resolve_sample_image(payload.sampleId, files.get("postureMosaic"))
    user_row = get_or_create_user(db, payload.userId)

    posture_report = (joint.get("postureReport") or posture.get("report") or "").strip()
    tongue_report = (joint.get("tongueReport") or tongue.get("report") or "").strip()
    joint_report = (joint.get("report") or "").strip()

    if (not payload.fakeAgent) or (not joint_report):
        profile_summary = "\n".join(
            [
                f"年龄：{(m.get('profileMeta') or {}).get('age', '未填写')}",
                f"性别：{(m.get('profileMeta') or {}).get('gender', '未填写')}",
                f"身高：{(m.get('profileMeta') or {}).get('height', '未填写')}",
                f"体重：{(m.get('profileMeta') or {}).get('weight', '未填写')}",
            ]
        )
        joint_report = generate_joint_comprehensive_report(
            profile_summary=profile_summary,
            posture_report=posture_report,
            posture_metrics={
                "titai_fb": posture.get("titai_fb"),
                "tixing_fb": posture.get("tixing_fb"),
                "titai_lr": posture.get("titai_lr"),
                "tixing_lr": posture.get("tixing_lr"),
            },
            tongue_report=tongue_report,
            tongue_extra={"tongueInfo": tongue.get("metaTongueInfo")} if tongue.get("metaTongueInfo") else None,
            tcm_ten_questions=m.get("tcmTenQuestions"),
            analysis_mode="expert" if str(payload.analysisMode).lower() == "expert" else "normal",
            model=payload.model,
            extra_user_requirements=None,
        )

    rec = save_assessment(
        db,
        user=user_row,
        titai_fb={"type": "joint_final", "fromSampleId": payload.sampleId},
        tixing_fb={"fromSampleId": payload.sampleId},
        titai_lr=posture.get("titai_lr"),
        tixing_lr=posture.get("tixing_lr"),
        posture_analysis_text=posture_report,
        tongue_analysis_text=tongue_report,
        comprehensive_analysis_text=joint_report,
        front_image_path=posture_front_path,
        processed_image_path=posture_processed_path,
        meta={
            "analysisType": "joint_final",
            "analysisMode": "expert" if str(payload.analysisMode).lower() == "expert" else "normal",
            "testMode": True,
            "sampleId": payload.sampleId,
            "fakeAgent": bool(payload.fakeAgent),
            "profileMeta": m.get("profileMeta") or {},
            "mosaicFrontImagePath": posture_mosaic_path,
        },
        tcm_ten_questions=m.get("tcmTenQuestions"),
    )
    meta2 = dict(rec.meta_json or {})
    # 测试联合报告自身也可作为“人体图来源记录”
    meta2["sourcePostureRecordId"] = rec.id
    rec.meta_json = meta2
    db.commit()
    db.refresh(rec)
    return {
        "success": True,
        "recordId": rec.id,
        "reportSerial": rec.report_serial,
        "createdAt": rec.created_at.isoformat() if rec.created_at else None,
        "postureReport": posture_report,
        "tongueReport": tongue_report,
        "jointReport": joint_report,
        "fakeAgent": bool(payload.fakeAgent),
        "sourcePostureRecordId": rec.id,
    }
