from __future__ import annotations

import json
import logging
import os
from http import HTTPStatus
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from dashscope import Application
from routes.utils.ai_mock import is_mock_ai_enabled, mock_text

logger = logging.getLogger(__name__)

load_dotenv()

# 避免单次请求体过大导致上游返回 400（上下文/请求长度限制）
_MAX_JSON_PROMPT_CHARS = 70_000


def _json_for_prompt(obj: Any, *, max_chars: int = _MAX_JSON_PROMPT_CHARS) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    if len(s) <= max_chars:
        return s
    tail = "\n\n…（JSON 过长已截断，分析仅基于上述片段）"
    return s[: max_chars - len(tail)] + tail


def _get_history_analysis_agent_app_id() -> str:
    app_id = os.getenv("history_analysis_AGENT_APP_ID")
    if not app_id or not str(app_id).strip():
        raise RuntimeError(
            "未配置历史分析智能体应用 ID：请在环境变量中设置 history_analysis_AGENT_APP_ID。"
        )
    return str(app_id).strip()


def _call_history_agent(prompt: str, *, model: Optional[str] = None) -> str:
    """调用百炼历史分析智能体（单轮 prompt）；输出格式与提示词以知识库为准。"""
    _ = model
    if is_mock_ai_enabled():
        return mock_text("history_report")

    api_key = os.getenv("AGENT_API_KEY")
    if not api_key or not str(api_key).strip():
        raise RuntimeError(
            "未配置 AGENT_API_KEY：请在环境变量中设置阿里云百炼 API Key。"
        )

    response = Application.call(
        api_key=api_key.strip(),
        app_id=_get_history_analysis_agent_app_id(),
        prompt=prompt,
    )

    if response.status_code != HTTPStatus.OK:
        logger.error(
            "历史分析智能体失败 request_id=%s code=%s msg=%s",
            response.request_id,
            response.status_code,
            response.message,
        )
        raise RuntimeError(
            f"历史分析智能体调用失败: request_id={response.request_id}, "
            f"code={response.status_code}, message={response.message}"
        )

    text = getattr(response.output, "text", None) if response.output is not None else None
    if not text:
        raise RuntimeError("历史分析智能体返回为空。")
    return text if isinstance(text, str) else str(text)


def _strip_or_none(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _to_number(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        n = float(v)
    except Exception:
        return None
    return n if n == n and n not in (float("inf"), float("-inf")) else None


def _enrich_user_data(profile: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(profile or {})
    h = _to_number(out.get("height"))
    w = _to_number(out.get("weight"))
    if h is not None and w is not None and h > 0 and w > 0:
        h_m = h / 100.0 if h > 10 else h
        if h_m > 0:
            bmi = w / (h_m * h_m)
            if bmi == bmi and bmi not in (float("inf"), float("-inf")):
                out["bmi"] = round(float(bmi), 4)
    return out


def build_joint_report_rows(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    从库中每条评估记录读取「联合报告」正文（comprehensive_analysis_text），
    按时间序列交给智能体做纵向分析；不单独抽取体态/舌苔分项。
    """
    out: List[Dict[str, Any]] = []
    for r in records:
        meta = r.get("meta_json") if isinstance(r.get("meta_json"), dict) else {}
        user_data = _enrich_user_data(meta.get("profileMeta") if isinstance(meta.get("profileMeta"), dict) else {})
        out.append(
            {
                "record_id": r.get("id"),
                "timestamp": r.get("created_at") or r.get("createdAt"),
                "joint_report_text": _strip_or_none(r.get("comprehensive_analysis_text")),
                "user_data": user_data,
            }
        )
    return out


def has_joint_report_content(rows: List[Dict[str, Any]]) -> bool:
    return any((r.get("joint_report_text") or "").strip() for r in rows)


def analyze_history_from_joint_reports(
    joint_report_rows: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    **kwargs,
) -> str:
    """
    对多条已落库的联合报告正文做一次纵向历史分析；仅调用一次历史分析智能体。
    """
    _ = kwargs
    if not joint_report_rows:
        return "未选中任何记录，无法进行历史分析。"
    if not has_joint_report_content(joint_report_rows):
        return "所选记录在数据库中暂无联合报告正文，无法进行历史记录分析。"

    payload_json = _json_for_prompt(joint_report_rows)
    prompt = f"""
【任务】联合报告纵向历史分析

请结合你方知识库：本任务的角色说明、输出结构与合规要求见知识库中的「历史分析」及「输出要求」或同等约定文档。

以下为按用户勾选顺序从数据库读取的多条「联合报告」正文（每条对应一次联合评估的结论）。空字段表示该次未保存联合报告正文。

【联合报告序列】
{payload_json}

请根据上述联合报告内容，完成纵向变化趋势分析与综合健康建议（输出结构与合规要求以知识库为准）。
""".strip()
    return _call_history_agent(prompt, model=model)
