from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Account, AssessmentRecord, User, UserProfile

DEFAULT_ALLERGY_HISTORY = "无过敏史"


def normalize_allergy_history(value: str | None) -> str:
    t = (value or "").strip()
    return t if t else DEFAULT_ALLERGY_HISTORY


def effective_nickname(user: User) -> str:
    uid = (user.client_user_id or "").strip() or "anonymous"
    nn = (user.nickname or "").strip()
    return nn if nn else uid


def normalize_nickname_for_storage(client_user_id: str | None, nickname: str | None) -> str | None:
    if nickname is None:
        return None
    uid = (str(client_user_id).strip() if client_user_id else "") or "anonymous"
    nn = (nickname or "").strip()
    if not nn:
        return None
    if nn == uid:
        return None
    return nn[:128]


def apply_user_nickname_from_partial(db: Session, client_user_id: str | None, partial: dict[str, Any]) -> User:
    """仅当 partial 含键 nickname 时更新（model_dump(exclude_unset=True)）。"""
    user = get_or_create_user(db, client_user_id)
    if "nickname" not in partial:
        return user
    user.nickname = normalize_nickname_for_storage(client_user_id, partial.get("nickname"))
    db.commit()
    db.refresh(user)
    return user


def set_user_nickname(db: Session, client_user_id: str | None, nickname: str | None) -> User:
    user = get_or_create_user(db, client_user_id)
    user.nickname = normalize_nickname_for_storage(client_user_id, nickname)
    db.commit()
    db.refresh(user)
    return user


def _json_safe(obj: Any) -> Any:
    """把 numpy 等转成可存进 JSON 的类型。"""
    try:
        import numpy as np
    except ImportError:
        np = None  # type: ignore
    if obj is None:
        return None
    if np is not None:
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def get_or_create_user(db: Session, client_user_id: str | None) -> User:
    uid = (str(client_user_id).strip() if client_user_id else "") or "anonymous"
    row = db.execute(select(User).where(User.client_user_id == uid)).scalar_one_or_none()
    if row is not None:
        return row
    row = User(client_user_id=uid)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_assessment(
    db: Session,
    *,
    user: User,
    titai_fb: Any,
    tixing_fb: Any,
    titai_lr: Any,
    tixing_lr: Any,
    posture_analysis_text: str | None,
    tongue_analysis_text: str | None,
    comprehensive_analysis_text: str | None,
    front_image_path: str | None,
    processed_image_path: str | None = None,
    meta: dict | None,
    tcm_ten_questions: dict | None = None,
    history_chart_data: list[dict] | None = None,
    user_requirements: list[dict] | None = None,
) -> AssessmentRecord:
    rec = AssessmentRecord(
        user_id=user.id,
        titai_fb=_json_safe(titai_fb),
        tixing_fb=_json_safe(tixing_fb),
        titai_lr=_json_safe(titai_lr),
        tixing_lr=_json_safe(tixing_lr),
        posture_analysis_text=posture_analysis_text,
        tongue_analysis_text=tongue_analysis_text,
        comprehensive_analysis_text=comprehensive_analysis_text,
        history_chart_data=_json_safe(history_chart_data),
        front_image_path=front_image_path,
        processed_image_path=(str(processed_image_path).strip() if processed_image_path else None),
        meta_json=_json_safe(meta),
        user_requirements=_json_safe(user_requirements) if user_requirements is not None else None,
        tcm_ten_questions=_json_safe(tcm_ten_questions),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def list_records_for_user(db: Session, client_user_id: str | None, limit: int = 50):
    uid = (str(client_user_id).strip() if client_user_id else "") or "anonymous"
    user = db.execute(select(User).where(User.client_user_id == uid)).scalar_one_or_none()
    if user is None:
        return []
    rows = (
        db.execute(
            select(AssessmentRecord)
            .where(AssessmentRecord.user_id == user.id)
            .order_by(AssessmentRecord.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return rows


def get_record_for_user(db: Session, client_user_id: str | None, record_id: int) -> AssessmentRecord | None:
    uid = (str(client_user_id).strip() if client_user_id else "") or "anonymous"
    user = db.execute(select(User).where(User.client_user_id == uid)).scalar_one_or_none()
    if user is None:
        return None
    return (
        db.execute(
            select(AssessmentRecord).where(
                AssessmentRecord.id == record_id,
                AssessmentRecord.user_id == user.id,
            )
        )
        .scalars()
        .first()
    )


def delete_record_for_user(db: Session, client_user_id: str | None, record_id: int) -> bool:
    uid = (str(client_user_id).strip() if client_user_id else "") or "anonymous"
    user = db.execute(select(User).where(User.client_user_id == uid)).scalar_one_or_none()
    if user is None:
        return False

    row = (
        db.execute(
            select(AssessmentRecord).where(
                AssessmentRecord.id == record_id,
                AssessmentRecord.user_id == user.id,
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        return False

    db.delete(row)
    db.commit()
    return True


def create_account(db: Session, username: str, password: str, nickname: str | None = None) -> tuple[bool, str]:
    uid = (username or "").strip()
    pwd = (password or "").strip()
    if not uid or not pwd:
        return False, "账号和密码不能为空"

    existing = db.execute(select(Account).where(Account.username == uid)).scalar_one_or_none()
    if existing is not None:
        return False, "账号已存在"

    account = Account(username=uid, password=pwd)
    db.add(account)
    # 确保分析数据按账号隔离：预创建同名 user 记录
    user = get_or_create_user(db, uid)
    user.nickname = normalize_nickname_for_storage(uid, nickname)
    db.commit()
    return True, "注册成功"


def authenticate_account(db: Session, username: str, password: str) -> bool:
    uid = (username or "").strip()
    pwd = (password or "").strip()
    if not uid or not pwd:
        return False

    account = db.execute(select(Account).where(Account.username == uid)).scalar_one_or_none()
    if account is None:
        return False
    return account.password == pwd


def get_profile_for_user(db: Session, client_user_id: str | None) -> UserProfile | None:
    user = get_or_create_user(db, client_user_id)
    return db.execute(select(UserProfile).where(UserProfile.user_id == user.id)).scalar_one_or_none()


def create_profile_for_user(
    db: Session,
    client_user_id: str | None,
    *,
    age: int | None,
    gender: str | None,
    height: float | None,
    weight: float | None,
    medical_history: str | None,
    work_habit: str | None,
    allergy_history: str | None,
) -> tuple[bool, str, UserProfile | None]:
    user = get_or_create_user(db, client_user_id)
    existing = db.execute(select(UserProfile).where(UserProfile.user_id == user.id)).scalar_one_or_none()
    if existing is not None:
        return False, "该账号已上传个人信息，请使用修改功能。", None

    row = UserProfile(
        user_id=user.id,
        age=age,
        gender=(gender or "").strip() or None,
        height=height,
        weight=weight,
        medical_history=(medical_history or "").strip() or None,
        work_habit=(work_habit or "").strip() or None,
        allergy_history=normalize_allergy_history(allergy_history),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return True, "个人信息上传成功。", row


def update_profile_for_user(
    db: Session,
    client_user_id: str | None,
    *,
    age: int | None,
    gender: str | None,
    height: float | None,
    weight: float | None,
    medical_history: str | None,
    work_habit: str | None,
    allergy_history: str | None,
) -> tuple[bool, str, UserProfile | None]:
    user = get_or_create_user(db, client_user_id)
    row = db.execute(select(UserProfile).where(UserProfile.user_id == user.id)).scalar_one_or_none()
    if row is None:
        return False, "该账号尚未上传个人信息，请先上传。", None

    row.age = age
    row.gender = (gender or "").strip() or None
    row.height = height
    row.weight = weight
    row.medical_history = (medical_history or "").strip() or None
    row.work_habit = (work_habit or "").strip() or None
    row.allergy_history = normalize_allergy_history(allergy_history)
    db.commit()
    db.refresh(row)
    return True, "个人信息修改成功。", row


def save_profile_for_user(
    db: Session,
    client_user_id: str | None,
    *,
    age: int | None,
    gender: str | None,
    height: float | None,
    weight: float | None,
    medical_history: str | None,
    work_habit: str | None,
    allergy_history: str | None,
) -> tuple[bool, str, UserProfile | None]:
    existing = get_profile_for_user(db, client_user_id)
    if existing is None:
        return create_profile_for_user(
            db,
            client_user_id,
            age=age,
            gender=gender,
            height=height,
            weight=weight,
            medical_history=medical_history,
            work_habit=work_habit,
            allergy_history=allergy_history,
        )
    return update_profile_for_user(
        db,
        client_user_id,
        age=age,
        gender=gender,
        height=height,
        weight=weight,
        medical_history=medical_history,
        work_habit=work_habit,
        allergy_history=allergy_history,
    )

def get_latest_record_with_posture_text(db: Session, client_user_id: str | None) -> AssessmentRecord | None:
    """该用户最近一次包含非空体态分析正文的评估记录（用于联合报告）。"""
    uid = (str(client_user_id).strip() if client_user_id else "") or "anonymous"
    user = db.execute(select(User).where(User.client_user_id == uid)).scalar_one_or_none()
    if user is None:
        return None
    rows = (
        db.execute(
            select(AssessmentRecord)
            .where(AssessmentRecord.user_id == user.id)
            .order_by(AssessmentRecord.created_at.desc())
        )
        .scalars()
        .all()
    )
    for r in rows:
        if (r.posture_analysis_text or "").strip():
            return r
    return None


def get_latest_record_with_tongue_text(db: Session, client_user_id: str | None) -> AssessmentRecord | None:
    """该用户最近一次包含非空舌苔分析正文的评估记录（用于联合报告）。"""
    uid = (str(client_user_id).strip() if client_user_id else "") or "anonymous"
    user = db.execute(select(User).where(User.client_user_id == uid)).scalar_one_or_none()
    if user is None:
        return None
    rows = (
        db.execute(
            select(AssessmentRecord)
            .where(AssessmentRecord.user_id == user.id)
            .order_by(AssessmentRecord.created_at.desc())
        )
        .scalars()
        .all()
    )
    for r in rows:
        if (r.tongue_analysis_text or "").strip():
            return r
    return None
