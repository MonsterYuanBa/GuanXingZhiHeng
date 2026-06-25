from __future__ import annotations

import json
import os
from http import HTTPStatus
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from dashscope import Application

from routes.utils.api_helpers import image_file_to_data_url, safe_json_loads
from routes.utils.ai_mock import is_mock_ai_enabled, mock_text, mock_tongue_structured
from routes.utils.tcm_ten_prompt import format_tcm_ten_questions_plain
from routes.utils.structured_output_protocol import structured_output_protocol

load_dotenv()


def _get_shetai_agent_app_id() -> str:
    app_id = os.getenv("shetai_Agent_App_ID")
    if not app_id or not str(app_id).strip():
        raise RuntimeError(
            "未配置舌苔分析智能体应用 ID：请在环境变量中设置 shetai_Agent_App_ID。"
        )
    tongue_app_id = str(app_id).strip()
    joint_app_id = str(os.getenv("JOINT_REPORT_AGENT_APP_ID") or "").strip()
    if joint_app_id and tongue_app_id == joint_app_id:
        raise RuntimeError(
            "舌苔智能体配置错误：SHETAI_AGENT_APP_ID 与 "
            "JOINT_REPORT_AGENT_APP_ID 相同，已阻止误调用常规分析智能体。"
        )
    return tongue_app_id


def analyze_tongue_image(
    image_path: str,
    mime: str = "image/jpeg",
    *,
    tcm_ten_questions: Optional[Dict[str, Any]] = None,
    analysis_mode: str = "normal",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    调用百炼舌苔智能体分析舌象图；返回值为 safe_json_loads 解析结果（非 JSON 时含 rawText）。
    model：保留参数以兼容路由，请求中不使用。
    """
    _ = model
    if is_mock_ai_enabled():
        return mock_tongue_structured()

    data_url = image_file_to_data_url(image_path, mime=mime)

    tcm_block = format_tcm_ten_questions_plain(tcm_ten_questions)

    mode = "expert" if str(analysis_mode or "").strip().lower() == "expert" else "normal"
    if mode == "expert":
        prompt = f"""
你是一名专业中医，存在普通模式和专家模式。用户很可能存在肥胖、体重大等烦恼，现在你需要以专家深度分析模式输出报告，
结合用户的舌苔图像，以及上传的中医十问，结合知识库以及网络专业可靠中医知识，对用户的体质进行分析，强调证据链（观察现象 -> 解释 -> 可执行建议）与风险提示边界。

{structured_output_protocol(
    section_key_examples=["overall", "tongue_body", "tcm_ten", "conclusion"],
    item_key_examples=["tongue_color", "coating_color", "sleep_emotion", "diet_bowel"],
)}

1.中医十问（用户自填，可能未提供；未提供时勿编造）：
{tcm_block}

2.舌象图片已随本请求提供。

3.中医体质学说最主流、国家标准的分类是 9 种基本体质，出自《中医体质分类与判定》（中华中医药学会标准）。
中医 9 种体质（完整版）
平和质（健康理想体质）
气虚质（气不足、易疲劳）
阳虚质（怕冷、阳气不足）
阴虚质（怕热、口干、内热）
痰湿质（肥胖、痰多、身体沉重）
湿热质（长痘、口苦、油腻、易上火）
血瘀质（面色暗、有斑、痛经、刺痛）
气郁质（情绪抑郁、敏感、胸闷）
特禀质（过敏体质、易过敏、先天禀赋异常）
简要特点：
平和质：阴阳平衡，精力充沛，少生病。
气虚质：语声低、懒动、易出汗、易感冒。
阳虚质：畏寒怕冷、手脚凉、喜热饮、大便稀。
阴虚质：手足心热、盗汗、口干咽燥、舌红少苔。
痰湿质：体型肥胖、腹部松软、痰多、困倦。
湿热质：面油、痤疮、口苦口臭、大便黏滞。
血瘀质：肤色晦暗、瘀斑、疼痛固定、舌有瘀点。
气郁质：多愁善感、嗳气、胸闷、失眠焦虑。
特禀质：过敏性鼻炎、哮喘、荨麻疹、药物过敏等。

4.输出规范：

一、整体状态参考分析
根据用户舌象图像信息与中医十问自填内容进行常规分析。
强调本报告基于图像算法与中医养生逻辑判断，结果仅供健康管理参考，不构成任何临床诊断。

二、舌象与体质分析
根据检测数据，整体体质状态基本平和，或存在某类倾向较为明显。
1.舌象指标分析：对用户的舌头从各个角度进行详细、专业的分析。
（1） 舌体颜色：说明当前颜色状态及可能对应的寒热、气血倾向。
（2） 舌苔颜色：说明当前苔色及可能对应的寒热、湿邪倾向。
（3） 舌苔厚薄：说明厚薄程度及可能对应的邪气深浅、胃气状态。
（4） 湿润度：说明润燥状态及可能对应的津液、水湿倾向。
（5） 裂纹与齿痕：说明有无裂纹、齿痕及可能对应的阴血、脾虚倾向。
2.中医十问分析：结合中医知识，从中医十问出发，详细分析用户的体质
（1） 寒热与汗液：结合冷热、汗出情况说明阴阳、固摄状态。
（2） 睡眠与情志：结合睡眠、情绪说明心神、肝气疏泄状态。
（3） 饮食与二便：结合食欲、口味、大小便说明脾胃、肠道、膀胱功能倾向。
（4） 劳倦与疼痛：结合体力、疼痛表现说明气血、经络通畅倾向。

三、 综合体质判断
1.结合知识库，深度搜索网络中医相关知识，对舌象与十问分别进行总结；
2.然后综合舌象特征与十问分析，对用户的整体健康状况进行分析，判断用户属于上述九种体质中的哪种；详细说明整体体质倾向。

""".strip()
    else:
        prompt = f"""
你是一名专业中医，存在普通模式和专家模式。用户很可能存在肥胖、体重大等烦恼，现在你需要以普通分析模式输出报告，
结合用户的舌苔图像，以及上传的中医十问，结合知识库以及网络专业可靠中医知识，对用户的体质进行分析。  

{structured_output_protocol(
    section_key_examples=["overall", "tongue_body", "tcm_ten", "conclusion"],
    item_key_examples=["tongue_color", "coating_color", "sleep_emotion", "diet_bowel"],
)}

1.中医十问（用户自填，可能未提供；未提供时勿编造）：
{tcm_block}

2.舌象图片已随本请求提供。

3.中医体质学说最主流、国家标准的分类是 9 种基本体质，出自《中医体质分类与判定》（中华中医药学会标准）。
中医 9 种体质（完整版）
平和质（健康理想体质）
气虚质（气不足、易疲劳）
阳虚质（怕冷、阳气不足）
阴虚质（怕热、口干、内热）
痰湿质（肥胖、痰多、身体沉重）
湿热质（长痘、口苦、油腻、易上火）
血瘀质（面色暗、有斑、痛经、刺痛）
气郁质（情绪抑郁、敏感、胸闷）
特禀质（过敏体质、易过敏、先天禀赋异常）
简要特点：
平和质：阴阳平衡，精力充沛，少生病。
气虚质：语声低、懒动、易出汗、易感冒。
阳虚质：畏寒怕冷、手脚凉、喜热饮、大便稀。
阴虚质：手足心热、盗汗、口干咽燥、舌红少苔。
痰湿质：体型肥胖、腹部松软、痰多、困倦。
湿热质：面油、痤疮、口苦口臭、大便黏滞。
血瘀质：肤色晦暗、瘀斑、疼痛固定、舌有瘀点。
气郁质：多愁善感、嗳气、胸闷、失眠焦虑。
特禀质：过敏性鼻炎、哮喘、荨麻疹、药物过敏等。

4.输出规范

一、整体状态参考分析
根据用户舌象图像信息与中医十问自填内容进行常规分析。
强调本报告基于图像算法与中医养生逻辑判断，结果仅供健康管理参考，不构成任何临床诊断。

二、舌象与体质分析
根据检测数据，整体体质状态基本平和，或存在某类倾向较为明显。
1.舌象指标分析：
（1） 舌体颜色：说明当前颜色状态及可能对应的寒热、气血倾向。
（2） 舌苔颜色：说明当前苔色及可能对应的寒热、湿邪倾向。
（3） 舌苔厚薄：说明厚薄程度及可能对应的邪气深浅、胃气状态。
（4） 湿润度：说明润燥状态及可能对应的津液、水湿倾向。
（5） 裂纹与齿痕：说明有无裂纹、齿痕及可能对应的阴血、脾虚倾向。
2.中医十问分析：
（1） 寒热与汗液：结合冷热、汗出情况说明阴阳、固摄状态。
（2） 睡眠与情志：结合睡眠、情绪说明心神、肝气疏泄状态。
（3） 饮食与二便：结合食欲、口味、大小便说明脾胃、肠道、膀胱功能倾向。
（4） 劳倦与疼痛：结合体力、疼痛表现说明气血、经络通畅倾向。

三、 综合体质判断
根据知识库及网络知识，对舌象与十问进行统一归纳，综合舌象特征与十问分析，判断用户属于上述九种体质中的哪种；
对整体健康状况进行分析，说明整体体质倾向。

""".strip()

    api_key = os.getenv("AGENT_API_KEY")
    if not api_key or not str(api_key).strip():
        raise RuntimeError(
            "未配置 AGENT_API_KEY：请在环境变量中设置阿里云百炼 API Key。"
        )

    response = Application.call(
        api_key=api_key.strip(),
        app_id=_get_shetai_agent_app_id(),
        prompt=prompt,
        image_list=[data_url],
    )

    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"舌苔智能体调用失败: request_id={response.request_id}, "
            f"code={response.status_code}, message={response.message}"
        )

    content = getattr(response.output, "text", None) if response.output is not None else None
    if not content:
        raise RuntimeError("舌苔智能体返回为空。")
    return safe_json_loads(content)


def _strip_duplicate_summary_heading(summary: str) -> str:
    """报告拼装时已有「二、综合小结」小标题，去掉模型在 summary 里重复的标题行。"""
    s = summary.strip()
    if not s:
        return s
    for prefix in (
        "二、综合小结",
        "二、 综合小结",
        "综合小结：",
        "综合小结",
    ):
        if s.startswith(prefix):
            s = s[len(prefix) :].lstrip(" \t\n\r：:，,")
            break
    return s


def _field_display(v: Any) -> str:
    """避免 f-string 把 None 格式化成字面量 'None'。"""
    if v is None:
        return "—"
    s = str(v).strip()
    if not s or s.lower() == "none":
        return "—"
    return s


def _normalize_bullet_analysis(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    if isinstance(raw, list):
        out: list[str] = []
        for x in raw:
            if x is None:
                continue
            s = str(x).strip()
            if s and s.lower() != "none":
                out.append(s)
        return out
    return []


def format_tongue_analysis_report(tongue_info: Dict[str, Any]) -> str:
    """将舌苔视觉分析结果格式化为面向用户的报告正文（存库 / 接口返回）。"""
    if tongue_info.get("error"):
        return f"舌苔图像分析失败：{_field_display(tongue_info.get('error'))}"

    # 智能体返回非 JSON 时 safe_json_loads 仅保留原文
    if tongue_info.get("parseError") and tongue_info.get("rawText"):
        raw = str(tongue_info["rawText"]).strip()
        return raw if raw else "（智能体返回无法解析为 JSON，且正文为空）"

    bullets = _normalize_bullet_analysis(
        tongue_info.get("bulletAnalysis") or tongue_info.get("bullet_analysis")
    )

    sm = tongue_info.get("summary")
    sm = "" if sm is None else str(sm).strip()
    if sm.lower() == "none":
        sm = ""
    summary = _strip_duplicate_summary_heading(sm)

    if bullets:
        header = "舌苔图像客观信息（仅作图像表面描述，不代表医疗诊断）"
        body = "\n".join([header, "", "一、分项观察", *bullets, "", "二、综合小结", summary or "（无）"])
        return body.strip()

    if summary:
        return summary

    return "（智能体返回内容无法作为报告展示：请按 prompt 输出可读正文，或非 JSON 纯文本。）"


def improve_tongue_report(
    *,
    previous_output: str,
    reviewer_comment: str,
    tongue_extra: Optional[Dict[str, Any]] = None,
    tcm_ten_questions: Optional[Dict[str, Any]] = None,
    iteration: int,
    max_iterations: int,
    analysis_mode: str = "expert",
    model: Optional[str] = None,
) -> str:
    _ = model
    if is_mock_ai_enabled():
        return mock_text("expert_tongue_report")
    extra_text = "（无）"
    if tongue_extra:
        try:
            extra_text = json.dumps(tongue_extra, ensure_ascii=False, indent=2)
        except Exception:
            extra_text = str(tongue_extra)

    tcm_block = format_tcm_ten_questions_plain(tcm_ten_questions)
    mode = "expert" if str(analysis_mode or "").strip().lower() == "expert" else "normal"
    prompt = f"""
你在进行“舌苔报告迭代改写”。这是第 {iteration}/{max_iterations} 轮。
当前分析模式：{mode}。

{structured_output_protocol(
    section_key_examples=["overall", "tongue_body", "tcm_ten", "conclusion"],
    item_key_examples=["tongue_color", "coating_color", "sleep_emotion", "diet_bowel"],
)}

【原始输入（不可忽略）】
中医十问：
{tcm_block}
舌苔结构化信息：
{extra_text}

【你上一次输出】
{previous_output or "（空）"}

【统筹评审意见（必须逐条落实）】
{reviewer_comment or "（无）"}

请输出改写后的完整舌苔报告正文（只输出正文，不要额外解释）。
""".strip()

    api_key = os.getenv("AGENT_API_KEY")
    if not api_key or not str(api_key).strip():
        raise RuntimeError("未配置 AGENT_API_KEY。")

    response = Application.call(
        api_key=api_key.strip(),
        app_id=_get_shetai_agent_app_id(),
        prompt=prompt,
        temperature=0.35,
    )
    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"舌苔智能体迭代调用失败: request_id={response.request_id}, "
            f"code={response.status_code}, message={response.message}"
        )
    text = getattr(response.output, "text", None) if response.output is not None else None
    if not text:
        raise RuntimeError("舌苔智能体迭代返回为空。")
    return str(text)
