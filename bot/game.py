import json, time, random
from . import db, config

# ——————————————— انرژی و سطح ———————————————
async def regen_energy(player):
    """انرژی با زمان پر می‌شه — بدون تسک، موقع هر اکشن چک می‌شه."""
    now = int(time.time())
    gain = (now - player["last_active"]) // config.ENERGY_REGEN_SEC
    if gain > 0 and player["energy"] < config.MAX_ENERGY:
        energy = min(config.MAX_ENERGY, player["energy"] + gain)
        await db.update_player(player["id"], energy=energy, last_active=now)
        return {**player, "energy": energy}
    return player

async def spend_energy(pid, amount=config.ENERGY_PER_ACTION):
    p = await db.get_player(pid)
    p = await regen_energy(p)
    if p["energy"] < amount:
        return False, p
    await db.update_player(pid, energy=p["energy"] - amount, last_active=int(time.time()))
    return True, p

async def check_level(pid, p):
    """سطح‌بندی — امتیاز و سطوح هیچ‌وقت کم نمی‌شن."""
    need = await db.xp_for_level(p["level"])
    leveled = 0
    while p["xp"] >= need:
        p = {**p, "xp": p["xp"] - need, "level": p["level"] + 1,
             "max_hp": p["max_hp"] + 15, "attack": p["attack"] + 2, "defense": p["defense"] + 1}
        need = await db.xp_for_level(p["level"])
        leveled += 1
    if leveled:
        p["hp"] = p["max_hp"]  # لول آپ → شارژ کامل
        await db.update_player(pid, xp=p["xp"], level=p["level"], max_hp=p["max_hp"],
                               attack=p["attack"], defense=p["defense"], hp=p["hp"])
    return p, leveled

MOBS = [
    ("🐀 موش غول‌پیکر", 40, 8, 2),
    ("🦂 عقرب صحرا", 60, 12, 4),
    ("🐺 گرگ گرسنه", 90, 16, 6),
    ("🧟 زامبی سرگردان", 120, 20, 8),
    ("👻 روح جنگل", 160, 26, 12),
    ("🦂 عنکبوت ملکه", 220, 32, 16),
]

def roll_mob(level: int):
    i = min(len(MOBS) - 1, level // 3 + random.randint(0, 2))
    return MOBS[i]

def dmg(atk, dfn):
    base = max(2, atk - dfn // 2)
    return max(1, base + random.randint(-2, 4))

# ——————————————— PvE نوبتی ———————————————
async def start_pve(pid, p):
    name, hp, atk, dfn = roll_mob(p["level"])
    hp = int(hp * (1 + p["level"] * 0.08))
    atk = int(atk * (1 + p["level"] * 0.05))
    state = {"kind": "pve", "npc": name, "hp": hp, "max_hp": hp, "atk": atk, "dfn": dfn,
             "p_hp": p["hp"], "guard": False, "skill_ready": True}
    cur = await (await db.db()).execute(
        "INSERT INTO battles(kind,p1,npc,state,active,created_date) VALUES('pve',?,?,?,1,?)",
        ("pve", pid, name, json.dumps(state), int(time.time())))
    await (await db.db()).commit()
    return cur.lastrowid, state

async def active_battle(pid):
    cur = await (await db.db()).execute(
        "SELECT * FROM battles WHERE active=1 AND (p1=? OR p2=?) ORDER BY id DESC LIMIT 1", (pid, pid))
    return await cur.fetchone()

async def close_battle(bid):
    await (await db.db()).execute("UPDATE battles SET active=0 WHERE id=?", (bid,))
    await (await db.db()).commit()

async def save_state(bid, state, turn=1):
    await (await db.db()).execute(
        "UPDATE battles SET state=?, turn=? WHERE id=?", (json.dumps(state), turn, bid))
    await (await db.db()).commit()

# ——————————————— ویروس ———————————————
async def infect(attacker, victim):
    now = int(time.time())
    if now - attacker["last_infect"] < 300:  # هر ۵ دقیقه یک آلودگی
        return "cooldown", None
    if victim["infected_until"] and victim["infected_until"] > now:
        return "already", None
    dur = 3600 * (1 + attacker["level"] // 10)  # ۱ ساعت + سطح
    await db.update_player(victim["id"], infected_by=attacker["id"], infected_until=now + dur)
    await db.update_player(attacker["id"], last_infect=now)
    return "ok", now + dur

async def apply_infection_tick(p):
    """عفونت فعال: هر ساعت HP کم می‌شه ولی امتیاز هیچ‌وقت! (امتیاز فقط برای مبتلا‌کننده است)"""
    now = int(time.time())
    if p["infected_until"] and p["infected_until"] > now:
        hours = (now - (p["last_active"] or now)) // 3600
        if hours >= 1:
            hp = max(1, p["hp"] - 2 * hours)  # نمی‌میره، فقط ضعیف می‌شه
            await db.update_player(p["id"], hp=hp)
            if p["infected_by"]:
                await db.add_score(p["infected_by"], config.SCORE_INFECTION_HOUR * hours)
        return True
    elif p["infected_until"]:
        await db.update_player(p["id"], infected_by=None, infected_until=None)
    return False
