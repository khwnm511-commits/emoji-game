"""Repository — تنها لایهٔ دسترسی به دیتابیس. همهٔ خواندن/نوشتن از اینجا."""
import json, time
import asyncpg
from . import db, config, gamedata

_now = time.time


def _row(d: asyncpg.Record) -> dict:
    return dict(d) if d is not None else None


# ——————————————— پلیر ———————————————
async def get_player(pid: int) -> dict | None:
    async with db.pool().acquire() as c:
        p = _row(await c.fetchrow("SELECT * FROM players WHERE id=$1", pid))
    if p:
        p = await _lazy_regen(p)
    return p


async def _lazy_regen(p: dict) -> dict:
    """انرژی و عفونت سرور-ساید روی هر خواندن، دقیق و بدون حلقه."""
    now = int(_now())
    changed = {}
    if p["energy"] < config.MAX_ENERGY and p["energy_ts"] > 0:
        regen = (now - p["energy_ts"]) // config.ENERGY_REGEN_SEC
        if regen > 0:
            changed["energy"] = min(config.MAX_ENERGY, p["energy"] + regen)
            changed["energy_ts"] = now - ((now - p["energy_ts"]) % config.ENERGY_REGEN_SEC)
    # پیشروی عفونت — هر INFECTION_CHECK_SEC یک بررسی سرور-ساید
    if p["infection_stage"] > 0 and p["infection_virus"] and now - p["infection_ts"] > config.INFECTION_CHECK_SEC:
        v = gamedata.VIRUSES[p["infection_virus"]]
        import random
        if random.random() < v["rate"]:
            ns = min(4, p["infection_stage"] + 1)
            changed["infection_stage"] = ns
            # جهش نادر
            if ns >= 3 and random.random() < v["mutation"] and p["infection_virus"] == "t":
                changed["abilities"] = json.dumps(list(set(p["abilities"] + ["t_mut"])))
        changed["infection_ts"] = now
    # پایان بستری/مرگ موقت
    if p["status"] != "active" and p["status_until"] and now > p["status_until"]:
        changed["status"] = "active"
        changed["status_until"] = 0
        changed["hp"] = max(p["hp"], p["max_hp"] // 2)
    if changed:
        await update_player(p["id"], **changed)
        p.update(changed)
        p["abilities"] = json.loads(p["abilities"]) if isinstance(p["abilities"], str) else p["abilities"]
    else:
        p["abilities"] = json.loads(p["abilities"]) if isinstance(p["abilities"], str) else p["abilities"]
        p["story_flags"] = json.loads(p["story_flags"]) if isinstance(p["story_flags"], str) else p["story_flags"]
        p["boost"] = json.loads(p["boost"]) if isinstance(p["boost"], str) else p["boost"]
        p["emojis_owned"] = json.loads(p["emojis_owned"]) if isinstance(p["emojis_owned"], str) else p["emojis_owned"]
    return p


async def create_player(pid: int, name: str, username: str | None, gender: str,
                        appearance: str, background: str) -> dict:
    now = int(_now())
    async with db.pool().acquire() as c:
        await c.execute(
            """INSERT INTO players (id, name, username, gender, appearance, background, energy_ts, created_date, last_active)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$7,$7)""",
            pid, name, username, gender, appearance, background, now)
    return await get_player(pid)


async def update_player(pid: int, **fields):
    if not fields:
        return
    cols, vals = [], []
    for i, (k, v) in enumerate(fields.items(), start=1):
        cols.append(f"{k}=${i}")
        vals.append(v)
    vals.append(pid)
    async with db.pool().acquire() as c:
        await c.execute(f"UPDATE players SET {', '.join(cols)} WHERE id=${len(vals)}", *vals)


async def give(pid: int, coins: int = 0, xp: int = 0, score: int = 0, energy: int = 0,
               heal: int = 0) -> dict:
    """پاداش سرور-ساید — atomic، انرژی منفی مجاز، سطح‌آپ خودکار."""
    async with db.lock(f"player:{pid}"):
        p = await get_player(pid)
        assert p, "player missing"
        f = {}
        if coins:
            f["coins"] = max(0, p["coins"] + coins)
        if energy:
            f["energy"] = min(config.MAX_ENERGY, max(0, p["energy"] + energy))
            if energy > 0 and f["energy"] == config.MAX_ENERGY:
                f["energy_ts"] = int(_now())
        if heal:
            f["hp"] = min(p["max_hp"], p["hp"] + heal)
        if xp or score:
            f["xp"] = p["xp"] + xp
            f["score"] = p["score"] + score
            need = p["level"] * config.XP_PER_LEVEL
            while f["xp"] >= need:
                f["xp"] -= need
                f["level"] = p["level"] + 1 if "level" not in f else f["level"] + 1
                f["max_hp"] = (p["max_hp"] if "max_hp" not in f else f["max_hp"]) + 10
                f["hp"] = (f.get("max_hp", p["max_hp"]))
                f["atk"] = (p["atk"] if "atk" not in f else f["atk"]) + 2
                f["def"] = (p["def"] if "def" not in f else f["def"]) + 1
                need = f["level"] * config.XP_PER_LEVEL
        await update_player(pid, **f)
    return await get_player(pid)


# ——————————————— کوله ———————————————
async def inv(pid: int) -> dict[str, int]:
    async with db.pool().acquire() as c:
        rows = await c.fetch("SELECT item_id, qty FROM inventory WHERE player_id=$1 AND qty>0", pid)
    return {r["item_id"]: r["qty"] for r in rows}


async def inv_add(pid: int, item_id: str, qty: int = 1) -> bool:
    """ظرفیت کوله چک می‌شه."""
    lock = await db.lock(f"inv:{pid}")
    async with lock:
        p = await get_player(pid)
        cur = await inv(pid)
        slots = sum(1 for q in cur.values() if q > 0)
        if item_id not in cur and slots >= p["slots"]:
            return False
        async with db.pool().acquire() as c:
            await c.execute(
                "INSERT INTO inventory VALUES ($1,$2,$3) ON CONFLICT (player_id, item_id) DO UPDATE SET qty=inventory.qty+$3",
                pid, item_id, qty)
    return True


async def inv_take(pid: int, item_id: str, qty: int = 1) -> bool:
    async with db.pool().acquire() as c:
        n = await c.fetchval("SELECT qty FROM inventory WHERE player_id=$1 AND item_id=$2", pid, item_id)
        if not n or n < qty:
            return False
        await c.execute("UPDATE inventory SET qty=qty-$3 WHERE player_id=$1 AND item_id=$2", pid, item_id, qty)
        return True


# ——————————————— مأموریت ———————————————
async def missions_of(pid: int, status: str) -> list[dict]:
    async with db.pool().acquire() as c:
        rows = await c.fetch("SELECT * FROM missions WHERE player_id=$1 AND status=$2 ORDER BY id DESC",
                             pid, status)
    return [_row(r) for r in rows]


async def mission_state(pid: int, mid: str) -> dict | None:
    async with db.pool().acquire() as c:
        return _row(await c.fetchrow(
            "SELECT * FROM missions WHERE player_id=$1 AND mission_id=$2 ORDER BY id DESC LIMIT 1", pid, mid))


async def mission_start(pid: int, mid: str):
    async with db.pool().acquire() as c:
        await c.execute("INSERT INTO missions (player_id, mission_id, region, created_date) VALUES ($1,$2,$3,$4)",
                        pid, mid, gamedata.MISSIONS[mid]["region"], int(_now()))


async def mission_progress(pid: int, mid: str, delta: int = 1):
    async with db.pool().acquire() as c:
        m = await c.fetchrow("SELECT * FROM missions WHERE player_id=$1 AND mission_id=$2 AND status='active' ORDER BY id DESC LIMIT 1", pid, mid)
        if not m:
            return
        prog = m["progress"] + delta
        st = "done" if prog >= gamedata.MISSIONS[mid]["target"] else "active"
        await c.execute("UPDATE missions SET progress=$2, status=$3, done_date=$4 WHERE id=$1",
                        m["id"], prog, st, int(_now()) if st == "done" else 0)


async def mission_claim(pid: int, mid: str):
    async with db.lock(f"player:{pid}"):
        m = await mission_state(pid, mid)
        if not m or m["status"] != "done":
            return None
        async with db.pool().acquire() as c:
            await c.execute("UPDATE missions SET status='claimed' WHERE id=$1", m["id"])
    return gamedata.MISSIONS[mid]


# ——————————————— داستان ———————————————
async def story_log(pid: int, node: str, choice: str):
    async with db.pool().acquire() as c:
        await c.execute("INSERT INTO story_log (player_id, node, choice, ts) VALUES ($1,$2,$3,$4)",
                        pid, node, choice, int(_now()))


# ——————————————— NPC ———————————————
async def npc_rel_get(pid: int, nid: str) -> dict:
    async with db.pool().acquire() as c:
        r = _row(await c.fetchrow("SELECT * FROM npc_rel WHERE player_id=$1 AND npc_id=$2", pid, nid))
    if not r:
        return {"player_id": pid, "npc_id": nid, "trust": 0, "loyalty": 0, "status": "neutral"}
    return r


async def npc_trust_add(pid: int, nid: str, delta: int):
    async with db.pool().acquire() as c:
        await c.execute(
            "INSERT INTO npc_rel VALUES ($1,$2,$3,$4,'neutral') ON CONFLICT (player_id, npc_id) DO UPDATE SET trust=npc_rel.trust+$3",
            pid, nid, delta, 0)


async def npc_all(pid: int) -> dict:
    async with db.pool().acquire() as c:
        rows = await c.fetch("SELECT npc_id, trust FROM npc_rel WHERE player_id=$1", pid)
    return {r["npc_id"]: r["trust"] for r in rows}


# ——————————————— روابط بازیکنان ———————————————
async def rel_get(pid: int, tid: int) -> dict | None:
    async with db.pool().acquire() as c:
        return _row(await c.fetchrow("SELECT * FROM player_rel WHERE player_id=$1 AND target_id=$2", pid, tid))


async def rel_update(pid: int, tid: int, trust=0, loyalty=0, friendship=0, status=None):
    async with db.pool().acquire() as c:
        await c.execute(
            "INSERT INTO player_rel VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (player_id, target_id) DO UPDATE SET trust=player_rel.trust+$3, loyalty=player_rel.loyalty+$4, friendship=player_rel.friendship+$5",
            pid, tid, trust, loyalty, friendship, status or "stranger")
        if status:
            await c.execute("UPDATE player_rel SET status=$3 WHERE player_id=$1 AND target_id=$2", pid, tid, status)


async def rels_of(pid: int) -> list[dict]:
    async with db.pool().acquire() as c:
        rows = await c.fetch(
            "SELECT pr.*, p.name FROM player_rel pr JOIN players p ON p.id=pr.target_id WHERE pr.player_id=$1 ORDER BY pr.friendship DESC LIMIT 10", pid)
    return [_row(r) for r in rows]


# ——————————————— دوستان ———————————————
async def friends_of(pid: int) -> list[dict]:
    async with db.pool().acquire() as c:
        rows = await c.fetch("SELECT f.friend_id, p.name FROM friends f JOIN players p ON p.id=f.friend_id WHERE f.player_id=$1", pid)
    return [_row(r) for r in rows]


async def friend_add(pid: int, fid: int) -> bool:
    if pid == fid:
        return False
    async with db.pool().acquire() as c:
        if not await c.fetchval("SELECT 1 FROM players WHERE id=$1", fid):
            return False
        await c.execute("INSERT INTO friends VALUES ($1,$2,$3) ON CONFLICT DO NOTHING", pid, fid, int(_now()))
        await c.execute("INSERT INTO friends VALUES ($1,$2,$3) ON CONFLICT DO NOTHING", fid, pid, int(_now()))
    return True


# ——————————————— کلن ———————————————
async def my_clan(pid: int) -> dict | None:
    async with db.pool().acquire() as c:
        m = _row(await c.fetchrow(
            "SELECT c.* FROM clans c JOIN clan_members cm ON cm.clan_id=c.id WHERE cm.player_id=$1", pid))
    return m


async def clan_create(pid: int, name: str) -> str | None:
    async with db.pool().acquire() as c:
        try:
            cid = await c.fetchval("INSERT INTO clans (name, leader_id, created_date) VALUES ($1,$2,$3) RETURNING id",
                                   name, pid, int(_now()))
            await c.execute("INSERT INTO clan_members VALUES ($1,$2,'leader')", pid, cid)
        except asyncpg.UniqueViolationError:
            return None
    return cid


async def clan_join(pid: int, cid: int) -> bool:
    async with db.lock(f"player:{pid}"):
        async with db.pool().acquire() as c:
            if await c.fetchval("SELECT 1 FROM clan_members WHERE player_id=$1", pid):
                return False
            await c.execute("INSERT INTO clan_members VALUES ($1,$2,'member')", pid, cid)
    return True


async def clans_top(limit: int = 10) -> list[dict]:
    async with db.pool().acquire() as c:
        rows = await c.fetch("SELECT * FROM clans ORDER BY points DESC LIMIT $1", limit)
    return [_row(r) for r in rows]


# ——————————————— نبردها ———————————————
async def battle_create(kind: str, p1: int, p2: int | None = None, enemy_id: str | None = None,
                        chat_id: int = 0, state: dict | None = None) -> int:
    async with db.pool().acquire() as c:
        return await c.fetchval(
            "INSERT INTO battles (kind, chat_id, p1, p2, enemy_id, state, created_date) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id",
            kind, chat_id, p1, p2, enemy_id, json.dumps(state or {}), int(_now()))


async def battle_active(pid: int) -> dict | None:
    async with db.pool().acquire() as c:
        r = await c.fetchrow(
            "SELECT * FROM battles WHERE active AND (p1=$1 OR p2=$1) ORDER BY id DESC LIMIT 1", pid)
    if not r:
        return None
    b = _row(r)
    b["state"] = json.loads(b["state"]) if isinstance(b["state"], str) else b["state"]
    return b


async def battle_update(bid: int, state: dict, turn: int | None = None, active: bool | None = None):
    sets = ["state=$2"]
    vals = [json.dumps(state)]
    if turn is not None:
        sets.append(f"turn=${len(vals)+1}"); vals.append(turn)
    if active is not None:
        sets.append(f"active=${len(vals)+1}"); vals.append(active)
    vals.append(bid)
    async with db.pool().acquire() as c:
        await c.execute(f"UPDATE battles SET {', '.join(sets)} WHERE id=${len(vals)}", *vals)


async def battle_get(bid: int) -> dict | None:
    async with db.pool().acquire() as c:
        r = await c.fetchrow("SELECT * FROM battles WHERE id=$1", bid)
    if not r:
        return None
    b = _row(r)
    b["state"] = json.loads(b["state"]) if isinstance(b["state"], str) else b["state"]
    return b


async def battle_deactivate(bid: int):
    async with db.pool().acquire() as c:
        await c.execute("UPDATE battles SET active=FALSE WHERE id=$1", bid)


# ——————————————— باس ———————————————
async def boss_event_create(boss_id: str, chat_id: int, starts_at: int, ends_at: int) -> int:
    b = gamedata.BOSSES[boss_id]
    async with db.pool().acquire() as c:
        return await c.fetchval(
            "INSERT INTO boss_events (boss_id, region, chat_id, hp, max_hp, starts_at, ends_at, created_date) VALUES ($1,$2,$3,$4,$4,$5,$6,$7) RETURNING id",
            boss_id, b["region"], chat_id, b["hp"], starts_at, ends_at, int(_now()))


async def boss_active(chat_id: int | None = None) -> list[dict]:
    q = "SELECT * FROM boss_events WHERE status='active' AND ends_at > $1"
    args = [int(_now())]
    if chat_id is not None:
        q += " AND (chat_id=$2 OR chat_id=0)"
        args.append(chat_id)
    async with db.pool().acquire() as c:
        rows = await c.fetch(q, *args)
    return [_row(r) for r in rows]


async def boss_by_id(eid: int) -> dict | None:
    async with db.pool().acquire() as c:
        return _row(await c.fetchrow("SELECT * FROM boss_events WHERE id=$1", eid))


async def boss_hit(eid: int, pid: int, dmg: int) -> dict:
    """ضربهٔ اتمیک به باس — قفل روی ایونت. برمی‌گرداند وضعیت جدید + فاز."""
    async with db.lock(f"boss:{eid}"):
        async with db.pool().acquire() as c:
            e = _row(await c.fetchrow("SELECT * FROM boss_events WHERE id=$1 FOR UPDATE", eid))
            if not e or e["status"] != "active":
                return {"ok": False, "why": "این باس دیگه فعال نیست"}
            hp = max(0, e["hp"] - dmg)
            ranking = json.loads(e["ranking"]) if isinstance(e["ranking"], str) else e["ranking"]
            ranking[str(pid)] = ranking.get(str(pid), 0) + dmg
            status = "active" if hp > 0 else "killed"
            await c.execute("UPDATE boss_events SET hp=$2, ranking=$3, status=$4 WHERE id=$1",
                            eid, hp, json.dumps(ranking), status)
            await c.execute("INSERT INTO boss_hits (event_id, player_id, dmg, ts) VALUES ($1,$2,$3,$4)",
                            eid, pid, dmg, int(_now()))
            # امتیاز کلن
            m = await c.fetchrow("SELECT clan_id FROM clan_members WHERE player_id=$1", pid)
            if m:
                week = time.strftime("%Y-W%W")
                await c.execute(
                    "INSERT INTO clan_war (week, clan_id, points) VALUES ($1,$2,$3) ON CONFLICT (week, clan_id) DO UPDATE SET points=clan_war.points+$3",
                    week, m["clan_id"], dmg)
                await c.execute("UPDATE clans SET points=points+$2 WHERE id=$1", m["clan_id"], dmg)
            # فاز
            b = gamedata.BOSSES[e["boss_id"]]
            frac = hp / e["max_hp"]
            phase = 1
            for ph in b["phases"][1:]:
                if frac <= ph["hp"]:
                    phase += 1
            return {"ok": True, "hp": hp, "max_hp": e["max_hp"], "status": status,
                    "phase": min(phase, len(b["phases"])), "ranking": ranking, "boss_id": e["boss_id"]}


async def boss_set_msg(eid: int, chat_id: int, msg_id: int):
    async with db.pool().acquire() as c:
        await c.execute("UPDATE boss_events SET msg_chat_id=$2, msg_id=$3 WHERE id=$1", eid, chat_id, msg_id)


async def boss_set_status(eid: int, status: str):
    async with db.pool().acquire() as c:
        await c.execute("UPDATE boss_events SET status=$2 WHERE id=$1", eid, status)


async def boss_last(boss_id: str) -> dict | None:
    async with db.pool().acquire() as c:
        return _row(await c.fetchrow(
            "SELECT * FROM boss_events WHERE boss_id=$1 ORDER BY id DESC LIMIT 1", boss_id))


# ——————————————— جهان گروه ———————————————
async def world_get(chat_id: int) -> dict | None:
    async with db.pool().acquire() as c:
        return _row(await c.fetchrow("SELECT * FROM worlds WHERE chat_id=$1", chat_id))


async def world_create(chat_id: int, name: str) -> bool:
    async with db.pool().acquire() as c:
        if await c.fetchval("SELECT 1 FROM worlds WHERE chat_id=$1", chat_id):
            return False
        await c.execute("INSERT INTO worlds VALUES ($1,$2,1,0,$3)", chat_id, name[:60], int(_now()))
    return True


# ——————————————— رویداد جهانی ———————————————
async def event_active(kind: str | None = None) -> list[dict]:
    q = "SELECT * FROM events WHERE ends_at > $1 AND starts_at <= $1"
    args = [int(_now())]
    if kind:
        q += " AND kind=$2"; args.append(kind)
    async with db.pool().acquire() as c:
        rows = await c.fetch(q, *args)
    return [_row(r) for r in rows]


async def event_create(kind: str, starts_at: int, ends_at: int, data: dict | None = None):
    async with db.pool().acquire() as c:
        await c.execute("INSERT INTO events (kind, data, starts_at, ends_at) VALUES ($1,$2,$3,$4)",
                        kind, json.dumps(data or {}), starts_at, ends_at)


async def event_announced(eid: int):
    async with db.pool().acquire() as c:
        await c.execute("UPDATE events SET announced=TRUE WHERE id=$1", eid)


# ——————————————— خرید ———————————————
async def purchase_record(pid: int, pack: str, charge_id: str, stars: int) -> bool:
    try:
        async with db.pool().acquire() as c:
            await c.execute("INSERT INTO purchases VALUES (DEFAULT,$1,$2,$3,$4,$5)",
                            pid, pack, charge_id, stars, int(_now()))
        return True
    except asyncpg.UniqueViolationError:
        return False


# ——————————————— رتبه‌بندی ———————————————
async def top_players(limit: int = 10) -> list[dict]:
    async with db.pool().acquire() as c:
        rows = await c.fetch("SELECT name, level, score FROM players ORDER BY score DESC LIMIT $1", limit)
    return [_row(r) for r in rows]


# ——————————————— ایموجی ———————————————
async def emoji_buy(pid: int, num: int, coins: int) -> bool:
    async with db.lock(f"player:{pid}"):
        p = await get_player(pid)
        owned = p["emojis_owned"]
        if num in owned or p["coins"] < coins:
            return False
        await update_player(pid, coins=p["coins"] - coins, emojis_owned=json.dumps(owned + [num]))
    return True
