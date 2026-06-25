from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.crud import authenticate_account, create_account, effective_nickname, get_or_create_user
from db.database import get_db

from .schemas import AuthPayload

router = APIRouter(prefix='/api/auth', tags=['auth'])


@router.post('/register')
def register_account(payload: AuthPayload, db: Session = Depends(get_db)):
    ok, msg = create_account(db, payload.account, payload.password, payload.nickname)
    if not ok:
        return {'success': False, 'message': msg}
    uid = payload.account.strip()
    user = get_or_create_user(db, uid)
    return {'success': True, 'message': msg, 'userId': uid, 'nickname': effective_nickname(user)}


@router.post('/login')
def login_account(payload: AuthPayload, db: Session = Depends(get_db)):
    account = (payload.account or '').strip()
    ok = authenticate_account(db, account, payload.password)
    if not ok:
        return {'success': False, 'message': '账号或密码错误'}
    user = get_or_create_user(db, account)
    return {
        'success': True,
        'message': '登录成功',
        'token': f'mask-token-{account}',
        'userId': account,
        'nickname': effective_nickname(user),
    }
