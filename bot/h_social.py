"""اجتماعی — روابط، دوستان، تیم، کلن، رویدادها، کانال، بکاپ اونر."""
import json, time
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from . import config, db, repo, kb, ui, sec, gamedata
from .h_core import St, me, home_text, NOW

r = Router()


@r.callback_query(F.data == "rel:list")
async def rel_list(cbq: CallbackQuery):
    p = await me(cbq)
    rels = await repo.rels_of(p["id"])
    await cbq.message.edit_text(ui.panel("❤️ روابط", "رابطه با بازیکن‌های دیگه."),
                                reply_markup=kb.relations(rels))
    await cbq.answer()


@r.callback_query(F.data == "rel:new")
async def rel_new(cbq: CallbackQuery, state: FSMContext):
    await state.set_state(St.rel_add)
    await cbq.message.edit_text("❤️ آیدی عددی بازیکن رو بفرست\nبرای لغو /start بزن")
    await cbq.answer()


@r.message(St.rel_add)
async def rel_add(msg: Message, state: FSMContext):
    p = await repo.get_player(msg.from_user.id)
    await state.clear()
    if not p or not msg.text or not msg.text.isdigit():
        return await msg.answer("❌ آیدی معتبر نیست", reply_markup=kb.nav())
    tid = int(msg.text)
    if tid == p["id"]:
        return await msg.answer("❌ با خودت نمی‌شه!", reply_markup=kb.nav())
    t = await repo.get_player(tid)
    if not t:
        return await msg.answer("❌ بازیکن پیدا نشد", reply_markup=kb.nav())
    await repo.rel_update(p["id"], tid, trust=5)
    await msg.answer(f"✅ رابطه با **{t['name']}** ثبت شد", reply_markup=kb.nav())


@r.callback_query(F.data.startswith("rel:view:"))
async def rel_view(cbq: CallbackQuery):
    p = await me(cbq)
    tid = int(cbq.data.split(":")[2])
    t = await repo.get_player(tid)
    if not t:
        return await cbq.answer("بازیکن پیدا نشد", show_alert=True)
    rel = await repo.rel_get(p["id"], tid)
    await cbq.message.edit_text(
        ui.panel(f"❤️ {t['name']}",
                 f"🤝 اعتماد: {rel['trust'] if rel else 0} | ❤️ وفاداری: {rel['loyalty'] if rel else 0} | "
                 f"👥 دوستی: {rel['friendship'] if rel else 0}",
                 f"📊 وضعیت: {rel['status'] if rel else 'غریبه'} | Lv.{t['level']}"),
        reply_markup=kb.rel_actions(tid, rel["status"] if rel else "stranger"))
    await cbq.answer()


@r.callback_query(F.data.startswith("rel:gift:"))
async def rel_gift(cbq: CallbackQuery):
    p = await me(cbq)
    tid = int(cbq.data.split(":")[2])
    if p["coins"] < 20:
        return await cbq.answer("🪙 سکه کمه", show_alert=True)
    p = await repo.give(p["id"], coins=-20)
    await repo.give(tid, coins=15)
    await repo.rel_update(p["id"], tid, trust=5)
    await cbq.answer("🎁 هدیه رفت — اعتماد +۵", show_alert=True)


@r.callback_query(F.data.startswith("rel:coop:"))
async def rel_coop(cbq: CallbackQuery):
    p = await me(cbq)
    tid = int(cbq.data.split(":")[2])
    await repo.rel_update(p["id"], tid, loyalty=5, friendship=3)
    await repo.rel_update(tid, p["id"], loyalty=5, friendship=3)
    await cbq.answer("🤝 هم‌بازی ثبت شد — وفاداری +۵", show_alert=True)


@r.callback_query(F.data.startswith("rel:break:"))
async def rel_break(cbq: CallbackQuery):
    p = await me(cbq)
    tid = int(cbq.data.split(":")[2])
    await repo.rel_update(p["id"], tid, status="enemy")
    await repo.update_player(p["id"], reputation=p["reputation"] - 10)
    await cbq.answer("💔 رابطه قطع شد — اعتبارت کم شد", show_alert=True)


# ——————————————— دوستان ———————————————
@r.callback_query(F.data == "fr:list")
async def fr_list(cbq: CallbackQuery):
    p = await me(cbq)
    fl = await repo.friends_of(p["id"])
    await cbq.message.edit_text(ui.panel("🤝 دوستان", "آیدی خودت توی پروفایله."),
                                reply_markup=kb.friends(fl))
    await cbq.answer()


@r.callback_query(F.data == "fr:add")
async def fr_add(cbq: CallbackQuery, state: FSMContext):
    await state.set_state(St.friend_add)
    await cbq.message.edit_text("🤝 آیدی عددی دوستت رو بفرست\nبرای لغو /start بزن")
    await cbq.answer()


@r.message(St.friend_add)
async def fr_add_id(msg: Message, state: FSMContext):
    p = await repo.get_player(msg.from_user.id)
    await state.clear()
    if not p or not msg.text or not msg.text.isdigit():
        return await msg.answer("❌ آیدی معتبر نیست", reply_markup=kb.nav())
    ok = await repo.friend_add(p["id"], int(msg.text))
    await msg.answer("✅ دوست شد" if ok else "❌ بازیکن پیدا نشد", reply_markup=kb.nav())


# ——————————————— تیم (فقط داخل گروه) ———————————————
@r.callback_query(F.data == "tm:menu")
async def tm_menu(cbq: CallbackQuery):
    if cbq.message.chat.type == "private":
        return await cbq.answer("👥 تیم فقط تو گروه ساخته می‌شه", show_alert=True)
    p = await me(cbq)
    in_team = bool((p["story_flags"] or {}).get("team"))
    await cbq.message.edit_text(ui.panel("👥 تیم", "تیم گروهی برای Co-op و باس."),
                                reply_markup=kb.team_menu(in_team))
    await cbq.answer()


@r.callback_query(F.data == "tm:create")
async def tm_create(cbq: CallbackQuery):
    p = await me(cbq)
    flags = p["story_flags"] or {}
    flags["team"] = cbq.message.chat.id
    await repo.update_player(p["id"], story_flags=json.dumps(flags))
    await repo.world_create(cbq.message.chat.id, cbq.message.chat.title or "گروه")
    await cbq.answer("👥 تیم و جهان گروه ثبت شد!", show_alert=True)


@r.callback_query(F.data == "tm:invite")
async def tm_invite(cbq: CallbackQuery, state: FSMContext):
    await state.set_state(St.team_invite)
    await cbq.message.edit_text("👥 آیدی بازیکن رو برای دعوت بفرست")
    await cbq.answer()


@r.message(St.team_invite)
async def tm_invite_id(msg: Message, state: FSMContext):
    p = await repo.get_player(msg.from_user.id)
    await state.clear()
    if not p or not msg.text or not msg.text.isdigit():
        return await msg.answer("❌ آیدی معتبر نیست", reply_markup=kb.nav())
    tid = int(msg.text)
    t = await repo.get_player(tid)
    if not t:
        return await msg.answer("❌ بازیکن نیست", reply_markup=kb.nav())
    flags = t["story_flags"] or {}
    flags["team"] = msg.chat.id
    await repo.update_player(tid, story_flags=json.dumps(flags))
    await msg.bot.send_message(tid, f"👥 **{p['name']}** تو رو به تیم دعوت کرد!")
    await msg.answer("✅ دعوت شد", reply_markup=kb.nav())


# ——————————————— کلن ———————————————
@r.callback_query(F.data == "cl:menu")
async def cl_menu(cbq: CallbackQuery):
    p = await me(cbq)
    clan = await repo.my_clan(p["id"])
    top = await repo.clans_top(3)
    await cbq.message.edit_text(ui.panel("🏴 کلن", "جنگ هفتگی کلن‌ها = مجموع دمیج باس."),
                                reply_markup=kb.clan_menu(clan, top))
    await cbq.answer()


@r.callback_query(F.data == "cl:create")
async def cl_create(cbq: CallbackQuery, state: FSMContext):
    p = await me(cbq)
    if p["coins"] < 200:
        return await cbq.answer("🪙 ۲۰۰ سکه لازمه", show_alert=True)
    await state.set_state(St.clan_name)
    await cbq.message.edit_text("🏴 اسم کلن رو بفرست (۲۰۰ سکه)\nبرای لغو /start بزن")
    await cbq.answer()


@r.message(St.clan_name)
async def cl_create_name(msg: Message, state: FSMContext):
    p = await repo.get_player(msg.from_user.id)
    await state.clear()
    if not p:
        return
    name = (msg.text or "").strip()[:24]
    if not name or name.startswith("/"):
        return await msg.answer("❌ اسم معتبر نیست", reply_markup=kb.nav())
    if p["coins"] < 200:
        return await msg.answer("🪙 ۲۰۰ سکه لازمه", reply_markup=kb.nav())
    p = await repo.give(p["id"], coins=-200)
    ok = await repo.clan_create(p["id"], name)
    await msg.answer(f"🏴 کلن **{name}** ساخته شد! برای جذب اعضا دعوتش کن" if ok
                     else "❌ این اسم قبلاً ثبت شده", reply_markup=kb.nav())


@r.callback_query(F.data == "cl:list")
async def cl_list(cbq: CallbackQuery):
    clans = await repo.clans_top()
    await cbq.message.edit_text(ui.panel("🏴 کلن‌ها", "برای عضویت بزن."),
                                reply_markup=kb.clan_list(clans))
    await cbq.answer()


@r.callback_query(F.data.startswith("cl:join:"))
async def cl_join(cbq: CallbackQuery):
    p = await me(cbq)
    ok = await repo.clan_join(p["id"], int(cbq.data.split(":")[2]))
    await cbq.answer("✅ عضو شدی" if ok else "قبلاً تو یه کلنی", show_alert=True)
    await cl_list(cbq)


@r.callback_query(F.data == "cl:leave")
async def cl_leave(cbq: CallbackQuery):
    async with db.pool().acquire() as c:
        await c.execute("DELETE FROM clan_members WHERE player_id=$1", cbq.from_user.id)
    await cbq.answer("خارج شدی")
    await cl_menu(cbq)


@r.callback_query(F.data == "cl:top")
async def cl_top(cbq: CallbackQuery):
    import time as _t
    week = _t.strftime("%Y-W%W")
    async with db.pool().acquire() as c:
        rows = await c.fetch(
            "SELECT cl.name, cw.points FROM clan_war cw JOIN clans cl ON cl.id=cw.clan_id WHERE cw.week=$1 ORDER BY cw.points DESC LIMIT 10", week)
    body = "\n".join(f"{i+1}. {r['name']} — {r['points']:,}⚔️" for i, r in enumerate(rows)) or "این هفته هنوز جنگی نبوده"
    await cbq.message.edit_text(ui.panel("🏴 جنگ هفتگی کلن‌ها", body), reply_markup=kb.nav("cl:menu"))
    await cbq.answer()


# ——————————————— رویدادها ———————————————
@r.callback_query(F.data == "ev:list")
async def ev_list(cbq: CallbackQuery):
    from . import sched
    acts = await repo.event_active()
    names = []
    for e in acts:
        left = e["ends_at"] - NOW()
        names.append(f"{sched.EVENT_NAMES.get(e['kind'], e['kind'])} — {ui.fmt_time(left)}")
    nxt = sched.next_event_name()
    await cbq.message.edit_text(ui.panel("🎉 رویدادها", "\n".join(names) if names else "فعلاً رویداد فعالی نیست."),
                                reply_markup=kb.events(names, [nxt] if nxt else []))
    await cbq.answer()


# ——————————————— کانال ———————————————
@r.callback_query(F.data == "ch:check")
async def ch_check(cbq: CallbackQuery):
    from .h_core import ensure_member, channel_url
    ok = await ensure_member(cbq.bot, cbq.from_user.id)
    if ok:
        await cbq.answer("✅ عضویت تأیید شد — ممنون!", show_alert=True)
    else:
        await cbq.answer("❌ هنوز عضو نشدی", show_alert=True)


# ——————————————— بکاپ اونر ———————————————
@r.callback_query(F.data == "bk:now")
async def backup_now(cbq: CallbackQuery):
    if not config.OWNER_ID or cbq.from_user.id != config.OWNER_ID:
        return await cbq.answer("🔒 فقط صاحب ربات!", show_alert=True)
    await cbq.answer("در حال بکاپ...")
    from . import backup
    ok = await backup.send_backup(cbq.bot, "🛡 بکاپ دستی — دامپ کامل PostgreSQL")
    await cbq.answer("✅ بکاپ تو پیویت فرستاده شد!" if ok else "⚠️ خطا در بکاپ — لاگ رو ببین",
                     show_alert=True)
