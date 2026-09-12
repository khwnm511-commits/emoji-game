import json, time
from aiogram.types import LabeledPrice
from . import db, config, emojis

# پکیج‌های استارز — تلگرام استارز (XTR)
STARS_PACKS = {
    50:  {"title": "۵۰ سکه طلا",            "desc": "۵۰۰ سکه داخل بازی",              "coins": 500,  "vaccines": 0, "emojis": 0},
    150: {"title": "پک جنگجو",               "desc": "۱۶۰۰ سکه + ۳ واکسن ویروس",       "coins": 1600, "vaccines": 3, "emojis": 0},
    400: {"title": "پک افسانه‌ای",            "desc": "۴۵۰۰ سکه + پک کامل ایموجی‌ها",   "coins": 4500, "vaccines": 0, "emojis": 100},
    99:  {"title": "پک ۱۰ ایموجی پرمیوم",      "desc": "۱۰ ایموجی دلخواه آزاد می‌شه",     "coins": 0,    "vaccines": 0, "emojis": 10},
}

async def invoice_payload(stars: int, pid: int) -> str:
    return f"pack:{stars}:{pid}:{int(time.time())}"

async def grant_pack(pid: int, stars: int):
    """بعد از پرداخت موفق استارز — بدون باگ، اتمیک."""
    pack = STARS_PACKS.get(stars)
    if not pack:
        return None
    p = await db.get_player(pid)
    if not p:
        return None
    owned = json.loads(p["emojis_owned"])
    if pack["emojis"] >= 100:
        owned = list(range(1, 101))
    elif pack["emojis"] > 0:
        locked = [i for i in range(1, 101) if i not in owned][:pack["emojis"]]
        owned += locked
    await db.update_player(
        pid,
        coins=p["coins"] + pack["coins"],
        vaccines=p["vaccines"] + pack["vaccines"],
        emojis_owned=json.dumps(owned))
    return pack

async def buy_emoji(pid: int, num: int):
    """خرید ایموجی تکی با ۲۵ استارز."""
    p = await db.get_player(pid)
    owned = json.loads(p["emojis_owned"])
    if num in owned:
        return None
    return f"emoji:{num}:{pid}:{int(time.time())}"

async def grant_emoji(pid: int, num: int):
    e = emojis.emoji_by_index(num)
    if not e:
        return False
    p = await db.get_player(pid)
    owned = json.loads(p["emojis_owned"])
    if num in owned:
        return False
    owned.append(num)
    await db.update_player(pid, emojis_owned=json.dumps(owned))
    return True
