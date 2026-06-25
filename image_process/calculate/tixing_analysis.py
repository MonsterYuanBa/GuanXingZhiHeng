# posture_analysis.py
import numpy as np
import math
from pathlib import Path
import cv2
import matplotlib.pyplot as plt

def get_line(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    if abs(dx) < 1e-6:
        k = 1e9
    else:
        k = (y2 - y1) / dx
    b = y1 - k * x1
    return k, b

def split_body_by_lines_front(mask, point_coords, point_names):
    # 处理mask (3, H, W) → (H, W)
    mask = mask[2].astype(bool)
    h, w = mask.shape

    # 取关键点索引
    l_sh_idx = point_names.index("left_shoulder")
    r_sh_idx = point_names.index("right_shoulder")
    l_hip_idx = point_names.index("left_hip")
    r_hip_idx = point_names.index("right_hip")
    l_knee_idx = point_names.index("left_knee")
    r_knee_idx = point_names.index("right_knee")
    l_ankle_idx = point_names.index("left_ankle")
    r_ankle_idx = point_names.index("right_ankle")
    head_idx = point_names.index("head") 
    neck_idx = point_names.index("neck") 
    lear_idx = point_names.index("left_ear") 
    rear_idx = point_names.index("right_ear") 

    # 原始浮点坐标 (x, y)
    l_sh = point_coords[l_sh_idx]
    r_sh = point_coords[r_sh_idx]
    l_hip = point_coords[l_hip_idx]
    r_hip = point_coords[r_hip_idx]
    l_knee = point_coords[l_knee_idx]
    r_knee = point_coords[r_knee_idx]
    l_ankle = point_coords[l_ankle_idx]
    r_ankle = point_coords[r_ankle_idx]
    head = point_coords[head_idx]
    neck = point_coords[neck_idx]
    lear = point_coords[lear_idx]
    rear = point_coords[rear_idx]

    # 计算斜线：肩线、髋线、膝线、踝线
    k_sh, b_sh = get_line(l_sh, r_sh)
    k_hip, b_hip = get_line(l_hip, r_hip)
    k_knee, b_knee = get_line(l_knee, r_knee)
    k_ankle, b_ankle = get_line(l_ankle, r_ankle)

    # 网格坐标
    yy, xx = np.mgrid[0:h, 0:w]
    line_sh = k_sh * xx + b_sh
    line_hip = k_hip * xx + b_hip
    line_knee = k_knee * xx + b_knee
    line_ankle = k_ankle * xx + b_ankle

    # ====================== 区域分割 ======================
    # 肩部以上肩部以下(肩线为界)
    upper_shoulder_mask = (yy <= line_sh) & mask
    lower_shoulder_mask = (yy > line_sh) & mask
    # torso_mask = (yy > line_sh) & (yy <= line_hip) & mask
    # 上下身(髋线为界)
    upper_body_mask = (yy <= line_hip) & mask
    lower_body_mask = (yy > line_hip) & mask
    upper_area = upper_body_mask.sum()  # 上身面积
    lower_area = lower_body_mask.sum()  # 下身面积

    # ====================== 1. 肩宽 ======================
    y_indices = np.where(lower_shoulder_mask)[0]
    if len(y_indices) > 0:
        top_y = y_indices.min()
        top_row = np.zeros_like(lower_shoulder_mask)
        top_row[top_y, :] = True
        top_row = top_row & mask
        x_points = xx[top_row]
        shoulder_width = x_points.max() - x_points.min() if len(x_points) > 0 else 0
    else:
        shoulder_width = 1e-6

    # ====================== 2. 身高（最高像素 - 最低像素） ======================
    ys_body = yy[mask]
    if len(ys_body) > 0:
        top_body_y = ys_body.min()
        bottom_body_y = ys_body.max()
        height = bottom_body_y - top_body_y
    else:
        height = 1e-6

    # ====================== 3. 头长（头顶 → 脖子） ======================
    head_length = np.abs(head[1] - neck[1])
    head_length = head_length if head_length > 0 else 1e-6

    # ====================== 4. 头宽(左耳 → 右耳) ======================
    head_width = np.abs(rear[0] - lear[0])
    head_width = head_width if head_width > 0 else 1e-6

    # ====================== 5. 腿长、大腿长、小腿长 ======================
    leg_length = np.abs(line_hip.mean() - line_ankle.mean())
    thigh_length = np.abs(line_hip.mean() - line_knee.mean())
    calf_length = np.abs(line_knee.mean() - line_ankle.mean())

    leg_length = leg_length if leg_length > 0 else 1e-6
    thigh_length = thigh_length if thigh_length > 0 else 1e-6
    calf_length = calf_length if calf_length > 0 else 1e-6

    # ====================== 6. 躯干长度 ======================
    torso_length = np.abs(line_sh.mean() - line_hip.mean())
    torso_length = torso_length if torso_length > 0 else 1e-6

    # ====================== 计算比例指标 ======================
    head_body_ratio = height / head_length                # 头身比
    leg_body_ratio = leg_length / height                  # 腿身比
    thigh_calf_ratio = thigh_length / calf_length         # 大腿小腿比
    torso_height_ratio = torso_length / height            # 躯干身高比
    head_shoulder_ratio = head_width / shoulder_width     # 头肩比(宽度)
    upper_lower_body_ratio = upper_area / lower_area      # 上下身面积比

    return (shoulder_width,height,
        head_body_ratio, leg_body_ratio,
        thigh_calf_ratio, torso_height_ratio, 
        head_shoulder_ratio, upper_lower_body_ratio
    )

def split_body_by_lines_left(mask, point_coords, point_names):
    # 处理mask (3, H, W) → (H, W)
    mask = mask[2].astype(bool)
    h, w = mask.shape

    # 取左侧关键点索引
    l_sh_idx = point_names.index("left_shoulder")
    l_elbow_idx = point_names.index("left_elbow")
    l_hip_idx = point_names.index("left_hip")
    l_knee_idx = point_names.index("left_knee")
    l_ankle_idx = point_names.index("left_ankle")
    head_idx = point_names.index("head")
    neck_idx = point_names.index("neck")

    # 坐标 (x, y)
    l_sh = point_coords[l_sh_idx]
    l_elbow = point_coords[l_elbow_idx]
    l_hip = point_coords[l_hip_idx]
    l_knee = point_coords[l_knee_idx]
    l_ankle = point_coords[l_ankle_idx]
    head = point_coords[head_idx]
    neck = point_coords[neck_idx]

    # 水平线直接用 y 坐标
    y_sh = l_sh[1]
    y_elbow = l_elbow[1]
    y_hip = l_hip[1]
    y_knee = l_knee[1]
    y_ankle = l_ankle[1]

    # 网格坐标
    yy, xx = np.mgrid[0:h, 0:w]

    # ====================== 区域分割 ======================
    torso_region_mask = (yy >= y_sh) & (yy <= y_hip) & mask #躯干(肩线与髋线之间)
    abdomen_region_mask = (yy >= y_elbow) & (yy <= y_hip) & mask #腹部(肘线与髋线之间)
    # ====================== 身高（最高像素 - 最低像素） ======================
    ys_body = yy[mask]
    if len(ys_body) > 0:
        top_body_y = ys_body.min()
        bottom_body_y = ys_body.max()
        height = bottom_body_y - top_body_y
    else:
        height = 1e-6
    # ====================== 腹部核心指标 ======================
    # 腹部最前点 (左侧图取 x 最小)
    abdomen_x_vals = xx[abdomen_region_mask]
    if len(abdomen_x_vals) > 0:
        min_x_abdomen = abdomen_x_vals.min()
    else:
        min_x_abdomen = l_hip[0]

    # 中线：头顶 + 髋 + 脚踝 平均x
    body_center_x = (head[0] + l_hip[0] + l_ankle[0]) / 3

    # 躯干厚度：躯干区域最大x - 最小x
    torso_x_vals = xx[torso_region_mask]
    if len(torso_x_vals) > 0:
        body_width = torso_x_vals.max() - torso_x_vals.min()
    else:
        body_width = 1e-6

    # 突出量 + 比例
    protrusion = abs(min_x_abdomen - body_center_x)
    abdomen_ratio = protrusion / body_width if body_width != 0 else 0.0


    return height,abdomen_ratio
    
def split_body_by_lines_right(mask, point_coords, point_names):
    # 处理mask (3, H, W) → (H, W)
    mask = mask[2].astype(bool)
    h, w = mask.shape

    # 取右侧关键点索引
    r_sh_idx = point_names.index("right_shoulder")
    r_elbow_idx = point_names.index("right_elbow")
    r_hip_idx = point_names.index("right_hip")
    r_knee_idx = point_names.index("right_knee")
    r_ankle_idx = point_names.index("right_ankle")
    head_idx = point_names.index("head")
    neck_idx = point_names.index("neck")

    # 坐标 (x, y)
    r_sh = point_coords[r_sh_idx]
    r_elbow = point_coords[r_elbow_idx]
    r_hip = point_coords[r_hip_idx]
    r_knee = point_coords[r_knee_idx]
    r_ankle = point_coords[r_ankle_idx]
    head = point_coords[head_idx]
    neck = point_coords[neck_idx]

    # 水平线直接用 y 坐标
    y_sh = r_sh[1]
    y_elbow = r_elbow[1]
    y_hip = r_hip[1]
    y_knee = r_knee[1]
    y_ankle = r_ankle[1]

    # 网格坐标
    yy, xx = np.mgrid[0:h, 0:w]

    # ====================== 区域分割 ======================
    torso_region_mask = (yy >= y_sh) & (yy <= y_hip) & mask  # 躯干(肩线与髋线之间)
    abdomen_region_mask = (yy >= y_elbow) & (yy <= y_hip) & mask  # 腹部(肘线与髋线之间)

    # ====================== 身高 ======================
    ys_body = yy[mask]
    if len(ys_body) > 0:
        top_body_y = ys_body.min()
        bottom_body_y = ys_body.max()
        height = bottom_body_y - top_body_y
    else:
        height = 1e-6

    # ====================== 腹部核心指标 ======================
    # 右侧视图：身体朝前的方向是 x 最大
    abdomen_x_vals = xx[abdomen_region_mask]
    if len(abdomen_x_vals) > 0:
        max_x_abdomen = abdomen_x_vals.max() 
    else:
        max_x_abdomen = r_hip[0]

    # 中线：头顶 + 髋 + 脚踝 平均x
    body_center_x = (head[0] + r_hip[0] + r_ankle[0]) / 3

    # 躯干厚度
    torso_x_vals = xx[torso_region_mask]
    if len(torso_x_vals) > 0:
        body_width = torso_x_vals.max() - torso_x_vals.min()
    else:
        body_width = 1e-6

    # 突出量 + 比例
    protrusion = abs(max_x_abdomen - body_center_x)
    abdomen_ratio = protrusion / body_width if body_width != 0 else 0.0

    return height, abdomen_ratio