from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.crud import (
    apply_user_nickname_from_partial,
    create_profile_for_user,
    effective_nickname,
    get_or_create_user,
    get_profile_for_user,
    save_assessment,
    save_profile_for_user,
    set_user_nickname,
    update_profile_for_user,
)
from db.database import get_db
from routes.schemas import NicknamePayload, ProfilePayload, TcmTenQuestionsPayload

router = APIRouter(prefix='/api/profile', tags=['profile'])


def _profile_to_dict(row):
    if row is None:
        return None
    u = row.user
    return {
        'userId': u.client_user_id if u else None,
        'nickname': effective_nickname(u) if u else None,
        'age': row.age,
        'gender': row.gender,
        'height': row.height,
        'weight': row.weight,
        'medicalHistory': row.medical_history,
        'workHabit': row.work_habit,
        'allergyHistory': row.allergy_history or '无过敏史',
        'createdAt': row.created_at.isoformat() if row.created_at else None,
        'updatedAt': row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get('')
def get_profile(userId: str, db: Session = Depends(get_db)):
    user = get_or_create_user(db, userId)
    nick = effective_nickname(user)
    row = get_profile_for_user(db, userId)
    if row is None:
        return {
            'success': True,
            'message': 'No profile row.',
            'userId': user.client_user_id,
            'nickname': nick,
            'profile': None,
        }
    return {
        'success': True,
        'message': 'Profile fetched.',
        'userId': user.client_user_id,
        'nickname': nick,
        'profile': _profile_to_dict(row),
    }


def _with_nickname_response(user, ok: bool, message: str, profile_dict):
    return {
        'success': ok,
        'message': message,
        'userId': user.client_user_id,
        'nickname': effective_nickname(user),
        'profile': profile_dict,
    }


@router.post('/upload')
def upload_profile(payload: ProfilePayload, db: Session = Depends(get_db)):
    partial = payload.model_dump(exclude_unset=True)
    apply_user_nickname_from_partial(db, payload.userId, partial)
    ok, message, row = create_profile_for_user(
        db,
        payload.userId,
        age=payload.age,
        gender=payload.gender,
        height=payload.height,
        weight=payload.weight,
        medical_history=payload.medicalHistory,
        work_habit=payload.workHabit,
        allergy_history=payload.allergyHistory,
    )
    user = get_or_create_user(db, payload.userId)
    return _with_nickname_response(user, ok, message, _profile_to_dict(row))


@router.put('/update')
def update_profile(payload: ProfilePayload, db: Session = Depends(get_db)):
    partial = payload.model_dump(exclude_unset=True)
    apply_user_nickname_from_partial(db, payload.userId, partial)
    ok, message, row = update_profile_for_user(
        db,
        payload.userId,
        age=payload.age,
        gender=payload.gender,
        height=payload.height,
        weight=payload.weight,
        medical_history=payload.medicalHistory,
        work_habit=payload.workHabit,
        allergy_history=payload.allergyHistory,
    )
    user = get_or_create_user(db, payload.userId)
    return _with_nickname_response(user, ok, message, _profile_to_dict(row))


@router.post('/save')
def save_profile(payload: ProfilePayload, db: Session = Depends(get_db)):
    partial = payload.model_dump(exclude_unset=True)
    apply_user_nickname_from_partial(db, payload.userId, partial)
    ok, message, row = save_profile_for_user(
        db,
        payload.userId,
        age=payload.age,
        gender=payload.gender,
        height=payload.height,
        weight=payload.weight,
        medical_history=payload.medicalHistory,
        work_habit=payload.workHabit,
        allergy_history=payload.allergyHistory,
    )
    user = get_or_create_user(db, payload.userId)
    return _with_nickname_response(user, ok, message, _profile_to_dict(row))


@router.put('/nickname')
def update_nickname(payload: NicknamePayload, db: Session = Depends(get_db)):
    user = set_user_nickname(db, payload.userId, payload.nickname)
    return {'success': True, 'message': '昵称已更新。', 'userId': user.client_user_id, 'nickname': effective_nickname(user)}


@router.post('/save-tcm-ten-questions')
def save_tcm_ten_questions(payload: TcmTenQuestionsPayload, db: Session = Depends(get_db)):
    """将当前填写的中医十问写入一条评估记录（无体态/舌苔正文，可在历史记录中查看）。"""
    user_row = get_or_create_user(db, payload.userId)
    record = save_assessment(
        db,
        user=user_row,
        titai_fb={'type': 'tcm_ten_only'},
        tixing_fb=None,
        titai_lr=None,
        tixing_lr=None,
        posture_analysis_text=None,
        tongue_analysis_text=None,
        comprehensive_analysis_text=None,
        front_image_path=None,
        meta={
            'analysisType': 'tcm_ten_only',
            'generatedAt': datetime.utcnow().isoformat(),
        },
        tcm_ten_questions=payload.tcmTenQuestions,
    )
    return {
        'success': True,
        'message': '中医十问已保存到数据库。',
        'recordId': record.id,
        'createdAt': record.created_at.isoformat() if record.created_at else None,
    }
