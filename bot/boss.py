import json, time, asyncio
from aiogram import Bot
from . import db, config

PHASES = {
    1: "🌀 فاز ۱ — آرامش قبل طوفان",
    2: "🔥 فاز ۲ — خشم باس!",
    3: "💀 فاز ۳ — مرگ یا زندگی",
}

async def avg_player_power():
    cur = await (await db.db()).execute(
        "SELECT COUNT(*) c, AVG(attack) a FROM players WHERE last_active > ?",
        (int(time.time()) - 86400,))
    row = await cur.fetchone()
    n, avg_atk = row["c"] or 1, row["a"] or 10
    return n, avg_atk

async def schedule_hp(kind: str):
    n, avg_atk = await avg_player_power()
    conf = config.BOSS_CONFIG[kind]
    # HP = ضربی از توان گروه فعال؛ برای ۱۰۰ نفر یا ۱۰۰ هزار نفر منطقی می‌مونه
    scale = max(0.5, min(3.0, n / 50.0))
    return int(conf["hp"] * scale * (avg_atk / 10.0))

async def spawn_boss(bot: Bot, kind: str):
    conf = config.BOSS_CONFIG[kind]
    now = int(time.time())
    hp = await schedule_hp(kind)
    starts = now + conf["warn"]  # زمان آماده‌سازی + کانت‌داون
    cur = await (await db.db()).execute(
        """INSERT INTO boss_events(kind,name,hp,max_hp,starts_at,ends_at,active,ranking,created_date)
           VALUES(?,?,?,?,?,?,1,'{}',?)""",
        (kind, conf["name"], hp, hp, starts, starts + conf["window"], now))
    await (await db.db()).commit()
    bid = cur.lastrowid
    await announce(bot,
        f"👑 «{conf['name']}» وارد منطقه می‌شه!\n"
        f"⏳ آماده‌سازی: {conf['warn']//60} دقیقه\n"
        f"❤️ HP: {hp:,}\n"
        f"⚔️ بعد از کانت‌داون نبرد شروع می‌شه — تجهیزات رو آماده کن و اسکواد بچین!")
    return bid

async def get_active_boss():
    cur = await (await db.db()).execute(
        "SELECT * FROM boss_events WHERE active=1 ORDER BY id DESC LIMIT 1")
    return await cur.fetchone()

async def boss_hit(boss, p):
    now = int(time.time())
    if now < boss["starts_at"]:
        return None, "⏳ هنوز کانت‌داون تموم نشده!"
    if now - p["last_boss_hit"] < 30:  # هر ۳۰ ثانیه یک ضربه
        return None, "😌 نفس تازه کن! هر ۳۰ ثانیه یک ضربه."
    dmg = p["attack"] * 2 + max(0, p["level"] * 2)
    new_hp = max(0, boss["hp"] - dmg)
    phase = boss["phase"]
    if new_hp < boss["max_hp"] * 0.33:
        phase = 3
    elif new_hp < boss["max_hp"] * 0.66:
        phase = 2
    ranking = json.loads(boss["ranking"])
    ranking[str(p["id"])] = ranking.get(str(p["id"]), 0) + dmg
    await (await db.db()).execute(
        "UPDATE boss_events SET hp=?, phase=?, ranking=? WHERE id=?",
        (new_hp, phase, json.dumps(ranking), boss["id"]))
    await (await db.db()).execute(
        "INSERT INTO boss_hits(event_id,player_id,dmg,ts) VALUES(?,?,?,?)",
        (boss["id"], p["id"], dmg, now))
    await db.update_player(p["id"], last_boss_hit=now)
    await db.add_score(p["id"], config.SCORE_BOSS_HIT, xp=5)  # امتیاز باس هم هیچ‌وقت کم نمی‌شه
    await (await db.db()).commit()
    return dmg, phase

async def finish_boss(bot: Bot, boss):
    ranking = json.loads(boss["ranking"])
    if boss["hp"] <= 0:
        # پیروزی — جایزه‌ها
        top = sorted(ranking.items(), key=lambda x: -x[1])[:10]
        names = []
        for i, (pid, d) in enumerate(top):
            p = await db.get_player(int(pid))
            if p:
                reward = [500, 300, 200][i] if i < 3 else 100
                await db.add_score(p["id"], config.SCORE_BOSS_KILL + reward, coins=reward // 2, xp=50)
                names.append(f"{i+1}. {p['name']} — {d:,} دمیج")
        await announce(bot,
            f"🏆 باس «{boss['name']}» شکست خورد!\n\n" + "\n".join(names) +
            f"\n\n⭐️ همه شرکت‌کننده‌ها امتیاز گرفتن. Respawn بعد از کول‌داون.")
    else:
        await announce(bot,
            f"💨 باس «{boss['name']}» برنگشت به تاریکی... نبرد بدون نتیجه تموم شد.\n"
            f"کول‌داون Respawn فعال شد.")
    await (await db.db()).execute(
        "UPDATE boss_events SET active=0 WHERE id=?", (boss["id"],))
    await (await db.db()).commit()

async def announce(bot: Bot, text: str):
    """اعلان عمومی به همه مشترک‌های باس."""
    cur = await (await db.db()).execute("SELECT id FROM players WHERE boss_sub=1")
    rows = await cur.fetchall()
    for row in rows:
        try:
            await bot.send_message(row["id"], text)
        except Exception:
            pass  # بلاک/آفلاین → بی‌صدا رد شو، بازیکن حفظ می‌شه

async def boss_loop(bot: Bot):
    """زمان‌بندی سمت سرور — بازیکن هیچ‌وقت نمی‌تونه Timer/Spawn/Phase رو دستکاری کنه."""
    last_spawn = {k: 0 for k in config.BOSS_CONFIG}
    phase_sent = {}
    while True:
        try:
            now = int(time.time())
            boss = await get_active_boss()
            if boss:
                if now >= boss["starts_at"]:
                    # شروع نبرد — یک بار
                    if boss["id"] not in phase_sent:
                        phase_sent[boss["id"]] = 1
                        await announce(bot, f"⚔️ نبرد با «{boss['name']}» شروع شد! حمله کن!")
                    elif phase_sent[boss["id"]] < boss["phase"]:
                        phase_sent[boss["id"]] = boss["phase"]
                        await announce(bot, f"{PHASES[boss['phase']]} — «{boss['name']}» قوی‌تر شد!")
                    if now >= boss["ends_at"] or boss["hp"] <= 0:
                        await finish_boss(bot, boss)
            else:
                for kind, conf in config.BOSS_CONFIG.items():
                    if now - last_spawn[kind] >= conf["every"]:
                        last_spawn[kind] = now
                        await spawn_boss(bot, kind)
                        break  # یک باس در هر لحظه — بدون باگ همزمانی
        except Exception:
            pass  # کرش نکنه هیچ‌وقت
        await asyncio.sleep(15)
