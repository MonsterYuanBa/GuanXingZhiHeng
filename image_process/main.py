import numpy as np
from pathlib import Path

from image_process.calculate import calculate_titai_fb, calculate_titai_lr, calcluate_tixing_fb, calcluate_tixing_lr
from image_process.mosaic_face import mosaic_face_process
from image_process.process_human import process_human
from image_process.utils.tilt_correction import tilt_correct
from image_process.utils.visualize import write_front_display_image
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SAM_CHECKPOINT = _ROOT / "models" / "sam_vit_h_4b8939.pth"


def main_process(
    sam_checkpoint_path=None,
    front_path="../test_img/IMG_6009.PNG",
    tilt_f=True,
    left_path=None,
    tilt_l=False,
    right_path=None,
    tilt_r=False,
    back_path=None,
    tilt_b=False,
    mosaic=False,
):
    sam_checkpoint_path = str(Path(sam_checkpoint_path) if sam_checkpoint_path else _DEFAULT_SAM_CHECKPOINT)
    titai_fb = None
    tixing_fb = None
    titai_lr = None
    tixing_lr = None
    processed_path = None
    mosaic_base_path = None

    if front_path is not None:
        # ==========处理front==========
        # 直接使用元组保存图像的关键点和mask信息
        # 正面阈值过高会偶发过滤掉 right_shoulder（如 score 0.68~0.74），导致后续按名称索引报错
        human_front:tuple[list[np.ndarray], list[str], np.ndarray] = process_human(front_path,kp_thres=0.6,
                                                                                   sam_checkpoint_path=sam_checkpoint_path)
        # 倾斜校正，tilt_correct_image_front_path可能没啥用
        if tilt_f:
            front_path, human_front = tilt_correct(front_path,human_front,w_mask_vs_kp=0.5)

        # ==========处理back==========
        # 这里有可能返回空的list
        human_back: tuple[list[np.ndarray], list[str], np.ndarray] = process_human(back_path, kp_thres=0.75,
                                                                                    sam_checkpoint_path=sam_checkpoint_path)
        if tilt_b:
            back_path, human_back = tilt_correct(back_path,human_back,w_mask_vs_kp=0.5)

        # ==========计算指标==========
        # 这里将back_path传入是为了判断human_back是否为空，决定指标计算方式
        titai_fb = calculate_titai_fb(human_front,
                                      human_back, back_path)
        tixing_fb = calcluate_tixing_fb(human_front,
                                        human_back,back_path)

        # 前端仅展示正面：
        # 先做人脸打码，再叠加 mask + 关键点，确保关键点不会被马赛克盖住
        display_base_path = front_path
        if mosaic:
            display_base_path = mosaic_face_process(front_path, human_front)
        mosaic_base_path = display_base_path if mosaic else None
        processed_path = write_front_display_image(display_base_path, human_front)

    if left_path is not None or right_path is not None:
        # ==========处理left==========
        human_left:tuple[list[np.ndarray], list[str], np.ndarray] = process_human(left_path,kp_thres=0.6,
                                                                                   sam_checkpoint_path=sam_checkpoint_path)
        if tilt_l:
            left_path, human_left = tilt_correct(left_path,human_left,w_mask_vs_kp=0.5)

        # ==========处理right==========
        human_right: tuple[list[np.ndarray], list[str], np.ndarray] = process_human(right_path, kp_thres=0.6,
                                                                                    sam_checkpoint_path=sam_checkpoint_path)
        if tilt_r:
            right_path, human_right = tilt_correct(right_path,human_right,w_mask_vs_kp=0.5)

        # ==========计算指标==========
        titai_lr = calculate_titai_lr(human_left, left_path,
                                      human_right, right_path)
        tixing_lr = calcluate_tixing_lr(human_left, left_path,
                                        human_right, right_path)

    # mosaic_base_path：仅做人脸马赛克的“处理前底图”（与 processed_path 尺寸一致，用于前端对比拉条）
    return titai_fb, tixing_fb, titai_lr, tixing_lr, processed_path, mosaic_base_path