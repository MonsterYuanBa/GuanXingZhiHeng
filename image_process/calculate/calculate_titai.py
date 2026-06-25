import numpy as np
from image_process.calculate.posture_analysis import (calculate_shoulder_tilt, calculate_pelvic_tilt,
                                                      calculate_head_forward_left, calculate_knee_alignment_left, calculate_head_forward_right, calculate_knee_alignment_right)

def _safe_call(fn, *args):
    """关键点缺失时返回None，避免index()抛ValueError直接中断整条链路。"""
    try:
        return fn(*args)
    except ValueError:
        return None

def _judge_side_by_keypoint_names(point_names: list[str]) -> str:
    """
    判断侧面图对应人体的哪一侧（用关键点是否存在来判断）。
    你的姿态算法使用RTMPose的 left/right 命名；当人物朝向反了时，
    可用的关键点集合会从 left_* 变成 right_*。
    """
    # 头前伸指数所需关键点
    left_head_need = {"left_ear", "left_shoulder", "left_hip"}
    right_head_need = {"right_ear", "right_shoulder", "right_hip"}
    # 膝关节对齐所需关键点
    left_knee_need = {"left_hip", "left_knee", "left_ankle"}
    right_knee_need = {"right_hip", "right_knee", "right_ankle"}

    left_head_ok = left_head_need.issubset(set(point_names))
    right_head_ok = right_head_need.issubset(set(point_names))
    left_knee_ok = left_knee_need.issubset(set(point_names))
    right_knee_ok = right_knee_need.issubset(set(point_names))

    left_ok = left_head_ok and left_knee_ok
    right_ok = right_head_ok and right_knee_ok

    if left_ok and not right_ok:
        return "left"
    if right_ok and not left_ok:
        return "right"

    # 两边都齐/都不齐时：优先使用存在 left_ear 的那套（更符合你原本的默认逻辑）
    if "left_ear" in point_names and "right_ear" not in point_names:
        return "left"
    if "right_ear" in point_names and "left_ear" not in point_names:
        return "right"
    if "left_ear" in point_names:
        return "left"
    if "right_ear" in point_names:
        return "right"
    # 最终兜底
    return "left"


def calculate_titai_fb(human_front,human_back, back_path):
    res = {}
    if back_path is not None:
        print("front+back联合计算算法暂时没写")

    else:
        # 仅使用front视角计算
        point_front_coords, point_front_names, mask = human_front
        kpts = np.array(point_front_coords)
        res["高低肩指数"] = calculate_shoulder_tilt(kpts,point_front_names)
        res["骨盆倾斜指数"] = calculate_pelvic_tilt(kpts,point_front_names)
        # print("\n========== 体态评估结果 ==========")
        # print("高低肩:", res["shoulder_tilt"])
        # print("骨盆倾斜:", res["pelvic_tilt"])
    return res


def calculate_titai_lr(human_left, left_path, human_right, right_path):
    res = {}
    head_left, knee_left = None, None
    head_right, knee_right = None, None

    # 侧面输入只有一张图时：先“判断这张图用left_*还是right_*关键点算”，再走对应算法。
    # 如果未来你一次传两张侧面（left/right各一张），则按左右分别计算并取平均。
    if left_path is not None and right_path is None:
        coords, names, _ = human_left
        kpts = np.array(coords)
        side = _judge_side_by_keypoint_names(names)
        if side == "left":
            head_left = _safe_call(calculate_head_forward_left, kpts, names)
            knee_left = _safe_call(calculate_knee_alignment_left, kpts, names)
            # 所选侧算不出来则回退到另一侧
            if head_left is None or knee_left is None:
                head_right = _safe_call(calculate_head_forward_right, kpts, names)
                knee_right = _safe_call(calculate_knee_alignment_right, kpts, names)
        else:
            head_right = _safe_call(calculate_head_forward_right, kpts, names)
            knee_right = _safe_call(calculate_knee_alignment_right, kpts, names)
            # 所选侧算不出来则回退到另一侧
            if head_right is None or knee_right is None:
                head_left = _safe_call(calculate_head_forward_left, kpts, names)
                knee_left = _safe_call(calculate_knee_alignment_left, kpts, names)

        # 统一写入 res（只有一个侧面时，返回可用的一侧指标）
        if head_left is not None and knee_left is not None:
            res["头前伸指数"] = head_left
            res["膝关节对齐指数"] = knee_left
        elif head_right is not None and knee_right is not None:
            res["头前伸指数"] = head_right
            res["膝关节对齐指数"] = knee_right
        # 两侧都算不出来则 res 保持空，后续智能体会按字段缺失跳过
        return res

    # 计算左视图（fallback到右侧关键点，保证不因缺点崩溃）
    if left_path is not None:
        coords, names, _ = human_left
        kpts = np.array(coords)
        head_left = _safe_call(calculate_head_forward_left, kpts, names)
        knee_left = _safe_call(calculate_knee_alignment_left, kpts, names)
        if head_left is None or knee_left is None:
            head_left = head_left if head_left is not None else _safe_call(calculate_head_forward_right, kpts, names)
            knee_left = knee_left if knee_left is not None else _safe_call(calculate_knee_alignment_right, kpts, names)

    # 计算右视图（fallback到左侧关键点，保证不因缺点崩溃）
    if right_path is not None:
        coords, names, _ = human_right
        kpts = np.array(coords)
        head_right = _safe_call(calculate_head_forward_right, kpts, names)
        knee_right = _safe_call(calculate_knee_alignment_right, kpts, names)
        if head_right is None or knee_right is None:
            head_right = head_right if head_right is not None else _safe_call(calculate_head_forward_left, kpts, names)
            knee_right = knee_right if knee_right is not None else _safe_call(calculate_knee_alignment_left, kpts, names)

    # ====================== 核心：左右都有 → 取平均 ======================
    if left_path is not None and right_path is not None:
        res["头前伸指数"] = (head_left + head_right) / 2
        res["膝关节对齐指数"] = (knee_left + knee_right) / 2
        print("左右视图均存在，取平均值")

    # 只有左侧
    elif left_path is not None:
        res["头前伸指数"] = head_left
        res["膝关节对齐指数"] = knee_left

    # 只有右侧
    elif right_path is not None:
        res["头前伸指数"] = head_right
        res["膝关节对齐指数"] = knee_right

    # 输出
    if res:
        print("\n========== 体态评估结果 ==========")
        print("头前伸:", res["头前伸指数"])
        print("膝对齐:", res["膝关节对齐指数"])

    return res