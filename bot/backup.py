"""🛡 بکاپ خودکار دیتابیس — اسنپ‌شات امن (حتی وسط نوشتن) + ارسال فایل به پیوی صاحب ربات هر ۲۴ ساعت.

- اسنپ‌شات با SQLite Backup API → سازگار با WAL، هیچ‌وقت خراب نمی‌شه
- ۷ بکاپ اخیر روی ولوم /data/backup نگه داشته می‌شه
- هر بکاپ همون لحظه به عنوان فایل توی پیوی صاحب ربات فرستاده می‌شه
  (اگه Railway کلاً بمیره، دیتا دست خودته)
"""
import asyncio, logging, os, sqlite3, time
from aiogram import Bot
from aiogram.types import BufferedInputFile
from . import config

log = logging.getLogger("backup")

DB_PATH = config.DB_PATH or "/data/game.db"
BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH) or "/data", "backup")
KEEP = 7          # تعداد بکاپ‌های محلی که نگه می‌داریم
EVERY_SEC = 24 * 3600


def make_snapshot() -> str:
    """اسنپ‌شات کامل و امن از دیتابیس — بلوکه‌کننده، تو thread جدا صدا زده می‌شه."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dst = os.path.join(BACKUP_DIR, f"game-{time.strftime('%Y-%m-%d_%H-%M')}.db")
    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(dst)
    try:
        with dst_conn:
            src_conn.backup(dst_conn)   # API رسمی بکاپ — سازگار با WAL
    finally:
        src_conn.close()
        dst_conn.close()
    # چرخش: فقط ۷ تا اخیر بمونن
    files = sorted(f for f in os.listdir(BACKUP_DIR)
                   if f.startswith("game-") and f.endswith(".db"))
    for old in files[:-KEEP]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass
    return dst


async def send_backup(bot: Bot, path: str, note: str = "🛡 بکاپ خودکار دیتابیس") -> bool:
    """ارسال فایل بکاپ به پیوی صاحب ربات."""
    if not config.OWNER_ID or not os.path.exists(path):
        return False
    with open(path, "rb") as f:
        data = f.read()
    await bot.send_document(
        config.OWNER_ID,
        document=BufferedInputFile(data, filename=os.path.basename(path)),
        caption=f"{note}\n📦 {len(data):,} بایت — {time.strftime('%Y-%m-%d %H:%M')}\n"
                f"برای برگردوندن: اسم فایل رو بذار game.db و جای فایل دیتابیس اصلی بذار.")
    return True


async def backup_loop(bot: Bot):
    # اولین بکاپ ~۲ دقیقه بعد از استارت، بعدش هر ۲۴ ساعت
    await asyncio.sleep(120)
    while True:
        try:
            path = await asyncio.to_thread(make_snapshot)
            await send_backup(bot, path)
            log.info("Backup OK → %s", path)
        except Exception as e:
            log.error("Backup failed: %s", e)
        await asyncio.sleep(EVERY_SEC)
