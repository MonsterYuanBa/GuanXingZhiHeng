"""SQLite 连接：数据存在项目目录下的 data/app.db 文件里。"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from db.models import AssessmentRecord, Base  # noqa: F401

# 可通过环境变量改成别的路径，例如 postgresql://...
_default_sqlite = Path(__file__).resolve().parent.parent / "data" / "app.db"
_default_sqlite.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_sqlite.as_posix()}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _migrate_assessment_record_schema() -> None:
    """旧库仅有 deepseek_text 时：新增三列、迁移数据并删除旧列（SQLite 3.35+ 支持 DROP COLUMN）。"""
    insp = inspect(engine)
    if not insp.has_table("assessment_records"):
        return
    cols = {c["name"] for c in insp.get_columns("assessment_records")}
    had_deepseek = "deepseek_text" in cols

    with engine.begin() as conn:
        if "posture_analysis_text" not in cols:
            conn.execute(text("ALTER TABLE assessment_records ADD COLUMN posture_analysis_text TEXT"))
        if "tongue_analysis_text" not in cols:
            conn.execute(text("ALTER TABLE assessment_records ADD COLUMN tongue_analysis_text TEXT"))
        if "comprehensive_analysis_text" not in cols:
            conn.execute(text("ALTER TABLE assessment_records ADD COLUMN comprehensive_analysis_text TEXT"))
        if "history_chart_data" not in cols:
            conn.execute(text("ALTER TABLE assessment_records ADD COLUMN history_chart_data JSON"))
        if "processed_image_path" not in cols:
            conn.execute(text("ALTER TABLE assessment_records ADD COLUMN processed_image_path VARCHAR(1024)"))

    if not had_deepseek:
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE assessment_records SET comprehensive_analysis_text = deepseek_text "
                "WHERE (comprehensive_analysis_text IS NULL OR trim(comprehensive_analysis_text) = '') "
                "AND deepseek_text IS NOT NULL"
            )
        )
        try:
            conn.execute(text("ALTER TABLE assessment_records DROP COLUMN deepseek_text"))
        except Exception:
            pass


def _migrate_user_profile_schema() -> None:
    insp = inspect(engine)
    if not insp.has_table("user_profiles"):
        return
    cols = {c["name"] for c in insp.get_columns("user_profiles")}
    with engine.begin() as conn:
        if "tcm_ten_questions" not in cols:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN tcm_ten_questions JSON"))
        if "allergy_history" not in cols:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN allergy_history VARCHAR(512)"))


def _migrate_user_nickname_column() -> None:
    insp = inspect(engine)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    with engine.begin() as conn:
        if "nickname" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(128)"))


def _migrate_tcm_ten_questions_to_assessment_records() -> None:
    """中医十问改存 assessment_records：加列，并把 user_profiles 里的旧数据迁到各用户最新一条记录。"""
    insp = inspect(engine)
    if not insp.has_table("assessment_records"):
        return
    cols = {c["name"] for c in insp.get_columns("assessment_records")}
    with engine.begin() as conn:
        if "tcm_ten_questions" not in cols:
            conn.execute(text("ALTER TABLE assessment_records ADD COLUMN tcm_ten_questions JSON"))

    if not insp.has_table("user_profiles"):
        return
    up_cols = {c["name"] for c in insp.get_columns("user_profiles")}
    if "tcm_ten_questions" not in up_cols:
        return

    with engine.connect() as conn:
        legacy_rows = conn.execute(
            text("SELECT user_id, tcm_ten_questions FROM user_profiles WHERE tcm_ten_questions IS NOT NULL")
        ).fetchall()

    db = SessionLocal()
    try:
        for user_id, tcm_json in legacy_rows:
            latest = (
                db.execute(
                    select(AssessmentRecord)
                    .where(AssessmentRecord.user_id == user_id)
                    .order_by(AssessmentRecord.created_at.desc(), AssessmentRecord.id.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if latest is None or latest.tcm_ten_questions is not None:
                continue
            latest.tcm_ten_questions = tcm_json
        db.commit()
    finally:
        db.close()


def _migrate_assessment_user_requirements_column() -> None:
    insp = inspect(engine)
    if not insp.has_table("assessment_records"):
        return
    cols = {c["name"] for c in insp.get_columns("assessment_records")}
    with engine.begin() as conn:
        if "user_requirements" not in cols:
            conn.execute(text("ALTER TABLE assessment_records ADD COLUMN user_requirements JSON"))


def _migrate_user_requirements_from_meta_json() -> None:
    """把旧版写在 meta_json.userRequirementLog 里的数组迁到列 user_requirements（带 seq）。"""
    from db.joint_requirements_store import normalize_stored_requirements

    db = SessionLocal()
    try:
        rows = db.execute(select(AssessmentRecord)).scalars().all()
        for rec in rows:
            col = getattr(rec, "user_requirements", None)
            if isinstance(col, list) and len(col) > 0:
                continue
            meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
            raw = meta.get("userRequirementLog")
            if not isinstance(raw, list) or len(raw) == 0:
                continue
            rec.user_requirements = normalize_stored_requirements(raw)
            meta2 = dict(meta)
            meta2.pop("userRequirementLog", None)
            rec.meta_json = meta2
        db.commit()
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_assessment_record_schema()
    # 须在任意 ORM 全表加载 AssessmentRecord 之前加列，否则 SELECT 会引用尚不存在的 user_requirements
    _migrate_assessment_user_requirements_column()
    _migrate_user_profile_schema()
    _migrate_user_nickname_column()
    _migrate_tcm_ten_questions_to_assessment_records()
    _migrate_user_requirements_from_meta_json()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
