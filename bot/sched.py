"""زمان‌بند مرکزی — همهٔ زمان‌بندی‌ها سرور-ساید. هیچ Timer داخل هندلرها نیست."""
import asyncio, json, logging, time
from aiogram import Bot
from . import config, db, repo, gamedata, ui

log = logging.getLogger("sched")
NOW = lambda: int(time.time())

EVENT_NAMES = {
    "double": "🧠 ایونت XP دوبرابر (آخر هفته)",
    "coin_rush": "🪙 ایونت سکهٔ دوبرابر (شیوع)",
}

_cache = {"kinds": set(), "ts": 0}


def active_kinds() -> set[str]:
    """کش ۶۰ ثانیه‌ای رویدادهای فعال — برای بونوس‌های سرور-ساید."""
    if NOW() - _cache["ts"] > 60:
        _cache["ts"] = NOW()
    return _cache["kinds"]


def next_event_name() -> str | None:
    acts = [k for k in _cache["kinds"]]
    return EVENT_NAMES[acts[0]] if acts else None


async def refresh_events():
    acts = await repo.event_active()
    kinds = {a["kind"] for a in acts}
    _cache["kinds"] = kinds
    _cache["ts"] = NOW()
    return kinds


async def channel_post(bot: Bot, text: str):
    if config.CHANNEL_ID:
        try:
            await bot.send_message(config.CHANNEL_ID, text)
        except Exception as e:
            log.warning("کانال در دسترس نیست: %s", e)


async def boss_loop(bot: Bot):
    """اسکن هر ۶۰ ثانیه — Spawn طبق شرط/فاصله، اعلان، شروع، پایان، Respawn Cooldown."""
    while True:
        try:
            await refresh_events()
            now = NOW()
            # ۱) باس جدید؟
            for bid, b in gamedata.BOSSES.items():
                if bid == "birkin_g":
                    # شرط داستانی: حداقل یک بازیکن باید به پایان فصل رسیده باشه
                    async with db.pool().acquire() as c:
                        ready = await c.fetchval("SELECT 1 FROM players WHERE story_flags @> '{\"final_ready\": true}' LIMIT 1")
                    if not ready:
                        continue
                active = await repo.boss_active()
                async with db.pool().acquire() as c:
                    scheduled = await c.fetchval("SELECT 1 FROM boss_events WHERE boss_id=$1 AND status='scheduled'", bid)
                if scheduled or any(e["boss_id"] == bid for e in active):
                    continue
                last = await repo.boss_last(bid)
                if last:
                    # Respawn Cooldown: بعد از کشته‌شدن، فاصله ۱.۵ برابر
                    gap = b["every"] * (1.5 if last["status"] == "killed" else 1.0)
                    if now - last["created_date"] < gap:
                        continue
                starts = now + b["warn"]
                eid = await repo.boss_event_create(bid, 0, starts, starts + b["window"])
                await db.set_config(f"boss_last:{bid}", now)
                msg = (f"📢 **{b['name']}** دارد بیدار می‌شود!\n"
                       f"📍 {gamedata.REGIONS[b['region']]['name']}\n"
                       f"⏳ شروع: {b['warn'] // 60} دقیقه دیگه | ⚔️ مدت: {b['window'] // 60} دقیقه\n"
                       f"❤️ {b['hp']:,} HP | فاز: {len(b['phases'])}")
                await channel_post(bot, msg)
                # اعلان به گروهای ثبت‌شده
                async with db.pool().acquire() as c:
                    worlds = await c.fetch("SELECT chat_id FROM worlds")
                for w in worlds:
                    try:
                        m = await bot.send_message(w["chat_id"], msg)
                        await repo.boss_set_msg(eid, w["chat_id"], m.message_id)
                    except Exception:
                        pass
            # ۲) گذار وضعیت‌ها
            async with db.pool().acquire() as c:
                due = await c.fetch("SELECT * FROM boss_events WHERE status='scheduled' AND starts_at <= $1", now)
                for e in due:
                    await c.execute("UPDATE boss_events SET status='active' WHERE id=$1", e["id"])
                    b = gamedata.BOSSES[e["boss_id"]]
                    await channel_post(bot, f"⚔️ **{b['name']}** فعاله!\n"
                                             f"📍 {gamedata.REGIONS[b['region']]['name']} | ❤️ {b['hp']:,}\n"
                                             f"از منوی 🧟 باس‌ها حمله کن — هر ۳۰ ثانیه یک ضربه.")
                expired = await c.fetch("SELECT * FROM boss_events WHERE status='active' AND ends_at <= $1", now)
                for e in expired:
                    await c.execute("UPDATE boss_events SET status='expired' WHERE id=$1", e["id"])
                    b = gamedata.BOSSES[e["boss_id"]]
                    await channel_post(bot, f"🏁 **{b['name']}** برنده شد و به لانه‌ش برگشت.\n"
                                             "دفعهٔ بعد با برنامهٔ بهتر بیاید — Cooldown رعایت می‌شه.")
        except Exception as e:
            log.error("boss_loop: %s", e)
        await asyncio.sleep(60)


async def events_loop(bot: Bot):
    """رویدادهای تکرارشونده — ایجاد خودکار وقتی هیچ نمونهٔ آینده/فعال نیست."""
    while True:
        try:
            now = NOW()
            # XP دوبرابر: آخر هفته ایرانی (پنجشنبه/جمعه)
            import datetime, zoneinfo
            dt = datetime.datetime.now(zoneinfo.ZoneInfo(config.TZ))
            if dt.weekday() in (3, 4):
                if not await repo.event_active("double"):
                    await repo.event_create("double", now, now + 24 * 3600)
                    await channel_post(bot, "🎉 ایونت XP دوبرابر شروع شد — ۲۴ ساعت!")
            # شیوع سکه: هر ۳ روز، ۶ ساعته
            async with db.pool().acquire() as c:
                future = await c.fetchval("SELECT 1 FROM events WHERE kind='coin_rush' AND ends_at > $1", now)
            if not future:
                await repo.event_create("coin_rush", now, now + 6 * 3600)
                await channel_post(bot, "☣️ ایونت شیوع: سکهٔ دوبرابر برای ۶ ساعت — با احتیاط شکار کنید!")
        except Exception as e:
            log.error("events_loop: %s", e)
        await asyncio.sleep(300)
