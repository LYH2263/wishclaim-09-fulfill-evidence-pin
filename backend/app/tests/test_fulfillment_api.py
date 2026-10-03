"""核销举证全链路 API 测试：预览、冻结写库、投影落地、已完成隔离。"""
from fastapi.testclient import TestClient

from app.main import app
from app.modules.fulfillment.channels import CHANNEL_KEYS

client = TestClient(app)


def _claimed_wish():
    wid = client.post("/api/wishes", json={"title": "钢笔", "note": "EF 尖"}).json()["id"]
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "alice"})
    return wid


def test_channels_endpoint_is_enum_source():
    keys = [c["key"] for c in client.get("/api/fulfillment/channels").json()["channels"]]
    assert keys == list(CHANNEL_KEYS)


def test_preview_does_not_change_status():
    wid = _claimed_wish()
    r = client.post(f"/api/wishes/{wid}/fulfill/preview",
                    json={"channel": "purchase", "reference": "SO-7"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "claimed" and body["persisted"] is False and body["ready"] is True
    # 库里仍是 claimed，无举证
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "claimed" and w["evidence_view"] is None


def test_incomplete_fulfill_rejected_and_stays_claimed():
    wid = _claimed_wish()
    for payload in ({}, {"channel": "purchase"}, {"channel": "purchase", "reference": "  "}):
        r = client.post(f"/api/wishes/{wid}/fulfill", json=payload)
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "incomplete_evidence"
        w = client.get(f"/api/wishes/{wid}").json()
        assert w["status"] == "claimed" and w["evidence"] is None


def test_free_text_channel_rejected():
    wid = _claimed_wish()
    r = client.post(f"/api/wishes/{wid}/fulfill",
                    json={"channel": "私信发截图", "reference": "X1"})
    assert r.status_code == 400
    assert "channel_invalid" in r.json()["detail"]["errors"]


def test_fulfreeze_then_three_projections_and_no_rewrite():
    wid = _claimed_wish()
    r = client.post(f"/api/wishes/{wid}/fulfill",
                    json={"channel": "handmade", "reference": "WIP-2", "note": "织了两周"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "fulfilled"
    assert body["snapshot"]["reference"] == "WIP-2"
    assert body["panel"]["frozen"] is True

    # 详情举证区
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "fulfilled"
    assert w["evidence_view"]["channel_label"] == "手工制作"
    assert w["evidence_view"]["frozen"] is True
    assert w["evidence_summary"] == "手工制作 · WIP-2"
    # 墙角标
    assert w["corner_tone"] == "done" and "手工制作" in w["corner_badge"]

    # 已完成列表摘要
    done = client.get("/api/done").json()
    card = next(c for c in done if c["id"] == wid)
    assert card["summary"] == "手工制作 · WIP-2" and card["status"] == "fulfilled"

    # 核销后禁止再改举证
    r2 = client.post(f"/api/wishes/{wid}/fulfill",
                     json={"channel": "other", "reference": "HACK", "note": "改"})
    assert r2.status_code == 409
    assert client.get(f"/api/wishes/{wid}").json()["evidence_view"]["reference"] == "WIP-2"


def test_unfulfilled_never_in_done():
    wid = _claimed_wish()
    ids = [c["id"] for c in client.get("/api/done").json()]
    assert wid not in ids


def test_cannot_fulfill_open_wish():
    wid = client.post("/api/wishes", json={"title": "杯", "note": ""}).json()["id"]
    r = client.post(f"/api/wishes/{wid}/fulfill",
                    json={"channel": "purchase", "reference": "SO-9"})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "need_claim"


def test_preview_only_for_claimed():
    # open 不能预览
    wid = client.post("/api/wishes", json={"title": "碟", "note": ""}).json()["id"]
    assert client.post(f"/api/wishes/{wid}/fulfill/preview", json={}).status_code == 400
    # fulfilled 后预览也关闭（举证已冻结）
    wid2 = _claimed_wish()
    client.post(f"/api/wishes/{wid2}/fulfill",
                json={"channel": "other", "reference": "DONE", "note": ""})
    assert client.post(f"/api/wishes/{wid2}/fulfill/preview",
                       json={"channel": "other", "reference": "X"}).status_code == 409
