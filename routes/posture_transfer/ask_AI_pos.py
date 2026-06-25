from __future__ import annotations

import json
import os
from http import HTTPStatus
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from dashscope import Application
from routes.utils.ai_mock import is_mock_ai_enabled, mock_text
from routes.utils.structured_output_protocol import structured_output_protocol

load_dotenv()


def _get_agent_app_id() -> str:
    app_id = os.getenv("AGENT_APP_ID")
    if not app_id or not str(app_id).strip():
        raise RuntimeError(
            "未配置体态分析智能体应用 ID：请在环境变量中设置 AGENT_APP_ID。"
        )
    posture_app_id = str(app_id).strip()
    joint_app_id = str(os.getenv("JOINT_REPORT_AGENT_APP_ID") or "").strip()
    if joint_app_id and posture_app_id == joint_app_id:
        raise RuntimeError(
            "体态智能体配置错误：POSTURE_AGENT_APP_ID/AGENT_APP_ID 与 "
            "JOINT_REPORT_AGENT_APP_ID 相同，已阻止误调用常规分析智能体。"
        )
    return posture_app_id


def ask_ai_posture(
    user_info: Dict[str, Any],
    posture_info: Dict[str, Any] | None = None,
    *,
    analysis_mode: str = "normal",
    model: Optional[str] = None,
) -> str:
    _ = model  # 智能体应用在控制台配置模型，请求侧不再传 model
    if is_mock_ai_enabled():
        return mock_text("posture_report")

    posture_text = "未提供体态数据。"
    if posture_info:
        posture_text = json.dumps(posture_info, ensure_ascii=False, indent=2)

    mode = "expert" if str(analysis_mode or "").strip().lower() == "expert" else "normal"
    if mode == "expert":
        prompt = f"""
你是资深体态分析专家，存在普通模式和专家模式。用户很可能存在肥胖、体重大等烦恼。
请在结论准确的前提下，结合知识库以及联网搜索相关知识，以专家模式，对用户的体型体态进行分析。

{structured_output_protocol(
    section_key_examples=["overall", "metrics", "analysis"],
    item_key_examples=["shoulder_index", "pelvis_tilt_index", "head_forward_index"],
)}

1.用户基本信息：
- userId: {user_info.get("userId")}
- 姓名: {user_info.get("name")}
- 年龄: {user_info.get("age")}
- 性别: {user_info.get("gender")}
- 身高: {user_info.get("height")}
- 体重: {user_info.get("weight")}
- 过敏情况: {user_info.get("allergyHistory") or "无过敏史"}

2.以下为本次检测得到的体态与体型数值（JSON）。请结合你方知识库：指标释义与计算说明见知识库中的「体态/体型指标说明。

体态检测结果：
{posture_text}

3.你的输出结构规范：

一、整体状态参考分析
用简短的段落，描述用户大体存在的问题以及体态情况。

二、指标分析
（一）体态指标分析：你需要说明各个指数的含义、详细说明当前数值可能代表的问题（如果有）、结合网络医学知识对相关问题以及其可能的产生原因进行解释
1. 高低肩指数：说明数值含义、左右高低倾向及程度。
2. 骨盆倾斜指数：说明数值含义、左右倾斜倾向及可能原因。
3. 头前伸指数：说明数值含义、头部前伸程度及潜在影响。
4. 膝关节对齐指数：说明数值含义、关节力线状态及风险提示。
5. 腹部前突指数：说明数值含义、腹部前突程度及核心状态。

（二）体型指标分析：你需要说明各个指数的含义、详细说明当前数值可能代表的问题（如果有）、结合网络医学知识对相关问题以及其可能的产生原因进行解释
1. 头身比：说明当前数值及正常性。
2. 腿身比、躯干身高比、上下身面积比：综合说明躯干与下肢比例特征。
3.大腿小腿比、头肩比：说明肢体与头肩比例协调程度。

三、常规分析
你需要结合知识库，深度搜索网络可靠的康复学以及体态学相关的医学知识，
判断是否存在肥胖，肥胖类型（例如腰部脂肪堆积/腹部脂肪堆积/腿部脂肪堆积等等），
综合用户的体型与体态指标，
对用户的体态身材状况、可能存在的体态问题进行详细、专业、科学可靠、深度的分析，暂时不做体态改进建议。

请按专家深度分析模式输出体态分析报告。
""".strip()
    else:
        prompt = f"""
你是资深体态分析专家，存在普通模式和专家模式。用户很可能存在肥胖、体重大等烦恼。
现在以普通模式，对用户体态体型数据进行分析。

{structured_output_protocol(
    section_key_examples=["overall", "metrics", "analysis"],
    item_key_examples=["shoulder_index", "pelvis_tilt_index", "head_forward_index"],
)}

1.用户基本信息：
- userId: {user_info.get("userId")}
- 姓名: {user_info.get("name")}
- 年龄: {user_info.get("age")}
- 性别: {user_info.get("gender")}
- 身高: {user_info.get("height")}
- 体重: {user_info.get("weight")}
- 过敏情况: {user_info.get("allergyHistory") or "无过敏史"}

2.以下为本次检测得到的体态与体型数值（JSON）。请结合你方知识库：指标释义与计算说明见知识库中的「体态/体型指标说明」；报告的结构、分段与表述规范见知识库中的「输出要求」或同等约定文档。若某字段为空或缺失，表示该次未算出，分析时可跳过。

体态检测结果：
{posture_text}

3.你的输出结构规范：

一、整体状态参考分析
用简短的段落，描述用户大体存在的问题以及体态情况。

二、指标分析
（一）体态指标分析：
1. 高低肩指数：说明数值含义、左右高低倾向及程度。
2. 骨盆倾斜指数：说明数值含义、左右倾斜倾向及可能原因。
3. 头前伸指数：说明数值含义、头部前伸程度及潜在影响。
4. 膝关节对齐指数：说明数值含义、关节力线状态及风险提示。
5. 腹部前突指数：说明数值含义、腹部前突程度及核心状态。

（二）体型指标分析：
1. 头身比：说明当前数值及正常性。
2. 腿身比、躯干身高比、上下身面积比：综合说明躯干与下肢比例特征。
3.大腿小腿比、头肩比：说明肢体与头肩比例协调程度。

三、常规分析
根据知识库以及网络知识，综合体型与体态指标，对体态身材以及可能存在的问题进行分析；
判断是否存在肥胖，肥胖类型（例如腰部脂肪堆积/腹部脂肪堆积/腿部脂肪堆积等等），暂时不输出体态改进建议。

请根据上述用户信息与本检测结果，撰写体态分析报告。
""".strip()

    api_key = os.getenv("AGENT_API_KEY")
    if not api_key or not str(api_key).strip():
        raise RuntimeError(
            "未配置 AGENT_API_KEY：请在环境变量中设置阿里云百炼 API Key。"
        )

    response = Application.call(
        api_key=api_key.strip(),
        app_id=_get_agent_app_id(),
        prompt=prompt,
    )

    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"体态智能体调用失败: request_id={response.request_id}, "
            f"code={response.status_code}, message={response.message}"
        )

    text = getattr(response.output, "text", None) if response.output is not None else None
    if not text:
        raise RuntimeError("体态智能体返回为空。")
    return text


def improve_posture_report(
    *,
    user_info: Dict[str, Any],
    posture_info: Dict[str, Any] | None,
    previous_output: str,
    reviewer_comment: str,
    iteration: int,
    max_iterations: int,
    analysis_mode: str = "expert",
    model: Optional[str] = None,
) -> str:
    _ = model
    if is_mock_ai_enabled():
        return mock_text("expert_posture_report")
    posture_text = "未提供体态数据。"
    if posture_info:
        posture_text = json.dumps(posture_info, ensure_ascii=False, indent=2)

    mode = "expert" if str(analysis_mode or "").strip().lower() == "expert" else "normal"
    prompt = f"""
你在进行“体态报告迭代改写”。这是第 {iteration}/{max_iterations} 轮。
当前分析模式：{mode}。

{structured_output_protocol(
    section_key_examples=["overall", "metrics", "analysis"],
    item_key_examples=["shoulder_index", "pelvis_tilt_index", "head_forward_index"],
)}

【原始输入（不可忽略）】
用户信息：
- userId: {user_info.get("userId")}
- 年龄: {user_info.get("age")}
- 性别: {user_info.get("gender")}
- 身高: {user_info.get("height")}
- 体重: {user_info.get("weight")}
- 过敏情况: {user_info.get("allergyHistory") or "无过敏史"}
体态数据(JSON)：
{posture_text}

【你上一次输出】
{previous_output or "（空）"}

【统筹评审意见（必须逐条落实）】
{reviewer_comment or "（无）"}

请按评审意见改写并输出新的完整体态报告正文（只输出正文，不要额外解释）。
""".strip()

    api_key = os.getenv("AGENT_API_KEY")
    if not api_key or not str(api_key).strip():
        raise RuntimeError("未配置 AGENT_API_KEY。")

    response = Application.call(
        api_key=api_key.strip(),
        app_id=_get_agent_app_id(),
        prompt=prompt,
    )
    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"体态智能体迭代调用失败: request_id={response.request_id}, "
            f"code={response.status_code}, message={response.message}"
        )
    text = getattr(response.output, "text", None) if response.output is not None else None
    if not text:
        raise RuntimeError("体态智能体迭代返回为空。")
    return str(text)
