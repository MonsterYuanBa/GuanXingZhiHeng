from __future__ import annotations

import json
import os
from http import HTTPStatus
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from dashscope import Application

from routes.utils.ai_mock import is_mock_ai_enabled, mock_text
from routes.utils.tcm_ten_prompt import format_tcm_ten_questions_plain
from routes.utils.structured_output_protocol import structured_output_protocol

load_dotenv()


def _get_joint_report_agent_app_id() -> str:
    app_id = (os.getenv("JOINT_REPORT_AGENT_APP_ID"))

    if not app_id or not str(app_id).strip():
        raise RuntimeError(
            "未配置联合报告智能体应用 ID：请在环境变量中设置 "
            "JOINT_REPORT_AGENT_APP_ID（百炼控制台中的应用 ID）。"
        )
    return str(app_id).strip()


def generate_joint_comprehensive_report(
    *,
    profile_summary: str,
    posture_report: str,
    posture_metrics: Optional[Dict[str, Any]],
    tongue_report: str,
    tongue_extra: Optional[Dict[str, Any]],
    tcm_ten_questions: Optional[Dict[str, Any]] = None,
    analysis_mode: str = "normal",
    model: Optional[str] = None,
    extra_user_requirements: Optional[str] = None,
) -> str:
    """
    综合用户档案、体态/体型数据与舌苔描述，生成联合健康管理建议（非医疗诊断）。
    通过百炼联合报告智能体生成正文；输出结构与合规要求以知识库为准。
    """
    _ = model  # 智能体在控制台配置模型，请求侧不再传 model
    if is_mock_ai_enabled():
        return mock_text("joint_report")

    metrics_text = "（无结构化体态/体型指标）"
    if posture_metrics:
        try:
            metrics_text = json.dumps(posture_metrics, ensure_ascii=False, indent=2)
        except Exception:
            metrics_text = str(posture_metrics)

    tongue_extra_text = ""
    if tongue_extra:
        try:
            tongue_extra_text = json.dumps(tongue_extra, ensure_ascii=False, indent=2)
        except Exception:
            tongue_extra_text = str(tongue_extra)

    tcm_block = format_tcm_ten_questions_plain(tcm_ten_questions)

    _extra_raw = (extra_user_requirements or "").strip()
    _extra_block = (
        f"\n【用户多次提交的补充需求】（按时间顺序；请在全部分析与建议中统筹考虑）\n{_extra_raw}\n"
        if _extra_raw
        else ""
    )

    mode = "expert" if str(analysis_mode or "").strip().lower() == "expert" else "normal"
    if mode == "expert":
        prompt = f"""
你是资深的体态分析专家，擅长结合用户的体态体型数据、中医体质以及舌苔等信息，针对用户给出体态分析以及改善的建议。
用户很可能存在肥胖。体型过大等烦恼。
你存在专家模式和普通模式，现在以专家模式，结合用户基本信息、体态体型数据、舌苔以及中医体质信息，给出分析和建议。
在该模式下，进行的任何分析与建议，都要通过联网等手段，保证确实真实科学、可行可靠。

{structured_output_protocol(
    section_key_examples=["overall", "posture_body", "tongue_tcm", "linkage", "guidance"],
    item_key_examples=["diet", "activity", "daily_life", "schedule", "posture_maintain"],
)}

1.材料说明：体态/舌苔检测与问卷均为参考信息，不等同医学检查；若某段正文写「暂无」或下列 JSON 中某字段缺失，表示该次未提供，撰写时按需跳过或简要说明信息不足。

【用户档案摘要】
{profile_summary}

【中医十问】（用户自填，可能未提供；非诊断依据）
{tcm_block}

【体态与体型分析正文】（系统记录）
{posture_report or "（暂无体态分析正文）"}

【体态/体型结构化数据】（JSON，仅供理解趋势）
{metrics_text}

【舌苔分析正文】（系统记录，图像现象描述）
{tongue_report or "（暂无舌苔分析正文）"}

【舌苔附加结构化信息】（JSON，若有）
{tongue_extra_text or "（无）"}
{_extra_block}
2.输出规范

一、整体状态参考分析
根据用户基本信息、体态检测结果、舌象图像及中医十问内容，用 1 至 3 个自然段进行综合概述（只在内容过长时才分段；用单个换行分段即可；段与段之间禁止空白行）。
强调本报告仅供健康管理参考，不构成任何医疗诊断。
若存在【用户多次提交的补充需求】，必须在本段中用 1-2 句话“回显复述”用户的主要补充情况/核心诉求，并明确说明“已纳入本次分析与建议”。
在后续各段落的分析与建议中，必须持续围绕这些补充情况与诉求进行取舍与侧重（例如：明确优先关注的目标、需要规避的项目、建议的个性化约束）。

二、体态与体型分析
结合体态体型数据、体态体型分析报告，同时针对这些数据进行联网搜索以及知识库查找，对体型体态进行判断。
总结整体姿态端正度、对称性与力线顺畅情况，说明体型比例与脂肪分布特点，对异常体态指标简要说明状态、受力、负荷及潜在影响。

三、舌象与中医体质分析
结合中医十问数据、舌苔分析报告，同时针对这些数据进行联网搜索以及知识库查找，对中医体质进行判断。
总结整体体质偏向，包括寒热、湿邪、津液气血与脏腑功能倾向，对异常舌象与十问条目简要说明表现与对应倾向。

四、体态与体质联动分析
结合体态体型分析以及舌苔中医分析，常规分析用户的体态体型体质；
判断是否存在肥胖，肥胖类型（例如腰部脂肪堆积/腹部脂肪堆积/腿部脂肪堆积等等）；
当前体态体型和肥胖可能导致什么潜在的慢性病，例如高血压、糖尿病、血脂等；
建议控制到大约多少体重，肌肉、脂肪分别建议控制多少；
说明体质如何影响肌肉、气血、循环并加重或缓解体态问题，同时说明体态异常如何影响受力、呼吸、经络并强化或改变体质倾向，综合体态与体质的内在关联与综合表现。

五、综合健康指导
这里的建议需要既写的全面，提供用户很多选择；
又要对其中一部分进行详细说明，防止建议过于泛泛而谈。
每一个部分都可以用多个段落进行描述，保证提供用户多样化全面选择、提供的建议具备高度可行性。
1.饮食与饮水建议：结合体态、脂肪分布、舌象与十问，给出进食节奏、口味、宜增宜控的具体方向。
2.适合的运动与活动：结合体型、体态与体质，给出适宜运动、强度、频率及需规避的运动项目。
3.日常生活注意事项：包括姿势、久坐、睡眠、情绪、环境等方面的具体注意内容。
4.作息与节律建议：结合体质与疲劳状态，给出作息、睡眠、午休与劳逸结合建议。
5.姿态日常维护：针对主要体态问题，给出站立、坐姿、行走、用屏等日常姿态提醒。

六、营养专项建议
1.饮食热量摄入的控制，根据用户性别，提供热量摄入建议，例如每日摄入多少热量，不高于多少、不低于多少，或者比原来减少多少热量摄入；
2.摄入营养元素的注意事项，例如体型用户不要因为减少食物摄入而导致维生素、矿物质摄入不足，应摄入哪种维生素的营养补充剂；
3.三餐的饭量或者能量占比；
4.提供一个一周食谱，每天早中晚建议吃些什么东西、每顿饭会有多少热量摄入；
5.营养素：每日建议摄入蛋白质、脂肪、碳水化合物、膳食纤维这些营养素分别多少克，这些都要说

七、运动专项建议
1.低运动量的运动：列举一些具体的运动可以做，这些运动分别怎么做，例如每周时长或者频率
2.中运动量的运动：列举一些具体的运动可以做，这些运动分别怎么做，例如每周时长或者频率
3.高运动量的运动：列举一些具体的运动可以做，这些运动分别怎么做，例如每周时长或者频率

""".strip()
    else:
        prompt = f"""
你是资深的体态分析专家，擅长结合用户的体态体型数据、中医体质以及舌苔等信息，针对用户给出体态分析以及改善的建议。
用户很可能存在肥胖。体型过大等烦恼。
你存在专家模式和普通模式，现在以普通模式，结合用户基本信息、体态体型数据、舌苔以及中医体质信息，给出分析和建议。

{structured_output_protocol(
    section_key_examples=["overall", "posture_body", "tongue_tcm", "linkage", "guidance"],
    item_key_examples=["diet", "activity", "daily_life", "schedule", "posture_maintain"],
)}

1.材料说明：体态/舌苔检测与问卷均为参考信息，不等同医学检查；若某段正文写「暂无」或下列 JSON 中某字段缺失，表示该次未提供，撰写时按需跳过或简要说明信息不足。

【用户档案摘要】
{profile_summary}

【中医十问】（用户自填，可能未提供；非诊断依据）
{tcm_block}

【体态与体型分析正文】（系统记录）
{posture_report or "（暂无体态分析正文）"}

【体态/体型结构化数据】（JSON，仅供理解趋势）
{metrics_text}

【舌苔分析正文】（系统记录，图像现象描述）
{tongue_report or "（暂无舌苔分析正文）"}

【舌苔附加结构化信息】（JSON，若有）
{tongue_extra_text or "（无）"}
{_extra_block}
2.输出规范

一、整体状态参考分析
根据用户基本信息、体态检测结果、舌象图像及中医十问内容，用一个自然段进行概括（无需额外分段；禁止空白行）。
本报告仅供健康管理参考，不构成任何医疗诊断。
若存在【用户多次提交的补充需求】，必须在本段中用 1-2 句话“回显复述”用户的主要补充情况/核心诉求，并明确说明“已纳入本次分析与建议”。
在后续各段落的分析与建议中，必须持续围绕这些补充情况与诉求进行取舍与侧重。

二、体态与体型分析
结合体态体型数据、体态体型分析报告，总结整体姿态端正度、对称性与力线顺畅情况，说明体型比例与脂肪分布特点，对异常体态指标简要说明状态、受力、负荷及潜在影响。

三、舌象与中医体质分析
结合中医十问数据、舌苔分析报告，总结整体体质偏向，包括寒热、湿邪、津液气血与脏腑功能倾向，对异常舌象与十问条目简要说明表现与对应倾向。

四、体态与体质常规分析
结合体态体型分析以及舌苔中医分析，常规分析用户的体态体型体质；
判断是否存在肥胖，肥胖类型（例如腰部脂肪堆积/腹部脂肪堆积/腿部脂肪堆积等等）；
当前体态体型和肥胖可能导致什么潜在的慢性病，例如高血压、糖尿病、血脂等；
建议控制到大约多少体重，肌肉、脂肪分别建议控制多少；
说明体质如何影响肌肉、气血、循环并加重或缓解体态问题，同时说明体态异常如何影响受力、呼吸、经络并强化或改变体质倾向，综合体态与体质的内在关联与综合表现。

五、综合健康指导
1.饮食与饮水建议：结合体态、脂肪分布、舌象与十问，给出进食节奏、口味、宜增宜控的具体方向。
2.适合的运动与活动：结合体型、体态与体质，给出适宜运动、强度、频率及需规避的运动项目。
3.日常生活注意事项：包括姿势、久坐、睡眠、情绪、环境等方面的具体注意内容。
4.作息与节律建议：结合体质与疲劳状态，给出作息、睡眠、午休与劳逸结合建议。
5.姿态日常维护：针对主要体态问题，给出站立、坐姿、行走、用屏等日常姿态提醒。

六、营养专项建议
1.饮食热量摄入的控制，根据用户性别，提供热量摄入建议，例如每日摄入多少热量，不高于多少、不低于多少，或者比原来减少多少热量摄入；
2.摄入营养元素的注意事项，例如体型用户不要因为减少食物摄入而导致维生素、矿物质摄入不足，应摄入哪种维生素的营养补充剂；
3.三餐的饭量或者能量占比；
4.提供一个一周食谱，每天早中晚建议吃些什么东西、每顿饭会有多少热量摄入；每日建议摄入蛋白质、脂肪、碳水化合物等营养素分别多少克；

七、运动专项建议
1.低运动量的运动：列举一些具体的运动可以做，这些运动分别怎么做，例如每周时长或者频率
2.中运动量的运动：列举一些具体的运动可以做，这些运动分别怎么做，例如每周时长或者频率
3.高运动量的运动：列举一些具体的运动可以做，这些运动分别怎么做，例如每周时长或者频率

""".strip()

    api_key = os.getenv("AGENT_API_KEY")
    if not api_key or not str(api_key).strip():
        raise RuntimeError(
            "未配置 AGENT_API_KEY：请在环境变量中设置阿里云百炼 API Key。"
        )

    response = Application.call(
        api_key=api_key.strip(),
        app_id=_get_joint_report_agent_app_id(),
        prompt=prompt,
        temperature=0.35,
    )

    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"联合报告智能体调用失败: request_id={response.request_id}, "
            f"code={response.status_code}, message={response.message}"
        )

    text = getattr(response.output, "text", None) if response.output is not None else None
    if not text:
        raise RuntimeError("联合报告智能体返回为空。")
    return text if isinstance(text, str) else str(text)


def improve_joint_comprehensive_report(
    *,
    profile_summary: str,
    posture_report: str,
    tongue_report: str,
    previous_output: str,
    reviewer_comment: str,
    iteration: int,
    max_iterations: int,
    tcm_ten_questions: Optional[Dict[str, Any]] = None,
    user_requirement: Optional[str] = None,
    analysis_mode: str = "expert",
    model: Optional[str] = None,
) -> str:
    _ = model
    if is_mock_ai_enabled():
        return mock_text("expert_joint_report", user_requirement)
    tcm_block = format_tcm_ten_questions_plain(tcm_ten_questions)
    mode = "expert" if str(analysis_mode or "").strip().lower() == "expert" else "normal"
    prompt = f"""
你在进行“综合报告迭代改写”。这是第 {iteration}/{max_iterations} 轮。
当前分析模式：{mode}。

{structured_output_protocol(
    section_key_examples=["overall", "posture_body", "tongue_tcm", "linkage", "guidance"],
    item_key_examples=["diet", "activity", "daily_life", "schedule", "posture_maintain"],
)}

【原始输入（不可忽略）】
用户档案摘要：
{profile_summary}

中医十问：
{tcm_block}

体态报告：
{posture_report or "（无）"}

舌苔报告：
{tongue_report or "（无）"}

【你上一次输出】
{previous_output or "（空）"}

【统筹评审意见（必须逐条落实）】
{reviewer_comment or "（无）"}

【用户额外需求（常规分析智能体补充要求）】
{(user_requirement or "").strip() or "（无）"}

【写作要求：用户需求必须显式体现】
- 如果上述“用户额外需求”不为空：你必须在报告的「一、整体状态参考分析」中用 1-2 句回显复述核心需求/特殊状况，让用户确认你已理解并纳入考虑。
- 在后续分析与建议中必须持续呼应这些需求（在饮食/运动/作息/日常姿态维护中体现“因人而异”的取舍与侧重）。

请输出改写后的完整常规分析报告正文（只输出正文，不要额外解释）。
""".strip()

    api_key = os.getenv("AGENT_API_KEY")
    if not api_key or not str(api_key).strip():
        raise RuntimeError("未配置 AGENT_API_KEY。")

    response = Application.call(
        api_key=api_key.strip(),
        app_id=_get_joint_report_agent_app_id(),
        prompt=prompt,
        temperature=0.35,
    )

    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"联合报告智能体迭代调用失败: request_id={response.request_id}, "
            f"code={response.status_code}, message={response.message}"
        )
    text = getattr(response.output, "text", None) if response.output is not None else None
    if not text:
        raise RuntimeError("联合报告智能体迭代返回为空。")
    return text if isinstance(text, str) else str(text)
