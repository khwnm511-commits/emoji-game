"""مانیتورینگ توکن/حساب Railway — هر وقت تموم شد یا خطا داد، توی پیوی ربات به صاحبش خبر می‌ده."""
import asyncio, json, time
import aiohttp
from aiogram import Bot
from . import config

GRAPHQL = "https://api.railway.app/graphql/v2"

QUERY = """query {
  me { id email }
  projects { edges { node { id name } } }
}"""

async def check_token(token: str) -> tuple[bool, str]:
    """بررسی سلامت توکن — بدون لو دادن مقدارش."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(GRAPHQL, json={"query": QUERY},
                              headers={"Authorization": f"Bearer {token}"},
                              timeout=aiohttp.ClientTimeout(total=20)) as r:
                data = await r.json()
                if data.get("errors") or not data.get("data", {}).get("me"):
                    return False, "توکن Railway نامعتبره یا دسترسی‌ش تموم شده!"
                return True, f"اتصال Railway سالمه — کاربر: {data['data']['me'].get('email', '?')}"
    except Exception as e:
        return False, f"خطا در اتصال به Railway: {e}"

async def monitor_loop(bot: Bot):
    if not config.OWNER_ID or not config.RAILWAY_TOKEN:
        return
    last_state = None
    while True:
        ok, msg = await check_token(config.RAILWAY_TOKEN)
        # فقط وقتی پیام بده که وضعیت عوض شده، یا هر ۲۴ ساعت یک چک سالم
        if ok:
            if last_state is not None:  # بعد از خطا بهبود پیدا کرده
                try:
                    await bot.send_message(config.OWNER_ID, f"✅ {msg}")
                except Exception:
                    pass
            last_state = True
        else:
            try:
                await bot.send_message(
                    config.OWNER_ID,
                    f"⚠️ {msg}\n\n"
                    f"برو توی Railway یه توکن جدید بسازی و آپدیتش کن تا ربات قطع نشه.")
            except Exception:
                pass
            last_state = False
        await asyncio.sleep(config.RAILWAY_CHECK_SEC)
