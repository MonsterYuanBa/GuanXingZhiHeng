from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.crud import get_or_create_user, save_assessment
from db.database import get_db
from db.models import AssessmentRecord
from routes.schemas import HistoryAnalysisPayload

from .ask_AI_history import (
    analyze_history_from_joint_reports,
    build_joint_report_rows,
    has_joint_report_content,
)

router = APIRouter(prefix='/api/history-analysis', tags=['history-analysis'])

_METRIC_SKIP_KEYS = {
    # 结构化对象里常见的元字段
    "type",
    "sourcePostureRecordId",
    "sourceTongueRecordId",
    "sourceRecordIds",
    "sourceCount",
}


def _to_number(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


def _collect_numeric_metrics(obj: Any, *, prefix: str = "", out: Optional[Dict[str, float]] = None, depth: int = 0) -> Dict[str, float]:
    """
    深度遍历结构化数据，稳定提取「可画折线图」的数值字段。
    - 只收集 int/float 或可转 float 的字符串
    - 跳过明显是元字段的 key
    - 限制递归深度避免超大对象
    """
    if out is None:
        out = {}
    if obj is None or depth > 6:
        return out

    if isinstance(obj, dict):
        for k, v in obj.items():
            ks = str(k)
            if ks in _METRIC_SKIP_KEYS:
                continue
            next_prefix = f"{prefix}.{ks}" if prefix else ks
            num = _to_number(v)
            if num is not None:
                out[next_prefix] = num
                continue
            if isinstance(v, (dict, list, tuple)):
                _collect_numeric_metrics(v, prefix=next_prefix, out=out, depth=depth + 1)
        return out

    if isinstance(obj, (list, tuple)):
        # list 里一般不是稳定指标，这里只在元素为 dict 时继续递归，并用索引做 path（保守）
        for i, v in enumerate(obj):
            next_prefix = f"{prefix}[{i}]" if prefix else f"[{i}]"
            num = _to_number(v)
            if num is not None:
                out[next_prefix] = num
                continue
            if isinstance(v, (dict, list, tuple)):
                _collect_numeric_metrics(v, prefix=next_prefix, out=out, depth=depth + 1)
        return out

    num = _to_number(obj)
    if num is not None and prefix:
        out[prefix] = num
    return out


def _resolve_posture_data_from_record(r: Dict[str, Any]) -> Dict[str, Any]:
    """
    从一条历史记录中，尽可能稳定地拿到体态/体型结构化数据：
    优先 meta.postureMetricsSnapshot，其次联合记录 titai_fb.type=joint_final 的 titai_fb.postureData，
    最后退回该条记录自身的 titai/tixing 字段。
    """
    meta = r.get("meta_json") if isinstance(r.get("meta_json"), dict) else {}
    if isinstance(meta, dict):
        snap = meta.get("postureMetricsSnapshot")
        if isinstance(snap, dict) and snap:
            return snap

    titai = r.get("titai_fb")
    if isinstance(titai, dict):
        if titai.get("type") in ("joint_final", "joint") and isinstance(titai.get("postureData"), dict):
            return titai["postureData"]

    # 最后兜底：用该条记录自身结构
    return {
        "titai_fb": r.get("titai_fb"),
        "tixing_fb": r.get("tixing_fb"),
        "titai_lr": r.get("titai_lr"),
        "tixing_lr": r.get("tixing_lr"),
    }


def _resolve_profile_snapshot_from_record(r: Dict[str, Any]) -> Dict[str, Any]:
    meta = r.get("meta_json") if isinstance(r.get("meta_json"), dict) else {}
    profile_meta = meta.get("profileMeta") if isinstance(meta.get("profileMeta"), dict) else None
    if isinstance(profile_meta, dict):
        return dict(profile_meta)
    return {}


def _compute_bmi(height: Any, weight: Any) -> Optional[float]:
    h = _to_number(height)
    w = _to_number(weight)
    if h is None or w is None or h <= 0 or w <= 0:
        return None
    h_m = h / 100.0 if h > 10 else h
    if h_m <= 0:
        return None
    bmi = w / (h_m * h_m)
    if bmi != bmi or bmi in (float("inf"), float("-inf")):
        return None
    return round(float(bmi), 4)


def _enrich_profile_snapshot(profile_meta: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(profile_meta or {})
    bmi = _compute_bmi(enriched.get("height"), enriched.get("weight"))
    if bmi is not None:
        enriched["bmi"] = bmi
    return enriched


def _build_chart_source_items(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    生成折线图 source 数据：
    [
      { "id": 1, "timestamp": "...", "metrics": { "titai_fb.shoulder_tilt": 0.1, ... } },
      ...
    ]
    """
    items: List[Dict[str, Any]] = []
    for r in records:
        ts = r.get("created_at") or r.get("createdAt") or r.get("timestamp")
        posture_data = _resolve_posture_data_from_record(r)
        profile_meta = _enrich_profile_snapshot(_resolve_profile_snapshot_from_record(r))
        metrics = _collect_numeric_metrics(posture_data)
        bmi = _to_number(profile_meta.get("bmi"))
        if bmi is not None:
            metrics["BMI"] = bmi
        if not metrics:
            continue
        items.append(
            {
                "id": r.get("id"),
                "timestamp": ts,
                "metrics": metrics,
                "profileMeta": profile_meta,
                "userData": profile_meta,
            }
        )
    return items


def _build_trend_rows(chart_source_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    生成左侧趋势数据（通用版，前端可直接展示）：
    [
      { key, first, last, delta, direction },
      ...
    ]
    """
    if not chart_source_items:
        return []

    # 汇总每个 key 的时间序列（按 items 顺序即时间顺序）
    series: Dict[str, List[float]] = {}
    for item in chart_source_items:
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        for k, v in metrics.items():
            num = _to_number(v)
            if num is None:
                continue
            series.setdefault(str(k), []).append(num)

    rows: List[Dict[str, Any]] = []
    for k, arr in series.items():
        if not arr:
            continue
        first = arr[0]
        last = arr[-1]
        delta = last - first
        direction = "flat"
        if delta > 1e-9:
            direction = "up"
        elif delta < -1e-9:
            direction = "down"
        rows.append(
            {
                "key": k,
                "first": first,
                "last": last,
                "delta": delta,
                "direction": direction,
            }
        )

    # 稳定排序：变化幅度大的在前
    rows.sort(key=lambda x: abs(float(x.get("delta") or 0.0)), reverse=True)
    return rows


def _collect_record_ids(payload: HistoryAnalysisPayload) -> List[int]:
    ids: List[int] = []
    for item in payload.items or []:
        if item.id is not None:
            ids.append(int(item.id))
    if payload.recordIds:
        ids.extend(int(x) for x in payload.recordIds)
    # 去重且保持顺序
    return list(dict.fromkeys(ids))


@router.post('/generate')
def generate_history_analysis(
    payload: HistoryAnalysisPayload,
    db: Session = Depends(get_db),
):
    """
    用户勾选联合报告对应的历史记录 → 按 userId 从库中取记录（校验归属）
    → 仅读取每条记录的联合报告正文 comprehensive_analysis_text → 单次调用历史分析智能体
    → 入库并返回（折线图仍基于各条记录中的结构化 titai/tixing 指标）
    """
    print("------waiting for AI response...------")
    record_ids = _collect_record_ids(payload)
    if not record_ids:
        raise HTTPException(
            status_code=400,
            detail="未传入任何历史记录 ID：请在 items 中提供 id，或使用 recordIds。",
        )

    user_row = get_or_create_user(db, payload.userId)
    stmt = (
        select(AssessmentRecord)
        .where(
            AssessmentRecord.user_id == user_row.id,
            AssessmentRecord.id.in_(record_ids),
        )
    )
    db_records: List[AssessmentRecord] = list(db.execute(stmt).scalars().all())

    if len(db_records) != len(record_ids):
        found = {r.id for r in db_records}
        missing = sorted(set(record_ids) - found)
        raise HTTPException(
            status_code=400,
            detail=f"部分记录不存在或不属于当前用户，无法分析的 id：{missing}",
        )

    # 关键：保序返回“前端勾选顺序”，而不是按 created_at 排序
    db_records_by_id = {r.id: r for r in db_records}
    records_dicts: list[dict] = []
    for rid in record_ids:
        r = db_records_by_id.get(rid)
        if r is None:
            # 理论上不会走到这里，但保持兜底
            continue
        records_dicts.append(
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
                "titai_fb": r.titai_fb,
                "tixing_fb": r.tixing_fb,
                "titai_lr": r.titai_lr,
                "tixing_lr": r.tixing_lr,
                "posture_analysis_text": r.posture_analysis_text,
                "tongue_analysis_text": r.tongue_analysis_text,
                "comprehensive_analysis_text": r.comprehensive_analysis_text,
                "front_image_path": r.front_image_path,
                "meta_json": r.meta_json,
                "tcm_ten_questions": r.tcm_ten_questions,
            }
        )

    joint_rows = build_joint_report_rows(records_dicts)
    if not has_joint_report_content(joint_rows):
        raise HTTPException(
            status_code=400,
            detail="所选记录在数据库中暂无联合报告正文，无法执行历史记录分析。",
        )

    chart_source_items = _build_chart_source_items(records_dicts)
    trend_rows = _build_trend_rows(chart_source_items)
    source_profile_snapshots: List[Dict[str, Any]] = [
        {
            "id": x.get("id"),
            "timestamp": x.get("timestamp"),
            "profileMeta": x.get("profileMeta") if isinstance(x.get("profileMeta"), dict) else {},
            "userData": x.get("userData") if isinstance(x.get("userData"), dict) else {},
        }
        for x in chart_source_items
    ]
    # 便于前端直接画折线图：把 metrics 展开到顶层，带 timestamp
    history_chart_data: List[Dict[str, Any]] = [
        {
            "id": x.get("id"),
            "timestamp": x.get("timestamp"),
            "profileMeta": x.get("profileMeta") if isinstance(x.get("profileMeta"), dict) else {},
            "userData": x.get("userData") if isinstance(x.get("userData"), dict) else {},
            **(x.get("metrics") if isinstance(x.get("metrics"), dict) else {}),
        }
        for x in chart_source_items
    ]

    try:
        hm = payload.model
        report_text = analyze_history_from_joint_reports(joint_rows, model=hm)
    except Exception as e:
        logger.exception("历史分析调用智能体失败")
        return {
            "success": False,
            "msg": f"历史分析调用智能体失败：{e}",
            "recordId": None,
            "createdAt": None,
            "analysisType": "history_analysis",
            "historyAnalysisReport": None,
            "historyChartData": history_chart_data,
            "trendData": trend_rows,
        }

    record = save_assessment(
        db,
        user=user_row,
        titai_fb={
            "type": "history_analysis",
            "sourceRecordIds": record_ids,
            "sourceCount": len(db_records),
            "analysisMode": "joint_reports",
        },
        tixing_fb=None,
        titai_lr=None,
        tixing_lr=None,
        posture_analysis_text=None,
        tongue_analysis_text=None,
        comprehensive_analysis_text=report_text.strip() if report_text else None,
        history_chart_data=history_chart_data,
        front_image_path=None,
        meta={
            "analysisType": "history_analysis",
            "generatedAt": datetime.utcnow().isoformat(),
            "sourceRecordIds": record_ids,
            "sourceCount": len(db_records),
            "analysisMode": "joint_reports",
            "jointReportsHistoryAnalysis": report_text,
            "trendData": trend_rows,
            "sourceProfileSnapshots": source_profile_snapshots,
        },
    )

    return {
        "success": True,
        "msg": "历史记录分析完成",
        "recordId": record.id,
        "createdAt": record.created_at.isoformat() if record.created_at else None,
        "analysisType": "history_analysis",
        "historyAnalysisReport": report_text,
        "historyChartData": history_chart_data,
        "trendData": trend_rows,
    }
