from __future__ import annotations

import json
import os
import re
from http import HTTPStatus
from typing import Any, Dict

from dotenv import load_dotenv
from dashscope import Application
from routes.utils.ai_mock import is_mock_ai_enabled, mock_text

load_dotenv()
MAX_CONTEXT_LEN = 12000
MAX_REPORT_LEN = 6000


def _truncate_text(text: str, max_len: int) -> tuple[str, bool]:
    raw = text or ""
    if len(raw) <= max_len:
        return raw, False
    kept = raw[:max_len]
    return kept + f"\n\n[TRUNCATED total={len(raw)} kept={max_len}]", True


def _get_reviewer_app_id() -> str:
    app_id = os.getenv("Test_Agent_APP_ID")
    if not app_id or not str(app_id).strip():
        raise RuntimeError(
            "未配置统筹评审智能体应用 ID：请在环境变量中设置 Test_Agent_APP_ID。"
        )
    return str(app_id).strip()


def _extract_json_obj(text: str) -> Dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def evaluate_report_quality(
    *,
    report_type: str,
    report_text: str,
    base_context: str,
    iteration: int,
    max_iterations: int,
) -> Dict[str, Any]:
    if is_mock_ai_enabled():
        return {"score": 1, "comment": mock_text("review_comment"), "raw": '{"score":1,"comment":"mock"}'}
    context_input, context_truncated = _truncate_text(base_context or "", MAX_CONTEXT_LEN)
    report_input, report_truncated = _truncate_text(report_text or "", MAX_REPORT_LEN)
    app_id = _get_reviewer_app_id()
    is_joint_report = "综合" in (report_type or "")
    if is_joint_report:
        prompt = f"""
你是“常规分析建议评估智能体”。请只做评估，不要改写正文。

评估目标（常规分析与建议）：
1. 体态与体质常规分析这一部分，是否充分考虑了体态与体型分析以及舌象与中医体质分析，然后给出了常规分析。
2.建议是否有可执行性，是否对用户有用，避免空话；
3.综合健康指导这一部分：
（1）是否综合考虑了体态与体型分析以及舌象与中医体质分析；
（2）需要既有几条比较概括、全面的建议，也要举几个具体例子；
（3）是否考虑了用户的实际状况，比如25岁的人，在建议睡眠时间这里，不应该建议他晚上九点之前睡觉，因为这不现实。
（4）是否考虑了一些禁忌，例如糖尿病人不要让他吃甜食；体重大的人，不要建议他跑步；火气大的人，不要让他吃一些热性食物；湿气重忌生冷寒凉，等等。
（5）是否具有科学性，是否符合中医理论。
4.是否包含合理边界与风险提示（非诊断、何时建议线下就医）；
5.内容是否前后一致、无明显矛盾。
6.不需要太苛刻，给出你的优化建议。

输入上下文：
{context_input}

当前轮次：{iteration}/{max_iterations}
待评审正文：
{report_input or "（空）"}

请严格仅输出 JSON（不要额外解释）：
{{
  "score": 0 或 1,
  "comment": "点评：指出哪里不清楚、哪里空泛、如何改进，要求可执行"
}}
""".strip()
    else:
        prompt = f"""
你是“单项报告评估智能体”。请只做评估，不要改写正文。

评估目标（体态体型/舌苔）：
1.描述是否具体，是否存在无信息量的套话；
2.对于体态体型，输出的分析是否具有科学性；对于舌苔，输出的分析是否充分结合了中医十问的信息、是否充分从中医角度进行解释。
3.是否既具备专业性，从专业角度进行解释，也保证用户确实能够理解。
4.不需要太苛刻，给出你的优化建议。

输入上下文：
{context_input}

当前轮次：{iteration}/{max_iterations}
待评审正文：
{report_input or "（空）"}

请严格仅输出 JSON（不要额外解释）：
{{
  "score": 0 或 1,
  "comment": "点评：指出哪里不清楚、哪里空泛、如何改进，要求可执行"
}}
""".strip()

    api_key = os.getenv("AGENT_API_KEY")
    if not api_key or not str(api_key).strip():
        raise RuntimeError("未配置 AGENT_API_KEY。")

    response = Application.call(
        api_key=api_key.strip(),
        app_id=app_id,
        prompt=prompt,
        temperature=0.2,
    )

    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            "调用智能体失败: "
            f"request_id={response.request_id}, code={response.status_code}, message={response.message}"
        )

    text = getattr(response.output, "text", None) if response.output is not None else None
    if not text:
        raise RuntimeError("调用智能体失败: 返回为空")

    parsed = _extract_json_obj(str(text))
    if isinstance(parsed, dict):
        score_raw = parsed.get("score")
        score = 1 if str(score_raw).strip() in ("1", "true", "True") else 0
        comment = str(parsed.get("comment") or "").strip() or "未提供改进意见"
        return {"score": score, "comment": comment, "raw": str(text)}

    normalized = str(text).strip()
    score = 1 if normalized.startswith("1") else 0
    return {"score": score, "comment": normalized, "raw": normalized}

