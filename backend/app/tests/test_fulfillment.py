from datetime import datetime, timezone

from app.modules.fulfillment import channels, freeze, preview, projection

NOW = datetime(2026, 1, 10, 8, 0, tzinfo=timezone.utc)
COMPLETE = {"channel": "express_delivery", "ref": "SF123", "note": "已签收"}


# ---- channels ----

def test_channel_enum_is_closed_set():
    assert channels.is_valid("express_delivery")
    assert not channels.is_valid("顺风快递")   # 自由文本一律不认
    assert not channels.is_valid("")
    assert not channels.is_valid(None)
    assert channels.label_of("photo_confirm") == "照片确认"
    assert channels.short_of("offline_handover") == "面交"


# ---- preview（纯读，不改 status）----

def test_preview_for_claimed_offers_channels():
    pv = preview.build_preview("claimed", "alice", None)
    assert pv["can_submit"] is True and pv["frozen"] is False
    assert {c["value"] for c in pv["channels"]} >= {"express_delivery", "photo_confirm"}
    assert pv["proof"] is None


def test_preview_for_fulfilled_is_frozen_without_channels():
    snap = freeze.build_snapshot(COMPLETE, "alice", NOW)
    pv = preview.build_preview("fulfilled", "alice", snap)
    assert pv["can_submit"] is False and pv["frozen"] is True
    assert pv["channels"] == []
    assert "快递寄送" in pv["summary"]


# ---- freeze（校验 + 快照冻结）----

def test_freeze_accepts_complete_proof():
    assert freeze.validate("claimed", COMPLETE)["ok"] is True


def test_freeze_rejects_missing_fields():
    for partial in ({}, {"channel": "express_delivery"},
                    {"channel": "express_delivery", "ref": "SF123"}):
        v = freeze.validate("claimed", partial)
        assert v["ok"] is False and v["status"] == 422 and v["reason"] == "proof_incomplete"
        assert v["missing"]


def test_freeze_rejects_blank_fields():
    v = freeze.validate("claimed", {"channel": "  ", "ref": "", "note": "\n"})
    assert v["ok"] is False and v["reason"] == "proof_incomplete"
    assert set(v["missing"]) == {"channel", "ref", "note"}


def test_freeze_rejects_unknown_channel():
    v = freeze.validate("claimed", {"channel": "wechat_redpacket", "ref": "1", "note": "x"})
    assert v["ok"] is False and v["status"] == 422 and v["reason"] == "bad_channel"


def test_freeze_blocks_when_not_claimed():
    assert freeze.validate("open", COMPLETE)["reason"] == "need_claim"
    assert freeze.validate("released", COMPLETE)["reason"] == "need_claim"


def test_freeze_blocks_rewrite_after_fulfilled():
    v = freeze.validate("fulfilled", COMPLETE)
    assert v["ok"] is False and v["status"] == 409 and v["reason"] == "proof_frozen"


def test_snapshot_freezes_channel_labels():
    snap = freeze.build_snapshot(COMPLETE, "bob", NOW)
    assert snap["channel"] == "express_delivery"
    assert snap["channel_label"] == "快递寄送" and snap["channel_short"] == "快递"
    assert snap["ref"] == "SF123" and snap["claimer"] == "bob"
    assert snap["fulfilled_at"] == NOW.isoformat()


# ---- projection（三路一致）----

def test_projections_all_empty_without_snapshot():
    assert projection.badge(None) is None
    assert projection.card(None) is None
    assert projection.detail(None) is None


def test_three_projections_share_one_snapshot():
    snap = freeze.build_snapshot(COMPLETE, "bob", NOW)
    b, cd, dt = projection.badge(snap), projection.card(snap), projection.detail(snap)
    assert b["channel"] == cd["channel"] == dt["channel"] == "express_delivery"
    assert "已核销" in b["text"]
    assert "凭证 SF123" in cd["summary"]
    assert dt["note"] == "已签收"
    # detail 返回副本，外部篡改不回灌快照
    dt["ref"] = "hacked"
    assert projection.detail(snap)["ref"] == "SF123"
