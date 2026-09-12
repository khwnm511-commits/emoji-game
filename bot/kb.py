from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton as Btn
from . import emojis

# دکمه‌های رنگی با مربع‌های رنگی تلگرام
R = {"red": "🟥", "orange": "🟧", "yellow": "🟨", "green": "🟩", "blue": "🟦", "purple": "🟪"}

def main_menu(player) -> InlineKeyboardMarkup:
    kb = [
        [Btn(text=f"{R['red']}⚔️ نبرد نوبتی", callback_data="b:menu"),
         Btn(text=f"{R['purple']}🦠 بازی ویروس", callback_data="v:menu")],
        [Btn(text=f"{R['blue']}❤️ عشق و روابط", callback_data="l:menu"),
         Btn(text=f"{R['orange']}👑 باس‌ها", callback_data="boss:menu")],
        [Btn(text=f"{R['yellow']}🛍 فروشگاه ایموجی", callback_data="shop:menu"),
         Btn(text=f"{R['green']}🌍 گپ سراسری", callback_data="c:menu")],
        [Btn(text="👤 پروفایل من", callback_data="m:prof"),
         Btn(text="🏆 برترین‌ها", callback_data="m:top")],
        [Btn(text="⭐️ خرید با استارز", callback_data="stars:menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[Btn(text="🔙 منوی اصلی", callback_data="m:main")]])

# ——————————————— نبرد ———————————————
def battle_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [Btn(text="🤖 نبرد با هیولا (PvE)", callback_data="b:pve"),
         Btn(text="🆚 دوئل با بازیکن (PvP)", callback_data="b:pvp")],
        [Btn(text="🔙 منوی اصلی", callback_data="m:main")],
    ])

def battle_actions(can_skill: bool) -> InlineKeyboardMarkup:
    kb = [[
        Btn(text=f"{R['red']}🗡 حمله", callback_data="b:atk"),
        Btn(text=f"{R['blue']}🛡 دفاع", callback_data="b:def"),
    ]]
    if can_skill:
        kb.append([Btn(text=f"{R['purple']}💥 ضربه ویژه", callback_data="b:skl"),
                   Btn(text="🏃 فرار", callback_data="b:flee")])
    else:
        kb.append([Btn(text="🏃 فرار", callback_data="b:flee")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def accept_duel(battle_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [Btn(text="⚔️ قبول دوئل", callback_data=f"b:acc:{battle_id}"),
         Btn(text="❌ رد", callback_data=f"b:rej:{battle_id}")],
    ])

# ——————————————— ویروس ———————————————
def virus_menu(infected: bool) -> InlineKeyboardMarkup:
    kb = [
        [Btn(text="🦠 آلوده کردن بازیکن", callback_data="v:go"),
         Btn(text="💉 واکسن (۱۵ سکه)", callback_data="v:vac")],
    ]
    if infected:
        kb.append([Btn(text="🚑 درمان فوری (۳۰ سکه)", callback_data="v:cure")])
    kb.append([Btn(text="🔙 منوی اصلی", callback_data="m:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_virus() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[Btn(text="🔙 منوی ویروس", callback_data="v:menu")]])

# ——————————————— عشق و روابط ———————————————
def love_menu(rels: list) -> InlineKeyboardMarkup:
    kb = []
    for r in rels[:6]:
        flag = "💜" if r["status"] in ("partner", "close") else "🤝" if r["status"] == "friend" else "💔" if r["broken"] else "👤"
        kb.append([Btn(text=f"{flag} {r['target_name']}", callback_data=f"l:view:{r['id']}")])
    kb.append([Btn(text="➕ رابطه جدید / NPC", callback_data="l:new")])
    kb.append([Btn(text="🔙 منوی اصلی", callback_data="m:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def love_actions(rel_id: int, status: str) -> InlineKeyboardMarkup:
    kb = [
        [Btn(text="🎁 هدیه (۲۰ سکه) → +اعتماد", callback_data=f"l:gift:{rel_id}"),
         Btn(text="🤝 کمک در مأموریت → +وفاداری", callback_data=f"l:help:{rel_id}")],
        [Btn(text="🙏 احترام بگذار → +احترام", callback_data=f"l:resp:{rel_id}"),
         Btn(text="⏳ وقت گذراندن → +سابقه", callback_data=f"l:hist:{rel_id}")],
    ]
    if status not in ("partner", "enemy", "broken"):
        kb.append([Btn(text="💍 پیشنهاد رابطه", callback_data=f"l:prop:{rel_id}")])
    if status in ("partner", "friend", "close"):
        kb.append([Btn(text="💔 قطع رابطه (سابقه می‌مونه)", callback_data=f"l:break:{rel_id}")])
    kb.append([Btn(text="🔙 روابط", callback_data="l:menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def npc_list() -> InlineKeyboardMarkup:
    from .love import NPCS
    kb = [[Btn(text=f"🧙 {n}", callback_data=f"l:npc:{i}")] for i, n in enumerate(NPCS)]
    kb.append([Btn(text="👤 بازیکن با آیدی", callback_data="l:pl"),
               Btn(text="🔙 روابط", callback_data="l:menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ——————————————— باس ———————————————
def boss_menu(subscribed: bool, active: dict | None) -> InlineKeyboardMarkup:
    kb = []
    if active:
        kb.append([Btn(text="⚔️ حمله به باس!", callback_data="boss:hit")])
    toggle = "🔕 خاموش کردن اعلان‌ها" if subscribed else "🔔 روشن کردن اعلان‌ها"
    kb.append([Btn(text=toggle, callback_data="boss:sub")])
    kb.append([Btn(text="🔙 منوی اصلی", callback_data="m:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ——————————————— گپ سراسری ———————————————
def chat_menu(on: bool) -> InlineKeyboardMarkup:
    kb = [
        [Btn(text="💬 آخرین پیام‌های دنیای بازی", callback_data="c:read")],
        [Btn(text="🔕 خروج از گپ" if on else "🔔 ورود به گپ", callback_data="c:toggle")],
        [Btn(text="🔙 منوی اصلی", callback_data="m:main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ——————————————— فروشگاه ایموجی ———————————————
def shop_menu(owned_count: int) -> InlineKeyboardMarkup:
    kb = [
        [Btn(text=f"{R['yellow']}😀 ایموجی‌های پرمیوم ({owned_count}/۱۰۰)", callback_data="e:pg:0")],
        [Btn(text="💉 آیتم‌ها", callback_data="shop:items")],
        [Btn(text="🔙 منوی اصلی", callback_data="m:main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def emoji_page(n: int, owned: list[int]) -> InlineKeyboardMarkup:
    rows = []
    items = emojis.page(n)
    row = []
    for i, (e, _cid) in enumerate(items):
        num = n * emojis.PAGE_SIZE + i + 1
        mark = "✅" if num in owned else "🔒"
        row.append(Btn(text=f"{mark}{e}", callback_data=f"e:buy:{num}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = []
    if n > 0:
        nav.append(Btn(text="◀️", callback_data=f"e:pg:{n-1}"))
    nav.append(Btn(text=f"📄 {n+1}/{emojis.PAGES}", callback_data="e:none"))
    if n < emojis.PAGES - 1:
        nav.append(Btn(text="▶️", callback_data=f"e:pg:{n+1}"))
    rows.append(nav)
    rows.append([Btn(text="🔙 فروشگاه", callback_data="shop:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ——————————————— استارز ———————————————
def stars_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [Btn(text="⭐️ ۵۰ استارز → ۵۰۰ سکه", callback_data="pay:50")],
        [Btn(text="⭐️ ۱۵۰ استارز → ۱۶۰۰ سکه + ۳ واکسن", callback_data="pay:150")],
        [Btn(text="⭐️ ۴۰۰ استارز → ۴۵۰۰ سکه + پک ایموجی", callback_data="pay:400")],
        [Btn(text="⭐️ ۹۹ استارز → پک ۱۰ ایموجی دلخواه", callback_data="pay:99")],
        [Btn(text="🔙 منوی اصلی", callback_data="m:main")],
    ])

def back_shop() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[Btn(text="🔙 فروشگاه", callback_data="shop:menu")]])

def items_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [Btn(text="💉 واکسن — ۱۵ سکه", callback_data="buy:vac"),
         Btn(text="🍞 نان — ۲۰ سکه (HP+40)", callback_data="buy:bread")],
        [Btn(text="⚔️ شمشیر — ۸۰ سکه (ATK+3)", callback_data="buy:sword"),
         Btn(text="🛡 سپر — ۸۰ سکه (DEF+3)", callback_data="buy:shield")],
        [Btn(text="🔙 فروشگاه", callback_data="shop:menu")],
    ])
