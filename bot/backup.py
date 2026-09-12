"""🛡 بکاپ PostgreSQL — دامپ JSON کامل همهٔ جدول‌ها + ارسال به پیوی صاحب ربات هر ۲۴ ساعت."""
import asyncio, json, logging, time
import aiohttp
from aiogram import Bot
from aiogram.types import BufferedInputFile
from . import config, db

log = logging.getLogger("backup")


async def make_dump() -> tuple[str, bytes]:
    """دامپ کامل همهٔ جدول‌ها به JSON — برای ریستور واقعی."""
    from . import db as _db
    dump = {"_meta": {"ts": int(time.time()), "season": config.SEASON}}
    async with db.pool().acquire() as c:
        for t in _db.TABLES:
            rows = await c.fetch(f"SELECT * FROM {t}")
            dump[t] = [dict(r) for r in rows]
            for r in dump[t]:
                for k, v in r.items():
                    if isinstance(v, (bytes, memoryview)):
                        r[k] = v.hex()
    data = json.dumps(dump, ensure_ascii=False, default=str).encode()
    return f"game-backup-{time.strftime('%Y-%m-%d_%H-%M')}.json", data


async def send_backup(bot: Bot, note: str = "🛡 بکاپ خودکار دیتابیس") -> bool:
    if not config.OWNER_ID:
        return False
    try:
        name, data = await make_dump()
        await bot.send_document(
            config.OWNER_ID, document=BufferedInputFile(data, filename=name),
            caption=f"{note}\n📦 {len(data):,} بایت — {time.strftime('%Y-%m-%d %H:%M UTC')}")
        log.info("Backup sent: %s", name)
        return True
    except Exception as e:
        log.error("Backup failed: %s", e)
        return False


async def backup_loop(bot: Bot):
    await asyncio.sleep(120)
    while True:
        await send_backup(bot)
        await asyncio.sleep(24 * 3600)


# ——————————————— مانیتورینگ توکن Railway ———————————————
GRAPHQL = "https://api.railway.app/graphql/v2"
Q = "query { me { id email } projects { edges { node { id name } } } }"


async def check_token(token: str) -> tuple[bool, str]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(GRAPHQL, json={"query": Q},
                              headers={"Authorization": f"Bearer {token}"},
                              timeout=aiohttp.ClientTimeout(total=20)) as r:
                data = await r.json()
                if data.get("errors") or not data.get("data", {}).get("me"):
                    return False, "توکن Railway نامعتبره یا اعتبارش تموم شده!"
                return True, f"اتصال Railway سالمه — کاربر: {data['data']['me'].get('email', '?')}"
    except Exception as e:
        return False, f"خطا در اتصال به Railway: {e}"


async def monitor_loop(bot: Bot):
    if not config.OWNER_ID or not config.RAILWAY_TOKEN:
        return
    last = None
    while True:
        ok, msg = await check_token(config.RAILWAY_TOKEN)
        if ok and last is False:
            await bot.send_message(config.OWNER_ID, f"✅ {msg}")
        elif not ok and last is not False:
            await bot.send_message(config.OWNER_ID,
                                   f"⚠️ {msg}\n\nبرو توی Railway توکن جدید بساز تا ربات قطع نشه.")
        last = ok
        await asyncio.sleep(config.RAILWAY_CHECK_SEC)
