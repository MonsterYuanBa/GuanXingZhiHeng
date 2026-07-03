from __future__ import annotations

from datetime import datetime
import json
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.crud import (
    get_record_for_user,
    get_latest_record_with_posture_text,
    get_latest_record_with_tongue_text,
    list_records_for_user,
    get_or_create_user,
    get_profile_for_user,
    save_assessment,
)
from db.database import get_db
from db.joint_requirements_store import (
    append_to_record_meta,
    format_entries_for_prompt,
    get_entries_for_record,
    merge_entries_from_records,
    normalize_stored_requirements,
    remove_entry_by_seq,
    set_record_user_requirement_log,
)
from routes.posture_transfer.ask_AI_pos import improve_posture_report
from routes.review_orchestrator.ai import evaluate_report_quality
from routes.schemas import JointDetailedAnalysisPayload, JointReportPayload, JointUserRequirementAppend
from routes.tongue_transfer.ask_AI_tongue import improve_tongue_report
from routes.utils.ai_mock import is_mock_ai_enabled
from routes.utils.system_console import clear_system_status_lines, get_system_status_lines, push_system_status
from .ask_AI_analyse import generate_joint_comprehensive_report, improve_joint_comprehensive_report

router = APIRouter(prefix='/api/joint-report', tags=['joint-report'])


@router.get('/status')
def get_joint_report_status(userId: str = Query(..., alias="userId")):
    return {
        "success": True,
        "userId": (userId or "admin").strip() or "admin",
        "lines": get_system_status_lines(userId),
    }


@router.post('/status/clear')
def clear_joint_report_status(userId: str = Query(..., alias="userId")):
    clear_system_status_lines(userId)
    return {
        "success": True,
        "userId": (userId or "admin").strip() or "admin",
    }


@router.get("/user-requirements")
def list_joint_user_requirements(
    userId: str = Query(..., alias="userId"),
    recordId: Optional[int] = Query(None, alias="recordId"),
    db: Session = Depends(get_db),
):
    uid = (userId or "admin").strip() or "admin"
    entries: list = []
    if recordId is not None and int(recordId) > 0:
        entries = get_entries_for_record(db, uid, int(recordId))
    return {"success": True, "userId": uid, "entries": entries}


@router.post("/user-requirement")
def append_joint_user_requirement(
    payload: JointUserRequirementAppend,
    db: Session = Depends(get_db),
    remove_seq: Optional[int] = Query(None, alias="removeSeq"),
):
    rid = payload.recordId

    # 删除走 URL 查询参数 removeSeq，不依赖 body 里新增字段（避免旧模型忽略字段后误走「text 为空」）
    if remove_seq is not None:
        try:
            rs = int(remove_seq)
        except (TypeError, ValueError):
            return {"success": False, "message": "序号无效", "entries": []}
        if rs < 1:
            return {"success": False, "message": "序号无效", "entries": []}
        if rid is None or int(rid) <= 0:
            return {
                "success": False,
                "message": "请提供已落库的记录 recordId",
                "entries": [],
            }
        rec = get_record_for_user(db, payload.userId, int(rid))
        if rec is None:
            return {"success": False, "message": "记录不存在", "entries": []}
        entries = remove_entry_by_seq(db, rec, rs)
        return {"success": True, "message": "已删除", "entries": entries}

    if payload.clearExisting:
        if rid is None or int(rid) <= 0:
            return {
                "success": False,
                "message": "请提供已落库的记录 recordId",
                "entries": [],
            }
        rec = get_record_for_user(db, payload.userId, int(rid))
        if rec is None:
            return {"success": False, "message": "记录不存在", "entries": []}
        set_record_user_requirement_log(db, rec, [])
        return {"success": True, "message": "已清除原有需求", "entries": []}

    text = (payload.text or "").strip()
    if not text:
        return {"success": False, "message": "需求内容不能为空", "entries": []}
    if rid is None or int(rid) <= 0:
        return {
            "success": False,
            "message": "请提供已落库的记录 recordId（需求仅保存在该条历史记录上）",
            "entries": [],
        }
    rec = get_record_for_user(db, payload.userId, int(rid))
    if rec is None:
        return {"success": False, "message": "记录不存在", "entries": []}
    entries = append_to_record_meta(db, rec, text)
    return {"success": True, "message": "已保存", "entries": entries}


def _format_profile_for_prompt(db: Session, user_id: str) -> str:
    p = get_profile_for_user(db, user_id)
    if p is None:
        return "系统中暂无该用户的档案信息（年龄、性别、身高、体重等均未填写）。"
    lines = [
        f"年龄：{p.age if p.age is not None else '未填写'}",
        f"性别：{p.gender or '未填写'}",
        f"身高：{p.height if p.height is not None else '未填写'}",
        f"体重：{p.weight if p.weight is not None else '未填写'}",
        f"过敏情况：{(p.allergy_history or '').strip() or '无过敏史'}",
        f"既往相关情况（用户自填，仅供参考）：{p.medical_history or '未填写'}",
        f"工作/作息习惯（用户自填）：{p.work_habit or '未填写'}",
    ]
    return "\n".join(lines)


def _profile_snapshot_from_user_profile(db: Session, user_id: str) -> Dict[str, Any]:
    p = get_profile_for_user(db, user_id)
    if p is None:
        return {
            "age": None,
            "gender": None,
            "height": None,
            "weight": None,
            "allergyHistory": "无过敏史",
            "medicalHistory": None,
            "workHabit": None,
        }
    return {
        "age": p.age,
        "gender": p.gender,
        "height": p.height,
        "weight": p.weight,
        "allergyHistory": (p.allergy_history or "").strip() or "无过敏史",
        "medicalHistory": p.medical_history,
        "workHabit": p.work_habit,
    }


def _resolve_profile_snapshot_for_joint(db: Session, user_id: str, posture_rec: Any) -> tuple[Dict[str, Any], str]:
    meta = posture_rec.meta_json if posture_rec is not None and isinstance(posture_rec.meta_json, dict) else {}
    profile_meta = meta.get("profileMeta") if isinstance(meta.get("profileMeta"), dict) else None
    if profile_meta:
        return dict(profile_meta), str(meta.get("profileSource") or "posture_record")
    return _profile_snapshot_from_user_profile(db, user_id), "database"


def _posture_metrics_from_record(rec: Any) -> Dict[str, Any]:
    return {
        "titai_fb": rec.titai_fb,
        "tixing_fb": rec.tixing_fb,
        "titai_lr": rec.titai_lr,
        "tixing_lr": rec.tixing_lr,
    }


def _tongue_extra_from_record(rec: Any) -> Optional[Dict[str, Any]]:
    extra: Dict[str, Any] = {}
    meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
    tx = rec.tixing_fb if isinstance(rec.tixing_fb, dict) else {}
    if meta.get("tongueInfo") is not None:
        extra["tongueInfo"] = meta["tongueInfo"]
    if tx.get("tongueStructured") is not None:
        extra["tongueStructured"] = tx["tongueStructured"]
    return extra if extra else None


HEAVY_KEYS = {
    "resultImageUrl",
    "imageUrl",
    "result_image_url",
    "image_url",
    "previewUrl",
    "dataUrl",
    "frontImage",
    "sideImage",
}


def _is_data_url(s: Any) -> bool:
    return isinstance(s, str) and s.startswith("data:") and "base64," in s


def _strip_heavy(value: Any, depth: int = 0) -> Any:
    if value is None or depth > 8:
        return value
    if isinstance(value, str):
        return None if _is_data_url(value) else value
    if isinstance(value, list):
        out_list = []
        for v in value:
            vv = _strip_heavy(v, depth + 1)
            if vv is not None:
                out_list.append(vv)
        return out_list
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if k in HEAVY_KEYS:
                continue
            if _is_data_url(v):
                continue
            vv = _strip_heavy(v, depth + 1)
            if vv is not None:
                out[k] = vv
        return out
    return value


def _safe_context_text(value: Any, max_len: int = 8000) -> str:
    cleaned = _strip_heavy(value)
    try:
        text = json.dumps(cleaned, ensure_ascii=False, indent=2)
    except Exception:
        text = str(cleaned)
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n...[TRUNCATED total={len(text)} kept={max_len}]"


def _resolve_record_for_detail(db: Session, user_id: str, record_id: Optional[int]):
    if record_id is not None:
        rec = get_record_for_user(db, user_id, record_id)
        if rec is not None:
            return rec
    rows = list_records_for_user(db, user_id, limit=1)
    return rows[0] if rows else None


def _iterative_refine_report(
    *,
    user_id: str,
    report_type: str,
    initial_text: str,
    base_context: str,
    max_rounds: int,
    improve_fn,
):
    text = (initial_text or "").strip()
    rounds: list[Dict[str, Any]] = []
    rewrite_count = 0
    for i in range(1, max_rounds + 1):
        push_system_status(
            user_id,
            f"专家深度分析-{report_type}：开始评估（第{i}轮）",
            "#3b82f6",
        )
        try:
            review = evaluate_report_quality(
                report_type=report_type,
                report_text=text,
                base_context=base_context,
                iteration=i,
                max_iterations=max_rounds,
            )
        except Exception as e:
            msg = f"失败（第{i}轮）：{e}"
            rounds.append({"round": i, "score": 0, "comment": msg, "error": True, "stage": "review"})
            push_system_status(user_id, f"专家深度分析-{report_type}：评估失败，流程停止", "#ef4444")
            break
            
        score = int(review.get("score") or 0)
        comment = str(review.get("comment") or "")
        rounds.append({"round": i, "score": score, "comment": comment})
        if score == 1 and rewrite_count >= 1:
            push_system_status(user_id, f"专家深度分析-{report_type}：评估通过", "#22c55e")
            return text, rounds

        if score == 1 and rewrite_count < 1:
            push_system_status(user_id, f"专家深度分析-{report_type}：改写优化中（第1轮）")
            comment = "评估已通过。请在不改变结论前提下做一轮精炼改写，提升可读性和可执行性。"
        else:
            push_system_status(user_id, f"专家深度分析-{report_type}：评估未通过，改写（第{i}轮）")

        try:
            if is_mock_ai_enabled():
                # 测试模式下增加短暂停顿，让前端流程动画更接近真实调用节奏
                time.sleep(2)
            text = improve_fn(text, comment, i)
            rewrite_count += 1
        except Exception as e:
            msg = f"失败（第{i}轮）：{e}"
            rounds.append({"round": i, "score": 0, "comment": msg, "error": True, "stage": "improve"})
            push_system_status(user_id, f"专家深度分析-{report_type}：改写失败，流程停止", "#ef4444")
            break

    push_system_status(user_id, f"专家深度分析-{report_type}：结束")
    return text, rounds


def _has_iteration_error(rounds: list[Dict[str, Any]]) -> bool:
    return any(bool(r.get("error")) for r in rounds)


@router.post('/generate')
def generate_joint_report(payload: JointReportPayload, db: Session = Depends(get_db)):
    print("------waiting for AI response...------")
    push_system_status(payload.userId, "常规分析：收到生成请求")
    push_system_status(payload.userId, "常规分析：正在整理体态与舌苔数据")
    analysis_mode = "expert" if str(getattr(payload, "analysisMode", "")).strip().lower() == "expert" else "normal"
    profile_summary = _format_profile_for_prompt(db, payload.userId)

    posture_rec = get_latest_record_with_posture_text(db, payload.userId)
    tongue_rec = get_latest_record_with_tongue_text(db, payload.userId)

    posture_report = (posture_rec.posture_analysis_text or "").strip() if posture_rec else ""
    if not posture_report:
        posture_report = (payload.postureReport or "").strip()

    tongue_report = (tongue_rec.tongue_analysis_text or "").strip() if tongue_rec else ""
    if not tongue_report:
        tongue_report = (payload.tongueReport or "").strip()

    if not posture_report and not tongue_report:
        push_system_status(payload.userId, "常规分析：未找到可用的体态/舌苔正文，无法生成")
        return {
            "success": False,
            "message": "未找到体态或舌苔分析正文：请先在系统中完成体态与舌苔分析并保存记录，或检查 userId 是否与分析时一致。",
            "recordId": None,
            "createdAt": None,
            "analysisType": "joint_final",
            "postureReport": posture_report,
            "tongueReport": tongue_report,
            "jointReport": None,
            "mockAi": is_mock_ai_enabled(),
        }

    posture_metrics: Optional[Dict[str, Any]] = None
    if posture_rec:
        posture_metrics = _posture_metrics_from_record(posture_rec)
    elif payload.postureData:
        posture_metrics = {"fromRequest": payload.postureData}

    tongue_extra: Optional[Dict[str, Any]] = None
    if tongue_rec:
        tongue_extra = _tongue_extra_from_record(tongue_rec)
    if tongue_extra is None and payload.tongueData:
        tongue_extra = {"fromRequest": payload.tongueData}

    tcm_for_prompt: Optional[Dict[str, Any]] = None
    if isinstance(getattr(payload, "tcmTenQuestions", None), dict) and payload.tcmTenQuestions:
        tcm_for_prompt = payload.tcmTenQuestions
    elif posture_rec is not None and getattr(posture_rec, "tcm_ten_questions", None) is not None:
        tcm_for_prompt = posture_rec.tcm_ten_questions
    elif tongue_rec is not None and getattr(tongue_rec, "tcm_ten_questions", None) is not None:
        tcm_for_prompt = tongue_rec.tcm_ten_questions

    merged_pre_joint_reqs = merge_entries_from_records(
        db, payload.userId, posture_rec, tongue_rec
    )
    extra_req_text = format_entries_for_prompt(merged_pre_joint_reqs)

    try:
        push_system_status(payload.userId, "常规分析：正在分析中")
        # joint_report =  "hahaha"
        joint_report = generate_joint_comprehensive_report(
            profile_summary=profile_summary,
            posture_report=posture_report,
            posture_metrics=posture_metrics,
            tongue_report=tongue_report,
            tongue_extra=tongue_extra,
            tcm_ten_questions=tcm_for_prompt,
            analysis_mode=analysis_mode,
            model=payload.model,
            extra_user_requirements=extra_req_text or None,
        )
        push_system_status(payload.userId, "常规分析：分析完成，正在写入报告")
    except Exception as e:
        push_system_status(payload.userId, f"常规分析：分析失败：{e}")
        return {
            "success": False,
            "message": f"联合报告生成失败：{e}",
            "recordId": None,
            "createdAt": None,
            "analysisType": "joint_final",
            "postureReport": posture_report,
            "tongueReport": tongue_report,
            "jointReport": None,
            "mockAi": is_mock_ai_enabled(),
        }

    user_row = get_or_create_user(db, payload.userId)
    profile_meta_snapshot, profile_source = _resolve_profile_snapshot_for_joint(db, payload.userId, posture_rec)
    tcm_ten = tcm_for_prompt
    if tcm_ten is None and posture_rec is not None:
        tcm_ten = getattr(posture_rec, "tcm_ten_questions", None)
    if tcm_ten is None and tongue_rec is not None:
        tcm_ten = getattr(tongue_rec, "tcm_ten_questions", None)

    joint_titai_lr = None
    joint_tixing_lr = None
    if isinstance(posture_metrics, dict):
        joint_titai_lr = posture_metrics.get("titai_lr")
        joint_tixing_lr = posture_metrics.get("tixing_lr")
    if joint_titai_lr is None and isinstance(payload.postureData, dict):
        joint_titai_lr = payload.postureData.get("titai_lr") or payload.postureData.get("titaiLr")
    if joint_tixing_lr is None and isinstance(payload.postureData, dict):
        joint_tixing_lr = payload.postureData.get("tixing_lr") or payload.postureData.get("tixingLr")

    record = save_assessment(
        db,
        user=user_row,
        titai_fb={
            "type": "joint_final",
            "sourcePostureRecordId": posture_rec.id if posture_rec else None,
            "postureData": payload.postureData,
        },
        tixing_fb={
            "sourceTongueRecordId": tongue_rec.id if tongue_rec else None,
            "tongueData": payload.tongueData,
        },
        titai_lr=joint_titai_lr,
        tixing_lr=joint_tixing_lr,
        posture_analysis_text=posture_report,
        tongue_analysis_text=tongue_report,
        comprehensive_analysis_text=joint_report,
        front_image_path=None,
        meta={
            "analysisType": "joint_final",
            "analysisMode": analysis_mode,
            "generatedAt": datetime.utcnow().isoformat(),
            "postureAt": payload.postureAt,
            "tongueAt": payload.tongueAt,
            "sourcePostureRecordId": posture_rec.id if posture_rec else None,
            "sourceTongueRecordId": tongue_rec.id if tongue_rec else None,
            "profileMeta": profile_meta_snapshot,
            "profileSource": profile_source,
            "profileSummarySnapshot": profile_summary,
            "postureMetricsSnapshot": posture_metrics,
            "tongueExtraSnapshot": tongue_extra,
        },
        tcm_ten_questions=tcm_ten,
        user_requirements=merged_pre_joint_reqs if merged_pre_joint_reqs else normalize_stored_requirements([]),
    )
    push_system_status(
        payload.userId,
        f"常规分析：报告已保存，报告编号: {record.report_serial}（内部记录 {record.id}）",
    )

    return {
        "success": True,
        "msg": "联合报告生成完成",
        "recordId": record.id,
        "reportSerial": record.report_serial,
        "createdAt": record.created_at.isoformat() if record.created_at else None,
        "analysisType": "joint_final",
        "sourcePostureRecordId": posture_rec.id if posture_rec else None,
        "sourceTongueRecordId": tongue_rec.id if tongue_rec else None,
        "postureReport": posture_report,
        "tongueReport": tongue_report,
        "jointReport": joint_report,
        "mockAi": is_mock_ai_enabled(),
    }


@router.post('/detailed-analysis')
def detailed_analysis(payload: JointDetailedAnalysisPayload, db: Session = Depends(get_db)):
    user_id = payload.userId
    max_rounds = max(1, min(int(payload.maxRounds or 3), 3))
    analysis_mode = "expert" if str(getattr(payload, "analysisMode", "")).strip().lower() == "expert" else "normal"
    push_system_status(user_id, "开始专家深度分析：准备读取历史记录")

    source = _resolve_record_for_detail(db, user_id, payload.recordId)
    if source is None:
        push_system_status(user_id, "专家深度分析失败：未找到可用历史记录")
        return {"success": False, "message": "未找到可用历史记录", "recordId": None}

    req_from_log = format_entries_for_prompt(get_entries_for_record(db, user_id, source.id))
    legacy = (payload.userRequirement or "").strip()
    if legacy:
        user_requirement = f"{req_from_log}\n{legacy}".strip() if req_from_log else legacy
    else:
        user_requirement = req_from_log

    user_row = get_or_create_user(db, user_id)
    _req_copy = get_entries_for_record(db, user_id, source.id)
    cloned_user_req = _req_copy if _req_copy else None
    clone_meta_base = dict(source.meta_json or {})
    clone_meta_base.pop("userRequirementLog", None)
    cloned = save_assessment(
        db,
        user=user_row,
        titai_fb=source.titai_fb,
        tixing_fb=source.tixing_fb,
        titai_lr=source.titai_lr,
        tixing_lr=source.tixing_lr,
        posture_analysis_text=source.posture_analysis_text,
        tongue_analysis_text=source.tongue_analysis_text,
        comprehensive_analysis_text=source.comprehensive_analysis_text,
        front_image_path=source.front_image_path,
        processed_image_path=source.processed_image_path,
        meta={
            **clone_meta_base,
            "analysisType": "joint_detailed",
            "detailSourceRecordId": source.id,
            "detailStartedAt": datetime.utcnow().isoformat(),
        },
        tcm_ten_questions=source.tcm_ten_questions,
        history_chart_data=source.history_chart_data,
        user_requirements=cloned_user_req,
    )
    push_system_status(user_id, f"已创建专家深度分析记录（复制自#{source.id} -> #{cloned.id}）")

    profile_summary = _format_profile_for_prompt(db, user_id)
    posture_metrics = _posture_metrics_from_record(source)
    tongue_extra = _tongue_extra_from_record(source)
    posture_metrics_clean = _strip_heavy(posture_metrics)
    tongue_extra_clean = _strip_heavy(tongue_extra)
    tcm_for_prompt = source.tcm_ten_questions if isinstance(source.tcm_ten_questions, dict) else None

    posture_text, posture_rounds = _iterative_refine_report(
        user_id=user_id,
        report_type="体态体型报告",
        initial_text=source.posture_analysis_text or "",
        base_context="仅评审体态体型报告文本质量（是否具体、可执行、避免空话）。",
        max_rounds=max_rounds,
        improve_fn=lambda prev, comment, i: improve_posture_report(
            user_info={"userId": user_id},
            posture_info=posture_metrics_clean,
            previous_output=prev,
            reviewer_comment=comment,
            iteration=i,
            max_iterations=max_rounds,
            analysis_mode=analysis_mode,
            model=payload.model,
        ),
    )
    if _has_iteration_error(posture_rounds):
        push_system_status(user_id, "专家深度分析中断：体态体型报告阶段出现错误，流程已停止")
        return {
            "success": False,
            "message": "专家深度分析失败：体态体型报告改写阶段出错，已停止。",
            "recordId": cloned.id,
            "sourceRecordId": source.id,
            "detailReviews": {"posture": posture_rounds},
        }

    tongue_text, tongue_rounds = _iterative_refine_report(
        user_id=user_id,
        report_type="舌苔报告",
        initial_text=source.tongue_analysis_text or "",
        base_context="仅评审舌苔报告文本质量（是否具体、可执行、避免空话）。",
        max_rounds=max_rounds,
        improve_fn=lambda prev, comment, i: improve_tongue_report(
            previous_output=prev,
            reviewer_comment=comment,
            tongue_extra=tongue_extra_clean,
            tcm_ten_questions=tcm_for_prompt,
            iteration=i,
            max_iterations=max_rounds,
            analysis_mode=analysis_mode,
            model=payload.model,
        ),
    )
    if _has_iteration_error(tongue_rounds):
        push_system_status(user_id, "专家深度分析中断：舌苔报告阶段出现错误，流程已停止")
        return {
            "success": False,
            "message": "专家深度分析失败：舌苔报告改写阶段出错，已停止。",
            "recordId": cloned.id,
            "sourceRecordId": source.id,
            "detailReviews": {"posture": posture_rounds, "tongue": tongue_rounds},
        }

    joint_text, joint_rounds = _iterative_refine_report(
        user_id=user_id,
        report_type="综合报告",
        initial_text=source.comprehensive_analysis_text or "",
        base_context="仅评审综合报告文本质量（是否具体、可执行、避免空话）。",
        max_rounds=max_rounds,
        improve_fn=lambda prev, comment, i: improve_joint_comprehensive_report(
            profile_summary=profile_summary,
            posture_report=posture_text,
            tongue_report=tongue_text,
            previous_output=prev,
            reviewer_comment=comment,
            iteration=i,
            max_iterations=max_rounds,
            tcm_ten_questions=tcm_for_prompt,
            user_requirement=user_requirement,
            analysis_mode=analysis_mode,
            model=payload.model,
        ),
    )
    if _has_iteration_error(joint_rounds):
        push_system_status(user_id, "专家深度分析中断：综合报告阶段出现错误，流程已停止")
        return {
            "success": False,
            "message": "专家深度分析失败：综合报告改写阶段出错，已停止。",
            "recordId": cloned.id,
            "sourceRecordId": source.id,
            "detailReviews": {"posture": posture_rounds, "tongue": tongue_rounds, "joint": joint_rounds},
        }

    cloned.posture_analysis_text = posture_text
    cloned.tongue_analysis_text = tongue_text
    cloned.comprehensive_analysis_text = joint_text
    meta = dict(cloned.meta_json or {})
    if user_requirement:
        meta["userRequirement"] = user_requirement
        if not is_mock_ai_enabled():
            push_system_status(user_id, "已接收用户补充需求，将作为常规分析提示词的一部分")
    meta["analysisMode"] = analysis_mode
    meta["detailFinishedAt"] = datetime.utcnow().isoformat()
    meta["detailReviews"] = {
        "posture": posture_rounds,
        "tongue": tongue_rounds,
        "joint": joint_rounds,
    }
    cloned.meta_json = meta
    db.commit()
    db.refresh(cloned)
    push_system_status(
        user_id,
        f"专家深度分析完成，报告编号: {cloned.report_serial}（内部记录 {cloned.id}）",
    )

    _mock = is_mock_ai_enabled()
    _legacy_strip = legacy.strip() if legacy else ""
    return {
        "success": True,
        "msg": "专家深度分析完成",
        "recordId": cloned.id,
        "reportSerial": cloned.report_serial,
        "createdAt": cloned.created_at.isoformat() if cloned.created_at else None,
        "sourceRecordId": source.id,
        "postureReport": cloned.posture_analysis_text or "",
        "tongueReport": cloned.tongue_analysis_text or "",
        "jointReport": cloned.comprehensive_analysis_text or "",
        "detailReviews": meta.get("detailReviews"),
        "mockAi": _mock,
        "mockSupplementalRequirement": _legacy_strip if _mock and _legacy_strip else None,
    }
