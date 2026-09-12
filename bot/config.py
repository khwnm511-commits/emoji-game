import os

# ————— اتصال‌ها —————
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
RAILWAY_TOKEN = os.getenv("RAILWAY_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")          # PostgreSQL
REDIS_URL = os.getenv("REDIS_URL", "")               # اختیاری — بدونش از حافظهٔ درون‌پروسه استفاده می‌شه
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))       # کانال رسمی بازی
TZ = os.getenv("TZ_NAME", "Asia/Tehran")

SEASON = 1

# ————— شخصیت —————
START_HP = 100
START_ENERGY = 100
MAX_ENERGY = 100
ENERGY_REGEN_SEC = 60          # ۱ انرژی در دقیقه (سرور-ساید)
ENERGY_COST_BATTLE = 5
ENERGY_COST_ACTION = 3

XP_PER_LEVEL = 120             # سطح n → n*120 xp

# ————— نبرد —————
CRIT_BASE = 0.05
DODGE_BASE = 0.05
BLOCK_BASE = 0.10
COUNTER_BASE = 0.10
MAX_STATUS_TURNS = 4

# ————— ویروس —————
INFECTION_CHECK_SEC = 6 * 3600     # هر ۶ ساعت پیشروی/بررسی عفونت
VACCINE_COST = 15                  # سکه

# ————— زمان‌بندی باس (سرور-ساید) —————
BOSS_CHECK_SEC = 60                # اسکن برنامه باس‌ها

# ————— اقتصاد —————
START_COINS = 50

# ————— استارز —————
STARS_PACKAGES = {
    "p25":  {"stars": 25,  "label": "پک بقا",       "coins": 300,  "vaccines": 2,  "energy": 0,  "slots": 0, "boost": None,   "emoji_pack": 0},
    "p60":  {"stars": 60,  "label": "پک مأمور",     "coins": 800,  "vaccines": 5,  "energy": 50, "slots": 0, "boost": None,   "emoji_pack": 0},
    "p120": {"stars": 120, "label": "پک عملیات",    "coins": 1800, "vaccines": 5,  "energy": 0,  "slots": 0, "boost": "xp",   "emoji_pack": 0},
    "p250": {"stars": 250, "label": "پک تایرنت",    "coins": 4000, "vaccines": 10, "energy": 100, "slots": 10, "boost": "dmg", "emoji_pack": 0},
    "p500": {"stars": 500, "label": "پک آمبرلا",    "coins": 9000, "vaccines": 20, "energy": 200, "slots": 20, "boost": "all", "emoji_pack": 10},
}
BOOST_HOURS = {"xp": 24, "dmg": 24, "all": 72}

# ————— کانال —————
CHANNEL_REMIND_SEC = 40 * 60       # یادآوری عضویت حداکثر هر ۴۰ دقیقه

# ————— مانیتورینگ railway —————
RAILWAY_CHECK_SEC = 6 * 3600

# ————— UI: رنگ دکمه‌ها (استاندارد ثابت) —————
BLUE, RED, GREEN, YELLOW, DARK = "🟦", "🟩", "🟥", "🟨", "⚫️"
# 🔵 منو/عملیات عادی | 🔴 خطر/مبارزه | 🟢 تأیید/درمان | 🟡 هشدار/وضعیت | ⚫ اطلاعات/فرعی
