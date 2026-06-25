from image_process.pred.pred_human_kp import predict_human_kp, keypoint_name
from image_process.pred.pred_human_mask import get_human_mask
import numpy as np


def process_human(image_path,
                  kp_thres,
                  sam_checkpoint_path,
                  model_type="vit_h",
                  method="body26",
                  device="cuda",
                  save_img=False
                  ) -> tuple[list[np.ndarray], list[str], np.ndarray]:

    if image_path is None:
        return [], [], np.empty((0,), dtype=np.float32)

    # ----------获取人体关键点----------
    human_kp_many, id2name = predict_human_kp(image_path, method=method)
    human_kp = human_kp_many[0]

    kpts = human_kp["keypoints"]
    scores = human_kp["keypoint_scores"]
    print(f"--- person 0 ({len(kpts)} keypoints) ---")

    # 对human_kp进行处理筛选
    point_coords: list[np.ndarray] = []
    point_names:list[str] = []
    for i, s in enumerate(scores):
        # 打印基本信息
        x, y = float(kpts[i][0]), float(kpts[i][1])
        name = keypoint_name(id2name, i)
        print(f"  [{i:2d}] {name:16s}  x={x:8.2f}  y={y:8.2f}  score={s:.4f}")

        # 根据置信度阈值筛选
        if s >= kp_thres:
            point_coords.append(kpts[i])
            point_names.append(name)

    # ----------获取人体mask----------
    human_mask = get_human_mask(image_path,
                   point_coords,
                   sam_checkpoint_path,
                   model_type=model_type,
                   device=device,
                   draw_prompt_points=True,save_img=save_img)

    return point_coords, point_names, human_mask
