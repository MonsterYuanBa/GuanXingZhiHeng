from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.crud import (
    get_or_create_user,
    get_profile_for_user,
    get_record_for_user,
    normalize_allergy_history,
    save_assessment,
)
from db.database import SessionLocal, get_db
from db.models import AssessmentRecord
from routes.posture_transfer.ask_AI_pos import ask_ai_posture
from routes.utils.api_helpers import save_uploaded_image, to_json_safe

router = APIRouter(prefix='/api/posture', tags=['posture'])


def _run_posture_ai_background(
    record_id: int,
    user_info: Dict[str, Any],
    posture_info: Dict[str, Any],
    model: Optional[str],
    analysis_mode: str,
) -> None:
    db = SessionLocal()
    try:
        rec = db.execute(select(AssessmentRecord).where(AssessmentRecord.id == record_id)).scalars().first()
        if rec is None:
            return
        try:
            report_text = ask_ai_posture(
                user_info,
                posture_info,
                analysis_mode=analysis_mode,
                model=model,
            )
            rec.posture_analysis_text = report_text
            meta = dict(rec.meta_json or {})
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


def _image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        return ''
    content = path.read_bytes()
    b64 = base64.b64encode(content).decode('utf-8')
    suffix = path.suffix.lower()
    mime = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
    }.get(suffix, 'image/jpeg')
    return f'data:{mime};base64,{b64}'


def _missing_number(value: Any) -> bool:
    if value is None:
        return True
    try:
        return float(value) <= 0
    except Exception:
        return True


def _missing_text(value: Any) -> bool:
    return value is None or str(value).strip() == ''

_POSTURE_KEY_CN_MAP = {
    "shoulder_tilt": "高低肩指数",
    "pelvic_tilt": "骨盆倾斜指数",
    "head_forward": "头前伸指数",
    "knee_alignment": "膝关节对齐指数",
}


def _normalize_posture_metric_keys_cn(data: Any) -> Any:
    """
    将体态结果中的英文 key 统一映射为中文 key。
    兼容旧流程仍返回英文 key 的情况。
    """
    if not isinstance(data, dict):
        return data
    out: Dict[str, Any] = {}
    for k, v in data.items():
        out[_POSTURE_KEY_CN_MAP.get(str(k), str(k))] = v
    return out


@router.post('/analyze')
async def analyze_posture(
    background_tasks: BackgroundTasks,
    meta: UploadFile = File(...),
    userId: Optional[str] = Form(default=None),
    frontImage: UploadFile = File(...),
    sideImage: UploadFile = File(...),
    model: Optional[str] = Form(default=None),
    analysisMode: Optional[str] = Form(default="normal"),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    print("---------------image proecss---------------")

    meta_obj: Dict[str, Any] = {}
    try:
        raw = await meta.read()
        meta_obj = json.loads(raw)
    except Exception:
        meta_obj = {'_raw_meta': 'parse_failed'}

    merged_user_id = (meta_obj.get('userId') if isinstance(meta_obj, dict) else None) or userId or 'admin'
    incoming_profile = meta_obj if isinstance(meta_obj, dict) else {}

    profile_meta = {
        'age': incoming_profile.get('age'),
        'gender': incoming_profile.get('gender'),
        'height': incoming_profile.get('height'),
        'weight': incoming_profile.get('weight'),
        'medicalHistory': incoming_profile.get('medicalHistory'),
        'workHabit': incoming_profile.get('workHabit'),
        'allergyHistory': incoming_profile.get('allergyHistory'),
    }
    source = 'request'

    need_db_fallback = (
        _missing_number(profile_meta['age'])
        or _missing_text(profile_meta['gender'])
        or _missing_number(profile_meta['height'])
        or _missing_number(profile_meta['weight'])
        or _missing_text(profile_meta['medicalHistory'])
        or _missing_text(profile_meta['workHabit'])
    )

    if need_db_fallback:
        db_profile = get_profile_for_user(db, merged_user_id)
        if db_profile is not None:
            if _missing_number(profile_meta['age']):
                profile_meta['age'] = db_profile.age
            if _missing_text(profile_meta['gender']):
                profile_meta['gender'] = db_profile.gender
            if _missing_number(profile_meta['height']):
                profile_meta['height'] = db_profile.height
            if _missing_number(profile_meta['weight']):
                profile_meta['weight'] = db_profile.weight
            if _missing_text(profile_meta['medicalHistory']):
                profile_meta['medicalHistory'] = db_profile.medical_history
            if _missing_text(profile_meta['workHabit']):
                profile_meta['workHabit'] = db_profile.work_habit
            if _missing_text(profile_meta.get('allergyHistory')):
                profile_meta['allergyHistory'] = db_profile.allergy_history
            source = 'database'

    profile_meta['allergyHistory'] = normalize_allergy_history(profile_meta.get('allergyHistory'))

    merged = {
        'userId': merged_user_id,
        'profileMeta': profile_meta,
        'profileSource': source,
    }

    # 先落库拿到 recordId，再用 recordId 固定命名保存图片（同 ID 可覆盖）
    user_row = get_or_create_user(db, merged_user_id)
    analysis_mode = "expert" if str(analysisMode or "").strip().lower() == "expert" else "normal"
    record = save_assessment(
        db,
        user=user_row,
        titai_fb=None,
        tixing_fb=None,
        titai_lr=None,
        tixing_lr=None,
        posture_analysis_text=None,
        tongue_analysis_text=None,
        comprehensive_analysis_text=None,
        front_image_path=None,
        processed_image_path=None,
        meta={
            'analysisType': 'posture_only',
            'analysisMode': analysis_mode,
            'generatedAt': datetime.utcnow().isoformat(),
            'aiStatus': 'pending',
            'profileMeta': profile_meta,
            'profileSource': source,
        },
        tcm_ten_questions=None,
    )

    front_path, front_image_info = await save_uploaded_image(
        frontImage,
        preferred_stem=f"{record.id}_posture_front",
        overwrite=True,
    )
    side_path, side_image_info = await save_uploaded_image(
        sideImage,
        preferred_stem=f"{record.id}_posture_side",
        overwrite=True,
    )
    record.front_image_path = front_path
    db.commit()

    # ---------------有图像处理---------------
    import os
    _ROOT = Path(__file__).resolve().parents[2]
    sam_checkpoint_path = os.getenv(
        "SAM_CHECKPOINT_PATH",
        str(_ROOT / "models" / "sam_vit_h_4b8939.pth"),
    )
    from image_process import main_process

    titai_fb, tixing_fb, titai_lr, tixing_lr, processed_path, mosaic_base_path = main_process(
        sam_checkpoint_path=sam_checkpoint_path,
        front_path=front_path,
        left_path=side_path,
        right_path=None,
        mosaic=True
    )
    print(titai_fb)
    print(titai_lr)
    print(tixing_fb)
    print(tixing_lr)

    # # ---------------无图像处理1---------------
    # titai_fb = {'高低肩指数': 0.03368673324222257, '骨盆倾斜指数': 0.03368672699526495}
    # titai_lr = {'头前伸指数': 0.08849543773366204, '膝关节对齐指数': 0.03883818239934535}
    # tixing_fb = {'头身比': 7.533027399851884, '腿身比': 0.43016070267214324,
    # '大腿小腿比': 1.0847156140661094, '躯干身高比': 0.2705522456851588,
    # '头肩比': 0.3961865916755629, '上下身面积比': 1.0981624523633697}
    # tixing_lr = {'腹部前突指数': 0.40199514195538966}
    # processed_path = front_path

    # # ---------------无图像处理2---------------
    # titai_fb = {'高低肩指数': 0.0818622202339661, '骨盆倾斜指数': 0.05411017480814968}
    # titai_lr = {'头前伸指数': 0.060869525625573385, '膝关节对齐指数': 0.035960470879906226}
    # tixing_fb = {'头身比': 7.656523948616715, '腿身比': 0.43749268999503726,
    # '大腿小腿比': 1.0756126175772545, '躯干身高比': 0.2750917225913206,
    # '头肩比': 0.397014689895342, '上下身面积比': 1.0879287137242233}
    # tixing_lr = {'腹部前突指数': 0.4524240746491459}
    # processed_path = front_path
    # # ---------------无图像处理3---------------
    # titai_fb = {'高低肩指数': 0.07967611389921195, '骨盆倾斜指数': 0.03293640414822189}
    # titai_lr = {'头前伸指数': 0.04385964152198854, '膝关节对齐指数':0.03496046680914616 }
    # tixing_fb = {'头身比': 7.493588184825447, '腿身比': 0.4337743552231866,
    #              '大腿小腿比': 1.0618923968391418, '躯干身高比': 0.27584996293740927,
    #              '头肩比': 0.3990004837878643, '上下身面积比': 1.1207298413412232}
    # tixing_lr = {'腹部前突指数': 0.4218203895970395}
    # processed_path = front_path
    # # ---------------无图像处理4---------------
    # titai_fb = {'高低肩指数': 0.04883517476145499, '骨盆倾斜指数': 0.03350275978092839}
    # titai_lr = {'头前伸指数':0.04464285703686824 , '膝关节对齐指数': 0.036237411288602}
    # tixing_fb = {'头身比': 7.641334739363611, '腿身比': 0.4322576802057202,
    #              '大腿小腿比': 1.0825559789950046, '躯干身高比': 0.2733116011321085,
    #              '头肩比': 0.37208727695430516, '上下身面积比': 1.1186127809722948}
    # tixing_lr = {'腹部前突指数': 0.3862466333119292}
    # processed_path = front_path
    #         # ---------------无图像处理5--------------
    # titai_fb = {'高低肩指数': 0.03350238627372401, '骨盆倾斜指数': 0.032366620756693794}
    # titai_lr = {'头前伸指数': 0.04125634534563579, '膝关节对齐指数':0.03146873950764869 }
    # tixing_fb = {'头身比': 7.5196554314255435, '腿身比': 0.42979168561179165,
    #              '大腿小腿比': 1.089535766185014, '躯干身高比': 0.2708950349220681,
    #              '头肩比': 0.3923317307692308, '上下身面积比': 1.0995975963665001}
    # tixing_lr = {'腹部前突指数':0.4018946550894473 }
    # processed_path = front_path


    # ---------------继续---------------
    titai_fb = _normalize_posture_metric_keys_cn(titai_fb)
    titai_lr = _normalize_posture_metric_keys_cn(titai_lr)

    titai_fb = to_json_safe(titai_fb)
    tixing_fb = to_json_safe(tixing_fb)
    titai_lr = to_json_safe(titai_lr)
    tixing_lr = to_json_safe(tixing_lr)

    # 前端展示：优先用 main_process 生成的 mask+关键点图；无则退回原上传图
    display_path = processed_path if processed_path else front_path
    result_image_data_url = _image_to_data_url(display_path)

    posture_info = {
        'titaiFront': to_json_safe(titai_fb),
        'tixingFront': to_json_safe(tixing_fb),
        'titaiSide': to_json_safe(titai_lr),
        'tixingSide': to_json_safe(tixing_lr),
    }

    user_info = {
        'userId': merged_user_id,
        'name': incoming_profile.get('name') if isinstance(incoming_profile, dict) else None,
        'age': profile_meta.get('age'),
        'gender': profile_meta.get('gender'),
        'height': profile_meta.get('height'),
        'weight': profile_meta.get('weight'),
        'allergyHistory': profile_meta.get('allergyHistory'),
    }

    titai_fb_stored = {**titai_fb, 'type': 'posture_only'}
    tcm_ten = incoming_profile.get('tcmTenQuestions') if isinstance(incoming_profile, dict) else None
    record.titai_fb = to_json_safe(titai_fb_stored)
    record.tixing_fb = to_json_safe(tixing_fb)
    record.titai_lr = to_json_safe(titai_lr)
    record.tixing_lr = to_json_safe(tixing_lr)
    record.posture_analysis_text = None
    record.tongue_analysis_text = None
    record.comprehensive_analysis_text = None
    record.processed_image_path = processed_path
    meta2 = dict(record.meta_json or {})
    # 仅马赛克底图（无关键点/无mask），用于综合报告页人体图像对比拉条
    meta2['mosaicFrontImagePath'] = mosaic_base_path
    record.meta_json = meta2
    record.tcm_ten_questions = to_json_safe(tcm_ten)
    db.commit()
    print("------waiting for AI response...------")
    background_tasks.add_task(
        _run_posture_ai_background,
        record.id,
        user_info,
        posture_info,
        model,
        analysis_mode,
    )

    return {
        'success': True,
        'msg': '体态数据已生成，智能体正在分析中',
        'authorization': authorization,
        'receivedMeta': meta_obj,
        'receivedFieldsMerged': merged,
        'deepseek_advice': '',
        'aiPending': True,
        'titai_fb': titai_fb,
        'tixing_fb': tixing_fb,
        'titai_lr': titai_lr,
        'tixing_lr': tixing_lr,
        'resultImageUrl': result_image_data_url,
        'resultImageTransform': 'none',
        'displayImagePath': processed_path,
        # 'imageInfo': image_info,
        'recordId': record.id,
        'createdAt': record.created_at.isoformat() if record.created_at else None,
    }


@router.get('/report-status')
def get_posture_report_status(recordId: int = Query(...), userId: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    rec = get_record_for_user(db, userId, recordId)
    if rec is None:
        return {"success": False, "message": "record not found", "done": False}
    meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
    status = meta.get("aiStatus") or ("done" if (rec.posture_analysis_text or "").strip() else "pending")
    return {
        "success": True,
        "done": status == "done",
        "status": status,
        "report": rec.posture_analysis_text or "",
        "error": meta.get("aiError") or "",
    }
