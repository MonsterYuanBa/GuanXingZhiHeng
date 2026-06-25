from image_process.calculate.tixing_analysis import split_body_by_lines_left,split_body_by_lines_front,split_body_by_lines_right

def _safe_split(fn, mask, point_coords, point_names):
    """关键点缺失时返回None，避免index()报错中断整条链路。"""
    try:
        return fn(mask, point_coords, point_names)
    except ValueError:
        return None

def _judge_side_for_tixing(point_names: list[str]) -> str:
    """
    侧面输入只有一张时，判断用 left_* 还是 right_* 的分割函数。
    split_body_by_lines_left/right 都会依赖大量 left/right 关键点；因此用“关键点集合是否齐全”来判定。
    """
    left_need = {"left_shoulder", "left_elbow", "left_hip", "left_knee", "left_ankle", "head", "neck"}
    right_need = {"right_shoulder", "right_elbow", "right_hip", "right_knee", "right_ankle", "head", "neck"}

    left_ok = left_need.issubset(set(point_names))
    right_ok = right_need.issubset(set(point_names))

    if left_ok and not right_ok:
        return "left"
    if right_ok and not left_ok:
        return "right"

    # 兜底：只要能看到 left/ right 关键点，就优先用对应那边
    if "left_hip" in point_names and "right_hip" not in point_names:
        return "left"
    if "right_hip" in point_names and "left_hip" not in point_names:
        return "right"
    if "left_hip" in point_names:
        return "left"
    if "right_hip" in point_names:
        return "right"
    return "left"

def calcluate_tixing_fb(human_front,human_back, back_path):
    res = {}
    if back_path is None:
        # 仅使用front视角计算

        point_front_coords, point_front_names, mask = human_front
        (shoulder_width, height,
        head_body_ratio, leg_body_ratio,
        thigh_calf_ratio, torso_height_ratio, 
        head_shoulder_ratio,upper_lower_body_ratio)  = split_body_by_lines_front(mask, point_front_coords, point_front_names)

        # ====================== 比例指标（不输出身高/肩宽原始量） ======================
        res["头身比"] = head_body_ratio
        res["腿身比"] = leg_body_ratio
        res["大腿小腿比"] = thigh_calf_ratio
        res["躯干身高比"] = torso_height_ratio
        res["头肩比"] = head_shoulder_ratio
        res["上下身面积比"] = upper_lower_body_ratio

    else:
        # front+back
        print("联合计算算法暂时没写")
    # if res:
        # 打印所有指标

        # print("【体型比例指标计算结果】")
        # print("="*60)
        # print(f"身高 (像素)        : {height:.1f}")
        # print(f"肩宽                : {shoulder_width:.1f}")
        # print(f"头身比              : {head_body_ratio:.2f}")
        # print(f"腿身比              : {leg_body_ratio:.2f}")
        # print(f"大腿小腿比          : {thigh_calf_ratio:.2f}")
        # print(f"躯干身高比          : {torso_height_ratio:.2f}")
        # print(f"头肩比              : {head_shoulder_ratio:.2f}")
        # print("="*60)
    return res

def calcluate_tixing_lr(human_left, left_path, human_right, right_path):
    res = {}
    height_left = None
    abdomen_left = None
    height_right = None
    abdomen_right = None

    # 侧面只有一张图：先判定这张图对应 left_* 还是 right_*，再调用对应分割函数
    if left_path is not None and right_path is None:
        point_coords, point_names, mask = human_left
        side = _judge_side_for_tixing(point_names)
        if side == "left":
            out = _safe_split(split_body_by_lines_left, mask, point_coords, point_names)
            if out is None:
                out = _safe_split(split_body_by_lines_right, mask, point_coords, point_names)
        else:
            out = _safe_split(split_body_by_lines_right, mask, point_coords, point_names)
            if out is None:
                out = _safe_split(split_body_by_lines_left, mask, point_coords, point_names)
        if out is not None:
            _h, _abd = out
            res["腹部前突指数"] = _abd
        return res

    # ====================== 左侧计算 ======================
    if left_path is not None:
        point_coords, point_names, mask = human_left
        out = _safe_split(split_body_by_lines_left, mask, point_coords, point_names)
        if out is None:
            out = _safe_split(split_body_by_lines_right, mask, point_coords, point_names)
        if out is not None:
            height_left, abdomen_left = out

    # ====================== 右侧计算 ======================
    if right_path is not None:
        point_coords, point_names, mask = human_right
        out = _safe_split(split_body_by_lines_right, mask, point_coords, point_names)
        if out is None:
            out = _safe_split(split_body_by_lines_left, mask, point_coords, point_names)
        if out is not None:
            height_right, abdomen_right = out

    # ====================== 结果合并（左右都有则取平均） ======================
    if left_path is not None and right_path is not None:
        # 左右都存在 → 取平均
        if abdomen_left is not None and abdomen_right is not None:
            res["腹部前突指数"] = (abdomen_left + abdomen_right) / 2
            print("【左右视图均存在，取平均值】")
        else:
            # 只要其中一个可用，就直接用该侧
            res["腹部前突指数"] = abdomen_left if abdomen_left is not None else abdomen_right
            print("【左右视图存在但关键点缺失，使用可用的一侧】")

    elif left_path is not None:
        # 仅左侧
        if abdomen_left is not None:
            res["腹部前突指数"] = abdomen_left

    elif right_path is not None:
        # 仅右侧
        if abdomen_right is not None:
            res["腹部前突指数"] = abdomen_right

    # # ====================== 统一打印 ======================
    # if res:
    #     print("\n【体型比例指标计算结果】")
    #     print("=" * 60)
    #     print(f"腹部前突指数       : {res['腹部前突指数']:.2f}")
    #     print("=" * 60)

    return res