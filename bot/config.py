import os
import asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))          # تلگرام آیدی صاحب ربات (برای اعلان توکن railway)
RAILWAY_TOKEN = os.getenv("RAILWAY_TOKEN", "")      # توکن railway برای مانیتورینگ
DB_PATH = os.getenv("DB_PATH", "/data/game.db")     # روی railway ولوم /data
DEV_DB = os.getenv("DEV_DB", "")                    # برای تست لوکال

SEASON = 1  # فصل ۱ — فقط از دیتابیس خونده می‌شه، این مقدار اولیه‌ست

# ————— تنظیمات بازی —————
START_HP = 100
START_ATK = 10
START_DEF = 5
START_COINS = 50
MAX_ENERGY = 100
ENERGY_REGEN_SEC = 60          # هر دقیقه ۱ انرژی
ENERGY_PER_ACTION = 5

# امتیاز هیچ‌وقت کم نمی‌شه — فقط افزایشی است
SCORE_KILL_PVE = 15
SCORE_WIN_PVP = 40
SCORE_WIN_LOSS = 15            # بازنده هم امتیاز می‌گیره که سکر کم نشه
SCORE_INFECTION_HOUR = 10      # هر ساعت عفونت فعال → امتیاز به مبتلا‌کننده
SCORE_BOSS_HIT = 5
SCORE_BOSS_KILL = 250

# ————— باس‌ها —————
BOSS_CONFIG = {
    "mini":     {"every": 3 * 3600,  "hp": 2000,   "name": "🐺 گرگ خاکستری",    "window": 900,   "warn": 600},
    "regional": {"every": 12 * 3600, "hp": 8000,   "name": "🐉 اژدهای کوهستان",  "window": 1800,  "warn": 900},
    "story":    {"every": 24 * 3600, "hp": 20000,  "name": "☠️ جادوگ سیاه",      "window": 2400,  "warn": 1200},
    "world":    {"every": 24 * 3600, "hp": 50000,  "name": "👑 پادشاه سایه‌ها",   "window": 3600,  "warn": 1800},
    "final":    {"every": 7 * 86400,"hp": 150000, "name": "💀 ویرانگر جهانی",    "window": 5400,  "warn": 3600},
}

# ————— گپ سراسری —————
CHAT_RATE_SEC = 12            # هر بازیکن هر ۱۲ ثانیه یک پیام
CHAT_MAX_LEN = 400

# ————— مانیتورینگ railway —————
RAILWAY_CHECK_SEC = 6 * 3600   # هر ۶ ساعت یک بار
