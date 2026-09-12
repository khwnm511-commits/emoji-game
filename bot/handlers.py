import json, time
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (Message, CallbackQuery, LabeledPrice,
                           PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton as Btn)
from . import db, config, kb, emojis, game, love, boss, chat, shop

r = Router()

class St(StatesGroup):
    infect_id = State()
    duel_id = State()
    rel_player = State()
    rel_player_name = State()

def ts(t):
    return t.strftime("%H:%M")

async def me(cbq_or_msg, state=None):
    """بازیکن همیشه حفظ می‌شه — از هر دسترسی."""
    m = cbq_or_msg.message if isinstance(cbq_or_msg, CallbackQuery) else cbq_or_msg
    p = await db.get_player(m.chat.id)
    if p:
        p = await game.regen_energy(p)
        await game.apply_infection_tick(p)
        p = await db.get_player(m.chat.id)
    return p

# ——————————————— شروع و منو ———————————————
@r.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    await state.clear()
    await db.ensure_player(msg.chat.id, msg.from_user.first_name or "بازیکن",
                           msg.from_user.username)
    p = await db.get_player(msg.chat.id)
    season = await db.get_config("season", config.SEASON)
    txt = (
        f"🎮 **Emoji Game** — فصل {['۱','۲','۳','۴','۵'][min(4,int(season)-1)]} 🏰\n\n"
        f"سلام {p['name']} عزیز! به دنیای جنگ‌ها، ویروس‌ها، عشق و باس‌های جهانی خوش اومدی.\n"
        f"⭐️ امتیازت هیچ‌وقت کم نمی‌شه — فقط بالا می‌ره!\n\n"
        f"🏆 امتیاز: **{p['score']:,}**   🪙 سکه: **{p['coins']:,}**\n"
        f"⚡️ سطح: **{p['level']}**   ❤️ HP: **{p['hp']}/{p['max_hp']}**"
    )
    await msg.answer(txt, reply_markup=kb.main_menu(p))

@r.callback_query(F.data == "m:main")
async def menu(cbq: CallbackQuery, state: FSMContext):
    await state.clear()
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    season = await db.get_config("season", config.SEASON)
    await cbq.message.edit_text(
        f"🎮 **Emoji Game** — فصل {['۱','۲','۳','۴','۵'][min(4,int(season)-1)]}\n"
        f"🏆 امتیاز: **{p['score']:,}** (هیچ‌وقت کم نمی‌شه)\n"
        f"🪙 سکه: **{p['coins']:,}**   ⚡️ سطح: **{p['level']}**   ❤️ **{p['hp']}/{p['max_hp']}**\n\nیه گزینه انتخاب کن:",
        reply_markup=kb.main_menu(p))
    await cbq.answer()

@r.callback_query(F.data == "m:prof")
async def profile(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    rels = await love.list_rels(p["id"])
    owned = json.loads(p["emojis_owned"])
    emoji_line = ""
    if owned:
        shown = owned[:15]
        text_part = "".join(emojis.emoji_by_index(i)[0] for i in shown)
        ents = emojis.custom_entities(text_part, shown)
        await cbq.message.edit_text(
            f"👤 **{p['name']}** — Lv.{p['level']}\n\n"
            f"🏆 امتیاز: **{p['score']:,}** (فقط بالا می‌ره!)\n"
            f"🪙 سکه: **{p['coins']:,}**\n"
            f"❤️ HP: **{p['hp']}/{p['max_hp']}**   🗡 ATK: **{p['attack']}**   🛡 DEF: **{p['defense']}**\n"
            f"⚡️ انرژی: **{p['energy']}/100**\n"
            f"💉 واکسن: **{p['vaccines']}**   💔 دل‌های شکسته: **{p['broken_hearts']}**\n"
            f"🆔 آیدی من: **{p[chr(105)+chr(100)]}**\n🎭 ایموجی‌های من: **{len(owned)}/۱۰۰**\n{text_part}",
            reply_markup=kb.back_main(), entities=ents)
        return await cbq.answer()
    await cbq.message.edit_text(
        f"👤 **{p['name']}** — Lv.{p['level']}\n\n"
        f"🏆 امتیاز: **{p['score']:,}** (فقط بالا می‌ره!)\n"
        f"🪙 سکه: **{p['coins']:,}**\n"
        f"❤️ HP: **{p['hp']}/{p['max_hp']}**   🗡 ATK: **{p['attack']}**   🛡 DEF: **{p['defense']}**\n"
        f"⚡️ انرژی: **{p['energy']}/100**\n"
        f"🆔 آیدی من: **{p[chr(105)+chr(100)]}**\n🎭 ایموجی‌ها: **{len(owned)}/۱۰۰** (از فروشگاه بخر!)",
        reply_markup=kb.back_main())
    await cbq.answer()

@r.callback_query(F.data == "m:top")
async def top(cbq: CallbackQuery):
    cur = await (await db.db()).execute(
        "SELECT name, score, level FROM players ORDER BY score DESC LIMIT 10")
    rows = await cur.fetchall()
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
    lines = [f"{medals[i]} {r['name']} — **{r['score']:,}** امتیاز (Lv.{r['level']})"
             for i, r in enumerate(rows)]
    season = await db.get_config("season", config.SEASON)
    await cbq.message.edit_text(
        f"🏆 برترین‌های فصل {['۱','۲','۳','۴','۵'][min(4,int(season)-1)]}:\n\n" + "\n".join(lines),
        reply_markup=kb.back_main())
    await cbq.answer()

# ——————————————— نبرد نوبتی ———————————————
@r.callback_query(F.data == "b:menu")
async def battle_menu(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    active = await game.active_battle(p["id"])
    if active and active["kind"] != "boss":
        await show_battle(cbq.message, active, p, edit=True)
        return await cbq.answer()
    await cbq.message.edit_text("⚔️ **نبرد نوبتی**\nحریف رو انتخاب کن:", reply_markup=kb.battle_menu())
    await cbq.answer()

async def show_battle(msg, b, p, edit=False, extra=""):
    st = json.loads(b["state"])
    if b["kind"] == "pve":
        txt = (f"⚔️ **نبرد نوبتی** vs {st['npc']}\n\n"
               f"❤️ حریف: **{max(0,st['hp'])}/{st['max_hp']}**\n"
               f"❤️ تو: **{max(0,st['p_hp'])}/{p['max_hp']}**\n{extra}\nنوبت توئه!")
        kb_ = kb.battle_actions(st.get("skill_ready", True))
    else:
        txt = (f"🆚 **دوئل** (نوبت {('تو' if b['turn'] == 1 else 'حریف')})\n\n"
               f"❤️ تو: **{max(0,st['p1_hp'])}**   ❤️ حریف: **{max(0,st['p2_hp'])}**\n{extra}")
        kb_ = kb.battle_actions(True)
    if edit:
        await msg.edit_text(txt, reply_markup=kb_)
    else:
        await msg.answer(txt, reply_markup=kb_)

@r.callback_query(F.data == "b:pve")
async def pve(cbq: CallbackQuery):
    p = await me(cbq)
    ok, p = await game.spend_energy(p["id"])
    if not ok:
        return await cbq.answer(f"😴 انرژی کمه! هر دقیقه ۱ تا پر می‌شه. ({p['energy']}/100)", show_alert=True)
    bid, st = await game.start_pve(p["id"], p)
    cur = await (await db.db()).execute("SELECT * FROM battles WHERE id=?", (bid,))
    b = await cur.fetchone()
    await cbq.message.edit_text(f"⚔️ **نبرد شروع شد!**\n\n🎲 حریف: {st['npc']}\n❤️ HP حریف: **{st['hp']}**")
    await show_battle(cbq.message, b, p)
    await cbq.answer()

async def pve_turn(cbq, action):
    p = await me(cbq)
    b = await game.active_battle(p["id"])
    if not b or b["kind"] != "pve":
        return await cbq.answer("نبردی نیست!", show_alert=True)
    st = json.loads(b["state"])
    extra = ""
    bonus = await love.partner_bonus(p["id"])  # پارتنر کمکت می‌کنه
    if action == "atk":
        d = game.dmg(int(p["attack"] * (1 + bonus)), st["dfn"])
        st["hp"] -= d
        extra = f"🗡 **{d}** دمیج زدی!"
    elif action == "def":
        st["guard"] = True
        extra = "🛡 حالت دفاعی!"
    elif action == "skl":
        if not st.get("skill_ready"):
            await cbq.answer("ضربه ویژه یک بار مصرفه!", show_alert=True)
            return
        d = game.dmg(int(p["attack"] * 2.5 * (1 + bonus)), st["dfn"])
        st["hp"] -= d
        st["skill_ready"] = False
        extra = f"💥 ضربه ویژه: **{d}** دمیج!"
    else:  # flee
        await game.close_battle(b["id"])
        await cbq.message.edit_text("🏃 فرار کردی... (امتیازت همون‌جوری که بود می‌مونه)",
                                    reply_markup=kb.battle_menu())
        return await cbq.answer()

    if st["hp"] <= 0:
        await game.close_battle(b["id"])
        await db.add_score(p["id"], config.SCORE_KILL_PVE, coins=10, xp=20)
        p, leveled = await game.check_level(p["id"], p)
        lt = f"\n🎉 **لول {p['level']}** رسیدی! آمارها آپ شد." if leveled else ""
        await cbq.message.edit_text(
            f"🏆 {st['npc']} رو شکست دادی!\n"
            f"⭐️ +{config.SCORE_KILL_PVE} امتیاز   🪙 +۱۰ سکه   ✨ +۲۰ XP{lt}",
            reply_markup=kb.battle_menu())
        return await cbq.answer()

    # نوبت حریف
    mob_dmg = game.dmg(st["atk"], p["defense"] + (6 if st.get("guard") else 0))
    st["p_hp"] = p["hp"] - mob_dmg
    st["guard"] = False
    extra += f"\n💥 حریف **{mob_dmg}** دمیج زد!"
    if st["p_hp"] <= 0:
        await game.close_battle(b["id"])
        await db.update_player(p["id"], hp=1)  # نمی‌میری، صفر نمی‌شی
        await db.add_score(p["id"], config.SCORE_WIN_LOSS, xp=10)  # باختی ولی امتیاز کم نشد!
        await cbq.message.edit_text(
            f"😵 از {st['npc']} باختی...\n"
            f"ولی امتیازت هیچ‌وقت کم نمی‌شه! ⭐️ +{config.SCORE_WIN_LOSS} امتیاز تجربه گرفتی.\n"
            f"❤️ تا فردا استراحت کن یا نان بخر.",
            reply_markup=kb.battle_menu())
        return await cbq.answer()
    await db.update_player(p["id"], hp=st["p_hp"])
    await game.save_state(b["id"], st)
    cur = await (await db.db()).execute("SELECT * FROM battles WHERE id=?", (b["id"],))
    b2 = await cur.fetchone()
    await show_battle(cbq.message, b2, {**p, "hp": st["p_hp"]}, edit=True, extra=extra)
    await cbq.answer()

@r.callback_query(F.data.in_({"b:atk", "b:def", "b:skl"}))
async def battle_actions(cbq: CallbackQuery):
    b = await game.active_battle(cbq.message.chat.id)
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    if b and b["kind"] == "pvp":
        await pvp_turn(cbq, p, b, cbq.data.split(":")[1])
    else:
        await pve_turn(cbq, cbq.data.split(":")[1])

@r.callback_query(F.data == "b:flee")
async def flee(cbq: CallbackQuery):
    b = await game.active_battle(cbq.message.chat.id)
    if b:
        await game.close_battle(b["id"])
    await cbq.message.edit_text("🏃 فرار کردی.", reply_markup=kb.battle_menu())
    await cbq.answer()

# ————— PvP —————
@r.callback_query(F.data == "b:pvp")
async def pvp_start(cbq: CallbackQuery, state: FSMContext):
    await cbq.message.edit_text(
        "🆚 آیدی عددی بازیکن رو بفرست تا چالش دوئل بره!\n"
        "(آیدی رو از پروفایلش یا با فوروارد پیامش از ربات @userinfobot بگیر)")
    await state.set_state(St.duel_id)
    await cbq.answer()

@r.message(St.duel_id)
async def pvp_challenge(msg: Message, state: FSMContext):
    raw = msg.text.replace("id", "").strip()
    if not raw.isdigit():
        return await msg.answer("فقط عدد بفرست! (آیدی تلگرام)")
    await state.clear()
    target = await db.get_player(int(raw))
    me_p = await db.get_player(msg.chat.id)
    if not target:
        return await msg.answer("این بازیکن هنوز عضو بازی نیست! 😕", reply_markup=kb.battle_menu())
    if target["id"] == msg.chat.id:
        return await msg.answer("با خودت دوئل؟! 😂", reply_markup=kb.battle_menu())
    st = {"kind": "pvp", "p1_hp": me_p["hp"], "p2_hp": target["hp"],
          "p1_atk": me_p["attack"], "p1_def": me_p["defense"],
          "p2_atk": target["attack"], "p2_def": target["defense"]}
    cur = await (await db.db()).execute(
        "INSERT INTO battles(kind,p1,p2,state,turn,active,created_date) VALUES('pvp',?,?,?,1,1,?)",
        ("pvp", msg.chat.id, target["id"], json.dumps(st), int(time.time())))
    await (await db.db()).commit()
    bid = cur.lastrowid
    try:
        await msg.bot.send_message(
            target["id"],
            f"⚔️ **{me_p['name']}** تو رو به دوئل نوبتی چالش کرد!\nقبول می‌کنی؟",
            reply_markup=kb.accept_duel(bid))
        await msg.answer(f"📩 چالش برای **{target['name']}** ارسال شد! منتظر قبولیش باش.",
                         reply_markup=kb.battle_menu())
    except Exception:
        await msg.answer("نتونستم بهش پیام بدم — ربات رو بلاک کرده.", reply_markup=kb.battle_menu())

@r.callback_query(F.data.startswith("b:acc:"))
async def pvp_accept(cbq: CallbackQuery):
    bid = int(cbq.data.split(":")[2])
    cur = await (await db.db()).execute("SELECT * FROM battles WHERE id=? AND active=1", (bid,))
    b = await cur.fetchone()
    if not b:
        return await cbq.answer("این دوئل دیگه معتبر نیست!", show_alert=True)
    p = await db.get_player(cbq.from_user.id)
    if p["id"] != b["p2"]:
        return await cbq.answer()
    await cbq.message.edit_text("⚔️ دوئل رو قبول کردی! نوبت‌ها می‌تاتین...")
    await cbq.message.answer("🆚 نبرد شروع شد! حریف شروع می‌کنه.")
    cur = await (await db.db()).execute("SELECT * FROM battles WHERE id=?", (bid,))
    b = await cur.fetchone()
    try:
        await cbq.bot.send_message(b["p1"], "⚔️ حریفت دوئل رو قبول کرد! نوبت توئه.")
        st = json.loads(b["state"])
        await cbq.bot.send_message(b["p1"],
            f"🆚 **دوئل**\n❤️ تو: **{st['p1_hp']}**   ❤️ حریف: **{st['p2_hp']}**",
            reply_markup=kb.battle_actions(True))
    except Exception:
        pass
    await cbq.answer()

@r.callback_query(F.data.startswith("b:rej:"))
async def pvp_reject(cbq: CallbackQuery):
    bid = int(cbq.data.split(":")[2])
    await (await db.db()).execute("UPDATE battles SET active=0 WHERE id=?", (bid,))
    await (await db.db()).commit()
    await cbq.message.edit_text("❌ دوئل رد شد.")
    await cbq.answer()

async def pvp_turn(cbq, p, b, action):
    st = json.loads(b["state"])
    if p["id"] == b["p1"] and b["turn"] != 1:
        return await cbq.answer("⏳ نوبت حریفه!", show_alert=True)
    if p["id"] == b["p2"] and b["turn"] != 2:
        return await cbq.answer("⏳ نوبت حریفه!", show_alert=True)
    my_key = "p1" if p["id"] == b["p1"] else "p2"
    opp_key = "p2" if my_key == "p1" else "p1"
    my_atk, opp_def = st[f"{my_key}_atk"], st[f"{opp_key}_def"]
    if action == "def":
        st[f"{my_key}_hp"] += 8  # دفاع = ترمیم کوچیک
        st[f"{my_key}_hp"] = min(st[f"{my_key}_hp"], p["max_hp"])
        extra = "🛡 دفاع کردی (+۸ HP)"
    else:
        mult = 2.5 if action == "skl" else 1
        d = game.dmg(int(my_atk * mult), opp_def)
        st[f"{opp_key}_hp"] -= d
        extra = f"🗡 **{d}** دمیج زدی!"
    await game.save_state(b["id"], st, turn=2 if b["turn"] == 1 else 1)
    if st[f"{opp_key}_hp"] <= 0:
        await game.close_battle(b["id"])
        loser_id = b["p1"] if opp_key == "p1" else b["p2"]
        await db.add_score(p["id"], config.SCORE_WIN_PVP, coins=50, xp=40)
        await db.add_score(loser_id, config.SCORE_WIN_LOSS, xp=15)  # امتیاز بازنده هم کم نمی‌شه
        winner_p, leveled = await game.check_level(p["id"], await db.get_player(p["id"]))
        await cbq.message.edit_text(
            f"🏆 **{p['name']}** دوئل رو برد!\n"
            f"⭐️ +{config.SCORE_WIN_PVP} امتیاز   🪙 +۵۰ سکه",
            reply_markup=kb.back_main())
        try:
            await cbq.bot.send_message(loser_id,
                f"😵 دوئل رو باختی، ولی امتیازت هیچ‌وقت کم نمی‌شه! ⭐️ +{config.SCORE_WIN_LOSS}")
        except Exception:
            pass
        return await cbq.answer()
    # پیام به حریف
    opp_id = b["p1"] if my_key == "p2" else b["p2"]
    try:
        await cbq.bot.send_message(opp_id,
            f"🆚 **دوئل در جریه**\n{extra}\n❤️ تو: **{max(0,st[opp_key+'_hp'])}**   ❤️ حریف: **{max(0,st[my_key+'_hp'])}**\nنوبت توئه!",
            reply_markup=kb.battle_actions(True))
    except Exception:
        pass
    await cbq.message.edit_text(
        f"🆚 **دوئل**\n{extra}\n❤️ تو: **{max(0,st[my_key+'_hp'])}**   ❤️ حریف: **{max(0,st[opp_key+'_hp'])}**\n⏳ نوبت حریف...",
        reply_markup=None)
    await cbq.answer()

# ——————————————— ویروس ———————————————
@r.callback_query(F.data == "v:menu")
async def virus_menu(cbq: CallbackQuery, state: FSMContext):
    await state.clear()
    p = await me(cbq)
    now = int(time.time())
    infected = p["infected_until"] and p["infected_until"] > now
    status = ""
    if infected:
        remain = (p["infected_until"] - now) // 60
        src = await db.get_player(p["infected_by"])
        who = src["name"] if src else "؟"
        status = f"\n🦠 **آلوده‌ای!** مبتلا‌کننده: {who}\n⏳ {remain} دقیقه مونده (تا اون موقع هر ساعت HP کم می‌شه)\n"
    await cbq.message.edit_text(
        f"🦠 **بازی ویروس**\n{status}\n"
        f"بازیکن‌ها رو آلوده کن → هر ساعت عفونت فعال برات امتیاز می‌سازه!\n"
        f"واکسن بخر که مصون شی. 💉",
        reply_markup=kb.virus_menu(bool(infected)))
    await cbq.answer()

@r.callback_query(F.data == "v:go")
async def infect_go(cbq: CallbackQuery, state: FSMContext):
    await cbq.message.edit_text("🦠 آیدی عددی بازیکنی که می‌خوای آلوده کنی رو بفرست:")
    await state.set_state(St.infect_id)
    await cbq.answer()

@r.message(St.infect_id)
async def do_infect(msg: Message, state: FSMContext):
    await state.clear()
    raw = msg.text.strip()
    if not raw.isdigit():
        return await msg.answer("فقط عدد!", reply_markup=kb.back_virus())
    victim = await db.get_player(int(raw))
    attacker = await db.get_player(msg.chat.id)
    if not victim or victim["id"] == attacker["id"]:
        return await msg.answer("این بازیکن نیست یا خودتی! 😅", reply_markup=kb.back_virus())
    result, until = await game.infect(attacker, victim)
    if result == "cooldown":
        return await msg.answer("⏳ هر ۵ دقیقه یک آلودگی!", reply_markup=kb.back_virus())
    if result == "already":
        return await msg.answer("😐 این یکی از قبل آلوده‌ست!", reply_markup=kb.back_virus())
    try:
        await msg.bot.send_message(victim["id"],
            f"🦠 **{attacker['name']}** تو رو به ویروس آلوده کرد!\n"
            f"⏳ تا {time.strftime('%H:%M', time.localtime(until))} آلوده‌ای.\n"
            f"با واکسن یا درمان فوری خلاص شو — منوی 🦠 ویروس")
    except Exception:
        pass
    await msg.answer(
        f"🦠 آلوده‌سازی انجام شد! تا وقتی مبتلا باشه، هر ساعت **{config.SCORE_INFECTION_HOUR} امتیاز** می‌گیری.",
        reply_markup=kb.back_virus())

@r.callback_query(F.data == "v:vac")
async def buy_vaccine(cbq: CallbackQuery):
    p = await me(cbq)
    if p["coins"] < 15:
        return await cbq.answer(f"🪙 سکه کمه! (۱۵ لازمه، {p['coins']} داری)", show_alert=True)
    await db.update_player(p["id"], coins=p["coins"] - 15, vaccines=p["vaccines"] + 1)
    await cbq.answer("💉 واکسن خریدی! دفعه بعد که آلوده شی خودکار مصرف می‌شه.")
    await virus_menu(cbq, None)

@r.callback_query(F.data == "v:cure")
async def cure_now(cbq: CallbackQuery):
    p = await me(cbq)
    if p["vaccines"] > 0:
        await db.update_player(p["id"], vaccines=p["vaccines"] - 1,
                               infected_by=None, infected_until=None)
        await cbq.answer("💉 واکسنت مصرف شد — سالم شدی!", show_alert=True)
        return await virus_menu(cbq, None)
    if p["coins"] < 30:
        return await cbq.answer("🪙 ۳۰ سکه لازمه!", show_alert=True)
    await db.update_player(p["id"], coins=p["coins"] - 30,
                           infected_by=None, infected_until=None)
    await cbq.answer("🚑 درمان شدی!", show_alert=True)
    await virus_menu(cbq, None)

# ——————————————— عشق و روابط ———————————————
@r.callback_query(F.data == "l:menu")
async def love_menu(cbq: CallbackQuery, state: FSMContext):
    await state.clear()
    p = await me(cbq)
    rels = await love.list_rels(p["id"])
    await cbq.message.edit_text(
        "❤️ **عشق و روابط**\n\nهر رابطه ۴ ویژگی مستقل داره:\n"
        "🤝 اعتماد — 🛡 وفاداری — 🙏 احترام — ⏳ سابقه\n\n"
        "رفتار تو وضعیت رو عوض می‌کنه، نه دکمه‌ها. دروغ و خیانت اثر بلندمدت داره. "
        "بعضی رابطه‌ها تا آشکار شن مخفی می‌مونن! 🔒",
        reply_markup=kb.love_menu(rels))
    await cbq.answer()

@r.callback_query(F.data == "l:new")
async def love_new(cbq: CallbackQuery):
    await cbq.message.edit_text(
        "💬 با کی رابطه بسازیم؟\n\nNPCهای داستانی شخصیت و هدف خودشون رو دارن — "
        "همیشه باهات موافق نیستن!", reply_markup=kb.npc_list())
    await cbq.answer()

@r.callback_query(F.data.startswith("l:npc:"))
async def love_npc(cbq: CallbackQuery):
    i = int(cbq.data.split(":")[2])
    name, bio = love.NPCS[i]
    p = await me(cbq)
    rel = await love.upsert_rel(p["id"], 1000 + i, name, True)
    await cbq.message.edit_text(f"🧙 **{name}**\n{bio}\n\nرابطه شروع شد! با رفتارت رشدش بده.",
                                reply_markup=kb.love_actions(rel["id"], rel["status"]))
    await cbq.answer()

@r.callback_query(F.data == "l:pl")
async def love_player(cbq: CallbackQuery, state: FSMContext):
    await cbq.message.edit_text("👤 آیدی عددی بازیکن رو بفرست:")
    await state.set_state(St.rel_player)
    await cbq.answer()

@r.message(St.rel_player)
async def love_player_id(msg: Message, state: FSMContext):
    await state.clear()
    raw = msg.text.strip()
    if not raw.isdigit():
        return await msg.answer("فقط عدد!")
    target = await db.get_player(int(raw))
    if not target:
        return await msg.answer("این بازیکن عضو بازی نیست!", reply_markup=kb.back_main())
    if target["id"] == msg.chat.id:
        return await msg.answer("با خودت؟! 😂", reply_markup=kb.back_main())
    rel = await love.upsert_rel(msg.chat.id, target["id"], target["name"], False)
    try:
        await msg.bot.send_message(target["id"],
            f"👤 **{(await db.get_player(msg.chat.id))['name']}** رابطه‌ای با تو شروع کرد!\n"
            f"علاقه یک‌طرفه ممکنه — الزاماً به رابطه تبدیل نمی‌شه. 😉")
    except Exception:
        pass
    await msg.answer(f"💬 رابطه با **{target['name']}** ساخته شد. (مخفیه تا عمیق‌تر شه 🔒)",
                      reply_markup=kb.love_actions(rel["id"], rel["status"]))

@r.callback_query(F.data.startswith("l:view:"))
async def love_view(cbq: CallbackQuery):
    rid = int(cbq.data.split(":")[2])
    p = await me(cbq)
    rel = await love.get_rel(p["id"], rid)
    if not rel:
        return await cbq.answer("رابطه پیدا نشد!", show_alert=True)
    status_fa = {"stranger": "غریبه 👤", "friend": "دوست 🤝", "close": "صمیمی 💜",
                 "partner": "پارتنر 💗", "rival": "رقیب ⚡️", "enemy": "دشمن ⚔️",
                 "broken": "قطع‌شده 💔"}.get(rel["status"], rel["status"])
    hide = "\n🔒 رابطه هنوز مخفیه (اعتماد بالای ۵۰ = آشکار)" if rel["hidden"] else ""
    if rel["broken"]:
        hide += "\n💔 این رابطه قطع شده — سابقه‌ش همیشه می‌مونه و روابط بعدی سخت‌ترن."
    await cbq.message.edit_text(
        f"💗 **{rel['target_name']}** — {status_fa}\n\n"
        f"🤝 اعتماد: **{rel['trust']}**\n🛡 وفاداری: **{rel['loyalty']}**\n"
        f"🙏 احترام: **{rel['respect']}**\n⏳ سابقه: **{rel['history']}**{hide}",
        reply_markup=kb.love_actions(rel["id"], rel["status"]))
    await cbq.answer()

@r.callback_query(F.data.startswith("l:"))
async def love_act(cbq: CallbackQuery):
    parts = cbq.data.split(":")
    kind, rid = parts[1], int(parts[2])
    p = await me(cbq)
    if kind in ("gift", "help", "resp", "hist", "lie", "betray", "prop", "break"):
        if kind == "gift":
            if p["coins"] < 20:
                return await cbq.answer("🪙 ۲۰ سکه لازمه!", show_alert=True)
            await db.update_player(p["id"], coins=p["coins"] - 20)
        res = await love.act(p["id"], rid, kind)
        if not res:
            return await cbq.answer("خطا!", show_alert=True)
        if res.get("cooldown"):
            return await cbq.answer("⏳ هر ۲ دقیقه یک تعامل — عجله نکن!")
        if res.get("broken"):
            return await love_menu(cbq, None)
        await cbq.answer(res["msg"], show_alert=True)
        return await love_view(cbq)

# ——————————————— باس‌ها ———————————————
@r.callback_query(F.data == "boss:menu")
async def boss_menu(cbq: CallbackQuery):
    p = await me(cbq)
    b = await boss.get_active_boss()
    now = int(time.time())
    txt = "👑 **باس‌ها**\n\n"
    if b:
        if now < b["starts_at"]:
            remain = (b["starts_at"] - now) // 60
            txt += (f"👑 **{b['name']}**\n⏳ کانت‌داون: **{remain} دقیقه**\n"
                    f"❤️ HP: **{b['max_hp']:,}**\n\nآماده‌سازی کن، اسکواد بچین، تجهیزات بچین!")
        else:
            remain = max(0, (b["ends_at"] - now) // 60)
            ranking = json.loads(b["ranking"])
            top = sorted(ranking.items(), key=lambda x: -x[1])[:5]
            names = [f"{i+1}. {(await db.get_player(int(pid)))['name']}: {d:,}" for i, (pid, d) in enumerate(top) if await db.get_player(int(pid))]
            txt += (f"👑 **{b['name']}** — {boss.PHASES[b['phase']]}\n"
                    f"❤️ HP: **{b['hp']:,}/{b['max_hp']:,}**\n"
                    f"⏳ {remain} دقیقه از رویداد مونده\n👥 شرکت‌کننده: **{len(ranking)}**\n\n"
                    + ("🏆 رتبه‌بندی:\n" + "\n".join(names) if names else ""))
    else:
        txt += ("فعلاً باسی نیست. زمان‌بندی سمت سرور:\n\n"
                "🐺 مینی‌باس — هر ۳ ساعت\n🐉 باس منطقه‌ای — هر ۱۲ ساعت\n"
                "☠️ باس داستانی — هر ۲۴ ساعت\n👑 باس جهانی — روزانه\n💀 باس نهایی — هفتگی")
    await cbq.message.edit_text(txt, reply_markup=kb.boss_menu(bool(p["boss_sub"]), bool(b)))
    await cbq.answer()

@r.callback_query(F.data == "boss:sub")
async def boss_sub(cbq: CallbackQuery):
    p = await me(cbq)
    await db.update_player(p["id"], boss_sub=0 if p["boss_sub"] else 1)
    await cbq.answer("🔕 اعلان باس‌ها خاموش شد" if p["boss_sub"] else "🔔 اعلان باس‌ها روشن شد!")
    await boss_menu(cbq)

@r.callback_query(F.data == "boss:hit")
async def boss_hit_cb(cbq: CallbackQuery):
    p = await me(cbq)
    b = await boss.get_active_boss()
    if not b:
        return await cbq.answer("باسی نیست!", show_alert=True)
    d, phase_or_msg = await boss.boss_hit(b, p)
    if d is None:
        return await cbq.answer(phase_or_msg, show_alert=True)
    await cbq.answer(f"⚔️ {d:,} دمیج زدی! ({boss.PHASES[phase_or_msg]})", show_alert=True)
    await boss_menu(cbq)

# ——————————————— گپ سراسری ———————————————
@r.callback_query(F.data == "c:menu")
async def chat_menu(cbq: CallbackQuery, state: FSMContext):
    await state.clear()
    p = await me(cbq)
    await cbq.message.edit_text(
        f"🌍 **گپ سراسری**\n\n{'✅ عضو گپ هستی' if p['chat_on'] else '🔕 از گپ خارجی'}\n"
        "هر پیامی که اینجا بفرستی به همه اعضا می‌رسه (هر ۱۲ ثانیه یک پیام).\n"
        "دیتای هیچ بازیکنی هیچ‌وقت پاک نمی‌شه — حتی بعد فصل‌های بعد!",
        reply_markup=kb.chat_menu(bool(p["chat_on"])))
    await cbq.answer()

@r.callback_query(F.data == "c:read")
async def chat_read(cbq: CallbackQuery):
    msgs = await chat.last_messages(15)
    lines = [f"**[{m['name']} | Lv.{m['level']}]** {m['text']}" for m in msgs]
    await cbq.answer()
    if not lines:
        return await cbq.message.edit_text("🌍 هنوز کسی حرفی نزده... اولین باش!",
                                          reply_markup=kb.back_main())
    await cbq.message.edit_text("🌍 **آخرین پیام‌های دنیای بازی:**\n\n" + "\n".join(lines),
                                reply_markup=kb.back_main())

@r.callback_query(F.data == "c:toggle")
async def chat_toggle(cbq: CallbackQuery):
    p = await me(cbq)
    await db.update_player(p["id"], chat_on=0 if p["chat_on"] else 1)
    await cbq.answer("🔕 از گپ خارج شدی" if p["chat_on"] else "🔔 به گپ سراسری برگشتی!")
    await chat_menu(cbq, None)

@r.message(F.text, ~F.text.startswith("/"))
async def global_chat(msg: Message, state: FSMContext):
    """هر متن عادی → گپ سراسری. هیچ دیتایی گم نمی‌شه."""
    p = await db.get_player(msg.chat.id)
    if not p:
        return await msg.answer("اول /start بزن تا بازیکن بشی! 🎮")
    p = await game.regen_energy(p)
    result, extra = await chat.send_chat(msg.chat.id, p, msg.text)
    if result == "rate":
        return await msg.answer(f"⏳ {extra} ثانیه صبر کن.")
    if result == "long":
        return await msg.answer(f"✂️ حداکثر {config.CHAT_MAX_LEN} کاراکتر!")
    if result == "off":
        return await msg.answer("🔕 از گپ خارجی! از منو برگرد.")
    delivered = await chat.broadcast(msg.bot, p, msg.text)
    await msg.answer(f"🌍 به {delivered} بازیکن رسید! ⭐️ حضور توی گپ = فعالیت")

# ——————————————— فروشگاه و ایموجی ———————————————
@r.callback_query(F.data == "shop:menu")
async def shop_menu_cb(cbq: CallbackQuery, state: FSMContext):
    await state.clear()
    p = await me(cbq)
    owned = json.loads(p["emojis_owned"])
    await cbq.message.edit_text(
        "🛍 **فروشگاه**\n\n⭐️ پرمیوم: خرید ایموجی با استارز تلگرام\n🪙 آیتم‌ها: خرید با سکه",
        reply_markup=kb.shop_menu(len(owned)))
    await cbq.answer()

@r.callback_query(F.data.startswith("e:pg:"))
async def emoji_pages(cbq: CallbackQuery):
    n = int(cbq.data.split(":")[2])
    p = await me(cbq)
    owned = json.loads(p["emojis_owned"])
    await cbq.message.edit_text(
        f"🎭 **ایموجی‌های پرمیوم** — صفحه {n+1} از {emojis.PAGES}\n"
        f"مالک: {len(owned)}/۱۰۰ — ✅ داری / 🔒 قفل\n"
        f"هر ایموجی: ⭐️۲۵ استارز | پک کامل توی منوی استارز",
        reply_markup=kb.emoji_page(n, owned))
    await cbq.answer()

@r.callback_query(F.data == "e:none")
async def emoji_none(cbq: CallbackQuery):
    await cbq.answer()

@r.callback_query(F.data.startswith("e:buy:"))
async def emoji_buy(cbq: CallbackQuery):
    num = int(cbq.data.split(":")[2])
    p = await me(cbq)
    owned = json.loads(p["emojis_owned"])
    if num in owned:
        return await cbq.answer("اینو داری! ✅", show_alert=True)
    payload = await shop.buy_emoji(p["id"], num)
    e, _cid = emojis.emoji_by_index(num)
    await cbq.message.answer_invoice(
        title=f"ایموجی پرمیوم {e}",
        description="ایموجی سفارشی برای پروفایل و پیام‌هات — کیفیت پرمیوم تلگرام",
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label="ایموجی پرمیوم", amount=25)])
    await cbq.answer("⭐️ فاکتور استارز ارسال شد!")

@r.callback_query(F.data == "shop:items")
async def shop_items(cbq: CallbackQuery):
    await cbq.message.edit_text("🛒 آیتم‌ها (با سکه 🪙):", reply_markup=kb.items_menu())
    await cbq.answer()

@r.callback_query(F.data.startswith("buy:"))
async def buy_item(cbq: CallbackQuery):
    item = cbq.data.split(":")[1]
    p = await me(cbq)
    cost = {"vac": 15, "bread": 20, "sword": 80, "shield": 80}[item]
    if p["coins"] < cost:
        return await cbq.answer(f"🪙 سکه کمه! {cost} لازمه، {p['coins']} داری", show_alert=True)
    if item == "vac":
        await db.update_player(p["id"], coins=p["coins"] - cost, vaccines=p["vaccines"] + 1)
        await cbq.answer("💉 واکسن خریدی!")
    elif item == "bread":
        hp = min(p["max_hp"], p["hp"] + 40)
        await db.update_player(p["id"], coins=p["coins"] - cost, hp=hp)
        await cbq.answer(f"🍞 HP شد {hp}!")
    elif item == "sword":
        await db.update_player(p["id"], coins=p["coins"] - cost, attack=p["attack"] + 3)
        await cbq.answer("⚔️ شمشیر! ATK+3")
    else:
        await db.update_player(p["id"], coins=p["coins"] - cost, defense=p["defense"] + 3)
        await cbq.answer("🛡 سپر! DEF+3")

# ——————————————— استارز ———————————————
@r.callback_query(F.data == "stars:menu")
async def stars_menu_cb(cbq: CallbackQuery, state: FSMContext):
    await state.clear()
    await cbq.message.edit_text(
        "⭐️ **خرید با استارز تلگرام**\n\nپرداخت امن داخل تلگرام — بعد از پرداخت فوراً وصل می‌شه:",
        reply_markup=kb.stars_menu())
    await cbq.answer()

@r.callback_query(F.data.startswith("pay:"))
async def pay(cbq: CallbackQuery):
    stars = int(cbq.data.split(":")[1])
    pack = shop.STARS_PACKS[stars]
    payload = await shop.invoice_payload(stars, cbq.from_user.id)
    await cbq.message.answer_invoice(
        title=pack["title"],
        description=pack["desc"],
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=pack["title"], amount=stars)])
    await cbq.answer("⭐️ فاکتور ارسال شد!")

@r.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@r.message(F.successful_payment)
async def successful_payment(msg: Message):
    sp = msg.successful_payment
    payload = sp.invoice_payload
    cur = await (await db.db()).execute(
        "INSERT OR IGNORE INTO star_payments(player_id,stars,payload,charge_id,ts) VALUES(?,?,?,?,?)",
        (msg.chat.id, sp.total_amount, payload, sp.telegram_payment_charge_id, int(time.time())))
    await (await db.db()).commit()
    if cur.rowcount == 0:
        return  # پرداخت تکراری — بدون باگ، فقط یک بار جایزه
    parts = payload.split(":")
    if parts[0] == "pack":
        pack = await shop.grant_pack(msg.chat.id, int(parts[1]))
        if pack:
            await msg.answer(
                f"✅ پرداخت موفق! **{pack['title']}** فعال شد.\n"
                f"🪙 سکه‌ها: +{pack['coins']}   💉 واکسن: +{pack['vaccines']}   🎭 ایموجی: +{pack['emojis'] or 0}")
    elif parts[0] == "emoji":
        num = int(parts[1])
        if await shop.grant_emoji(msg.chat.id, num):
            e, _ = emojis.emoji_by_index(num)
            await msg.answer(f"✅ ایموجی پرمیوم {e} مال تو شد!")
