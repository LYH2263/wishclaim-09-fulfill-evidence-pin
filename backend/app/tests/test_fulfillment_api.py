PROOF = {"channel": "express_delivery", "ref": "SF-API-1", "note": "收件人已签收"}


def _new_claimed(client):
    wid = client.post("/api/wishes", json={"title": "举证链路", "note": "x"}).json()["id"]
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "alice"})
    return wid


def test_channels_served_by_backend(client):
    vals = {c["value"] for c in client.get("/api/fulfillment/channels").json()["channels"]}
    assert "express_delivery" in vals and "自由文本渠道" not in vals


def test_preview_does_not_change_status(client):
    wid = _new_claimed(client)
    r = client.get(f"/api/wishes/{wid}/proof-preview")
    assert r.status_code == 200
    pv = r.json()
    assert pv["status"] == "claimed" and pv["can_submit"] and pv["channels"]
    # 预览后仍是 claimed
    assert client.get(f"/api/wishes/{wid}").json()["status"] == "claimed"


def test_incomplete_proof_rejected_and_stays_claimed(client):
    wid = _new_claimed(client)
    r = client.post(f"/api/wishes/{wid}/fulfill",
                    json={"channel": "express_delivery", "ref": "", "note": "  "})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "proof_incomplete"
    assert "ref" in r.json()["detail"]["missing"]
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "claimed" and w["proof"] is None


def test_bad_channel_rejected(client):
    wid = _new_claimed(client)
    r = client.post(f"/api/wishes/{wid}/fulfill",
                    json={"channel": "carrier_pigeon", "ref": "1", "note": "x"})
    assert r.status_code == 422 and r.json()["detail"] == "bad_channel"
    assert client.get(f"/api/wishes/{wid}").json()["status"] == "claimed"


def test_fulfill_freezes_snapshot_and_locks_rewrite(client):
    wid = _new_claimed(client)
    r = client.post(f"/api/wishes/{wid}/fulfill", json=PROOF)
    assert r.status_code == 200 and r.json()["status"] == "fulfilled"
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "fulfilled" and w["proof"]["ref"] == "SF-API-1"
    assert w["proof_badge"] and "已核销" in w["proof_badge"]["text"]
    assert w["proof_card"]["summary"]
    # 核销后禁止再改举证
    again = client.post(f"/api/wishes/{wid}/fulfill", json=PROOF)
    assert again.status_code == 409 and again.json()["detail"] == "proof_frozen"


def test_cannot_fulfill_open_wish(client):
    wid = client.post("/api/wishes", json={"title": "无人认领", "note": ""}).json()["id"]
    assert client.post(f"/api/wishes/{wid}/fulfill", json=PROOF).status_code == 400


def test_done_only_lists_fulfilled_with_proof_summary(client):
    wid = _new_claimed(client)
    client.post(f"/api/wishes/{wid}/fulfill", json=PROOF)
    by_id = {r["id"]: r for r in client.get("/api/done").json()}
    assert wid in by_id
    assert by_id[wid]["status"] == "fulfilled" and by_id[wid]["proof_card"]["ref"] == "SF-API-1"
    # 未核销不得出现在已完成页
    open_id = client.post("/api/wishes", json={"title": "未核销", "note": ""}).json()["id"]
    claimed_id = _new_claimed(client)
    assert open_id not in by_id and claimed_id not in by_id
