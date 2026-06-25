"""中医十问格式化为联合报告等文本 prompt 片段（与舌苔视觉模块解耦）。"""
from __future__ import annotations

from typing import Any, Dict, Optional

_TCM_TEN_LABELS: Dict[str, str] = {
    "coldHeat": "一问寒热",
    "sweat": "二问汗",
    "sleep": "三问睡眠",
    "appetite": "四问饮食",
    "stool": "五问大便",
    "urination": "六问小便",
    "emotion": "七问情志",
    "energy": "八问劳倦",
    "thirst": "九问口渴",
    "pain": "十问疼痛",
}


def format_tcm_ten_questions_plain(tcm: Optional[Dict[str, Any]]) -> str:
    """供联合报告等使用的纯文本块（无舌苔专用指令）。"""
    if not tcm or not isinstance(tcm, dict):
        return "（用户未提供中医十问，本部分请勿编造。）"
    lines: list[str] = ["以下为用户在 App 中自填的中医十问（自陈信息，未经核实，仅供对照参考）："]
    any_val = False
    for key, value in tcm.items():
        if value is None or str(value).strip() == "":
            continue
        any_val = True
        label = _TCM_TEN_LABELS.get(key, key)
        lines.append(f"{label}（{key}）：{value}")
    if not any_val:
        return "（用户未填写有效的中医十问条目。）"
    return "\n".join(lines)
