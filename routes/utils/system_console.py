from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

SYSTEM_CONSOLE_STATUS_STORE: Dict[str, List[Dict[str, Any]]] = {}
SYSTEM_CONSOLE_STATUS_LIMIT = 100
SYSTEM_CONSOLE_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _normalize_user_id(user_id: Optional[str]) -> str:
    return (user_id or "admin").strip() or "admin"


def push_system_status(user_id: Optional[str], message: str, color: Optional[str] = None) -> None:
    uid = _normalize_user_id(user_id)
    ts = datetime.now(SYSTEM_CONSOLE_TIMEZONE).strftime("%H:%M:%S")
    line = {
        "text": f"[{ts}] {message}",
        "color": (color or "").strip() or None,
    }
    bucket = SYSTEM_CONSOLE_STATUS_STORE.setdefault(uid, [])
    bucket.append(line)
    if len(bucket) > SYSTEM_CONSOLE_STATUS_LIMIT:
        del bucket[:-SYSTEM_CONSOLE_STATUS_LIMIT]


def get_system_status_lines(user_id: Optional[str]) -> List[Dict[str, Any]]:
    uid = _normalize_user_id(user_id)
    return SYSTEM_CONSOLE_STATUS_STORE.get(uid, [])


def clear_system_status_lines(user_id: Optional[str]) -> None:
    uid = _normalize_user_id(user_id)
    SYSTEM_CONSOLE_STATUS_STORE.pop(uid, None)

