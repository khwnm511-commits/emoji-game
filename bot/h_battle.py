"""نبرد — PvE نوبتی، PvP دوئل، ضربه به باس. همه سرور-ساید."""
import json, time
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from . import config, db, repo, engine, kb, ui, sec, gamedata, ai
from .h_core import St, me, NOW, ensure_member, home_text

r = Router()


def _energy_fail(cbq, p, n=config.ENERGY_COST_BATTLE):
    if p["energy"] < n:
        return True
    return False


async def _battle_panel(cbq: CallbackQuery, p: dict, b: dict):
    st = b["state"]
    me_side = st["p1"]
    foe = st.get("p2") or st["enemy"]
    hint = ai.battle_hint(p, st)
    bar_len = 10
    ebar = "█" * max(0, round(foe["hp"] / foe["max_hp"] * bar_len))
    await cbq.message.edit_text(
        ui.panel("⚔️ نبرد فعال",
                 f"👤 تو: ❤️ {me_side['hp']}/{me_side['max_hp']}",
                 f"🧟 {foe['name']}: ❤️ {foe['hp']}/{foe['max_hp']}\n{ebar}{'░'*(bar_len-len(ebar))}",
                 footer=f"🤖 پیشنهاد: {hint}"),
        reply_markup=kb.battle_actions(True, bool(await repo.inv(p["id"])), False))
    await cbq.answer()


@r.callback_query(F.data == "b:menu")
async def battle_menu(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    await cbq.message.edit_text(
        ui.panel("⚔️ مبارزه", f"📍 منطقه: {gamedata.REGIONS[p['region']]['name']}",
                 ui.status_line(p), "جست‌وجوی دشمن انرژی می‌بره — نوبتی و تاکتیکی بجنگ."),
        reply_markup=kb.battle_menu())
    await cbq.answer()


@r.callback_query(F.data.startswith("b:hunt:"))
async def hunt(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    if p["status"] != "active":
        return await cbq.answer("🏥 فعلاً نمی‌تونی بجنگی — درمان کن", show_alert=True)
    rid = cbq.data.split(":")[2]
    rid = p["region"] if rid == "cur" else rid
    reg = gamedata.REGIONS[rid]
    if rid == "safezone" or not reg["enemies"]:
        return await cbq.answer("اینجا امنه — به منطقهٔ دیگه سفر کن", show_alert=True)
    if p["level"] < reg["lvl"]:
        return await cbq.answer(f"🔒 سطح {reg['lvl']} لازمه", show_alert=True)
    if await repo.battle_active(p["id"]):
        return await cbq.answer("توی نبرد دیگه‌ای!", show_alert=True)
    if _energy_fail(cbq, p):
        return await cbq.answer("⚡️ انرژی کمه", show_alert=True)
    if not sec.cd.check(p["id"], "hunt", 3):
        return await cbq.answer("⏳ لحظه‌ای صبر کن")
    # انتخاب دشمن بر اساس خطر منطقه — سرور-ساید
    import random
    enemy_id = random.choice(reg["enemies"])
    p = await repo.give(p["id"], energy=-config.ENERGY_COST_BATTLE)
    comp = (p["story_flags"] or {}).get("companion")
    st = engine.new_battle_state(p, "p1", gamedata.ENEMIES[enemy_id], rid, companion=comp)
    bid = await repo.battle_create("pve", p["id"], enemy_id=enemy_id, chat_id=cbq.message.chat.id, state=st)
    b = await repo.battle_get(bid)
    await _battle_panel(cbq, p, b)


async def _resolve(cbq: CallbackQuery, apply_fn) -> None:
    """بارگذاری نبرد فعال، اجرای امن اکشن، ذخیره، نمایش نتیجه."""
    p = await me(cbq)
    b = await repo.battle_active(p["id"])
    if not b:
        return await cbq.answer("نبرد فعالی نداری", show_alert=True)
    # قفل race: دو کلیک همزمان
    lock = await db.lock(f"battle:{b['id']}")
    if lock.locked():
        return await cbq.answer("⏳ در حال پردازش...")
    async with lock:
        b = await repo.battle_get(b["id"])  # re-read داخل قفل
        if not b["active"]:
            return await cbq.answer("نبرد تموم شده", show_alert=True)
        swapped = False
        if b["kind"] == "pvp" and b["p2"] == p["id"]:
            b["state"]["p1"], b["state"]["p2"] = b["state"]["p2"], b["state"]["p1"]
            swapped = True
        out = apply_fn(p, b)
        if out is None:
            if swapped:
                b["state"]["p1"], b["state"]["p2"] = b["state"]["p2"], b["state"]["p1"]
            return
        st = b["state"]
        if swapped:
            st["p1"], st["p2"] = st["p2"], st["p1"]
        st["turn"] += 1
        events = "\n".join(out.get("events", []))
        if out.get("win"):
            await repo.battle_deactivate(b["id"])
            if b["kind"] == "pvp":
                await _on_pvp_win(cbq, p, b, st)
            else:
                await _on_win(cbq, p, b, st)
        elif out.get("lose"):
            await repo.battle_deactivate(b["id"])
            if b["kind"] == "pvp":
                loser_name = st["p2"]["name"] if swapped else st["p1"]["name"]
                winner_id = b["p2"] if swapped else b["p1"]
                w = await repo.give(winner_id, xp=40, score=40, coins=20)
                await cbq.message.edit_text(
                    ui.report("دوئل PvP", "نبرد بازیکن‌ها", "—", loser_name, "❌ شکست",
                              f"برنده {w['name']} — ۴۰🏆 + ۲۰🪙", "شکست پیامد داره ولی پایان بازی نیست"),
                    reply_markup=kb.nav())
                await cbq.answer()
            else:
                await _on_lose(cbq, p, b, st)
        elif out.get("fled", False):
            await repo.battle_deactivate(b["id"])
            await cbq.message.edit_text(ui.panel("🏃 فرار", "فرار کردی — انرژی از دست رفت."),
                                         reply_markup=kb.nav())
            await cbq.answer()
        else:
            await repo.battle_update(b["id"], st, turn=st["turn"])
            await _battle_panel(cbq, p, b)


async def _on_win(cbq: CallbackQuery, p: dict, b: dict, st: dict):
    enemy_id = b["enemy_id"]
    comp = (p["story_flags"] or {}).get("companion")
    res = engine.pve_result(p, st, st["region"], enemy_id, comp)
    # بونوس رویداد فعال — فقط سرور
    from . import sched as _sched
    kinds = _sched.active_kinds()
    if "double" in kinds:
        res["xp"] *= 2
    if "coin_rush" in kinds:
        res["coins"] *= 2
    p = await repo.give(p["id"], coins=res["coins"], xp=res["xp"], score=res["xp"] // 2)
    consequence = []
    if res["item"]:
        ok = await repo.inv_add(p["id"], res["item"])
        consequence.append(f"🎁 لوت: {gamedata.ITEMS[res['item']]['name']}" if ok else "🎒 کوله پر بود — لوت از دست رفت")
    if res["infected"]:
        await repo.update_player(p["id"], infection_virus=res["infected"], infection_stage=1, infection_ts=NOW())
        consequence.append(f"☣️ آلوده شدی: {gamedata.VIRUSES[res['infected']]['name']}")
    else:
        consequence.append("🧬 سالم موندی")
    # پیشرفت مأموریت kill
    for m in await repo.missions_of(p["id"], "active"):
        mdef = gamedata.MISSIONS[m["mission_id"]]
        if mdef["type"] == "kill" and m["region"] == st["region"]:
            await repo.mission_progress(p["id"], m["mission_id"])
        elif mdef["type"] == "collect" and m["region"] == st["region"] and res["item"] == mdef.get("item"):
            await repo.mission_progress(p["id"], m["mission_id"])
    await cbq.message.edit_text(
        ui.report(gamedata.REGIONS[st["region"]]["name"], "جست‌وجو و نبرد",
                  f"❤️ {st['p1']['hp']}/{st['p1']['max_hp']}", gamedata.ENEMIES[enemy_id]["name"],
                  "✅ پیروزی", f"🪙 {res['coins']} + 🧠 {res['xp']} XP", "\n".join(consequence)),
        reply_markup=kb.nav())
    await cbq.answer()


async def _on_pvp_win(cbq: CallbackQuery, p: dict, b: dict, st: dict):
    """پیروزی PvP — برنده اونیه که ضربه آخر رو زده (میدان همیشه p1 بعد از سواپ سمت درست)."""
    winner_id = b["p1"] if st["p1"]["id"] == b["p1"] else b["p2"]
    loser_id = b["p2"] if winner_id == b["p1"] else b["p1"]
    w = await repo.give(winner_id, xp=40, score=40, coins=20)
    await repo.give(loser_id, xp=15, score=15)
    await repo.rel_update(winner_id, loser_id, trust=2, friendship=3)
    await repo.rel_update(loser_id, winner_id, friendship=3)
    await cbq.message.edit_text(
        ui.report("دوئل PvP", "نبرد بازیکن‌ها", f"❤️ {w['hp']}/{w['max_hp']}", st["p2"]["name"],
                  f"🏆 **{w['name']}** برنده شد", "۴۰🏆 + ۴۰ امتیاز + ۲۰🪙", "رابطه دو بازیکن ثبت شد"),
        reply_markup=kb.nav())
    await cbq.answer()


async def _on_lose(cbq: CallbackQuery, p: dict, b: dict, st: dict):
    pen = engine.defeat_penalty(p, st["enemy"]["danger"])
    if pen["status"] == "hospitalized":
        await repo.update_player(p["id"], status="hospitalized", status_until=NOW() + pen["minutes"] * 60, hp=pen["hp"])
        cons = f"🏥 بستری شدی — {pen['minutes']} دقیقه استراحت اجباری"
    else:
        await repo.update_player(p["id"], hp=pen["hp"])
        cons = f"🩹 زخمی شدی — HP روی {pen['hp']} ماند"
    await cbq.message.edit_text(
        ui.report(gamedata.REGIONS[st["region"]]["name"], "جست‌وجو و نبرد",
                  f"❤️ {pen['hp']}", st["enemy"]["name"], "❌ شکست", "—", cons),
        reply_markup=kb.nav())
    await cbq.answer()


# ——————————————— اکشن‌های نوبتی ———————————————
@r.callback_query(F.data == "bt:atk")
async def bt_atk(cbq: CallbackQuery):
    async def act(p, b):
        return engine.player_action(b["state"], "atk", p)
    await _resolve(cbq, act)


@r.callback_query(F.data == "bt:def")
async def bt_def(cbq: CallbackQuery):
    async def act(p, b):
        return engine.player_action(b["state"], "def", p)
    await _resolve(cbq, act)


@r.callback_query(F.data == "bt:insp")
async def bt_insp(cbq: CallbackQuery):
    async def act(p, b):
        return engine.player_action(b["state"], "insp", p)
    await _resolve(cbq, act)


@r.callback_query(F.data == "bt:flee")
async def bt_flee(cbq: CallbackQuery):
    async def act(p, b):
        p = await repo.give(p["id"], energy=-2)
        return engine.player_action(b["state"], "flee", p)
    await _resolve(cbq, act)


@r.callback_query(F.data == "bt:back")
async def bt_back(cbq: CallbackQuery):
    p = await me(cbq)
    b = await repo.battle_active(p["id"])
    if not b:
        return await cbq.answer("نبرد فعالی نیست", show_alert=True)
    await _battle_panel(cbq, p, b)


@r.callback_query(F.data == "bt:ab:0")
async def bt_abilities(cbq: CallbackQuery):
    p = await me(cbq)
    usable = [a for a in p["abilities"]
              if a in gamedata.ABILITIES and gamedata.ABILITIES[a]["type"] == "active"]
    await cbq.message.edit_text(ui.panel("🧬 توانایی", "یکی رو انتخاب کن."),
                                reply_markup=kb.ability_in_battle(usable, 0))
    await cbq.answer()


@r.callback_query(F.data.startswith("bt:useab:"))
async def bt_useab(cbq: CallbackQuery):
    aid = cbq.data.split(":")[2]

    async def act(p, b):
        st = b["state"]
        if st.get("cds", {}).get(aid, 0) > 0:
            return None
        return engine.player_action(st, "ability", p, ability_id=aid)
    await _resolve(cbq, act)


@r.callback_query(F.data == "bt:it:0")
async def bt_items(cbq: CallbackQuery):
    p = await me(cbq)
    inv = await repo.inv(p["id"])
    usable = [(i, q) for i, q in inv.items()
              if gamedata.ITEMS[i].get("heal") or gamedata.ITEMS[i].get("stun") or gamedata.ITEMS[i].get("boom")]
    if not usable:
        return await cbq.answer("آیتم قابل استفاده نداری", show_alert=True)
    await cbq.message.edit_text(ui.panel("🎒 آیتم‌ها", "مصرف تو نبرد."),
                                reply_markup=kb.items_in_battle(usable))
    await cbq.answer()


@r.callback_query(F.data.startswith("bt:useit:"))
async def bt_useit(cbq: CallbackQuery):
    iid = cbq.data.split(":")[2]

    async def act(p, b):
        it = gamedata.ITEMS[iid]
        if not await repo.inv_take(p["id"], iid):
            return None
        return engine.player_action(b["state"], "item", p, item=it)
    await _resolve(cbq, act)


# ——————————————— PvP ———————————————
@r.callback_query(F.data == "b:pvp")
async def pvp_start(cbq: CallbackQuery, state: FSMContext):
    p = await me(cbq)
    if p["status"] != "active":
        return await cbq.answer("🏥 فعلاً نمی‌تونی بجنگی", show_alert=True)
    await cbq.message.edit_text("🆚 **آیدی عددی حریف رو بفرست** (از پروفایلش)\nبرای لغو /start بزن")
    await state.set_state(St.pvp_target)
    await cbq.answer()


@r.message(St.pvp_target)
async def pvp_target(msg: Message, state: FSMContext):
    p = await repo.get_player(msg.from_user.id)
    if not p:
        await state.clear()
        return
    if not msg.text.isdigit():
        await state.clear()
        return await msg.answer(home_text(p), reply_markup=kb.main_menu(msg.from_user.id == config.OWNER_ID))
    tid = int(msg.text)
    t = await repo.get_player(tid)
    await state.clear()
    if not t or tid == p["id"]:
        return await msg.answer("❌ بازیکن پیدا نشد", reply_markup=kb.main_menu(False))
    if p["status"] != "active" or t["status"] != "active":
        return await msg.answer("❌ یکی از شماها در وضعیت جنگ نیست", reply_markup=kb.main_menu(False))
    bid = await repo.battle_create("pvp", p["id"], p2=tid, chat_id=msg.chat.id, state={})
    await msg.answer(f"⚔️ چالش دوئل برای **{t['name']}** فرستاده شد", reply_markup=kb.main_menu(False))
    await msg.bot.send_message(tid, f"⚔️ **{p['name']}** تو رو به دوئل دعوت کرد!",
                              reply_markup=kb.pvp_accept(bid))


@r.callback_query(F.data.startswith("bt:acc:"))
async def pvp_accept(cbq: CallbackQuery):
    p = await me(cbq)
    bid = int(cbq.data.split(":")[2])
    b = await repo.battle_get(bid)
    if not b or b["active"] is not True or b["p2"] != p["id"]:
        return await cbq.answer("این دعوت معتبر نیست", show_alert=True)
    p1 = await repo.get_player(b["p1"])
    st = engine.new_battle_state(p1, "p1", {}, "pvp", p2=p)
    await repo.battle_update(bid, st, turn=1)
    await cbq.message.edit_text("⚔️ دوئل شروع شد! نوبت با حریفته")
    await cbq.answer()
    await cbq.bot.send_message(b["p1"], "⚔️ حریفت قبول کرد — نوبت توئه", reply_markup=kb.battle_actions(True, True, True))
    await cbq.bot.send_message(b["p2"], "⚔️ نوبت حریفه — منتظر بمون", reply_markup=kb.battle_actions(False, False, False))


@r.callback_query(F.data.startswith("bt:rej:"))
async def pvp_reject(cbq: CallbackQuery):
    bid = int(cbq.data.split(":")[2])
    b = await repo.battle_get(bid)
    if b and not b["state"]:
        await repo.battle_deactivate(bid)
        await cbq.bot.send_message(b["p1"], "❌ دعوت دوئلت رد شد")
    await cbq.message.delete()
    await cbq.answer("رد شد")


# ——————————————— باس ———————————————
@r.callback_query(F.data == "boss:menu")
async def boss_menu(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    chat_id = cbq.message.chat.id
    world = await repo.world_get(chat_id) if cbq.message.chat.type != "private" else None
    acts = await repo.boss_active()
    if world:
        acts += await repo.boss_active(chat_id)
    names = [f"{gamedata.BOSSES[e['boss_id']]['name']} — ❤️ {e['hp']:,}/{e['max_hp']:,}" for e in acts]
    await cbq.message.edit_text(
        ui.panel("🧟 باس‌ها",
                 "\n".join(names) if names else "فعلاً باسی فعال نیست — زمان‌بندی سرور-ساید",
                 f"🔔 اعلان: {'روشن' if p['boss_sub'] else 'خاموش'}"),
        reply_markup=kb.boss_menu(names, p["boss_sub"]))
    await cbq.answer()


@r.callback_query(F.data == "boss:hit")
async def boss_hit(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    if not await ensure_member(cbq.bot, p["id"]):
        return await cbq.answer("📢 اول عضو کانال شو", show_alert=True)
    if p["status"] != "active":
        return await cbq.answer("🏥 نمی‌تونی بجنگی", show_alert=True)
    acts = await repo.boss_active() + (await repo.boss_active(cbq.message.chat.id) if cbq.message.chat.type != "private" else [])
    if not acts:
        return await cbq.answer("باس فعالی نیست", show_alert=True)
    e = acts[0]
    left = sec.cd.check(p["id"], f"boss{e['id']}", 30)
    if left:
        return await cbq.answer(f"⏳ {left:.0f} ثانیه بین ضربه‌ها", show_alert=True)
    if p["energy"] < 5:
        return await cbq.answer("⚡️ انرژی کمه", show_alert=True)
    p = await repo.give(p["id"], energy=-5)
    comp = (p["story_flags"] or {}).get("companion")
    dmg = engine.boss_hit_dmg(p, comp)
    r = await repo.boss_hit(e["id"], p["id"], dmg)
    if not r["ok"]:
        return await cbq.answer(r["why"], show_alert=True)
    b = gamedata.BOSSES[r["boss_id"]]
    if r["status"] == "killed":
        # پاداش بر اساس سهم دمیج — سرور-ساید
        total = sum(r["ranking"].values()) or 1
        my_share = r["ranking"].get(str(p["id"]), 0)
        my_reward = int(b["coins"] * my_share / total)
        p = await repo.give(p["id"], coins=my_reward, score=b["score"] * my_share // total, xp=b["score"] // 2)
        await cbq.answer(f"🏆 باس کشته شد! سهم تو: {my_reward} 🪙", show_alert=True)
        await cbq.message.edit_text(
            ui.report(gamedata.REGIONS[b["region"]]["name"], f"نبرد باس: {b['name']}",
                      f"❤️ {p['hp']}/{p['max_hp']}", b["name"], "🏆 پیروزی سراسری",
                      f"🪙 {my_reward} (سهم دمیج)", "Respawn با Cooldown"),
            reply_markup=kb.nav())
    else:
        ph = f"\n🧬 فاز {r['phase']}/{len(b['phases'])}!" if r["phase"] > e["phase"] else ""
        await cbq.answer(f"⚔️ {dmg} دمیج! باس: {r['hp']:,}/{r['max_hp']:,} {ph}", show_alert=True)


@r.callback_query(F.data == "boss:sub")
async def boss_sub(cbq: CallbackQuery):
    p = await me(cbq)
    await repo.update_player(p["id"], boss_sub=not p["boss_sub"])
    await cbq.answer("🔔 اعلان روشن شد" if not p["boss_sub"] else "🔕 خاموش شد")
    await boss_menu(cbq)
