from __future__ import annotations

import os
from typing import Any, Dict, Optional


def is_mock_ai_enabled() -> bool:
    raw = str(os.getenv("MOCK_AI_ENABLED") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def mock_text(kind: str, extra_user_requirements: Optional[str] = None) -> str:
    if kind == "posture_report":
        return (
            "【测试体态报告】\n"
            "1. 当前体态指标存在轻度不均衡，建议优先进行肩颈与骨盆稳定训练。\n"
            "2. 每周进行3-4次基础拉伸，每次10-15分钟。\n"
            "3. 连续久坐45分钟后起身活动3-5分钟。"
        )
    if kind == "tongue_report":
        return (
            "舌苔图像客观信息（仅作图像表面描述，不代表医疗诊断）\n\n"
            "一、分项观察\n"
            "1）舌体颜色：淡红\n"
            "2）舌苔颜色：薄白\n"
            "3）舌苔厚薄：偏薄\n"
            "4）舌苔分布：较均匀\n"
            "5）湿润度：中等\n\n"
            "二、综合小结\n"
            "整体表现较平稳，建议保持规律作息并减少熬夜。"
        )
    if kind == "joint_report":
        return (
            "【测试常规分析报告】\n"
            "体态与舌苔信息整体显示近期状态可控，主要问题集中在姿势负荷与作息节律。\n"
            "建议以可执行的小目标为主：工作日规律睡眠、每周固定训练计划、饮食清淡并减少高糖高油。"
        )
    if kind == "expert_posture_report":
        return (
            "【专家深度分析模式（测试）-体态报告】\n"
            "本段为测试输出，用于验证专家深度分析流程与前端展示，不代表真实智能体结论。"
        )
    if kind == "expert_tongue_report":
        return (
            "【专家深度分析模式（测试）-舌苔报告】\n"
            "本段为测试输出，用于验证专家深度分析流程与前端展示，不代表真实智能体结论。"
        )
    if kind == "expert_joint_report":
        base = (
            "【专家深度分析模式（测试）-综合报告】\n"
            "你当前看到的是专家深度分析链路下的模拟结果（Mock），用于联调流程、状态机与UI展示。\n"
            "该内容非真实智能体输出，请勿用于医学或健康判断。"
        )
        extra = (extra_user_requirements or "").strip()
        if extra:
            return f"{base}\n\n---\n【本条关联的用户需求】\n{extra}\n"
        return base
    if kind == "history_report":
        return (
            "【测试历史分析报告】\n"
            "近几次综合报告显示整体趋势稳定，局部指标有波动但未见明显恶化。\n"
            "建议继续保持当前干预节奏，并在2-4周后复查关键指标。"
        )
    if kind == "review_comment":
        return "测试模式：评审通过（用于前端联调）"
    return "测试模式：已返回模拟内容。"


def mock_tongue_structured() -> Dict[str, Any]:
    return {
        "tongueBodyColor": "淡红",
        "coatingColor": "薄白",
        "coatingThickness": "偏薄",
        "coatingDistribution": "较均匀",
        "moisture": "中等",
        "cracks": "无明显裂纹",
        "teethMarks": "无明显齿痕",
        "imageQuality": "可用",
        "summary": mock_text("expert_tongue_report"),
    }
