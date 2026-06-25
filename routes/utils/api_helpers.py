from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import UploadFile
from openai import OpenAI

load_dotenv()

_deepseek_client: Optional[OpenAI] = None
_vision_client: Optional[OpenAI] = None
_qianwen_client: Optional[OpenAI] = None


# =========================
# 模型客户端
# =========================
def get_deepseek_client() -> OpenAI:
    """
    Lazy init：避免在路由文件导入时就因为缺少环境变量导致启动失败。
    """
    global _deepseek_client
    if _deepseek_client is not None:
        return _deepseek_client

    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    _deepseek_client = OpenAI(api_key=api_key, base_url=base_url)
    return _deepseek_client

def get_vision_client() -> OpenAI:
    """
    豆包视觉模型客户端，懒加载初始化
    """
    global _vision_client
    if _vision_client is not None:
        return _vision_client

    api_key = os.getenv("VISION_API_KEY")
    base_url = os.getenv("VISION_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    _vision_client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )
    return _vision_client


def get_qianwen_client() -> OpenAI:
    """
    通义千问（阿里云 DashScope OpenAI 兼容接口），懒加载。
    密钥：优先 QIANWEN_API_KEY，否则读取 .env 中常见的 Qwen_API_KEY。
    地址：优先 QIANWEN_BASE_URL，否则 Qwen_BASE_URL，再否则默认 compatible-mode/v1。
    """
    global _qianwen_client
    if _qianwen_client is not None:
        return _qianwen_client

    api_key = os.getenv("QIANWEN_API_KEY") or os.getenv("Qwen_API_KEY")
    base_url = (
        os.getenv("QIANWEN_BASE_URL")
        or os.getenv("Qwen_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    if not api_key:
        raise RuntimeError(
            "通义千问未配置：请在 .env 中设置 QIANWEN_API_KEY 或 Qwen_API_KEY。"
        )
    _qianwen_client = OpenAI(api_key=api_key, base_url=base_url)
    return _qianwen_client


# =========================
# 工具函数
# =========================

def to_number(x: Any):
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def to_json_safe(obj: Any) -> Any:
    """把 numpy 标量/数组递归转成纯 Python，保证 FastAPI 能序列化成 JSON。"""
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None  # type: ignore

    if obj is None:
        return None

    if np is not None:
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()

    if isinstance(obj, dict):
        # JSON key 只能是字符串或原生类型；这里统一转成 str 更稳
        return {str(k): to_json_safe(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]

    return obj


async def save_uploaded_image(
    image: UploadFile,
    *,
    preferred_stem: str | None = None,
    overwrite: bool = False,
) -> tuple[str, Dict[str, Any]]:
    content = await image.read()
    save_dir = Path(
        os.getenv(
            "IMAGE_SAVE_DIR",
            str(Path(__file__).resolve().parent.parent / "uploads"),
        )
    )
    save_dir.mkdir(parents=True, exist_ok=True)

    # 取后缀：优先使用文件名后缀，其次根据 content_type 猜测
    suffix = Path(image.filename or "").suffix.lower()
    if not suffix:
        ct = (image.content_type or "").lower()
        if "jpeg" in ct:
            suffix = ".jpg"
        elif "png" in ct:
            suffix = ".png"
        elif "webp" in ct:
            suffix = ".webp"
        else:
            suffix = ".bin"

    if preferred_stem:
        safe = "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in str(preferred_stem))
        image_file_name = f"{safe}{suffix}"
        save_path = save_dir / image_file_name
        if (not overwrite) and save_path.exists():
            # 不允许覆盖时，退回随机命名，避免撞名
            now = datetime.now()
            image_file_name = (
                f"{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond:06d}_{secrets.token_hex(4)}{suffix}"
            )
    else:
        now = datetime.now()
        # 时间戳 + 微秒 + 随机后缀：同一请求内连续保存正面/侧面时，仅用「秒+毫秒桶」会撞名导致后写覆盖先写，
        # 表现为「返回的展示图变成侧面」等错乱。
        image_file_name = (
            f"{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond:06d}_{secrets.token_hex(4)}{suffix}"
        )
    save_path = save_dir / image_file_name
    save_path.write_bytes(content)
    image_path = str(save_path)

    image_info = {
        "filename": image.filename,
        "contentType": image.content_type,
        "sizeBytes": len(content),
        "savedPath": image_path,
    }
    return image_path, image_info


def safe_json_loads(text: str) -> Dict[str, Any]:
    """
    尽量把模型输出解析成 JSON
    """
    try:
        return json.loads(text)
    except Exception:
        pass

    text = text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(text)
        except Exception:
            pass

    return {
        "rawText": text,
        "parseError": True,
    }

def image_file_to_data_url(file_path: str, mime: str = "image/jpeg") -> str:
    """
    本地图片 -> data URL
    """
    with open(file_path, "rb") as f:
        content = f.read()
    b64 = base64.b64encode(content).decode("utf-8")
    return f"data:{mime};base64,{b64}"





def ask_deepseek(
    user_info: Dict[str, Any],
    titai_fb: Dict[str, float],
    tixing_fb: Dict[str, float],
    titai_lr: Dict[str, float],
    tixing_lr: Dict[str, float],
    *,
    model: Optional[str] = None,
) -> str:
    prompt = f"""
你是一名专业的体态评估助手，请根据以下信息生成中文分析建议。

用户信息：
- userId: {user_info.get("userId")}
- 姓名: {user_info.get("name")}
- 年龄: {user_info.get("age")}
- 性别: {user_info.get("gender")}
- 身高: {user_info.get("height")}
- 体重: {user_info.get("weight")}
- 过敏情况: {user_info.get("allergyHistory") or "无过敏史"}

然后我利用用户上传的正面和侧面图片，计算了一些体态指标以及体型指标。计算说明如下：
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
- 通过身高（mask最高点到最低点）与头部长度（头顶到颈部垂直距离）进行比值计算 
- 数值越大，说明头部在整体身高中占比越小 
- 反映人体头部与全身的比例关系，是评价体态美感、头身协调度的经典指标 
2. 腿身比（leg_body_ratio）： 
- 使用正面视角的髋、膝、踝关键点 
- 通过腿长（髋线平均纵坐标与踝线平均纵坐标之差）与整体身高进行比值计算 
- 数值越大，说明腿部比例越修长 
- 反映下肢长度在整体身高中的占比 
3. 大腿小腿比（thigh_calf_ratio）： 
- 使用正面视角的髋、膝、踝关键点 
- 通过大腿长度（髋线平均纵坐标与膝线平均纵坐标之差）与小腿长度（膝线平均纵坐标与踝线平均纵坐标之差）进行比值计算 
- 数值越接近 1，说明大腿和小腿比例较匀称 
- 反映下肢骨骼比例的协调性 
4. 躯干身高比（torso_height_ratio）： 
- 使用正面视角的肩、髋关键点 
- 通过躯干长度（肩线平均纵坐标与髋线平均纵坐标之差）与整体身高进行比值计算 
- 数值越大，说明躯干占身高比例越高 
- 反映躯干长短与上下身分割位置 
5. 上下身面积比（upper_lower_body_ratio）： 
- 使用正面视角的左右肩、左右髋关键点 
- 以左右髋连线为界，计算髋线以上面积与髋线以下面积的比值 
- 数值大于 1 表示上身体量较大，数值小于 1 表示下身体量较大 
- 反映体型重心及上/下身体量分布 
6. 头肩比（head_shoulder_ratio）： 
- 使用正面视角的左右耳关键点与左右肩关键点
- 通过头宽（左右耳横向距离）与肩宽进行比值计算。其中，肩宽基于mask轮廓宽度计算，而非肩点距离。采用人体mask计算，在左右肩连线下方，选取最靠近肩部的一行轮廓宽度作为肩宽。
- 数值越大，说明头部相对肩部宽度越大 
- 衡量头部宽度与肩部宽度的相对比例，反映视觉上的头肩平衡感

7. 腹部前突指数（Abdomen Protrusion）：
- 以肘部与髋部的垂直位置范围，截取腹部所在区域
- 在该区域内基于人体mask获取腹部区域像素
- 取最靠前的点作为腹部最前缘（左侧面图为最小x位置，右侧反之）
- 使用头部、髋部和踝部的水平位置平均值，作为身体整体中心参考位置
- 计算腹部最前缘相对于该中心的前移距离
- 使用肩部到髋部区域的身体前后厚度（mask宽度）进行归一化
- 数值越大表示腹部前突越明显

指标计算结果如下，我将以字典形式给你，其中如果有些内容是空的，说明这些指标没有计算，可以跳过：
{titai_fb}
{tixing_fb}
{titai_lr}
{tixing_lr}

请严格按照以下结构输出：
一、对于每个指标，进行分析
二、提供运动、饮食与日常生活习惯的建议

要求：
- 使用中文
- 表达清晰自然
- 适合普通用户阅读
- 不要夸大病情
""".strip()

    client = get_deepseek_client()
    resolved_model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    resp = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": "你是专业的体态分析助手,输出要简洁、有条理、避免重复。"},
            {"role": "user", "content": prompt},
        ],
        stream=False,
    )
    return resp.choices[0].message.content

