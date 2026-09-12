"""فروشگاه — آیتم، ایموجی پرمیوم، استارز. اقتصاد سرور-ساید + Idempotency."""
import json, time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from . import config, db, repo, kb, ui, sec, gamedata, emojis
from .h_core import me, NOW

r = Router()

EMOJI_PRICE = 50  # سکه برای هر ایموجی پرمیوم


@r.callback_query(F.data == "sh:menu")
async def shop_menu(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    await cbq.message.edit_text(ui.panel("🛒 فروشگاه", f"🪙 سکه: **{p['coins']:,}**",
                                         "آیتم با سکه — پرمیوم با استارز."),
                                reply_markup=kb.shop_menu())
    await cbq.answer()


@r.callback_query(F.data == "sh:items")
async def shop_items(cbq: CallbackQuery):
    p = await me(cbq)
    sell = [(i, it["price"]) for i, it in gamedata.ITEMS.items()]
    await cbq.message.edit_text(ui.panel("🎒 آیتم‌ها", f"🪙 {p['coins']:,} — خرید با یک کلیک."),
                                reply_markup=kb.shop_items(sell, p["coins"]))
    await cbq.answer()


@r.callback_query(F.data.startswith("sh:buy:"))
async def shop_buy(cbq: CallbackQuery):
    p = await me(cbq)
    iid = cbq.data.split(":")[2]
    it = gamedata.ITEMS[iid]
    if p["coins"] < it["price"]:
        return await cbq.answer("🪙 سکه کمه", show_alert=True)
    # تراکنش اتمیک + idempotent
    ok = await sec.idempotent(p["id"], "shop_buy", f"buy:{p['id']}:{iid}:{NOW()}")
    p = await repo.give(p["id"], coins=-it["price"])
    added = await repo.inv_add(p["id"], iid)
    if not added:
        await repo.give(p["id"], coins=it["price"])  # برگشت وجه — کوله پره
        return await cbq.answer("🎒 کوله‌ت پره — ظرفیت بیشتر لازمه", show_alert=True)
    await cbq.answer(f"✅ {it['name']} خریدی", show_alert=True)


# ——————————————— ایموجی‌های پرمیوم ———————————————
@r.callback_query(F.data.startswith("e:pg:"))
async def emoji_pg(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    n = int(cbq.data.split(":")[2])
    await cbq.message.edit_text(ui.panel("🎭 ایموجی‌های پرمیوم", f"دارای {len(p['emojis_owned'])}/۱۰۰ — هر کدوم {EMOJI_PRICE} 🪙"),
                                reply_markup=kb.emoji_page(n, p["emojis_owned"]))
    await cbq.answer()


@r.callback_query(F.data.startswith("e:buy:"))
async def emoji_buy(cbq: CallbackQuery):
    p = await me(cbq)
    num = int(cbq.data.split(":")[2])
    if num in p["emojis_owned"]:
        return await cbq.answer("دارشی!", show_alert=True)
    # پک رایگان از استارز؟
    boost = p["boost"] or {}
    if boost.get("emoji_picks", 0) > 0:
        ok = await sec.idempotent(p["id"], "emoji_pick", f"ep:{p['id']}:{num}")
        if not ok:
            return await cbq.answer("در حال پردازش...")
        boost["emoji_picks"] -= 1
        await repo.update_player(p["id"], boost=json.dumps(boost),
                                 emojis_owned=json.dumps(p["emojis_owned"] + [num]))
        return await cbq.answer("✅ ایموجی پک رایگان برداشتی!", show_alert=True)
    if p["coins"] < EMOJI_PRICE:
        return await cbq.answer(f"🪙 {EMOJI_PRICE} سکه لازمه", show_alert=True)
    ok = await repo.emoji_buy(p["id"], num, EMOJI_PRICE)
    await cbq.answer("✅ خریدی!" if ok else "❌ سکه کم بود", show_alert=True)
    await emoji_pg(cbq)


# ——————————————— استارز ———————————————
@r.callback_query(F.data == "sh:stars")
async def stars_menu(cbq: CallbackQuery):
    await cbq.message.edit_text(ui.panel("⭐️ پرمیوم با استارز",
                                         "پک‌ها فقط یک‌بار پاداش می‌دن — همهٔ خریدها ثبت می‌شن."),
                                reply_markup=kb.stars_packs())
    await cbq.answer()


@r.callback_query(F.data.startswith("pay:"))
async def pay_start(cbq: CallbackQuery):
    p = await me(cbq)
    if not p:
        return await cbq.answer("اول /start بزن!", show_alert=True)
    pid = cbq.data.split(":")[1]
    pack = config.STARS_PACKAGES[pid]
    await cbq.bot.send_invoice(
        chat_id=cbq.message.chat.id,
        title=f"پک {pack['label']} — RE: Global Collapse",
        description=f"⭐️ {pack['stars']} استارز → {pack['coins']:,} سکه"
                     + (f" + {pack['vaccines']} واکسن" if pack["vaccines"] else "")
                     + (f" + {pack['energy']} انرژی" if pack["energy"] else "")
                     + (f" + {pack['slots']} ظرفیت کوله" if pack["slots"] else "")
                     + (f" + Boost {config.BOOST_HOURS[pack['boost']]} ساعته" if pack["boost"] else "")
                     + (f" + پک {pack['emoji_pack']} ایموجی" if pack["emoji_pack"] else ""),
        payload=f"stars:{pid}:{p['id']}",
        currency="XTR",
        prices=[LabeledPrice(label=pack["label"], amount=pack["stars"])])
    await cbq.answer()


@r.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@r.message(F.successful_payment)
async def successful_pay(msg: Message):
    sp: SuccessfulPayment = msg.successful_payment
    pid = sp.invoice_payload.split(":")[1]
    charge = sp.telegram_payment_charge_id
    # Idempotency: هر پرداخت فقط یک‌بار
    ok = await repo.purchase_record(msg.from_user.id, pid, charge, sp.total_amount)
    if not ok:
        return  # دابل‌کلیک پرداخت — پاداش تکراری نمیده
    pack = config.STARS_PACKAGES[pid]
    p = await repo.get_player(msg.from_user.id)
    boost = p["boost"] or {}
    if pack["boost"] == "xp":
        boost["xp"] = NOW() + config.BOOST_HOURS["xp"] * 3600
    elif pack["boost"] == "dmg":
        boost["dmg"] = NOW() + config.BOOST_HOURS["dmg"] * 3600
    elif pack["boost"] == "all":
        boost["xp"] = boost["dmg"] = NOW() + config.BOOST_HOURS["all"] * 3600
    if pack["emoji_pack"]:
        boost["emoji_picks"] = boost.get("emoji_picks", 0) + pack["emoji_pack"]
    await repo.update_player(p["id"], boost=json.dumps(boost))
    p = await repo.give(p["id"], coins=pack["coins"], energy=pack["energy"])
    if pack["vaccines"]:
        await repo.inv_add(p["id"], "vaccine", pack["vaccines"])
    if pack["slots"]:
        await repo.update_player(p["id"], slots=p["slots"] + pack["slots"])
    await msg.answer(
        ui.panel("⭐️ پرداخت موفق",
                 f"🎁 پک **{pack['label']}** فعال شد",
                 f"🪙 +{pack['coins']:,} سکه" + (f" | 💉 +{pack['vaccines']} واکسن" if pack["vaccines"] else ""),
                 (f"⚡️ Boost تا {time.strftime('%H:%M', time.localtime(boost.get('xp', boost.get('dmg', NOW()))))}" if pack["boost"] else ""),
                 (f"🎭 {pack['emoji_pack']} انتخاب ایموجی رایگان داری" if pack["emoji_pack"] else ""),
                 footer="تراکنش در دیتابیس ثبت شد ✅"),
        reply_markup=kb.nav())
