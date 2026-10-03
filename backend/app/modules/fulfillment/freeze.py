"""举证冻结：完整举证校验 + 构造不可变快照。

规则：
- 仅 status=claimed 可核销；fulfilled 再提交 → proof_frozen（核销后禁止改举证）
- 必须提交完整举证：channel（枚举）+ ref（凭证号）+ note（说明），缺一或空白拒绝
- 快照内冻结渠道 label/short/icon，日后枚举文案调整不影响历史读模型
"""

from datetime import datetime, timezone

from . import channels

PROOF_FIELDS = ("channel", "ref", "note")


def _blank(v) -> bool:
    return not isinstance(v, str) or not v.strip()


def validate(status: str, body: dict) -> dict:
    """校验核销请求。返回 {"ok": True} 或 {"ok": False, "status": http, "reason": code, "missing": [...]}。"""
    if status == "fulfilled":
        return {"ok": False, "status": 409, "reason": "proof_frozen", "missing": []}
    if status != "claimed":
        return {"ok": False, "status": 400, "reason": "need_claim", "missing": []}

    missing = [f for f in PROOF_FIELDS if _blank(body.get(f))]
    if missing:
        return {"ok": False, "status": 422, "reason": "proof_incomplete", "missing": missing}

    value = body["channel"].strip()
    if not channels.is_valid(value):
        return {"ok": False, "status": 422, "reason": "bad_channel", "missing": []}
    return {"ok": True}


def build_snapshot(body: dict, claimer: str | None, now: datetime) -> dict:
    """校验通过后构造冻结快照（只在写库瞬间调用一次）。"""
    value = body["channel"].strip()
    return {
        "channel": value,
        "channel_label": channels.label_of(value),
        "channel_short": channels.short_of(value),
        "channel_icon": channels.icon_of(value),
        "ref": body["ref"].strip(),
        "note": body["note"].strip(),
        "claimer": claimer,
        "fulfilled_at": (now or datetime.now(timezone.utc)).isoformat(),
    }
