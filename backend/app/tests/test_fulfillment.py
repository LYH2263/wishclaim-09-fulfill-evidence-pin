"""fulfillment 模块纯函数测试：渠道枚举 / 预览 / 冻结 / 投影。"""
import json
from datetime import datetime, timezone

import pytest

from app.modules import fulfillment
from app.modules.fulfillment import channels, preview, freeze, projection

NOW = datetime(2026, 10, 3, 8, 0, tzinfo=timezone.utc)
CLAIMED = {"id": 1, "title": "键盘", "status": "claimed", "claimer": "alice",
           "evidence": None, "fulfilled_at": None}


# ---------- 渠道枚举 ----------

def test_channel_catalog_keys_match_constant():
    catalog = channels.channel_catalog()
    assert [c["key"] for c in catalog] == list(channels.CHANNEL_KEYS)
    assert all(c["label"] and c["hint"] for c in catalog)


def test_channel_label_unknown_is_none():
    assert channels.channel_label("purchase") == "实物购买"
    assert channels.channel_label("nope") is None


# ---------- 预览：不改 status ----------

def test_preview_lists_channels_and_summary_without_persisting():
    p = preview.preview_for(CLAIMED, {"channel": "purchase", "reference": "SO-1", "note": "  x  "})
    assert p["status"] == "claimed"
    assert p["persisted"] is False
    assert p["ready"] is True
    assert p["summary"] == "实物购买 · SO-1"
    assert len(p["channels"]) == len(channels.CHANNEL_KEYS)
    assert p["draft"]["note"] == "x"


def test_preview_empty_draft_is_not_ready():
    p = preview.preview_for(CLAIMED, {})
    assert p["ready"] is False
    assert set(p["missing"]) == {"channel", "reference"}
    assert p["summary"] is None


def test_preview_whitespace_only_counts_as_missing():
    p = preview.preview_for(CLAIMED, {"channel": "  ", "reference": "\t\n"})
    assert p["ready"] is False
    assert "channel" in p["missing"] and "reference" in p["missing"]


def test_preview_does_not_mutate_row():
    row = dict(CLAIMED)
    preview.preview_for(row, {"channel": "purchase", "reference": "SO-1"})
    assert row["status"] == "claimed" and row["evidence"] is None


# ---------- 冻结写库 ----------

def test_freeze_success_writes_snapshot():
    out = freeze.freeze_evidence("claimed", "alice",
                                 {"channel": "handmade", "reference": " WIP-9 ", "note": "织了两周"}, NOW)
    assert out["ok"] is True and out["snapshot"]
    snap = out["snapshot"]
    assert snap["channel"] == "handmade"
    assert snap["channel_label"] == "手工制作"
    assert snap["reference"] == "WIP-9"  # 空白被修剪
    assert snap["claimer"] == "alice"
    assert snap["fulfilled_at"] == NOW.isoformat()
    assert snap["schema"] == "fulfillment-evidence-v1"


@pytest.mark.parametrize("body", [
    {},
    {"channel": "purchase"},
    {"reference": "SO-1"},
    {"channel": "purchase", "reference": "   "},
    {"channel": "  ", "reference": "SO-1"},
    {"channel": "wechat-free-text", "reference": "SO-1"},  # 非枚举渠道拒绝
    {"channel": "purchase", "reference": ""},
])
def test_freeze_rejects_incomplete_or_unknown_channel(body):
    out = freeze.freeze_evidence("claimed", "alice", body, NOW)
    assert out["ok"] is False
    assert out["reason"] == "incomplete_evidence"
    assert out["snapshot"] is None
    assert out["errors"]


def test_freeze_requires_claimed_status():
    out = freeze.freeze_evidence("open", None, {"channel": "purchase", "reference": "SO-1"}, NOW)
    assert out["ok"] is False and out["reason"] == "need_claim" and out["snapshot"] is None
    out = freeze.freeze_evidence("released", None, {"channel": "purchase", "reference": "SO-1"}, NOW)
    assert out["ok"] is False and out["reason"] == "need_claim"


def test_freeze_after_fulfill_is_forbidden():
    # 核销后禁止再改举证
    out = freeze.freeze_evidence("fulfilled", "alice",
                                 {"channel": "other", "reference": "X", "note": "想改"}, NOW)
    assert out["ok"] is False and out["reason"] == "already_fulfilled" and out["snapshot"] is None


# ---------- 投影：三路同钉 ----------

def _fulfilled_row():
    snap = freeze.freeze_evidence("claimed", "alice",
                                  {"channel": "purchase", "reference": "SO-1", "note": "已送达"}, NOW)["snapshot"]
    row = dict(CLAIMED, status="fulfilled", evidence=json.dumps(snap, ensure_ascii=False),
               fulfilled_at=NOW.isoformat())
    return row, snap


def test_three_projections_share_one_snapshot():
    row, snap = _fulfilled_row()
    card = projection.done_card(row)
    panel = projection.detail_panel(row)
    badge = projection.corner_badge(row)
    assert card["summary"] == "实物购买 · SO-1"
    assert panel["frozen"] is True and panel["summary"] == card["summary"]
    assert panel["evidence"]["reference"] == "SO-1"
    assert panel["evidence"]["frozen"] is True
    assert badge["tone"] == "done" and "实物购买" in badge["text"]


def test_corner_badge_claimed_pending_open_none():
    assert projection.corner_badge(CLAIMED) == {"text": "待核销", "tone": "pending"}
    assert projection.corner_badge({**CLAIMED, "status": "open"})["text"] is None


def test_decorate_adds_projection_fields():
    row, _ = _fulfilled_row()
    d = fulfillment.decorate(row)
    assert d["evidence_summary"] == "实物购买 · SO-1"
    assert d["evidence_view"]["channel"] == "purchase"
    assert d["corner_badge"].startswith("✓") and d["corner_tone"] == "done"


def test_projection_tolerates_dirty_evidence():
    row = dict(CLAIMED, status="fulfilled", evidence="not-json", fulfilled_at=None)
    assert projection.parse_evidence(row["evidence"]) is None
    card = projection.done_card(row)
    assert card["summary"] is None and card["status"] == "fulfilled"
    assert projection.corner_badge(row)["text"] == "✓ 已核销"


def test_snapshot_label_is_pinned_even_if_enum_changes():
    # 快照钉住 label：即便渠道目录日后改名，投影仍读快照文案
    row, snap = _fulfilled_row()
    snap["channel_label"] = "旧渠道名"
    row["evidence"] = json.dumps(snap, ensure_ascii=False)
    assert projection.detail_panel(row)["evidence"]["channel_label"] == "旧渠道名"
