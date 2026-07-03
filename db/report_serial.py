"""用户可见报告（常规分析 / 专家深度 / 复查分析）的连续编号。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import AssessmentRecord

# 仅下列类型对用户展示为「报告」，参与连续编号；体态/舌苔/十问等中间记录不占号。
VISIBLE_REPORT_ANALYSIS_TYPES = frozenset(
    {
        "joint_final",
        "joint_detailed",
        "history_analysis",
        "joint",  # 旧数据兼容
    }
)


def _normalize_type(value: Any) -> str:
    return str(value or "").strip().lower()


def analysis_type_from_meta(meta: dict | None) -> str:
    if not isinstance(meta, dict):
        return ""
    return _normalize_type(meta.get("analysisType"))


def analysis_type_from_titai_fb(titai_fb: Any) -> str:
    if not isinstance(titai_fb, dict):
        return ""
    return _normalize_type(titai_fb.get("type"))


def should_assign_report_serial(meta: dict | None, titai_fb: Any = None) -> bool:
    t = analysis_type_from_meta(meta)
    if t in VISIBLE_REPORT_ANALYSIS_TYPES:
        return True
    return analysis_type_from_titai_fb(titai_fb) in VISIBLE_REPORT_ANALYSIS_TYPES


def next_report_serial(db: Session, user_id: int) -> int:
    current = db.execute(
        select(func.coalesce(func.max(AssessmentRecord.report_serial), 0)).where(
            AssessmentRecord.user_id == user_id
        )
    ).scalar_one()
    return int(current or 0) + 1


def backfill_report_serials(db: Session) -> None:
    """按用户、创建时间为既有可见报告补连续编号（1, 2, 3…）。用于首次加列后的全量回填。"""
    user_ids = db.execute(select(AssessmentRecord.user_id).distinct()).scalars().all()
    for user_id in user_ids:
        serial = 0
        rows = (
            db.execute(
                select(AssessmentRecord)
                .where(AssessmentRecord.user_id == user_id)
                .order_by(AssessmentRecord.created_at.asc(), AssessmentRecord.id.asc())
            )
            .scalars()
            .all()
        )
        for rec in rows:
            meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
            if not should_assign_report_serial(meta, rec.titai_fb):
                continue
            serial += 1
            if rec.report_serial != serial:
                rec.report_serial = serial
    db.commit()


def backfill_missing_report_serials(db: Session) -> None:
    """仅为尚未分配编号的可见报告接续分配（不改动已有编号）。"""
    user_ids = db.execute(select(AssessmentRecord.user_id).distinct()).scalars().all()
    changed = False
    for user_id in user_ids:
        current = db.execute(
            select(func.coalesce(func.max(AssessmentRecord.report_serial), 0)).where(
                AssessmentRecord.user_id == user_id
            )
        ).scalar_one()
        serial = int(current or 0)
        rows = (
            db.execute(
                select(AssessmentRecord)
                .where(
                    AssessmentRecord.user_id == user_id,
                    AssessmentRecord.report_serial.is_(None),
                )
                .order_by(AssessmentRecord.created_at.asc(), AssessmentRecord.id.asc())
            )
            .scalars()
            .all()
        )
        for rec in rows:
            meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
            if not should_assign_report_serial(meta, rec.titai_fb):
                continue
            serial += 1
            rec.report_serial = serial
            changed = True
    if changed:
        db.commit()
