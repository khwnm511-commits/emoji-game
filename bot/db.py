import os, json, time
import aiosqlite
from . import config

_db: aiosqlite.Connection | None = None

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY,            -- تلگرام آیدی
    name TEXT NOT NULL,
    username TEXT,
    score INTEGER NOT NULL DEFAULT 0,   -- امتیاز: هیچ‌وقت کم نمی‌شه
    coins INTEGER NOT NULL DEFAULT 50,
    level INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    hp INTEGER NOT NULL DEFAULT 100,
    max_hp INTEGER NOT NULL DEFAULT 100,
    attack INTEGER NOT NULL DEFAULT 10,
    defense INTEGER NOT NULL DEFAULT 5,
    energy INTEGER NOT NULL DEFAULT 100,
    infected_by INTEGER,                -- آیدی مبتلا‌کننده (بازی ویروس)
    infected_until INTEGER,            -- تایم‌استمپ پایان عفونت
    vaccines INTEGER NOT NULL DEFAULT 0,
    emojis_owned TEXT NOT NULL DEFAULT '[]',
    chat_on INTEGER NOT NULL DEFAULT 1, -- عضو گپ سراسری
    boss_sub INTEGER NOT NULL DEFAULT 1,-- اعلان باس‌ها
    relationship_points INTEGER NOT NULL DEFAULT 0,
    created_date INTEGER NOT NULL,
    last_active INTEGER NOT NULL,
    last_chat INTEGER NOT NULL DEFAULT 0,
    last_boss_hit INTEGER NOT NULL DEFAULT 0,
    last_infect INTEGER NOT NULL DEFAULT 0,
    broken_hearts INTEGER NOT NULL DEFAULT 0,   -- سابقه قطع رابطه
    betrayals INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_players_score ON players(score DESC);
CREATE INDEX IF NOT EXISTS idx_players_active ON players(last_active DESC);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,        -- آیدی بازیکن یا NPC
    target_name TEXT NOT NULL,
    is_npc INTEGER NOT NULL DEFAULT 0,
    trust INTEGER NOT NULL DEFAULT 0,      -- اعتماد
    loyalty INTEGER NOT NULL DEFAULT 0,   -- وفاداری
    respect INTEGER NOT NULL DEFAULT 0,   -- احترام
    history INTEGER NOT NULL DEFAULT 0,  -- سابقه مشترک
    status TEXT NOT NULL DEFAULT 'stranger', -- stranger/friend/close/partner/rival/enemy/broken
    hidden INTEGER NOT NULL DEFAULT 1,    -- رابطه مخفی تا trust>50
    broken INTEGER NOT NULL DEFAULT 0,    -- سابقه قطع رابطه
    betray_count INTEGER NOT NULL DEFAULT 0,
    last_action INTEGER NOT NULL DEFAULT 0,
    UNIQUE(player_id, target_id)
);
CREATE INDEX IF NOT EXISTS idx_rel_player ON relationships(player_id);

CREATE TABLE IF NOT EXISTS battles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,                -- pvp / pve / boss
    p1 INTEGER NOT NULL,
    p2 INTEGER,                        -- بازیکن دوم یا NULL برای boss
    npc TEXT,
    state TEXT NOT NULL,               -- json
    turn INTEGER NOT NULL DEFAULT 1,  -- 1 یا 2
    active INTEGER NOT NULL DEFAULT 1,
    created_date INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_battles_p1 ON battles(p1, active);
CREATE INDEX IF NOT EXISTS idx_battles_p2 ON battles(p2, active);

CREATE TABLE IF NOT EXISTS boss_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,               -- mini/regional/story/world/final
    name TEXT NOT NULL,
    hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    phase INTEGER NOT NULL DEFAULT 1,
    starts_at INTEGER NOT NULL,       -- زمان شروع (کانت‌داون قبلش warn)
    ends_at INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    ranking TEXT NOT NULL DEFAULT '{}',
    msg_chat_id INTEGER,
    msg_id INTEGER,
    created_date INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS boss_hits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    dmg INTEGER NOT NULL,
    ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bosshits ON boss_hits(event_id, player_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    level INTEGER NOT NULL,
    text TEXT NOT NULL,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS star_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    stars INTEGER NOT NULL,
    payload TEXT NOT NULL,
    charge_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    UNIQUE(charge_id)
);

CREATE TABLE IF NOT EXISTS season_stats (
    season INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    best_level INTEGER NOT NULL DEFAULT 1,
    kills INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    boss_dmg INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(season, player_id)
);
"""

async def init():
    global _db
    path = config.DEV_DB or config.DB_PATH
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _db.commit()

async def db():
    assert _db is not None, "db not initialised"
    return _db

# ——————————————— کمکی‌ها ———————————————
async def get_config(key: str, default=None):
    cur = await (await db()).execute("SELECT value FROM config WHERE key=?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else default

async def set_config(key: str, value):
    await (await db()).execute(
        "INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)))
    await (await db()).commit()

async def get_player(pid: int):
    cur = await (await db()).execute("SELECT * FROM players WHERE id=?", (pid,))
    return await cur.fetchone()

async def ensure_player(pid: int, name: str, username: str | None):
    await (await db()).execute(
        """INSERT INTO players(id,name,username,created_date,last_active)
           VALUES(?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name,
             username=COALESCE(excluded.username, players.username),
             last_active=excluded.last_active""",
        (pid, name, username, int(time.time()), int(time.time())))
    await (await db()).commit()

async def update_player(pid: int, **fields):
    if not fields:
        return
    sets = ",".join(f"{k}=?" for k in fields)
    await (await db()).execute(f"UPDATE players SET {sets} WHERE id=?", (*fields.values(), pid))
    await (await db()).commit()

async def add_score(pid: int, score: int, coins: int = 0, xp: int = 0):
    """امتیاز هیچ‌وقت کم نمی‌شه — فقط اضافه می‌شه."""
    await (await db()).execute(
        "UPDATE players SET score=score+?, coins=coins+?, xp=xp+? WHERE id=?",
        (score, coins, xp, pid))
    await (await db()).commit()

async def xp_for_level(level: int) -> int:
    return 50 * level * level
