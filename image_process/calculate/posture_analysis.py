# posture_analysis.py
import numpy as np
import math
from pathlib import Path

# =========================
# 点到直线距离
# =========================
def point_to_line_dist(p, a, b):
    x0, y0 = p
    x1, y1 = a
    x2, y2 = b
    return abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1) / math.hypot(y2 - y1, x2 - x1)

# =========================
# 1. 头前伸（侧面专用）
# =========================

def calculate_head_forward_left(kpts, point_names):
    ear_idx      = point_names.index("left_ear")
    shoulder_idx = point_names.index("left_shoulder")
    hip_idx      = point_names.index("left_hip")

    ear_x    = kpts[ear_idx, 0]
    shoulder_x = kpts[shoulder_idx, 0]
    shoulder_y = kpts[shoulder_idx, 1]
    hip_y    = kpts[hip_idx, 1]

    torso_length = abs(hip_y - shoulder_y) + 1e-6
    offset = abs(ear_x - shoulder_x)
    return offset / torso_length

def calculate_head_forward_right(kpts, point_names):
    ear_idx      = point_names.index("right_ear")
    shoulder_idx = point_names.index("right_shoulder")
    hip_idx      = point_names.index("right_hip")

    ear_x    = kpts[ear_idx, 0]
    shoulder_x = kpts[shoulder_idx, 0]
    shoulder_y = kpts[shoulder_idx, 1]
    hip_y    = kpts[hip_idx, 1]

    torso_length = abs(hip_y - shoulder_y) + 1e-6
    offset = abs(ear_x - shoulder_x)
    return offset / torso_length

# =========================
# 2. 高低肩（正面专用）
# =========================
def calculate_shoulder_tilt(kpts, point_names):
    l_idx = point_names.index("left_shoulder")
    r_idx = point_names.index("right_shoulder")
    l_shy = kpts[l_idx, 1]
    r_shy = kpts[r_idx, 1]
    shoulder_width = abs(kpts[r_idx, 0] - kpts[l_idx, 0]) + 1e-6
    return (r_shy - l_shy) / shoulder_width
# =========================
# 3. 骨盆倾斜（正面专用）
# =========================
def calculate_pelvic_tilt(kpts, point_names):
    l_idx = point_names.index("left_hip")
    r_idx = point_names.index("right_hip")

    l_hipy = kpts[l_idx, 1]
    r_hipy = kpts[r_idx, 1]
    hip_width = abs(kpts[r_idx, 0] - kpts[l_idx, 0]) + 1e-6
    return (r_hipy - l_hipy) / hip_width
# =========================
# 4. 膝对齐（侧面图专用）
# left 图 → 算左腿
# right 图 → 算右腿
# =========================
def calculate_knee_alignment_left(kpts, point_names):
    hip_idx = point_names.index("left_hip")
    knee_idx = point_names.index("left_knee")
    ankle_idx = point_names.index("left_ankle")

    hip = kpts[hip_idx]
    knee = kpts[knee_idx]
    ankle = kpts[ankle_idx]

    leg_length = np.linalg.norm(ankle - hip) + 1e-6
    knee_offset = point_to_line_dist(knee, hip, ankle)
    return knee_offset / leg_length

def calculate_knee_alignment_right(kpts, point_names):
    hip_idx = point_names.index("right_hip")
    knee_idx = point_names.index("right_knee")
    ankle_idx = point_names.index("right_ankle")

    hip = kpts[hip_idx]
    knee = kpts[knee_idx]
    ankle = kpts[ankle_idx]

    leg_length = np.linalg.norm(ankle - hip) + 1e-6
    knee_offset = point_to_line_dist(knee, hip, ankle)
    return knee_offset / leg_length
