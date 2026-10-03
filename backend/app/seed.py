import json

from app.db import connect


def init_db():
    c = connect()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS wishes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, note TEXT, status TEXT,
      claimer TEXT, claimed_at TEXT, expires_at TEXT, data_quality TEXT,
      proof_snapshot TEXT, fulfilled_at TEXT
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    """)
    # 旧库迁移：核销举证快照列
    cols = {r["name"] for r in c.execute("PRAGMA table_info(wishes)")}
    if "proof_snapshot" not in cols:
        c.execute("ALTER TABLE wishes ADD COLUMN proof_snapshot TEXT")
    if "fulfilled_at" not in cols:
        c.execute("ALTER TABLE wishes ADD COLUMN fulfilled_at TEXT")

    if c.execute("SELECT COUNT(*) c FROM wishes").fetchone()["c"] == 0:
        fulfilled_proof = {
            "channel": "express_delivery",
            "channel_label": "快递寄送",
            "channel_short": "快递",
            "channel_icon": "📦",
            "ref": "SF10245520",
            "note": "已签收，收件人确认无误",
            "claimer": "momo",
            "fulfilled_at": "2026-01-05T09:30:00+00:00",
        }
        c.executemany(
            "INSERT INTO wishes(title,note,status,claimer,claimed_at,expires_at,"
            "data_quality,proof_snapshot,fulfilled_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ("机械键盘", "红轴", "open", None, None, None, "clean", None, None),
                ("围巾", "羊毛", "open", None, None, None, "clean", None, None),
                ("脏愿望-空标题", "", "open", None, None, None, "dirty", None, None),
                ("过期锁样例", "应被TTL释放", "claimed", "ghost", "2020-01-01T00:00:00+00:00",
                 "2020-01-01T01:00:00+00:00", "dirty", None, None),
                ("羊毛围巾", "生日礼物", "fulfilled", "momo", "2026-01-04T20:00:00+00:00", None,
                 "clean", json.dumps(fulfilled_proof, ensure_ascii=False),
                 fulfilled_proof["fulfilled_at"]),
            ],
        )
        c.execute("INSERT INTO settings(key,value) VALUES ('ttl_seconds','86400')")
        c.execute("INSERT INTO settings(key,value) VALUES ('wall_title','暖粉愿望墙')")
        c.commit()
    c.close()
