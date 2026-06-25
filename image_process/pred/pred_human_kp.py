"""
MMPose 推理示例：对单张图做人体 2D 关键点检测，并打印每个点的坐标、置信度与关节名称。

依赖：已正确安装 mmpose / mmdet / mmengine 等（与当前环境一致）。
运行：python test2.py
"""
import warnings

from mmpose.apis import MMPoseInferencer


def keypoint_name(id2name: dict, idx: int) -> str:
    """按关键点下标取名称；兼容 meta 里 key 为 int 或 str 的情况。"""
    return id2name.get(idx) or id2name.get(str(idx)) or f"keypoint_{idx}"


def iter_persons(predictions):
    """
    把 result['predictions'] 展平成「多个人」的迭代器。

    结构说明（重要）：
    - 按「每张输入图」分组：最外层 list 的一格对应一张图
    - 每一格又是一个 list：这张图里检测到的每一个人（每人一个 dict）
    - 整体类似 [图1[{人0}, {人1}, ...],
              图2[{人0}, {人1}, ...]...]；
    - 单张图时常见为 [[{人1}, ...]]
    - 若直接把最外层当「人」遍历，会得到内层 list，用 person['keypoints'] 会 TypeError
    """
    for item in predictions or []:
        # 遍历每一张图
        if item is None:
            continue
        # 返回一连串人的dict
        else:
            yield from item


def predict_human_kp(img_path, method="human") -> tuple[list[dict],dict]:
    # PyTorch 部分版本会提示 meshgrid 的 indexing；与结果无关，这里屏蔽
    warnings.filterwarnings(
        "ignore",
        message=".*torch.meshgrid.*indexing.*",
        category=UserWarning,
    )

    # 'human'：metafile 里配置的人体 2D 流程（检测器 + 姿态网络），内部为 Pose2DInferencer
    inferencer = MMPoseInferencer(method)

    # 数据集元信息：关节「编号 -> 英文名」（如 left_hip、right_knee）
    # 与训练集定义一致（常见 COCO 17 点）；换模型后点数、名字可能不同
    meta = inferencer.inferencer.model.dataset_meta
    id2name = meta.get("keypoint_id2name") or {}

    # inferencer(...) 返回生成器；单张图取 next 即可。show=False 不弹窗，改 True 可看可视化
    result = next(inferencer(img_path, show=False))
    # print(result)
    persons = list(iter_persons(result.get("predictions", [])))

    # print(f"\ndataset: {meta.get('dataset_name', 'unknown')}, persons: {len(persons)}\n")
    if len(persons)!=1:
        warnings.warn("more than one person")

    return persons, id2name
