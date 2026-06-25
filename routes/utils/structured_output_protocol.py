from __future__ import annotations

from typing import Iterable, Optional


def structured_output_protocol(
    *,
    section_key_examples: Optional[Iterable[str]] = None,
    item_key_examples: Optional[Iterable[str]] = None,
) -> str:
    """
    返回“结构化输出协议”文本，用于插入到智能体 prompt 中。

    设计目标：
    - 数据库仍存整段文本，但文本内部用稳定分隔符标记段落/分点，方便前端结构化展示。
    - 允许调用方传入示例 key，提高模型一致性，但协议本身保持统一。
    """

    sec_ex = ""
    if section_key_examples:
        xs = [str(x).strip() for x in section_key_examples if str(x).strip()]
        if xs:
            sec_ex = f"  - section_key 示例：{' / '.join(xs)}。\n"

    item_ex = ""
    if item_key_examples:
        xs = [str(x).strip() for x in item_key_examples if str(x).strip()]
        if xs:
            item_ex = f"  - item_key 示例：{' / '.join(xs)}。\n"

    # 注意：这里刻意不使用三引号缩进，避免提示中出现多余前导空格，降低模型误差。
    return (
        "【结构化输出协议（必须严格遵守，用于前端分段展示；数据库仍存整段文本）】\n"
        "- 全文只输出“报告正文”，不要输出任何额外解释、致歉或自述。\n"
        "- 每个一级段落开始前，必须单独输出一行分隔符：<<<SECTION|section_key|段落标题>>>\n"
        f"{sec_ex}"
        "- 本协议为三层结构：SECTION（一级段落） > GROUP（二级分组） > ITEM（三级条目）。\n"
        "- 每个二级分组开始前，必须单独输出一行分隔符：<<<GROUP|group_key|分组标题>>>\n"
        "  - group_key 用英文小写+下划线；例：posture_metrics / body_shape_metrics / tcm_ten。\n"
        "- 每个三级条目开始前，必须单独输出一行分隔符：<<<ITEM|item_key|条目标题>>>\n"
        f"{item_ex}"
        "  - item_key 用英文小写+下划线；若条目标题不便写，可用 <<<ITEM>>>（但优先用带标题的 ITEM）。\n"
        "- 分隔符行前后不要加任何其他字符；分隔符必须独占一行。\n"
        "- 段落内容与条目内容写在分隔符之后，可多行，可有空行。\n"
        "- 若某 SECTION 内没有自然分组，也必须至少输出一个 GROUP 作为容器，再输出 ITEM。\n"
        "\n"
        "【排版与可读性要求（必须遵守）】\n"
        "- 必须主动换行：不同意思用不同段落表达。\n"
        "- 仅在正文过长（超过 4 行）时才拆分为多段；否则保持连贯，不要为了“好看”强行分段。\n"
        "- 禁止在段落之间插入空白行：段落之间只用单个换行分隔（使用 \\n），不要使用 \\n\\n。\n"
        "- 每个 <<<ITEM>>> 的内容建议用 2-4 个短段落或分行表达（现象/解释/可能原因/注意点），段落之间同样禁止空白行。\n"
        "- 尽量用短句：每段 1-2 句为宜；避免堆砌修饰词。\n"
    ).strip()

