from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from db.crud import get_record_for_user
from db.models import AssessmentRecord

_MAX_LEN = 4000


def normalize_stored_requirements(raw: object) -> list[dict[str, Any]]:
    """将任意原始列表规范为带顺序序号 seq 的数组（便于数据库存 JSON 数组）。"""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for e in raw:
        if isinstance(e, dict) and isinstance(e.get("text"), str):
            out.append(
                {
                    "text": str(e["text"])[:_MAX_LEN],
                    "at": str(e.get("at") or ""),
                }
            )
    for i, item in enumerate(out, 1):
        item["seq"] = i
    return out


def format_entries_for_prompt(entries: list[dict] | None) -> str:
    if not entries:
        return ""
    lines: list[str] = []
    for e in entries:
        t = (e.get("text") or "").strip()
        if not t:
            continue
        seq = e.get("seq")
        seq_s = str(seq) if isinstance(seq, int) and seq > 0 else ""
        ts = (e.get("at") or "").strip()
        prefix = f"[#{seq_s}] " if seq_s else ""
        lines.append(f"{prefix}[{ts}] {t}" if ts else f"{prefix}{t}")
    return "\n".join(lines)


def get_entries_for_record(db: Session, client_user_id: str | None, record_id: int) -> list[dict]:
    rec = get_record_for_user(db, client_user_id, record_id)
    if rec is None:
        return []
    col = getattr(rec, "user_requirements", None)
    if isinstance(col, list) and len(col) > 0:
        return normalize_stored_requirements(col)
    meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
    return normalize_stored_requirements(meta.get("userRequirementLog"))


def append_to_record_meta(db: Session, rec: AssessmentRecord, text: str) -> list[dict]:
    current: list = []
    col = getattr(rec, "user_requirements", None)
    if isinstance(col, list) and len(col) > 0:
        current = normalize_stored_requirements(col)
    elif isinstance(rec.meta_json, dict):
        current = normalize_stored_requirements(rec.meta_json.get("userRequirementLog"))
    current.append(
        {
            "seq": len(current) + 1,
            "text": text.strip()[:_MAX_LEN],
            "at": datetime.utcnow().isoformat() + "Z",
        }
    )
    for i, item in enumerate(current, 1):
        item["seq"] = i
    rec.user_requirements = current
    meta = dict(rec.meta_json or {})
    meta.pop("userRequirementLog", None)
    rec.meta_json = meta
    db.commit()
    db.refresh(rec)
    return list(current)


def remove_entry_by_seq(db: Session, rec: AssessmentRecord, seq: int) -> list[dict]:
    """按序号删除一条需求，并重新编号 seq。"""
    target = int(seq)

    def _entry_seq(e: dict) -> int:
        s = e.get("seq")
        try:
            return int(float(s))
        except (TypeError, ValueError):
            return 0

    current: list = []
    col = getattr(rec, "user_requirements", None)
    if isinstance(col, list) and len(col) > 0:
        current = normalize_stored_requirements(col)
    elif isinstance(rec.meta_json, dict):
        current = normalize_stored_requirements(rec.meta_json.get("userRequirementLog"))
    filtered = [e for e in current if isinstance(e, dict) and _entry_seq(e) != target]
    normalized = normalize_stored_requirements(filtered)
    rec.user_requirements = normalized
    meta = dict(rec.meta_json or {})
    meta.pop("userRequirementLog", None)
    rec.meta_json = meta
    db.commit()
    db.refresh(rec)
    return list(normalized)


def set_record_user_requirement_log(db: Session, rec: AssessmentRecord, entries: list[dict]) -> None:
    normalized = normalize_stored_requirements(entries)
    rec.user_requirements = normalized
    meta = dict(rec.meta_json or {})
    meta.pop("userRequirementLog", None)
    rec.meta_json = meta
    db.commit()
    db.refresh(rec)


def merge_entries_from_records(
    db: Session,
    client_user_id: str | None,
    *records: AssessmentRecord | None,
) -> list[dict[str, Any]]:
    """合并多条 assessment 上的用户需求（按记录顺序，同文去重），用于常规分析落库前汇总。"""
    seen: set[str] = set()
    raw: list[dict[str, Any]] = []
    for rec in records:
        if rec is None:
            continue
        rid = getattr(rec, "id", None)
        if rid is None:
            continue
        try:
            rid_int = int(rid)
        except (TypeError, ValueError):
            continue
        if rid_int <= 0:
            continue
        for e in get_entries_for_record(db, client_user_id, rid_int):
            t = (e.get("text") or "").strip()
            if not t or t in seen:
                continue
            seen.add(t)
            raw.append({"text": t, "at": str(e.get("at") or "")})
    return normalize_stored_requirements(raw)
