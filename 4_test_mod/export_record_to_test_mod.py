from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from db.database import SessionLocal
from db.models import AssessmentRecord, User

# -----------------------------
# 按需修改这三个配置后运行脚本
# -----------------------------
SOURCE_USER_ID = "admin"
SOURCE_RECORD_ID = 267
SAMPLE_ID = "267"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _sample_dir() -> Path:
    return Path(__file__).resolve().parent / SAMPLE_ID


def _resolve_src_path(src: str | None) -> Path | None:
    if not src:
        return None
    p = Path(src)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


def _safe_copy(src: str | None, dst: Path) -> str | None:
    p = _resolve_src_path(src)
    if p is None:
        return None
    if not p.exists() or not p.is_file():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dst)
    return str(dst)


def main() -> None:
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.client_user_id == SOURCE_USER_ID)).scalars().first()
        if user is None:
            raise RuntimeError(f"user not found: {SOURCE_USER_ID}")
        rec = (
            db.execute(
                select(AssessmentRecord).where(
                    AssessmentRecord.id == int(SOURCE_RECORD_ID),
                    AssessmentRecord.user_id == user.id,
                )
            )
            .scalars()
            .first()
        )
        if rec is None:
            raise RuntimeError(f"record not found: id={SOURCE_RECORD_ID} user={SOURCE_USER_ID}")

        base = _sample_dir()
        files = base / "files"
        files.mkdir(parents=True, exist_ok=True)

        rec_meta = rec.meta_json if isinstance(rec.meta_json, dict) else {}
        analysis_type = str(rec_meta.get("analysisType") or "").lower()

        posture_rec = rec
        tongue_rec = rec
        if analysis_type != "posture_only":
            spid = rec_meta.get("sourcePostureRecordId")
            if spid is not None:
                try:
                    pid = int(spid)
                except Exception:
                    pid = 0
                if pid > 0:
                    src = (
                        db.execute(
                            select(AssessmentRecord).where(
                                AssessmentRecord.id == pid,
                                AssessmentRecord.user_id == user.id,
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if src is not None:
                        posture_rec = src
            stid = rec_meta.get("sourceTongueRecordId")
            if stid is not None:
                try:
                    tid = int(stid)
                except Exception:
                    tid = 0
                if tid > 0:
                    src = (
                        db.execute(
                            select(AssessmentRecord).where(
                                AssessmentRecord.id == tid,
                                AssessmentRecord.user_id == user.id,
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if src is not None:
                        tongue_rec = src

        posture_front = posture_rec.front_image_path
        posture_side = None
        if posture_front:
            fp = _resolve_src_path(posture_front)
            if fp is None:
                fp = Path(posture_front)
            guess = fp.with_name(f"{posture_rec.id}_posture_side{fp.suffix}")
            if guess.exists():
                posture_side = str(guess)

        copied = {
            "postureFront": _safe_copy(posture_front, files / "posture_front.jpg"),
            "postureSide": _safe_copy(posture_side, files / "posture_side.jpg"),
            "postureProcessed": _safe_copy(posture_rec.processed_image_path, files / "posture_processed.jpg"),
            "postureMosaic": _safe_copy((posture_rec.meta_json or {}).get("mosaicFrontImagePath"), files / "posture_mosaic.jpg"),
            "tongueImage": _safe_copy(tongue_rec.front_image_path, files / "tongue_upload.jpg"),
        }

        manifest = {
            "sampleId": SAMPLE_ID,
            "exportedAt": datetime.utcnow().isoformat(),
            "source": {"userId": SOURCE_USER_ID, "recordId": rec.id},
            "missingNotes": {
                "postureSideUploadMissing": copied["postureSide"] is None,
                "originalUploadUnknownHint": "若缺用户上传原图，请手动补上 posture_front/posture_side/tongue_upload。",
            },
            "posture": {
                "titai_fb": posture_rec.titai_fb,
                "tixing_fb": posture_rec.tixing_fb,
                "titai_lr": posture_rec.titai_lr,
                "tixing_lr": posture_rec.tixing_lr,
                "report": posture_rec.posture_analysis_text or rec.posture_analysis_text or "",
            },
            "tongue": {
                "report": tongue_rec.tongue_analysis_text or rec.tongue_analysis_text or "",
                "metaTongueInfo": (tongue_rec.meta_json or {}).get("tongueInfo") if isinstance(tongue_rec.meta_json, dict) else None,
            },
            "joint": {
                "report": rec.comprehensive_analysis_text or "",
                "postureReport": rec.posture_analysis_text or "",
                "tongueReport": rec.tongue_analysis_text or "",
            },
            "files": {
                k: (str(Path(v).relative_to(base)).replace("\\", "/") if v else None) for k, v in copied.items()
            },
            "profileMeta": (rec.meta_json or {}).get("profileMeta") if isinstance(rec.meta_json, dict) else None,
            "tcmTenQuestions": rec.tcm_ten_questions,
        }
        out = base / "manifest.json"
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved: {out}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
