"""正面展示图上的脸部马赛克（基于 human_front 关键点）。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def _find_kp(point_coords: list[np.ndarray], point_names: list[str], pred) -> np.ndarray | None:
    for c, n in zip(point_coords, point_names):
        if pred(str(n).lower()):
            return np.asarray(c, dtype=np.float32).reshape(2)
    return None


def mosaic_face_process(image_path: str, human_front: tuple) -> str:
    """
    在输入图 image_path 上基于关键点做人脸马赛克。
    返回保存后的路径（与原图同目录，文件名加 _mosaic）。
    """
    point_coords, point_names, _mask = human_front

    img = cv2.imread(image_path)
    if img is None:
        return image_path

    h, w = img.shape[:2]
    nose = _find_kp(point_coords, point_names, lambda n: "nose" in n)
    le = _find_kp(point_coords, point_names, lambda n: "left" in n and "eye" in n)
    re = _find_kp(point_coords, point_names, lambda n: "right" in n and "eye" in n)

    if nose is None:
        return image_path

    eye_dist = None
    if le is not None and re is not None:
        eye_dist = float(np.linalg.norm(le - re))

    # --- 打码范围调参（仅改本段数字即可）---
    # 眼距倍数：越大椭圆越大；下限：检测不到双眼时用固定像素兜底
    eye_w_mul, eye_h_mul = 3.0, 3.9
    min_w_if_eyes, min_h_if_eyes = 120.0, 150.0
    fallback_w, fallback_h = 160, 195
    min_rx, min_ry = 28, 34
    nose_down_frac = 0.12  # 椭圆中心相对鼻点下移：越大越盖住下巴区域

    face_w = (
        int(max(eye_dist * eye_w_mul, min_w_if_eyes))
        if eye_dist and eye_dist > 1
        else fallback_w
    )
    face_h = (
        int(max(eye_dist * eye_h_mul, min_h_if_eyes))
        if eye_dist and eye_dist > 1
        else fallback_h
    )
    rx = max(face_w // 2, min_rx)
    ry = max(face_h // 2, min_ry)

    cx = int(round(float(nose[0])))
    cy = int(round(float(nose[1] + ry * nose_down_frac)))
    x1, x2 = max(0, cx - rx), min(w, cx + rx)
    y1, y2 = max(0, cy - ry), min(h, cy + ry)
    if x2 <= x1 or y2 <= y1:
        return image_path

    roi = img[y1:y2, x1:x2].copy()
    rh, rw = roi.shape[:2]
    if rh < 4 or rw < 4:
        return image_path

    # 增大 block，让马赛克块更粗、更明显
    block = max(20, min(rw, rh) // 8)
    small = cv2.resize(
        roi,
        (max(1, rw // block), max(1, rh // block)),
        interpolation=cv2.INTER_LINEAR,
    )
    mosaic_roi = cv2.resize(small, (rw, rh), interpolation=cv2.INTER_NEAREST)

    mask_face = np.zeros((rh, rw), dtype=np.uint8)
    cv2.ellipse(
        mask_face,
        (cx - x1, cy - y1),
        (rx, ry),
        0,
        0,
        360,
        255,
        -1,
    )
    img[y1:y2, x1:x2] = np.where(mask_face[..., None] > 0, mosaic_roi, roi)

    p = Path(image_path)
    out_path = p.with_name(f"{p.stem}_mosaic{p.suffix}")
    cv2.imwrite(str(out_path), img)
    return str(out_path)
