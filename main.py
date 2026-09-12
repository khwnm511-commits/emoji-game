import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from bot import db, config, handlers
from bot.boss import boss_loop
from bot.monitor import monitor_loop

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")

async def main():
    await db.init()
    if await db.get_config("season") is None:
        await db.set_config("season", config.SEASON)  # فصل ۱ شروع شد
    bot = Bot(token=config.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode="Markdown"))
    dp = Dispatcher()
    dp.include_router(handlers.r)
    # تسک‌های پس‌زمینه — زمان‌بندی سرور سمت
    asyncio.create_task(boss_loop(bot))
    asyncio.create_task(monitor_loop(bot))
    log.info("Bot started — Season %s", await db.get_config("season"))
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "pre_checkout_query"])

if __name__ == "__main__":
    asyncio.run(main())
