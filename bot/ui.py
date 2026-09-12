"""UI — قالب ثابت فارسی/RTL + گزارش استاندارد."""
from . import config, gamedata

LINE = "─" * 20

def panel(title: str, *sections: str, footer: str = "") -> str:
    """قالب رسمی پیام:
    🧬 عنوان
    ────────────
    ...اطلاعات...
    """
    body = "\n".join(s for s in sections if s)
    out = f"{title}\n{LINE}\n{body}"
    if footer:
        out += f"\n{LINE}\n{footer}"
    return out

def report(region: str, operation: str, health: str, enemy: str, result: str, reward: str, consequence: str) -> str:
    """گزارش استاندارد بعد از نبرد/مأموریت — فقط از دادهٔ واقعی."""
    return (f"⚔️ گزارش\n{LINE}\n"
            f"📍 منطقه: {region}\n"
            f"🎯 عملیات: {operation}\n"
            f"❤️ وضعیت: {health}\n"
            f"🧟 دشمن: {enemy}\n"
            f"📊 نتیجه: {result}\n"
            f"🎁 پاداش: {reward}\n"
            f"📌 پیامد: {consequence}")

def status_line(p: dict) -> str:
    st = gamedata.STAGES[p["infection_stage"]]
    status = p["status"]
    if status == "hospitalized":
        st = "🏥 بستری"
    elif status == "dead_temp":
        st = "☠️ مرگ موقت"
    return f"❤️ {p['hp']}/{p['max_hp']} | ⚡️ {p['energy']}/{config.MAX_ENERGY} | 🧬 {st}"

def fmt_time(sec: int) -> str:
    sec = int(sec)
    if sec < 60:
        return f"{sec} ثانیه"
    if sec < 3600:
        return f"{sec // 60} دقیقه"
    if sec < 86400:
        return f"{sec // 3600} ساعت و {(sec % 3600) // 60} دقیقه"
    return f"{sec // 86400} روز و {(sec % 86400) // 3600} ساعت"
