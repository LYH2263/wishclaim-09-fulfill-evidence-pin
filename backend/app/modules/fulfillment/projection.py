"""举证投影：从冻结快照派生三路读模型，保证墙角标 / 已完成摘要 / 详情举证区一致。

- badge:     墙角标（Wall 卡片角标，仅 fulfilled 有）
- card:      已完成列表摘要（Done 页卡片）
- detail:    详情页举证区（完整快照）
三路均只接受 fulfilled + 快照，未核销不产出任何举证投影。
"""


def badge(snapshot: dict | None) -> dict | None:
    if not snapshot:
        return None
    return {
        "text": f"{snapshot['channel_icon']} {snapshot['channel_short']}已核销",
        "channel": snapshot["channel"],
    }


def card(snapshot: dict | None) -> dict | None:
    if not snapshot:
        return None
    return {
        "channel": snapshot["channel"],
        "channel_label": snapshot["channel_label"],
        "channel_icon": snapshot["channel_icon"],
        "ref": snapshot["ref"],
        "fulfilled_at": snapshot["fulfilled_at"],
        "summary": f"{snapshot['channel_icon']} {snapshot['channel_label']} · 凭证 {snapshot['ref']}",
    }


def detail(snapshot: dict | None) -> dict | None:
    if not snapshot:
        return None
    return dict(snapshot)
