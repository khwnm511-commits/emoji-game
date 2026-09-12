import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from bot import db, config
from bot import h_core, h_battle, h_social, h_shop
from bot.backup import backup_loop, monitor_loop
from bot.sched import boss_loop, events_loop

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")


async def main():
    await db.init()
    if await db.get_config("season") is None:
        await db.set_config("season", config.SEASON)
    bot = Bot(token=config.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode="Markdown"))
    dp = Dispatcher()
    dp.include_router(h_core.r)
    dp.include_router(h_battle.r)
    dp.include_router(h_social.r)
    dp.include_router(h_shop.r)
    # زمان‌بند مرکزی — همهٔ زمان‌بندی‌ها سرور-ساید
    asyncio.create_task(boss_loop(bot))
    asyncio.create_task(events_loop(bot))
    asyncio.create_task(backup_loop(bot))
    asyncio.create_task(monitor_loop(bot))
    log.info("Bot started — RE: Global Collapse, Season %s", await db.get_config("season"))
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "pre_checkout_query"])


if __name__ == "__main__":
    asyncio.run(main())
