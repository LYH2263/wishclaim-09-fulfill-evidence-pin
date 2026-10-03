"""举证包预览：claimed 可先看「将提交什么 + 当前状态」，不写库、不改 status。"""

from . import channels


def build_preview(status: str, claimer: str | None, snapshot: dict | None) -> dict:
    """返回举证包预览读模型。

    - claimed 且尚无快照：给出摘要草稿与可选渠道枚举
    - claimed 且已有快照（理论上不会出现，防御性处理）：展示已冻结快照
    - fulfilled：展示已冻结快照，无枚举（核销后冻结，不引导再编辑）
    """
    if status == "fulfilled" and snapshot:
        return {
            "can_submit": False,
            "frozen": True,
            "summary": summary_text(snapshot),
            "channels": [],
            "proof": snapshot,
        }
    return {
        "can_submit": status == "claimed",
        "frozen": False,
        "summary": "待提交完整举证（渠道 + 凭证号 + 说明）后核销，快照将冻结不可改",
        "channels": channels.list_channels(),
        "proof": snapshot,
    }


def summary_text(snapshot: dict) -> str:
    return f"已通过{channels.label_of(snapshot['channel'])}核销 · 凭证 {snapshot['ref']}"
