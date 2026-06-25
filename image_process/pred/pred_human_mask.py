from pathlib import Path

import cv2
import numpy as np
import torch
from segment_anything import SamPredictor, sam_model_registry
from image_process.utils.visualize import visualize_masks_on_image


def run_demo(
    image_path: str,
    checkpoint_path: str,
    point_coords: np.ndarray,
    point_labels: np.ndarray,
    model_type: str = "vit_b",
    device: str = "cuda",
    draw_prompt_points: bool = False,
    save_img = False
):
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    if device == "cuda" and not torch.cuda.is_available():
        print("CUDA is not available, fallback to CPU.")
        device = "cpu"

    sam = sam_model_registry[model_type](checkpoint=checkpoint_path)
    sam.to(device=device)
    predictor = SamPredictor(sam)

    predictor.set_image(image_rgb)

    # 单目标、单提示模式，输出1或者3个mask
    masks, scores, logits = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=True,
    )

    print(f"masks shape:  {masks.shape}")
    print(f"scores shape: {scores.shape}")
    print(f"logits shape: {logits.shape}")
    print(f"scores: {scores}")

    if save_img:
        vis = visualize_masks_on_image(
            image_bgr=image_bgr,
            masks=masks,
            alpha=0.5,
            draw_prompt_points=draw_prompt_points,
            point_coords=point_coords,
            point_labels=point_labels,
        )
        out_path = str(Path(image_path).with_name(Path(image_path).stem + "_sam_vis.png"))
        cv2.imwrite(out_path, vis)
        print(f"Saved visualization to: {out_path}")

    # cv2.imshow("SAM masks overlay", vis)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
    # print(type(masks))
    return masks


def get_human_mask(
    image_path,
    point_coords,
    checkpoint_path,
    model_type: str = "vit_h",
    device: str = "cuda",
    draw_prompt_points: bool = False,
    save_img = False
):
    # 与 point_coords 每一行对应：1=前景点，0=背景点；这里默认全部前景点
    point_coords = np.array(point_coords, dtype=np.float32)

    n = int(np.asarray(point_coords).shape[0])
    point_labels = np.ones(n, dtype=np.int32)

    return run_demo(
        image_path=image_path,
        checkpoint_path=checkpoint_path,
        point_coords=point_coords,
        point_labels=point_labels,
        model_type=model_type,
        device=device,
        draw_prompt_points=draw_prompt_points,
        save_img=save_img
    )

