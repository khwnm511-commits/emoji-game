"""همهٔ کیبوردها — Inline، فارسی، با استاندارد رنگ ثابت:
🔵 منو/عادی 🟥 خطر/نبرد 🟩 تأیید/درمان 🟨 هشدار/مهم ⚫ اطلاعات/فرعی
همیشه 🔙 برگشت و 🏠 خانه در دسترس."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton as Btn, WebAppInfo
from . import config, gamedata

# ——————————————— کمکی‌ها ———————————————
def _mk(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)

def nav(back_cb: str | None = None) -> list:
    """ردیف ناوبری — همیشه دسترس."""
    if back_cb:
        return [Btn(text=f"{config.DARK}🔙 برگشت", callback_data=back_cb),
                Btn(text=f"{config.BLUE}🏠 خانه", callback_data="m:home")]
    return [Btn(text=f"{config.BLUE}🏠 خانه", callback_data="m:home")]

# ——————————————— شروع / آنبوردینگ ———————————————
def gender() -> InlineKeyboardMarkup:
    return _mk([
        [Btn(text=f"{config.BLUE}👨 مرد", callback_data="gen:m"),
         Btn(text=f"{config.DARK}👩 زن", callback_data="gen:f")],
    ])

# ——————————————— منوی اصلی ———————————————
def main_menu(is_owner: bool = False) -> InlineKeyboardMarkup:
    kb = [
        [Btn(text=f"{config.BLUE}👤 پروفایل", callback_data="m:prof"),
         Btn(text=f"{config.BLUE}📖 داستان", callback_data="st:node"),
         Btn(text=f"{config.BLUE}🎯 مأموریت‌ها", callback_data="mi:list"),
         Btn(text=f"{config.BLUE}🗺 جهان", callback_data="w:list")],
        [Btn(text=f"{config.RED}⚔️ مبارزه", callback_data="b:menu"),
         Btn(text=f"{config.BLUE}🧬 توانایی‌ها", callback_data="ab:list"),
         Btn(text=f"{config.BLUE}🎒 کوله", callback_data="inv:list"),
         Btn(text=f"{config.BLUE}❤️ روابط", callback_data="rel:list")],
        [Btn(text=f"{config.BLUE}🤝 دوستان", callback_data="fr:list"),
         Btn(text=f"{config.BLUE}👥 تیم", callback_data="tm:menu"),
         Btn(text=f"{config.BLUE}🏴 کلن", callback_data="cl:menu"),
         Btn(text=f"{config.BLUE}🏆 رتبه‌بندی", callback_data="rk:players")],
        [Btn(text=f"{config.YELLOW}🎉 رویدادها", callback_data="ev:list"),
         Btn(text=f"{config.RED}🧟 باس‌ها", callback_data="boss:menu"),
         Btn(text=f"{config.YELLOW}🛒 فروشگاه", callback_data="sh:menu"),
         Btn(text=f"{config.DARK}📘 راهنما", callback_data="gd:index")],
    ]
    return _mk(kb)

# ——————————————— پروفایل ———————————————
def profile(is_owner: bool, companion: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if companion:
        rows.append([Btn(text=f"{config.DARK}🤝 همراه فعلی: جدا کردن", callback_data="npc:drop")])
    else:
        rows.append([Btn(text=f"{config.DARK}🤝 انتخاب همراه از NPCها", callback_data="npc:pick")])
    rows.append(nav())
    if is_owner:
        rows.append([Btn(text=f"{config.GREEN}🛡 بکاپ فوری دیتابیس", callback_data="bk:now")])
    return _mk(rows)

# ——————————————— NPC ———————————————
def npc_list_page(page_i: int, trust_map: dict) -> InlineKeyboardMarkup:
    ids = gamedata.NPC_IDS
    PER = 8
    rows = []
    for nid in ids[page_i * PER:(page_i + 1) * PER]:
        n = gamedata.NPCS[nid]
        t = trust_map.get(nid, 0)
        rows.append([Btn(text=f"{config.DARK}{n['name']} ({t}🤝)", callback_data=f"npc:view:{nid}")])
    navr = []
    if page_i > 0:
        navr.append(Btn(text=f"{config.BLUE}◀️", callback_data=f"npc:pg:{page_i-1}"))
    navr.append(Btn(text=f"{config.DARK}📄 {page_i+1}", callback_data="npc:none"))
    if (page_i + 1) * PER < len(ids):
        navr.append(Btn(text=f"{config.BLUE}▶️", callback_data=f"npc:pg:{page_i+1}"))
    rows.append(navr)
    rows.append(nav())
    return _mk(rows)

def npc_view(nid: str, trust: int, is_companion: bool, can_ally: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_ally and not is_companion:
        rows.append([Btn(text=f"{config.GREEN}🤝 همراه من کن (اعتماد ۴۰+)", callback_data=f"npc:ally:{nid}")])
    if is_companion:
        rows.append([Btn(text=f"{config.RED}جدا کردن همراه", callback_data="npc:drop")])
    rows.append(nav("npc:pick"))
    return _mk(rows)

# ——————————————— داستان ———————————————
def story(node_id: str, choices: list) -> InlineKeyboardMarkup:
    rows = [[Btn(text=f"{config.BLUE}{c['label']}", callback_data=f"st:choice:{node_id}:{i}")]
            for i, c in enumerate(choices)]
    rows.append(nav())
    return _mk(rows)

# ——————————————— مأموریت‌ها ———————————————
def missions(active: list, available: list) -> InlineKeyboardMarkup:
    rows = []
    for mid in active:
        m = gamedata.MISSIONS[mid]
        rows.append([Btn(text=f"{config.YELLOW}🎯 {m['name']}", callback_data=f"mi:view:{mid}")])
    rows.append([Btn(text=f"{config.DARK}─────────", callback_data="mi:none")])
    for mid in available:
        m = gamedata.MISSIONS[mid]
        rows.append([Btn(text=f"{config.BLUE}📥 {m['name']}", callback_data=f"mi:view:{mid}")])
    rows.append(nav())
    return _mk(rows)

def mission_view(mid: str, started: bool, done: bool) -> InlineKeyboardMarkup:
    rows = []
    if not started and not done:
        rows.append([Btn(text=f"{config.GREEN}قبول مأموریت", callback_data=f"mi:start:{mid}")])
    if done:
        rows.append([Btn(text=f"{config.GREEN}🎁 دریافت پاداش", callback_data=f"mi:claim:{mid}")])
    rows.append(nav("mi:list"))
    return _mk(rows)

# ——————————————— جهان / مناطق ———————————————
def regions(unlocked_lvl: int, current: str) -> InlineKeyboardMarkup:
    rows = []
    for rid in gamedata.REGION_ORDER:
        r = gamedata.REGIONS[rid]
        lock = f"{config.RED}🔒" if unlocked_lvl < r["lvl"] else (f"{config.GREEN}📍" if rid == current else f"{config.BLUE}")
        rows.append([Btn(text=f"{lock} {r['name']} (خطر {r['danger']})" if r['danger'] else f"{config.GREEN}🏕 منطقهٔ امن",
                         callback_data=f"w:view:{rid}" if unlocked_lvl >= r["lvl"] else f"w:locked:{rid}")])
    rows.append(nav())
    return _mk(rows)

def region_view(rid: str, current: bool) -> InlineKeyboardMarkup:
    rows = []
    if not current:
        rows.append([Btn(text=f"{config.GREEN}🚶 سفر به این منطقه", callback_data=f"w:go:{rid}")])
    if rid != "safezone":
        rows.append([Btn(text=f"{config.RED}⚔️ جست‌وجوی دشمن", callback_data=f"b:hunt:{rid}")])
    rows.append(nav("w:list"))
    return _mk(rows)

# ——————————————— نبرد ———————————————
def battle_menu() -> InlineKeyboardMarkup:
    return _mk([
        [Btn(text=f"{config.RED}⚔️ جست‌وجوی دشمن (PvE)", callback_data="b:hunt:cur"),
         Btn(text=f"{config.RED}🆚 دوئل بازیکن (PvP)", callback_data="b:pvp")],
        nav(),
    ])

def battle_actions(can_ability: bool, has_items: bool, can_support: bool) -> InlineKeyboardMarkup:
    rows = [[
        Btn(text=f"{config.RED}⚔️ حمله", callback_data="bt:atk"),
        Btn(text=f"{config.BLUE}🛡 دفاع", callback_data="bt:def"),
    ], [
        Btn(text=f"{config.GREEN}🧬 توانایی", callback_data="bt:ab:0"),
        Btn(text=f"{config.GREEN}🎒 آیتم", callback_data="bt:it:0"),
    ]]
    if can_support:
        rows[1].append(Btn(text=f"{config.BLUE}🤝 حمایت", callback_data="bt:spt"))
    rows.append([
        Btn(text=f"{config.DARK}🔍 بررسی", callback_data="bt:insp"),
        Btn(text=f"{config.YELLOW}🏃 فرار", callback_data="bt:flee"),
    ])
    return _mk(rows)

def ability_in_battle(usable: list, page_i: int) -> InlineKeyboardMarkup:
    rows = [[Btn(text=f"{config.GREEN}{gamedata.ABILITIES[a]['name']}", callback_data=f"bt:useab:{a}")]
            for a in usable]
    rows.append([Btn(text=f"{config.DARK}🔙 برگشت به نبرد", callback_data="bt:back")])
    return _mk(rows)

def items_in_battle(items: list) -> InlineKeyboardMarkup:
    rows = [[Btn(text=f"{config.GREEN}{gamedata.ITEMS[i]['name']} ×{q}", callback_data=f"bt:useit:{i}")]
            for i, q in items[:8]]
    rows.append([Btn(text=f"{config.DARK}🔙 برگشت به نبرد", callback_data="bt:back")])
    return _mk(rows)

def pvp_accept(battle_id: int) -> InlineKeyboardMarkup:
    return _mk([[
        Btn(text=f"{config.GREEN}⚔️ قبول دوئل", callback_data=f"bt:acc:{battle_id}"),
        Btn(text=f"{config.RED}❌ رد", callback_data=f"bt:rej:{battle_id}"),
    ]])

# ——————————————— توانایی‌ها ———————————————
def abilities(owned: list) -> InlineKeyboardMarkup:
    rows = []
    for aid, a in gamedata.ABILITIES.items():
        if a["lvl"] == 0:
            continue  # جهشی جدا نمایش داده می‌شه
        mark = f"{config.GREEN}" if aid in owned else f"{config.RED}🔒"
        rows.append([Btn(text=f"{mark}{a['name']} — سطح {a['lvl']}", callback_data=f"ab:view:{aid}")])
    rows.append(nav())
    return _mk(rows)

# ——————————————— کوله ———————————————
def inventory(items: list, weapon: str | None, armor: str | None) -> InlineKeyboardMarkup:
    rows = []
    if weapon:
        rows.append([Btn(text=f"{config.DARK}🔫 سلاح: {gamedata.ITEMS[weapon]['name']}", callback_data=f"inv:uneq:w")])
    if armor:
        rows.append([Btn(text=f"{config.DARK}🛡 زره: {gamedata.ITEMS[armor]['name']}", callback_data=f"inv:uneq:a")])
    for iid, qty in items:
        it = gamedata.ITEMS[iid]
        rows.append([Btn(text=f"{config.BLUE}{it['name']} ×{qty}", callback_data=f"inv:view:{iid}")])
    rows.append(nav())
    return _mk(rows)

def item_view(iid: str, can_equip: bool, can_use: bool, qty: int) -> InlineKeyboardMarkup:
    rows = []
    if can_equip:
        rows.append([Btn(text=f"{config.GREEN}⚙️ تجهیز", callback_data=f"inv:eq:{iid}")])
    if can_use:
        rows.append([Btn(text=f"{config.GREEN}💊 استفاده", callback_data=f"inv:use:{iid}")])
    rows.append(nav("inv:list"))
    return _mk(rows)

# ——————————————— روابط بازیکنان ———————————————
def relations(rels: list) -> InlineKeyboardMarkup:
    rows = []
    for r in rels[:8]:
        mark = {"partner": "💜", "friend": "🤝", "rival": "⚔️", "enemy": "💔"}.get(r["status"], "👤")
        rows.append([Btn(text=f"{config.BLUE}{mark} {r['name']}", callback_data=f"rel:view:{r['target_id']}")])
    rows.append([Btn(text=f"{config.GREEN}➕ رابطه با بازیکن (آیدی)", callback_data="rel:new")])
    rows.append(nav())
    return _mk(rows)

def rel_actions(target_id: int, status: str) -> InlineKeyboardMarkup:
    rows = [[
        Btn(text=f"{config.GREEN}🎁 هدیه ۲۰ سکه", callback_data=f"rel:gift:{target_id}"),
        Btn(text=f"{config.BLUE}🤝 هم‌بازی (+وفاداری)", callback_data=f"rel:coop:{target_id}"),
    ]]
    if status not in ("enemy",):
        rows.append([Btn(text=f"{config.RED}💔 قطع رابطه", callback_data=f"rel:break:{target_id}")])
    rows.append(nav("rel:list"))
    return _mk(rows)

# ——————————————— دوستان ———————————————
def friends(fl: list) -> InlineKeyboardMarkup:
    rows = []
    for f in fl[:10]:
        rows.append([Btn(text=f"{config.GREEN}🤝 {f['name']}", callback_data=f"rel:view:{f['friend_id']}")])
    rows.append([Btn(text=f"{config.GREEN}➕ افزودن دوست (آیدی)", callback_data="fr:add")])
    rows.append(nav())
    return _mk(rows)

# ——————————————— تیم (گروه) ———————————————
def team_menu(in_team: bool) -> InlineKeyboardMarkup:
    rows = []
    if not in_team:
        rows.append([Btn(text=f"{config.GREEN}👥 ساخت تیم در این گروه", callback_data="tm:create")])
    else:
        rows.append([Btn(text=f"{config.BLUE}🤝 دعوت بازیکن به تیم", callback_data="tm:invite")])
    rows.append(nav())
    return _mk(rows)

# ——————————————— کلن ———————————————
def clan_menu(in_clan: dict | None, weekly_top: list) -> InlineKeyboardMarkup:
    rows = []
    if in_clan:
        rows.append([Btn(text=f"{config.BLUE}🏴 {in_clan['name']} — جنگ هفتگی", callback_data="cl:war")])
        rows.append([Btn(text=f"{config.RED}خروج از کلن", callback_data="cl:leave")])
    else:
        rows.append([Btn(text=f"{config.GREEN}🏆 ساخت کلن (۲۰۰ سکه)", callback_data="cl:create")])
        rows.append([Btn(text=f"{config.BLUE}🔽 لیست کلن‌ها", callback_data="cl:list")])
    if weekly_top:
        rows.append([Btn(text=f"{config.DARK}📊 رتبه کلن‌های هفته", callback_data="cl:top")])
    rows.append(nav())
    return _mk(rows)

def clan_list(clans: list) -> InlineKeyboardMarkup:
    rows = [[Btn(text=f"{config.BLUE}🏴 {c['name']} ({c['points']}⚡)", callback_data=f"cl:join:{c['id']}")]
            for c in clans[:8]]
    rows.append(nav("cl:menu"))
    return _mk(rows)

# ——————————————— رتبه‌بندی ———————————————
def ranking(top: list, mode: str) -> InlineKeyboardMarkup:
    rows = [[Btn(text=f"{config.BLUE}👤 بازیکنان" if mode != "players" else f"{config.GREEN}👤 بازیکنان", callback_data="rk:players"),
             Btn(text=f"{config.BLUE}🏴 کلن‌ها" if mode != "clans" else f"{config.GREEN}🏴 کلن‌ها", callback_data="rk:clans")]]
    rows.append(nav())
    return _mk(rows)

# ——————————————— رویدادها ———————————————
def events(active: list, next_up: list) -> InlineKeyboardMarkup:
    rows = []
    for e in active:
        rows.append([Btn(text=f"{config.YELLOW}🔥 {e}", callback_data="ev:none")])
    if next_up:
        rows.append([Btn(text=f"{config.DARK}⏳ {next_up}", callback_data="ev:none")])
    if not active and not next_up:
        rows.append([Btn(text=f"{config.DARK}فعلاً رویدادی نیست", callback_data="ev:none")])
    rows.append(nav())
    return _mk(rows)

# ——————————————— باس ———————————————
def boss_menu(active: list, subscribed: bool) -> InlineKeyboardMarkup:
    rows = []
    for b in active:
        rows.append([Btn(text=f"{config.RED}⚔️ حمله به {b}", callback_data=f"boss:hit")])
    toggle = f"{config.RED}🔕 خاموش اعلان" if subscribed else f"{config.GREEN}🔔 روشن اعلان"
    rows.append([Btn(text=toggle, callback_data="boss:sub")])
    rows.append(nav())
    return _mk(rows)

# ——————————————— فروشگاه ———————————————
def shop_menu() -> InlineKeyboardMarkup:
    return _mk([
        [Btn(text=f"{config.BLUE}🎒 آیتم‌ها", callback_data="sh:items")],
        [Btn(text=f"{config.YELLOW}🎭 ایموجی‌های پرمیوم", callback_data="e:pg:0")],
        [Btn(text=f"{config.YELLOW}⭐️ خرید پرمیوم با استارز", callback_data="sh:stars")],
        nav(),
    ])

def shop_items(items: list, coins: int) -> InlineKeyboardMarkup:
    rows = [[Btn(text=f"{config.BLUE}{gamedata.ITEMS[i]['name']} — {p} 🪙", callback_data=f"sh:buy:{i}")]
            for i, p in items]
    rows.append(nav("sh:menu"))
    return _mk(rows)

def stars_packs() -> InlineKeyboardMarkup:
    rows = []
    for pid, p in config.STARS_PACKAGES.items():
        rows.append([Btn(text=f"{config.YELLOW}⭐️ {p['stars']} — {p['label']}", callback_data=f"pay:{pid}")])
    rows.append(nav("sh:menu"))
    return _mk(rows)

def emoji_page(n: int, owned: list) -> InlineKeyboardMarkup:
    from . import emojis
    rows, row = [], []
    for i, (e, _cid) in enumerate(emojis.page(n)):
        num = n * emojis.PAGE_SIZE + i + 1
        mark = f"{config.GREEN}✅" if num in owned else f"{config.YELLOW}🔒"
        row.append(Btn(text=f"{mark}{e}", callback_data=f"e:buy:{num}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    navr = []
    if n > 0:
        navr.append(Btn(text=f"{config.BLUE}◀️", callback_data=f"e:pg:{n-1}"))
    navr.append(Btn(text=f"{config.DARK}📄 {n+1}/{emojis.PAGES}", callback_data="e:none"))
    if n < emojis.PAGES - 1:
        navr.append(Btn(text=f"{config.BLUE}▶️", callback_data=f"e:pg:{n+1}"))
    rows.append(navr)
    rows.append(nav("sh:menu"))
    return _mk(rows)

# ——————————————— راهنما ———————————————
def guide_index() -> InlineKeyboardMarkup:
    rows = [[Btn(text=f"{config.BLUE}{gamedata.GUIDE[k][0]}", callback_data=f"gd:view:{k}")]
            for k in gamedata.GUIDE]
    rows.append(nav())
    return _mk(rows)

def guide_page(key: str) -> InlineKeyboardMarkup:
    keys = list(gamedata.GUIDE)
    i = keys.index(key)
    navr = []
    if i > 0:
        navr.append(Btn(text=f"{config.BLUE}◀️ قبلی", callback_data=f"gd:view:{keys[i-1]}"))
    if i < len(keys) - 1:
        navr.append(Btn(text=f"{config.BLUE}▶️ بعدی", callback_data=f"gd:view:{keys[i+1]}"))
    if navr:
        rows = [navr]
    else:
        rows = []
    rows.append(nav("gd:index"))
    return _mk(rows)

# ——————————————— کانال ———————————————
def channel_join(url: str) -> InlineKeyboardMarkup:
    return _mk([
        [Btn(text=f"{config.GREEN}📢 عضویت در کانال", url=url)],
        [Btn(text=f"{config.GREEN}✅ بررسی عضویت", callback_data="ch:check")],
    ])
