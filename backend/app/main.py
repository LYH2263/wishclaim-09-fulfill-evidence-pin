import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.engines.claim_lock import claim_allowed, lock_payload, release_if_expired
from app.modules.fulfillment import channels as proof_channels
from app.modules.fulfillment import freeze as proof_freeze
from app.modules.fulfillment import preview as proof_preview
from app.modules.fulfillment import projection as proof_proj

app = FastAPI(title="Wishclaim", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup(): seed.init_db()

def now(): return datetime.now(timezone.utc)

def ttl():
    c = connect(); row = c.execute("SELECT value FROM settings WHERE key='ttl_seconds'").fetchone(); c.close()
    return int(row["value"] if row else 86400)

def sweep(c):
    for r in c.execute("SELECT * FROM wishes WHERE status='claimed'"):
        rel = release_if_expired(r["status"], r["expires_at"], now())
        if rel:
            c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=? WHERE id=?",
                      (rel["status"], None, None, None, r["id"]))

def serialize(r) -> dict:
    """行 → 对外读模型：解码举证快照，并钉上墙角标/已完成摘要/详情举证区三路投影。"""
    d = dict(r)
    raw = d.pop("proof_snapshot", None)
    snap = json.loads(raw) if raw else None
    d["proof"] = proof_proj.detail(snap)
    d["proof_badge"] = proof_proj.badge(snap)
    d["proof_card"] = proof_proj.card(snap)
    return d

@app.get("/api/health")
def health(): return {"ok": True, "project": "wishclaim"}

@app.get("/api/wishes")
def list_wishes():
    c = connect(); sweep(c); c.commit()
    rows = [serialize(r) for r in c.execute("SELECT * FROM wishes ORDER BY id DESC")]; c.close(); return rows

@app.get("/api/wishes/{wid}")
def get_wish(wid: int):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    d = serialize(r); c.close(); return d

class WishIn(BaseModel):
    title: str
    note: str = ""

@app.post("/api/wishes")
def create_wish(body: WishIn):
    c = connect()
    cur = c.execute("INSERT INTO wishes(title,note,status,data_quality) VALUES (?,?,?,?)",
                    (body.title, body.note, "open", "clean"))
    c.commit(); wid = cur.lastrowid; c.close(); return {"id": wid}

class ClaimIn(BaseModel):
    claimer: str

@app.post("/api/wishes/{wid}/claim")
def claim(wid: int, body: ClaimIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    allowed = claim_allowed(r["status"], r["claimer"], now(), r["expires_at"])
    if not allowed["ok"]:
        c.close(); raise HTTPException(409, allowed["reason"])
    p = lock_payload(body.claimer, now(), ttl())
    c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=? WHERE id=?",
              (p["status"], p["claimer"], p["claimed_at"], p["expires_at"], wid))
    c.commit(); c.close(); return p

@app.post("/api/wishes/{wid}/release")
def release(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "not_claimed")
    c.execute("UPDATE wishes SET status='released', claimer=NULL, claimed_at=NULL, expires_at=NULL WHERE id=?", (wid,))
    c.commit(); c.close(); return {"ok": True, "status": "released"}

class FulfillIn(BaseModel):
    channel: str
    ref: str
    note: str

@app.get("/api/fulfillment/channels")
def fulfillment_channels():
    return {"channels": proof_channels.list_channels()}

@app.get("/api/wishes/{wid}/proof-preview")
def proof_preview_route(wid: int):
    """举证包预览（摘要 + 渠道枚举）；纯读，不改 status。"""
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    snap = json.loads(r["proof_snapshot"]) if r["proof_snapshot"] else None
    pv = proof_preview.build_preview(r["status"], r["claimer"], snap)
    c.close(); return {"wish_id": wid, "status": r["status"], **pv}

@app.post("/api/wishes/{wid}/fulfill")
def fulfill(wid: int, body: FulfillIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    v = proof_freeze.validate(r["status"], body.model_dump())
    if not v["ok"]:
        c.close()
        if v.get("missing"):
            raise HTTPException(v["status"], detail={"code": v["reason"], "missing": v["missing"]})
        raise HTTPException(v["status"], v["reason"])
    snap = proof_freeze.build_snapshot(body.model_dump(), r["claimer"], now())
    c.execute("UPDATE wishes SET status='fulfilled', proof_snapshot=?, fulfilled_at=? WHERE id=?",
              (json.dumps(snap, ensure_ascii=False), snap["fulfilled_at"], wid))
    c.commit(); c.close()
    return {"ok": True, "status": "fulfilled", "proof": snap}

@app.get("/api/mine")
def mine(claimer: str):
    c = connect(); sweep(c); c.commit()
    rows = [serialize(r) for r in c.execute("SELECT * FROM wishes WHERE claimer=?", (claimer,))]; c.close(); return rows

@app.get("/api/done")
def done():
    # 未核销不得出现在已完成页：只投影 status=fulfilled
    c = connect()
    rows = [serialize(r) for r in c.execute(
        "SELECT * FROM wishes WHERE status='fulfilled' ORDER BY fulfilled_at DESC, id DESC")]
    c.close(); return rows

@app.get("/api/settings")
def settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close(); return rows

@app.get("/api/rules")
def rules():
    return {
        "mutex": "同一愿望同时只能被一人认领",
        "ttl": "认领超时未核销则自动释放",
        "fulfill": "核销须提交完整举证（渠道枚举+凭证号+说明），快照冻结后不可再改，状态变为 fulfilled",
    }
