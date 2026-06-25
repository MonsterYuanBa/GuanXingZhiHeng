from __future__ import annotations

from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

# MMPose `body26` 对应 Halpe-26 等 26 点人体格式：与 process_human 里 keypoint_name 一致，按「关节名」连边。
# 筛选低分关键点后只能用名称对齐，不能再用模型原始下标。
# 顺序：先躯干与四肢主链，再头脸，最后足踝细节（缺失的边会自动跳过）。
BODY26_SKELETON_EDGES: tuple[tuple[str, str], ...] = (
    # 头颈
    ("head", "neck"),
    ("neck", "nose"),
    # 脸轮廓（与常见 Halpe/COCO 可视化一致）
    ("nose", "left_eye"),
    ("nose", "right_eye"),
    ("left_eye", "left_ear"),
    ("right_eye", "right_ear"),
    # 肩带与上臂
    ("neck", "left_shoulder"),
    ("neck", "right_shoulder"),
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    # 躯干与骨盆
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "hip"),
    ("right_hip", "hip"),
    # 下肢
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
    # 足部（Halpe 26：趾、跟）
    ("left_ankle", "left_heel"),
    ("left_ankle", "left_big_toe"),
    ("left_ankle", "left_small_toe"),
    ("right_ankle", "right_heel"),
    ("right_ankle", "right_big_toe"),
    ("right_ankle", "right_small_toe"),
)


def _kp_dict_from_lists(
    point_coords: np.ndarray,
    point_names: Sequence[str],
) -> dict[str, tuple[int, int]]:
    pts = np.asarray(point_coords, dtype=np.float32).reshape(-1, 2)
    names = list(point_names)
    if len(names) != pts.shape[0]:
        return {}
    out: dict[str, tuple[int, int]] = {}
    for i, name in enumerate(names):
        x, y = float(pts[i, 0]), float(pts[i, 1])
        out[str(name)] = (int(round(x)), int(round(y)))
    return out


def _draw_skeleton_on_bgr(
    vis: np.ndarray,
    name_to_xy: dict[str, tuple[int, int]],
    edges: Sequence[tuple[str, str]],
    *,
    line_bgr: tuple[int, int, int] = (0, 255, 255),
    thickness: int = 3,
) -> None:
    for a, b in edges:
        pa = name_to_xy.get(a)
        pb = name_to_xy.get(b)
        if pa is None or pb is None:
            continue
        cv2.line(vis, pa, pb, line_bgr, thickness, lineType=cv2.LINE_AA)


def visualize_masks_on_image(
    image_bgr: np.ndarray,
    masks: np.ndarray,
    alpha: float = 0.5,
    *,
    draw_prompt_points: bool = False,
    point_coords: np.ndarray | None = None,
    point_labels: np.ndarray | None = None,
    draw_skeleton: bool = False,
    point_names: Sequence[str] | None = None,
    skeleton_edges: Sequence[tuple[str, str]] | None = None,
) -> np.ndarray:
    overlay = image_bgr.copy()
    colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
    ]  # BGR

    for i, mask in enumerate(masks):
        color = colors[i % len(colors)]
        mask_bool = mask.astype(bool)
        overlay[mask_bool] = color

    vis = cv2.addWeighted(overlay, alpha, image_bgr, 1.0 - alpha, 0)

    pts: np.ndarray | None = None
    if point_coords is not None:
        pts = np.asarray(point_coords, dtype=np.float32).reshape(-1, 2)

    if draw_skeleton and pts is not None and point_names is not None:
        edges = skeleton_edges if skeleton_edges is not None else BODY26_SKELETON_EDGES
        kp_map = _kp_dict_from_lists(pts, point_names)
        if kp_map:
            _draw_skeleton_on_bgr(vis, kp_map, edges)

    if draw_prompt_points and pts is not None:
        n = pts.shape[0]
        if point_labels is None:
            labels = np.ones(n, dtype=np.int32)
        else:
            labels = np.asarray(point_labels, dtype=np.int32).reshape(-1)
        for i in range(min(n, len(labels))):
            x, y = float(pts[i, 0]), float(pts[i, 1])
            cx, cy = int(round(x)), int(round(y))
            # 1=前景点 绿；0=背景点 红（与 SAM 常见约定一致）
            bgr = (0, 255, 0) if int(labels[i]) == 1 else (0, 0, 255)
            cv2.circle(vis, (cx, cy), 6, bgr, -1)
            cv2.circle(vis, (cx, cy), 10, (255, 255, 255), 2)

    return vis


def write_front_display_image(
    image_path: str,
    human_front: tuple[list[np.ndarray], list[str], np.ndarray],
    *,
    alpha: float = 0.5,
    suffix: str = "_display",
    draw_skeleton: bool = True,
) -> str:
    """
    与 pred_human_mask 里 save_img=True 时一致：在原图上叠加 SAM mask，并画出用于推理的关键点。
    process_human 中 save_img 固定为 False，由本函数单独落盘，供前端只展示正面结果。

    draw_skeleton：是否按 MMPose body26（Halpe-26）关节名连接骨架；低分被滤掉的关键点对应的边会自动省略。
    """
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    point_coords, point_names, masks = human_front
    masks = np.asarray(masks)
    if masks.ndim == 2:
        masks = masks[np.newaxis, ...]

    if len(point_coords) == 0:
        pts = None
        labels = None
        draw_pts = False
    else:
        pts = np.asarray(point_coords, dtype=np.float32).reshape(-1, 2)
        labels = np.ones(pts.shape[0], dtype=np.int32)
        draw_pts = True

    vis = visualize_masks_on_image(
        image_bgr=image_bgr,
        masks=masks,
        alpha=alpha,
        draw_prompt_points=draw_pts,
        point_coords=pts,
        point_labels=labels,
        draw_skeleton=draw_skeleton and draw_pts,
        point_names=point_names if draw_skeleton and draw_pts else None,
    )

    p = Path(image_path)
    out_path = p.with_name(f"{p.stem}{suffix}{p.suffix}")
    cv2.imwrite(str(out_path), vis)
    return str(out_path)