from __future__ import annotations

import json
import os
#import base64
from typing import Optional, Any, Dict

#from pathlib import Path
#from datetime import datetime

#from fastapi import FastAPI, Form, File, UploadFile, Header
#from fastapi.middleware.cors import CORSMiddleware

#from dotenv import load_dotenv
#from openai import OpenAI    #安装依赖 pip install openai python-dotenv

from routes.utils.api_helpers import (
    get_deepseek_client,
    get_qianwen_client,
    image_file_to_data_url,
    safe_json_loads,
)
from routes.utils.ai_mock import is_mock_ai_enabled, mock_text, mock_tongue_structured


POSTURE_PROMPT_GUIDE = """
我利用用户上传的正面和侧面图片，计算了一些体态指标以及体型指标。计算说明如下：

【关键说明】
本分析基于人体关键点检测结果和轮廓分割结果（mask）。
·所有关键点表示对应身体部位的结构中心位置，而非轮廓边缘。例如：
- 肩部关键点表示肩关节区域的中心位置，而非肩膀最外侧边缘
- 髋部关键点表示骨盆两侧髋关节的大致中心位置
- 膝、踝关键点表示关节中心位置

·关键线计算方法：
- 正面图中，关键线通过左右关键点拟合直线
- 侧面图中，关键线通过单侧关键点的水平或垂直坐标确定

·所有距离均基于图像像素坐标计算。例如：
- 身高由人体分割 mask 中最高点到最低点的垂直距离表示，即最高点与最低点的 y 坐标差
- 头部长度由头顶（head）到颈部（neck）的垂直距离表示
- 头部宽度由左右耳关键点（left_ear 与 right_ear）之间的水平距离表示

·面积相关指标基于人体分割 mask 像素统计。

【体态指标及计算说明】
1. 头前伸指数（head_forward_ratio）：
- 使用侧面视角的耳朵、肩膀和髋部关键点
- 通过比较耳朵与肩膀在前后方向的位置关系，判断头部是否前移
- 再结合肩膀到髋部的躯干长度进行标准化
- 数值越大，说明头部越向前伸出

2. 高低肩指数（shoulder_tilt）：
- 使用正面视角的左右肩关键点
- 比较左右肩在垂直方向的高度差
- 再结合两肩之间的水平距离进行标准化
- 正值表示左肩偏高，负值表示右肩偏高

3. 骨盆倾斜指数（pelvic_tilt）：
- 使用正面视角的左右髋关键点
- 比较左右髋部在垂直方向的高度差
- 再结合两髋之间的水平距离进行标准化
- 正值表示左髋偏高，负值表示右髋偏高

4. 膝关节对齐指数（knee_alignment）：
- 使用侧面单腿的髋、膝、踝关键点
- 以髋到踝的连线作为下肢力线参考
- 测量膝盖相对于该力线的前后偏移程度
- 再结合腿部长度进行标准化
- 数值越大表示膝关节偏离正常力线越明显

【体型指标及计算说明】
1. 头身比（head_body_ratio）：
- 使用正面视角的头顶和颈部关键点
- 通过身高与头部长度进行比值计算
- 数值越大，说明头部在整体身高中占比越小

2. 腿身比（leg_body_ratio）：
- 使用正面视角的髋、膝、踝关键点
- 通过腿长与整体身高进行比值计算
- 数值越大，说明腿部比例越修长

3. 大腿小腿比（thigh_calf_ratio）：
- 使用正面视角的髋、膝、踝关键点
- 通过大腿长度与小腿长度进行比值计算
- 数值越接近 1，说明大腿和小腿比例较匀称

4. 躯干身高比（torso_height_ratio）：
- 使用正面视角的肩、髋关键点
- 通过躯干长度与整体身高进行比值计算
- 数值越大，说明躯干占身高比例越高

5. 上下身面积比（upper_lower_body_ratio）：
- 以左右髋连线为界，计算髋线以上面积与髋线以下面积的比值
- 数值大于 1 表示上身体量较大，数值小于 1 表示下身体量较大

6. 头肩比（head_shoulder_ratio）：
- 通过头宽与肩宽进行比值计算
- 数值越大，说明头部相对肩部宽度越大

7. 腹部前突指数（abdomen_protrusion）：
- 基于侧面腹部区域 mask 计算腹部最前缘相对身体中心的前移程度
- 数值越大表示腹部前突越明显
""".strip()



def analyze_tongue_image(
    image_path: str,
    mime: str = "image/jpeg",
    *,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    调用通义千问视觉模型分析舌苔图片。
    model：可选；否则用 QIANWEN_VISION_MODEL、Qwen_MODEL，最后默认 qwen-vl-max。
    """
    if is_mock_ai_enabled():
        return mock_tongue_structured()
    client = get_qianwen_client()
    resolved_model = (
        model
        or os.getenv("QIANWEN_VISION_MODEL")
        or os.getenv("Qwen_MODEL")
        or "qwen-vl-max"
    )
    data_url = image_file_to_data_url(image_path, mime=mime)

    prompt = """
请你作为一个图像分析助手，只根据舌头图片中肉眼可见的信息，客观描述舌苔和舌体特征。
不要诊断疾病，不要给治疗建议，不要夸大结论。
如果看不清，请明确写“不确定”。

请严格输出 JSON，不要输出任何额外文字，格式如下：
{
  "tongueBodyColor": "舌体颜色，如淡红、偏红、偏淡、不确定",
  "coatingColor": "舌苔颜色，如白、淡黄、黄、灰白、不确定",
  "coatingThickness": "舌苔厚薄，如薄、较厚、局部较厚、不确定",
  "coatingDistribution": "舌苔分布，如均匀、中后部较多、舌根较厚、不均匀、不确定",
  "moisture": "湿润度，如偏湿润、偏干、不确定",
  "cracks": "裂纹情况，如无明显裂纹、可见少量裂纹、不确定",
  "teethMarks": "齿痕情况，如无明显齿痕、舌边轻微齿痕、不确定",
  "imageQuality": "图像质量，如清晰可判断、光线偏暗、颜色可能失真、角度影响判断",
  "summary": "用一句话总结舌苔表面特征，只描述现象，不作诊断"
}
""".strip()

    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {
                "role": "system",
                "content": "你是一个严谨的图像分析助手，只输出 JSON。"
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url
                        }
                    }
                ]
            }
        ],
        temperature=0.2
    )

    content = response.choices[0].message.content
    return safe_json_loads(content)


def generate_final_report(
    user_info: Dict[str, Any],
    posture_info: Optional[Dict[str, Any]] = None,
    tongue_info: Optional[Dict[str, Any]] = None,
    *,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    if is_mock_ai_enabled():
        return {"report": mock_text("joint_report")}
    posture_text = "未提供体态数据。"
    if posture_info:
        posture_text = json.dumps(posture_info, ensure_ascii=False, indent=2)

    tongue_text = "未提供舌苔图像信息。"
    if tongue_info:
        if tongue_info.get("error"):
            tongue_text = f"舌苔图像分析失败：{tongue_info.get('error')}"
        else:
            tongue_text = f"""
舌苔图像客观信息（仅作图像表面描述，不代表医疗诊断）：
- 舌体颜色: {tongue_info.get("tongueBodyColor")}
- 舌苔颜色: {tongue_info.get("coatingColor")}
- 舌苔厚薄: {tongue_info.get("coatingThickness")}
- 舌苔分布: {tongue_info.get("coatingDistribution")}
- 湿润度: {tongue_info.get("moisture")}
- 裂纹: {tongue_info.get("cracks")}
- 齿痕: {tongue_info.get("teethMarks")}
- 图像质量: {tongue_info.get("imageQuality")}
- 总结: {tongue_info.get("summary")}
""".strip()

    prompt = f"""
你是一名专业的健康状态分析助手，请根据以下信息生成一份中文综合报告。

信息来源包括：
1. 用户基本信息
2. 体态检测结果
3. 舌苔图像表面现象

重要要求：
1. 舌苔部分来自图像识别，只能作为参考，不是医学诊断。
2. 体态部分来自姿态与体型检测结果，只能用于健康管理和生活习惯建议，不做疾病诊断。
3. 所有判断必须使用谨慎措辞，例如“可能”“倾向于”“从现象看”“仅供参考”。
4. 不要做疾病诊断，不要夸大结论，不要制造焦虑。
5. 不要提供药物、方剂、治疗方案。
6. 输出应清晰、有条理、适合普通用户阅读。
7. 避免重复表达,只输出 JSON,不要输出任何额外文字。
8. 如果某部分信息不足或不可靠，请明确说明“该部分仅能做有限参考”。

用户基本信息：
- userId: {user_info.get("userId")}
- 姓名: {user_info.get("name")}
- 年龄: {user_info.get("age")}
- 性别: {user_info.get("gender")}
- 身高: {user_info.get("height")}
- 体重: {user_info.get("weight")}

体态数据计算说明：
{POSTURE_PROMPT_GUIDE}

体态检测结果（如果某些字段为空，表示该指标未成功计算，可跳过）：
{posture_text}

舌苔图像信息：
{tongue_text}

输出要求：
请在最终输出中使用换行符（\n）分段分行；不要把所有内容拼成一大段。
请严格不要使用项目符号符号 '-'，也不要使用 Markdown（如 ###、##、**）。

请按下面固定结构输出（每一行单独成行，空行可用于增强可读性）：
一、整体状态参考分析
1) 用 1-2 句话综合说明基本信息、体态数据、舌苔图像现象
2) 必须明确说明：本报告仅供健康管理参考，不构成医疗诊断

二、体态分析与建议
1) 结合体态数据概括姿态/体型的主要特点（空值跳过）
2) 体态建议1：给出简洁、具体、可执行的做法（围绕久坐、站姿、拉伸、活动、运动平衡、作息）
3) 体态建议2：同上
4) 体态建议3：同上
5) 体态建议4：同上

三、舌苔参考分析与建议
1) 仅根据舌苔表面现象给出倾向性描述（可提体虚/体热/体寒/湿气等倾向，但用谨慎措辞）
2) 必须明确说明：这只是图像现象参考，不是诊断
3) 舌苔建议1：围绕饮食、饮水、作息、观察变化给出可执行建议
4) 舌苔建议2：同上
5) 舌苔建议3：同上
6) 舌苔建议4：同上

输出时要求：
1. 不要使用 Markdown 语法
2. 不要输出 ###、##、**、- 等符号
3. 不要出现药物、方剂、治疗方案
4. 使用中文，表达清晰自然，不要出现绝对化医疗表述
""".strip()

    client = get_deepseek_client()
    resolved_model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {
                "role": "system",
                "content": "你是专业的健康分析助手，输出要简洁、有条理、避免重复，避免给出确定性医疗诊断。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        stream=False,
        temperature=0.4
    )

    return response.choices[0].message.content


def build_final_report(
    user_info: Dict[str, Any],
    posture_info: Optional[Dict[str, Any]] = None,
    tongue_image_path: Optional[str] = None,
    tongue_image_mime: str = "image/jpeg",
    *,
    tongue_model: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    完整流程：
    1. 如果有舌苔图片，先分析舌苔
    2. 再生成最终综合报告
    """
    tongue_info: Optional[Dict[str, Any]] = None

    if tongue_image_path:
        try:
            tongue_info = analyze_tongue_image(
                image_path=tongue_image_path,
                mime=tongue_image_mime,
                model=tongue_model,
            )
        except Exception as e:
            tongue_info = {"error": f"舌苔图像分析失败: {str(e)}"}

    report = generate_final_report(
        user_info=user_info,
        posture_info=posture_info,
        tongue_info=tongue_info,
        model=model,
    )

    return {
        "report": report,
        "tongueInfo": tongue_info,
        "postureInfo": posture_info,
    }