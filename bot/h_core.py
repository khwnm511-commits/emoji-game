"""هستهٔ هندلرها — شروع، منو، پروفایل، داستان، مأموریت، جهان، کوله، توانایی، راهنما، NPC، رتبه."""
import json, time, zoneinfo
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from . import config, db, repo, engine, kb, ui, sec, gamedata

r = Router()
TZ = zoneinfo.ZoneInfo(config.TZ)

class St(StatesGroup):
    gender = State()
    friend_add = State()
    rel_add = State()
    clan_name = State()
    team_invite = State()
    pvp_target = State()

NOW = lambda: int(time.time())


def home_text(p: dict) -> str:
    return ui.panel(
        f"🧬 RE: GLOBAL COLLAPSE — فصل {config.SEASON}",
        f"👤 {p['name']} | Lv.{p['level']} | 🏆 {p['score']:,}",
        ui.status_line(p),
        f"📍 {gamedata.REGIONS[p['region']]['name']} | 🪙 {p['coins']:,}",
        footer="یکی از دکمه‌ها رو انتخاب کن ⬇️")


async def me(x) -> dict | None:
    pid = x.from_user.id
    return await repo.get_player(pid)


async def ensure_member(bot: Bot, pid: int) -> bool:
    """عضویت کانال — اجباری برای باس‌ها، یادآوری کنترل‌شده."""
    if not config.CHANNEL_ID:
        return True
    try:
        m = await bot.get_chat_member(config.CHANNEL_ID, pid)
        return m.status in ("member", "administrator", "creator")
    except Exception:
        return True  # اگر کانال در دسترس نبود، بازی بلاک نشه


async def channel_remind(bot: Bot, p: dict, chat_id: int) -> bool:
    """یادآوری هر ۴۰ دقیقه حداکثر — Anti-Spam."""
    if not config.CHANNEL_ID:
        return False
    if await ensure_member(bot, p["id"]):
        return False
    if NOW() - p["last_remind"] < config.CHANNEL_REMIND_SEC:
        return False
    await repo.update_player(p["id"], last_remind=NOW())
    await bot.send_message(chat_id, "📢 برای باس‌فایت و رویدادها عضو کانال رسمی بازی شو.", reply_markup=kb.channel_join(await channel_url(bot)))
    return True


async def channel_url(bot: Bot) -> str:
    try:
        c = await bot.get_chat(config.CHANNEL_ID)
        if c.invite_link:
            return c.invite_link
        link = await bot.create_chat_invite_link(config.CHANNEL_ID)
        return link.invite_link
    except Exception:
        return "https://t.me/"


# ——————————————— /start و آنبوردینگ ———————————————
@r.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    p = await repo.get_player(msg.from_user.id)
    if p:
        return await msg.answer(home_text(p), reply_markup=kb.main_menu(msg.from_user.id == config.OWNER_ID))
    intro = ("🧬 **RE: GLOBAL COLLAPSE**\n" + ui.LINE + "\n"
             "شهر راکون سقوط کرده. ویروسها از آزمایشگاه آمبرلا بیرون ریخته‌اند و تنها راه بقا، پیوندن.\n\n"
             "⚔️ نبرد نوبتی | 🧬 ویروس و جهش | 📖 داستان شاخه‌ای\n"
             "👥 چندنفره گروهی | 👹 باس‌های سراسری | 🎭 ایموجی پرمیوم\n\n"
             "برای شروع، جنسیت شخصیتت رو انتخاب کن — بقیه خودکار ساخته می‌شه:")
    await state.set_state(St.gender)
    await msg.answer(intro, reply_markup=kb.gender())


@r.callback_query(St.gender, F.data.startswith("gen:"))
async def gen_pick(cbq: CallbackQuery, state: FSMContext):
    gender = "m" if cbq.data == "gen:m" else "f"
    ch = engine.gen_character(gender)
    await repo.create_player(cbq.from_user.id, ch["name"], cbq.from_user.username, gender,
                             ch["appearance"], ch["background"])
    await state.clear()
    p = await repo.get_player(cbq.from_user.id)
    await cbq.message.edit_text(
        ui.panel("👤 شخصیت تو ساخته شد", f"👤 **{p['name']}**", f"🎭 {p['appearance']}", f"📖 {p['background']}",
                 footer="داستان شروع شد — اولین انتخابت منتظرته ⬇️"),
        reply_markup=kb.story(p["story_node"], gamedata.STORY[p["story_node"]]["choices"]))
    await cbq.answer()


# ——————————————— خانه ———————————————
@r.callback_query(F.data == "m:home")
async def home(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    await cbq.message.edit_text(home_text(p), reply_markup=kb.main_menu(cbq.from_user.id == config.OWNER_ID))
    await cbq.answer()


# ——————————————— پروفایل ———————————————
@r.callback_query(F.data == "m:prof")
async def profile(cbq: CallbackQuery):
    p = await me(cbq)
    comp = (p["story_flags"] or {}).get("companion")
    npc_line = f"\n🤝 همراه: {gamedata.NPCS[comp]['name']}" if comp else ""
    inf = f"🧬 {gamedata.VIRUSES[p['infection_virus']]['name']} ({ui_stage(p)})" if p["infection_virus"] else f"🧬 {gamedata.STAGES[p['infection_stage']]}"
    await cbq.message.edit_text(ui.panel(
        f"👤 {p['name']} — Lv.{p['level']}",
        f"🎭 {p['appearance']}\n📖 {p['background']}",
        f"🏆 امتیاز: **{p['score']:,}** | 🪙 سکه: **{p['coins']:,}** | XP: {p['xp']}",
        f"🗡 ATK {p['atk']} | 🛡 DEF {p['def']} | 💨 SPD {p['spd']} | 🍀 {p['luck']}",
        f"🔫 {gamedata.ITEMS[p['weapon']]['name'] if p['weapon'] else 'بدون سلاح'} | "
        f"🦺 {gamedata.ITEMS[p['armor']]['name'] if p['armor'] else 'بدون زره'}",
        inf + npc_line,
        f"⭐️ اعتبار: {p['reputation']}",
        footer="هر سطح: HP+10 ATK+2 DEF+1"), reply_markup=kb.profile(cbq.from_user.id == config.OWNER_ID, comp))
    await cbq.answer()


def ui_stage(p):
    return gamedata.STAGES[p["infection_stage"]]


# ——————————————— داستان ———————————————
@r.callback_query(F.data == "st:node")
async def story_view(cbq: CallbackQuery):
    p = await me(cbq)
    node = gamedata.STORY[p["story_node"]]
    await cbq.message.edit_text(ui.panel(f"📖 {node['title']}", node["text"]),
                                reply_markup=kb.story(p["story_node"], node["choices"]))
    await cbq.answer()


@r.callback_query(F.data.startswith("st:choice:"))
async def story_choice(cbq: CallbackQuery):
    p = await me(cbq)
    _, _, node_id, idx = cbq.data.split(":")
    if node_id != p["story_node"]:
        return await cbq.answer("این بخش قدیمی شده", show_alert=True)
    c = gamedata.STORY[node_id]["choices"][int(idx)]
    fx = c.get("fx", {})
    # اعمال افکت‌ها — همه سرور-ساید
    parts = []
    if fx.get("trust"):
        for npc, d in fx["trust"].items():
            await repo.npc_trust_add(p["id"], npc, d)
    if fx.get("rep"):
        await repo.update_player(p["id"], reputation=p["reputation"] + fx["rep"])
    if fx.get("xp"):
        p = await repo.give(p["id"], xp=fx["xp"])
    if fx.get("coins"):
        p = await repo.give(p["id"], coins=fx["coins"])
    if fx.get("heal"):
        p = await repo.give(p["id"], heal=fx["heal"])
    if fx.get("unlock"):
        await repo.story_log(p["id"], "unlock", fx["unlock"])
        parts.append(f"🗺 منطقهٔ **{gamedata.REGIONS[fx['unlock']]['name']}** باز شد")
    if fx.get("mission"):
        await repo.mission_start(p["id"], fx["mission"])
        parts.append(f"🎯 مأموریت **{gamedata.MISSIONS[fx['mission']]['name']}** شروع شد")
    if fx.get("item"):
        await repo.inv_add(p["id"], fx["item"])
        parts.append(f"🎁 {gamedata.ITEMS[fx['item']]['name']} گرفتی")
    if fx.get("infect") and engine.random.random() < fx["infect"]:
        await repo.update_player(p["id"], infection_virus="t", infection_stage=1, infection_ts=NOW())
        parts.append("☣️ آلوده شدی! واکسن لازم داری")
    flags = p["story_flags"] or {}
    if fx.get("flag"):
        flags[fx["flag"]] = True
    nxt = c.get("next")
    if nxt:
        flags["node"] = nxt
        await repo.update_player(p["id"], story_flags=json.dumps(flags), story_node=nxt)
        await repo.story_log(p["id"], node_id, c["label"])
    if fx.get("flag") == "final_ready":
        parts.append("👹 باس فصل در آزمایشگاه فعال شد — منوی 🧟 باس‌ها")
    await cbq.message.edit_text(
        ui.panel(f"✅ انتخاب ثبت شد", f"«{c['label']}»", *parts),
        reply_markup=kb.story(nxt, gamedata.STORY[nxt]["choices"]) if nxt else kb.nav())
    await cbq.answer()


# ——————————————— مأموریت‌ها ———————————————
@r.callback_query(F.data == "mi:list")
async def missions_list(cbq: CallbackQuery):
    p = await me(cbq)
    active = [m["mission_id"] for m in await repo.missions_of(p["id"], "active")]
    done = {m["mission_id"] for m in await repo.missions_of(p["id"], "done")}
    claimed = {m["mission_id"] for m in await repo.missions_of(p["id"], "claimed")}
    avail = [mid for mid, m in gamedata.MISSIONS.items()
             if mid not in active and mid not in done and mid not in claimed and p["level"] >= m["req"]]
    await cbq.message.edit_text(ui.panel("🎯 مأموریت‌ها",
                                          "🎯 فعال‌ها را باز کن؛ پاداش فقط با ثبت سرور می‌آد."),
                                reply_markup=kb.missions(active, avail))
    await cbq.answer()


@r.callback_query(F.data.startswith("mi:view:"))
async def mission_view(cbq: CallbackQuery):
    p = await me(cbq)
    mid = cbq.data.split(":")[2]
    m = gamedata.MISSIONS[mid]
    st = await repo.mission_state(p["id"], mid)
    started = st is not None and st["status"] in ("active", "done", "claimed")
    done = st is not None and st["status"] == "done"
    prog = f"\n📊 پیشرفت: {st['progress']}/{m['target']}" if st else ""
    typ = {"kill": f"از بین بردن {m['target']} دشمن", "collect": f"جمع‌آوری {m['target']}× {gamedata.ITEMS.get(m.get('item',''),{}).get('name','')}",
           "boss": "کشته‌شدن باس مربوطه"}[m["type"]]
    await cbq.message.edit_text(
        ui.panel(f"🎯 {m['name']}",
                 f"📍 {gamedata.REGIONS[m['region']]['name']}\n{typ}\n🎁 {m['coins']} سکه + {m['xp']} XP{prog}"),
        reply_markup=kb.mission_view(mid, started, done))
    await cbq.answer()


@r.callback_query(F.data.startswith("mi:start:"))
async def mission_start_cb(cbq: CallbackQuery):
    p = await me(cbq)
    mid = cbq.data.split(":")[2]
    if cd_left := sec.cd.check(p["id"], "mission", 5):
        return await cbq.answer(f"⏳ {sec.cd.peek(p['id'],'mission'):.0f} ثانیه صبر کن", show_alert=True)
    await repo.mission_start(p["id"], mid)
    await cbq.answer("✅ مأموریت قبول شد!", show_alert=True)
    await missions_list(cbq)


@r.callback_query(F.data.startswith("mi:claim:"))
async def mission_claim(cbq: CallbackQuery):
    p = await me(cbq)
    mid = cbq.data.split(":")[2]
    ok = await sec.idempotent(p["id"], "mission_claim", f"mi:{p['id']}:{mid}:{(await repo.mission_state(p['id'], mid))['id']}")
    if not ok:
        return await cbq.answer("⚠️ این پاداش قبلاً داده شده", show_alert=True)
    m = await repo.mission_claim(p["id"], mid)
    if not m:
        return await cbq.answer("هنوز کامل نشده", show_alert=True)
    p = await repo.give(p["id"], coins=m["coins"], xp=m["xp"], score=m["xp"] // 2)
    await cbq.message.edit_text(
        ui.report(gamedata.REGIONS[m["region"]]["name"], f"مأموریت: {m['name']}",
                 f"❤️ {p['hp']}/{p['max_hp']}", "—", "✅ موفق",
                 f"🪙 {m['coins']} + 🧠 {m['xp']} XP", "پاداش سرور ثبت شد ✅"),
        reply_markup=kb.nav("mi:list"))
    await cbq.answer()


# ——————————————— جهان / مناطق ———————————————
@r.callback_query(F.data == "w:list")
async def regions_list(cbq: CallbackQuery):
    p = await me(cbq)
    await cbq.message.edit_text(
        ui.panel("🗺 جهان راکون", "هر منطقه خطر، لوت و دشمن خودش رو داره."),
        reply_markup=kb.regions(p["level"], p["region"]))
    await cbq.answer()


@r.callback_query(F.data.startswith("w:view:"))
async def region_view(cbq: CallbackQuery):
    p = await me(cbq)
    rid = cbq.data.split(":")[2]
    reg = gamedata.REGIONS[rid]
    enemies = "، ".join(gamedata.ENEMIES[e]["name"] for e in reg["enemies"]) or "امن"
    loot = "، ".join(gamedata.ITEMS[i]["name"] for i in reg["loot"]) or "—"
    await cbq.message.edit_text(
        ui.panel(f"🗺 {reg['name']}",
                 f"⚠️ خطر: {reg['danger']} | ☣️ ریسک آلودگی: {int(reg['risk']*100)}%",
                 f"🧟 دشمن‌ها: {enemies}", f"🎁 لوت: {loot}", f"🔓 سطح لازم: {reg['lvl']}"),
        reply_markup=kb.region_view(rid, p["region"] == rid))
    await cbq.answer()


@r.callback_query(F.data.startswith("w:go:"))
async def region_travel(cbq: CallbackQuery):
    p = await me(cbq)
    rid = cbq.data.split(":")[2]
    reg = gamedata.REGIONS[rid]
    if p["level"] < reg["lvl"]:
        return await cbq.answer(f"🔒 سطح {reg['lvl']} لازمه", show_alert=True)
    if p["energy"] < 5:
        return await cbq.answer("⚡️ انرژی کمه — ۱ در دقیقه برمی‌گرده", show_alert=True)
    p = await repo.give(p["id"], energy=-5)
    await repo.update_player(p["id"], region=rid)
    await cbq.answer(f"📍 به {reg['name']} رسیدی")
    await home(cbq)


# ——————————————— کوله ———————————————
@r.callback_query(F.data == "inv:list")
async def inventory_list(cbq: CallbackQuery):
    p = await me(cbq)
    inv = await repo.inv(p["id"])
    items = [(i, q) for i, q in sorted(inv.items())]
    await cbq.message.edit_text(
        ui.panel("🎒 کوله", f"ظرفیت: {len(items)}/{p['slots']}",
                 "🔫 سلاح و 🦺 زره رو از دکمه‌ها جدا کنی."),
        reply_markup=kb.inventory(items, p["weapon"], p["armor"]))
    await cbq.answer()


@r.callback_query(F.data.startswith("inv:view:"))
async def inv_view(cbq: CallbackQuery):
    p = await me(cbq)
    iid = cbq.data.split(":")[2]
    it = gamedata.ITEMS[iid]
    st = []
    if it["kind"] == "weapon": st.append(f"🗡 ATK +{it['atk']}")
    if it["kind"] == "armor": st.append(f"🛡 DEF +{it['def']}")
    if it.get("heal"): st.append(f"❤️ HP +{it['heal']}")
    if it.get("cure"): st.append("🧬 یک مرحله عفونت کم می‌کنه")
    if it.get("stun"): st.append("💡 دشمن رو گیج می‌کنه")
    await cbq.message.edit_text(
        ui.panel(f"{it['name']}", "\n".join(st) or "مصرفی ثبت نشده"),
        reply_markup=kb.item_view(iid, it["kind"] in ("weapon", "armor"), it["kind"] in ("med", "vaccine", "util"),
                                  (await repo.inv(p["id"])).get(iid, 0)))
    await cbq.answer()


@r.callback_query(F.data.startswith("inv:eq:"))
async def inv_equip(cbq: CallbackQuery):
    p = await me(cbq)
    iid = cbq.data.split(":")[2]
    it = gamedata.ITEMS[iid]
    slot = "weapon" if it["kind"] == "weapon" else "armor"
    await repo.update_player(p["id"], **{slot: iid})
    await cbq.answer(f"⚙️ {it['name']} تجهیز شد", show_alert=True)
    await inventory_list(cbq)


@r.callback_query(F.data.startswith("inv:uneq:"))
async def inv_uneq(cbq: CallbackQuery):
    p = await me(cbq)
    slot = "weapon" if cbq.data.endswith(":w") else "armor"
    await repo.update_player(p["id"], **{slot: None})
    await cbq.answer("🚫 جدا شد")
    await inventory_list(cbq)


@r.callback_query(F.data.startswith("inv:use:"))
async def inv_use(cbq: CallbackQuery):
    p = await me(cbq)
    iid = cbq.data.split(":")[2]
    it = gamedata.ITEMS[iid]
    if not await repo.inv_take(p["id"], iid):
        return await cbq.answer("نبود!", show_alert=True)
    if it["kind"] == "vaccine":
        if p["infection_stage"] == 0:
            await repo.inv_add(p["id"], iid)  # برش گردون
            return await cbq.answer("آلوده نیستی که!", show_alert=True)
        need = 3 if p["infection_stage"] >= 3 and not it.get("strong") else 0
        if p["infection_stage"] >= 3 and not it.get("strong"):
            await repo.inv_add(p["id"], iid)
            return await cbq.answer("🔴 مرحله شدید فقط با آنتی‌ویروس درمان می‌شه", show_alert=True)
        await repo.update_player(p["id"], infection_stage=0, infection_virus=None, infection_ts=NOW())
        await cbq.answer("✅ درمان کامل شدی", show_alert=True)
    elif it.get("heal"):
        p = await repo.give(p["id"], heal=it["heal"])
        await cbq.answer(f"❤️ +{it['heal']} HP", show_alert=True)
    else:
        await repo.inv_add(p["id"], iid)
        return await cbq.answer("این آیتم فقط توی نبرد کار داره", show_alert=True)
    await inventory_list(cbq)


# ——————————————— توانایی‌ها ———————————————
@r.callback_query(F.data == "ab:list")
async def abilities_list(cbq: CallbackQuery):
    p = await me(cbq)
    owned = [a for a in p["abilities"]]
    await cbq.message.edit_text(
        ui.panel("🧬 توانایی‌ها", "با سطح باز می‌شن — جهش‌ها جداگانه می‌آن."),
        reply_markup=kb.abilities(owned))
    await cbq.answer()


@r.callback_query(F.data.startswith("ab:view:"))
async def ability_view(cbq: CallbackQuery):
    aid = cbq.data.split(":")[2]
    a = gamedata.ABILITIES[aid]
    await cbq.answer(f"{a['name']} — {a['desc']} (Cooldown: {a['cd']} نوبت)", show_alert=True)


# ——————————————— NPC ———————————————
@r.callback_query(F.data == "npc:pick")
async def npc_pick(cbq: CallbackQuery):
    p = await me(cbq)
    trust = await repo.npc_all(p["id"])
    await cbq.message.edit_text(ui.panel("🧑‍🤝‍🧑 NPCهای بازی", "با اعتماد ۴۰+ همراه می‌شن."),
                                reply_markup=kb.npc_list_page(0, trust))
    await cbq.answer()


@r.callback_query(F.data.startswith("npc:pg:"))
async def npc_page(cbq: CallbackQuery):
    p = await me(cbq)
    trust = await repo.npc_all(p["id"])
    await cbq.message.edit_text(ui.panel("🧑‍🤝‍🧑 NPCها", "صفحهٔ بعدی/قبلی"),
                                reply_markup=kb.npc_list_page(int(cbq.data.split(":")[2]), trust))
    await cbq.answer()


@r.callback_query(F.data.startswith("npc:view:"))
async def npc_view(cbq: CallbackQuery):
    p = await me(cbq)
    nid = cbq.data.split(":")[2]
    n = gamedata.NPCS[nid]
    rel = await repo.npc_rel_get(p["id"], nid)
    comp = (p["story_flags"] or {}).get("companion")
    await cbq.message.edit_text(
        ui.panel(f"👤 {n['name']}",
                 f"🎖 {n['f']} | نقش: {n['role']}", f"💬 {n['pers']}",
                 f"🧬 توانایی همراه: {n['ability']}",
                 f"🤝 اعتماد: {rel['trust']} | ❤️ وفاداری: {rel['loyalty']}"),
        reply_markup=kb.npc_view(nid, rel["trust"], comp == nid, rel["trust"] >= 40 and comp is None))
    await cbq.answer()


@r.callback_query(F.data.startswith("npc:ally:"))
async def npc_ally(cbq: CallbackQuery):
    p = await me(cbq)
    nid = cbq.data.split(":")[2]
    rel = await repo.npc_rel_get(p["id"], nid)
    if rel["trust"] < 40:
        return await cbq.answer(f"🔒 اعتماد {40 - rel['trust']} تا کمه", show_alert=True)
    flags = p["story_flags"] or {}
    flags["companion"] = nid
    await repo.update_player(p["id"], story_flags=json.dumps(flags))
    await cbq.answer(f"🤝 {gamedata.NPCS[nid]['name']} همراهت شد", show_alert=True)
    await home(cbq)


@r.callback_query(F.data == "npc:drop")
async def npc_drop(cbq: CallbackQuery):
    p = await me(cbq)
    flags = p["story_flags"] or {}
    flags.pop("companion", None)
    await repo.update_player(p["id"], story_flags=json.dumps(flags))
    await cbq.answer("جدا شد")
    await home(cbq)


# ——————————————— رتبه‌بندی ———————————————
@r.callback_query(F.data.in_({"rk:players", "rk:clans"}))
async def ranking_cb(cbq: CallbackQuery):
    mode = cbq.data.split(":")[1]
    if mode == "players":
        top = await repo.top_players()
        body = "\n".join(f"{i+1}. {t['name']} — Lv.{t['level']} ({t['score']:,}🏆)" for i, t in enumerate(top)) or "هنوز کسی نیست"
        title = "🏆 برترین بازیکن‌ها"
    else:
        top = await repo.clans_top()
        body = "\n".join(f"{i+1}. {t['name']} — {t['points']:,}⚡" for i, t in enumerate(top)) or "هنوز کلنی نیست"
        title = "🏴 برترین کلن‌ها"
    await cbq.message.edit_text(ui.panel(title, body), reply_markup=kb.ranking(top, mode))
    await cbq.answer()


# ——————————————— راهنما ———————————————
@r.callback_query(F.data == "gd:index")
async def guide_index(cbq: CallbackQuery):
    await cbq.message.edit_text(ui.panel("📘 راهنما", "هر بخش: چیست / چه می‌کند / چطور / خطرش چیست."),
                                reply_markup=kb.guide_index())
    await cbq.answer()


@r.callback_query(F.data.startswith("gd:view:"))
async def guide_view(cbq: CallbackQuery):
    k = cbq.data.split(":")[2]
    t, what, does, how, risk = gamedata.GUIDE[k]
    await cbq.message.edit_text(ui.panel(t, f"1️⃣ {what}", f"2️⃣ {does}", f"3️⃣ {how}", f"4️⃣ {risk}"),
                                reply_markup=kb.guide_page(k))
    await cbq.answer()
