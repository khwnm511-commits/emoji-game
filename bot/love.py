import time
from . import db

# NPCهای داستانی — هر کدوم شخصیت و هدف خودشون رو دارن
NPCS = [
    ("آرش جنگجو", "⚔️ سرباز شهر — شجاع ولی بی‌حوصله"),
    ("مینا درمانگر", "💫 شفادهده روستا — مهربون و محتاط"),
    ("کاوه بازرگان", "🛒 تاجر مسافری — فقط منفعت مهمه براش"),
    ("شیرین دزد", "🗡 عضو گروه سایه — رازدار و شکاک"),
    ("استاد بهرام", "🧙 عابد کوهستان — حکیم و کم‌حرف"),
]

STATUS_ORDER = ["stranger", "friend", "close", "partner"]
BAD = ["rival", "enemy"]

def calc_status(trust, loyalty, respect, broken_before):
    """وضعیت از رفتار میاد، نه از دکمه."""
    if trust <= -30:
        return "enemy"
    if trust < -10:
        return "rival"
    if broken_before:
        return "friend" if trust >= 60 else "stranger"  # بعد از قطع رابطه، دوباره بالاتر نمی‌ره
    if trust >= 80 and respect >= 40 and loyalty >= 40:
        return "partner"
    if trust >= 50:
        return "close"
    if trust >= 20:
        return "friend"
    return "stranger"

async def list_rels(pid):
    cur = await (await db.db()).execute(
        "SELECT * FROM relationships WHERE player_id=? ORDER BY history DESC", (pid,))
    return await cur.fetchall()

async def get_rel(pid, rel_id):
    cur = await (await db.db()).execute(
        "SELECT * FROM relationships WHERE id=? AND player_id=?", (rel_id, pid))
    return await cur.fetchone()

async def upsert_rel(pid, target_id, target_name, is_npc):
    cur = await (await db.db()).execute(
        "SELECT * FROM relationships WHERE player_id=? AND target_id=?", (pid, target_id))
    r = await cur.fetchone()
    if r:
        return r
    broken_before = False
    cur = await (await db.db()).execute(
        "SELECT 1 FROM relationships WHERE player_id=? AND target_id=? AND broken=1", (pid, target_id))
    if await cur.fetchone():
        broken_before = True  # سابقه قطع رابطه برای همیشه می‌مونه
    await (await db.db()).execute(
        """INSERT INTO relationships(player_id,target_id,target_name,is_npc,hidden,created_date,last_action)
           VALUES(?,?,?,?,1,?,?)
           ON CONFLICT(player_id,target_id) DO NOTHING""",
        (pid, target_id, target_name, 1 if is_npc else 0, int(time.time()), int(time.time())))
    await (await db.db()).commit()
    cur = await (await db.db()).execute(
        "SELECT * FROM relationships WHERE player_id=? AND target_id=?", (pid, target_id))
    return await cur.fetchone()

async def act(pid, rel_id, kind):
    """رفتار بازیکن → تغییر trust/loyalty/respect/history + عواقب بلندمدت."""
    r = await get_rel(pid, rel_id)
    if not r:
        return None
    trust, loyalty, respect, history = r["trust"], r["loyalty"], r["respect"], r["history"]
    msg = ""
    now = int(time.time())
    cooldown = now - r["last_action"] < 120  # هر ۲ دقیقه یک تعامل
    if cooldown:
        return {"cooldown": True}

    if kind == "gift":      # هدیه → اعتماد
        trust += 6 + history // 50
        history += 2
        msg = "🎁 هدیه‌ت اثر گذاشت — اعتماد بیشتر شد."
    elif kind == "help":    # کمک در مأموریت → وفاداری
        loyalty += 7
        trust += 3
        history += 3
        msg = "🤝 کنارش جنگیدی — وفاداری بالاتر رفت."
    elif kind == "resp":    # احترام
        respect += 6
        trust += 1
        history += 1
        msg = "🙏 احترامت به چشم اومد."
    elif kind == "hist":    # وقت گذراندن → سابقه
        history += 5
        trust += 2
        msg = "⏳ سابقه مشترکتون عمیق‌تر شد."
    elif kind == "lie":     # دروغ — اثر بلندمدت
        trust -= 15
        respect -= 8
        msg = "🤥 دروغت لو رفت — اعتماد آسیب جدی دید."
    elif kind == "betray":  # خیانت — دشمنی + تغییر داستان
        trust -= 40
        loyalty -= 30
        respect -= 25
        betray_count = r["betray_count"] + 1
        await (await db.db()).execute(
            "UPDATE relationships SET betray_count=? WHERE id=?", (betray_count, rel_id))
        await db.update_player(pid, betrayals=(await db.get_player(pid))["betrayals"] + 1)
        msg = "⚔️ خیانت کردی — این کار هیچ‌وقت فراموش نمی‌شه و ممکنه مأموریت‌ها عوض بشن."
    elif kind == "propose":
        if r["is_npc"]:
            if trust >= 60:
                trust += 5
                msg = "💗 قبول کرد! رابطه شروع شد."
            else:
                trust -= 5
                msg = f"😔 هنوز به تو اعتماد کافی نداره... (علاقه یک‌طرفه فعلاً)"
        else:
            return {"need_accept": r}  # بازیکن واقعی باید قبول کنه
    elif kind == "break":
        await (await db.db()).execute(
            "UPDATE relationships SET broken=1, status='broken' WHERE id=?", (rel_id,))
        await db.update_player(pid, broken_hearts=(await db.get_player(pid))["broken_hearts"] + 1)
        await (await db.db()).commit()
        return {"broken": True, "msg": "💔 رابطه قطع شد. سابقه‌ش برای همیشه توی پرونده‌ست و روابط بعدی رو سخت‌تر می‌کنه."}

    broken_before = bool(r["broken"])
    status = calc_status(trust, loyalty, respect, broken_before)
    hidden = 1 if (r["hidden"] and trust < 50) else 0  # رابطه مخفی تا آشکار شدن
    await (await db.db()).execute(
        """UPDATE relationships SET trust=?, loyalty=?, respect=?, history=?, status=?, hidden=?, last_action=?
           WHERE id=?""",
        (trust, loyalty, respect, history, status, hidden, now, rel_id))
    await (await db.db()).commit()
    return {"msg": msg, "status": status, "trust": trust, "loyalty": loyalty,
            "respect": respect, "history": history, "hidden": hidden}

def rel_bonus(rel):
    """اثر رابطه روی گیم‌پلی — فقط تزئینی نیست."""
    if rel and rel["status"] == "partner" and rel["trust"] >= 70:
        return 0.10  # پارتنر تو نبرد کمکت می‌کنه: +۱۰٪ حمله
    if rel and rel["status"] == "enemy":
        return -0.05
    return 0

async def partner_bonus(pid):
    cur = await (await db.db()).execute(
        "SELECT * FROM relationships WHERE player_id=? AND status='partner' ORDER BY trust DESC LIMIT 1",
        (pid,))
    r = await cur.fetchone()
    return rel_bonus(r)
