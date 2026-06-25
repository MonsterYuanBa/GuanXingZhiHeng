import numpy as np
from pathlib import Path
import cv2
from image_process.utils.visualize import visualize_masks_on_image


def get_tilt_angle_mask(ori_img_path, mask) -> float:
    # 利用PCA等方法，根据mask拟合出一条人体中轴线
    # 获取影像的倾斜角度，角度制，逆时针为正角度
    # 中轴线相对 x 轴角度
    masks = np.asarray(mask)
    if masks.ndim == 2:
        masks = masks[None, ...]
    elif masks.ndim != 3:
        raise ValueError(f"mask 维度不合法: ndim={masks.ndim}, shape={masks.shape}")

    # SAM 常见输出为 (N, H, W)：将多个候选mask做并集，得到单个人体总mask
    masks_bool = masks > 0
    best_mask = np.any(masks_bool, axis=0)

    ys, xs = np.where(best_mask)
    if xs.size < 10:
        raise ValueError(f"有效mask像素太少，无法拟合中轴线: {xs.size}")

    # PCA 主方向
    # 前景点坐标
    coords = np.stack([xs.astype(np.float64), ys.astype(np.float64)], axis=1)
    # 去中心化
    centered = coords - coords.mean(axis=0, keepdims=True)
    # 协方差矩阵
    cov = centered.T @ centered / max(centered.shape[0] - 1, 1)
    # 特征分解
    eigvals, eigvecs = np.linalg.eigh(cov)
    # 取主成分
    principal = eigvecs[:, int(np.argmax(eigvals))]  # [dx, dy]

    # 相对 x 轴夹角：角度制，逆时针为正
    # (-180, 180]
    angle = float(np.degrees(np.arctan2(principal[1], principal[0])))
    if angle < 0:
        angle += 180
    tilt_angle = angle - 90
    return float(tilt_angle)

def get_tilt_angle_kp(point_coords, point_names) -> float:
    # 根据某些人体关键点，协助估计人体中轴倾斜角度
    
    pass

def tilt_correct_pic(ori_img_path, tilt_corrected_pth,
                     rotate_angle,
                     point_coords, point_names, mask) -> tuple[list[np.ndarray], np.ndarray]:
    # 根据角度，对影像进行倾斜校正，并保存为新的图像
    image_bgr = cv2.imread(ori_img_path)
    if image_bgr is None:
        raise FileNotFoundError(f"Cannot read image: {ori_img_path}")

    h, w = image_bgr.shape[:2]
    center = (w / 2.0, h / 2.0)

    # 计算旋转矩阵
    rot = cv2.getRotationMatrix2D(center, rotate_angle, 1.0)
    # 计算不裁剪的新画布大小，并平移旋转矩阵到新画布中心
    cos_v = float(abs(rot[0, 0]))
    sin_v = float(abs(rot[0, 1]))
    new_w = int(np.ceil(h * sin_v + w * cos_v))
    new_h = int(np.ceil(h * cos_v + w * sin_v))
    # 对平移项进行调整，调整画布中心
    rot[0, 2] += (new_w / 2.0) - center[0]
    rot[1, 2] += (new_h / 2.0) - center[1]

    # 旋转图像
    corrected_img = cv2.warpAffine(
        image_bgr,
        rot,
        (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    cv2.imwrite(tilt_corrected_pth, corrected_img)

    # 关键点同步旋转
    pts = np.asarray(point_coords, dtype=np.float32).reshape(-1, 2)
    if pts.shape[0] > 0:
        # 仿射矩阵需要齐次坐标
        ones = np.ones((pts.shape[0], 1), dtype=np.float32)
        pts_h = np.hstack([pts, ones])  # (N, 3)
        # 旋转变换
        pts_rot = (rot @ pts_h.T).T.astype(np.float32)
    else:
        pts_rot = np.empty((0, 2), dtype=np.float32)
    # 转换回列表形式
    corrected_point_coords = [pts_rot[i] for i in range(pts_rot.shape[0])]

    # mask 同步旋转，支持 (H,W) / (N,H,W)
    masks = np.asarray(mask)
    if masks.ndim == 2:
        masks = masks[None, ...]
    elif masks.ndim != 3:
        raise ValueError(f"mask 维度不合法: ndim={masks.ndim}, shape={masks.shape}")

    rotated_masks = []
    for i in range(masks.shape[0]):
        # 旋转并转换为bool
        rm = cv2.warpAffine(
            masks[i].astype(np.uint8),
            rot,
            (new_w, new_h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        ).astype(bool)
        rotated_masks.append(rm)
    # 将列表堆叠为数组
    corrected_mask = np.stack(rotated_masks, axis=0)

    # 复用现有 visualize.py 中的可视化函数
    vis = visualize_masks_on_image(
        image_bgr=corrected_img,
        masks=corrected_mask,
        alpha=0.5,
        draw_prompt_points=True,
        point_coords=pts_rot,
        point_labels=np.ones(pts_rot.shape[0], dtype=np.int32),
    )
    vis_path = str(Path(tilt_corrected_pth).with_name(Path(tilt_corrected_pth).stem + "_vis" + Path(tilt_corrected_pth).suffix))
    cv2.imwrite(vis_path, vis)

    return corrected_point_coords, corrected_mask



def tilt_correct(ori_img_path:str,
                 human:tuple[list[np.ndarray], list[str], np.ndarray],
                 w_mask_vs_kp:float):

    if ori_img_path is None:
        return human

    point_coords: list[np.ndarray]
    point_names: list[str]
    mask: np.ndarray
    point_coords, point_names, mask = human

    tilt_corrected_name = Path(ori_img_path).stem + "_tilt_corrected" + Path(ori_img_path).suffix
    tilt_corrected_pth = str(Path(ori_img_path).with_name(tilt_corrected_name))

    # 根据mask拟合一条人体中轴线，并获取中轴线相对 x 轴角度
    tilt_angle_mask = get_tilt_angle_mask(ori_img_path, mask)
    tilt_angle_kp = get_tilt_angle_kp(point_coords, point_names)

    # tilt_angle = w_mask_vs_kp * tilt_angle_mask + (1 - w_mask_vs_kp) * tilt_angle_kp
    tilt_angle = tilt_angle_mask


    # 根据倾斜角度，对影像/mask/keypoint进行校正
    point_coords, mask = tilt_correct_pic(ori_img_path, tilt_corrected_pth,
                                          tilt_angle,
                                          point_coords, point_names, mask)
    # 打包返回
    human = point_coords,point_names,mask
    return tilt_corrected_pth, human