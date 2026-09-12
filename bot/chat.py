import time
from . import db, config

async def send_chat(pid, p, text):
    """گپ سراسری — همه بازیکن‌ها همیشه حفظ می‌شن، هیچ‌چیز پاک نمی‌شه."""
    now = int(time.time())
    if not p["chat_on"]:
        return "off", None
    if now - p["last_chat"] < config.CHAT_RATE_SEC:
        wait = config.CHAT_RATE_SEC - (now - p["last_chat"])
        return "rate", wait
    if len(text) > config.CHAT_MAX_LEN:
        return "long", None
    await (await db.db()).execute(
        "INSERT INTO chat_messages(player_id,name,level,text,ts) VALUES(?,?,?,?,?)",
        (pid, p["name"], p["level"], text, now))
    await db.update_player(pid, last_chat=now)
    return "ok", None

async def last_messages(n=20):
    cur = await (await db.db()).execute(
        "SELECT * FROM chat_messages ORDER BY id DESC LIMIT ?", (n,))
    rows = await cur.fetchall()
    return list(reversed(rows))

async def broadcast(bot, sender, text):
    """پیام رو به اعضای آنلاین گپ می‌رسونیم."""
    cur = await (await db.db()).execute(
        "SELECT id FROM players WHERE chat_on=1 AND id != ?", (sender["id"],))
    rows = await cur.fetchall()
    msg = f"🌍 [{sender['name']} | Lv.{sender['level']}] {text}"
    delivered = 0
    for row in rows:
        try:
            await bot.send_message(row["id"], msg)
            delivered += 1
        except Exception:
            pass
    return delivered
