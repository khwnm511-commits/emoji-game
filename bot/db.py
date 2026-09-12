"""PostgreSQL — pool با asyncpg + اسکیما + تراکنش/قفل امن."""
import asyncio, logging, os, time
import asyncpg
from . import config

log = logging.getLogger("db")
_pool: asyncpg.Pool | None = None
_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS players (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT,
    gender TEXT NOT NULL,
    appearance TEXT NOT NULL,
    background TEXT NOT NULL,
    level INT NOT NULL DEFAULT 1,
    xp INT NOT NULL DEFAULT 0,
    score INT NOT NULL DEFAULT 0,
    coins INT NOT NULL DEFAULT 50,
    hp INT NOT NULL DEFAULT 100,
    max_hp INT NOT NULL DEFAULT 100,
    energy INT NOT NULL DEFAULT 100,
    energy_ts BIGINT NOT NULL DEFAULT 0,
    atk INT NOT NULL DEFAULT 10,
    def INT NOT NULL DEFAULT 5,
    spd INT NOT NULL DEFAULT 5,
    luck INT NOT NULL DEFAULT 5,
    reputation INT NOT NULL DEFAULT 0,
    region TEXT NOT NULL DEFAULT 'city',
    story_node TEXT NOT NULL DEFAULT 's1_intro',
    story_flags JSONB NOT NULL DEFAULT '{}',
    infection_virus TEXT,
    infection_stage INT NOT NULL DEFAULT 0,
    infection_ts BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    status_until BIGINT NOT NULL DEFAULT 0,
    abilities JSONB NOT NULL DEFAULT '["field_medic"]',
    weapon TEXT,
    armor TEXT,
    slots INT NOT NULL DEFAULT 20,
    boost JSONB NOT NULL DEFAULT '{}',
    emojis_owned JSONB NOT NULL DEFAULT '[]',
    chat_on BOOLEAN NOT NULL DEFAULT TRUE,
    boss_sub BOOLEAN NOT NULL DEFAULT TRUE,
    created_date BIGINT NOT NULL,
    last_active BIGINT NOT NULL,
    last_remind BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_players_score ON players(score DESC);

CREATE TABLE IF NOT EXISTS npc_rel (
    player_id BIGINT NOT NULL,
    npc_id TEXT NOT NULL,
    trust INT NOT NULL DEFAULT 0,
    loyalty INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'neutral',
    PRIMARY KEY (player_id, npc_id)
);

CREATE TABLE IF NOT EXISTS player_rel (
    player_id BIGINT NOT NULL,
    target_id BIGINT NOT NULL,
    trust INT NOT NULL DEFAULT 0,
    loyalty INT NOT NULL DEFAULT 0,
    friendship INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'stranger',
    PRIMARY KEY (player_id, target_id)
);

CREATE TABLE IF NOT EXISTS friends (
    player_id BIGINT NOT NULL,
    friend_id BIGINT NOT NULL,
    created_date BIGINT NOT NULL,
    PRIMARY KEY (player_id, friend_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    player_id BIGINT NOT NULL,
    item_id TEXT NOT NULL,
    qty INT NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, item_id)
);

CREATE TABLE IF NOT EXISTS battles (
    id SERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    chat_id BIGINT NOT NULL DEFAULT 0,
    p1 BIGINT NOT NULL,
    p2 BIGINT,
    enemy_id TEXT,
    boss_event_id INT,
    state JSONB NOT NULL DEFAULT '{}',
    turn INT NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_date BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_battles_active ON battles(active, p1);

CREATE TABLE IF NOT EXISTS boss_events (
    id SERIAL PRIMARY KEY,
    boss_id TEXT NOT NULL,
    region TEXT NOT NULL,
    chat_id BIGINT NOT NULL DEFAULT 0,
    phase INT NOT NULL DEFAULT 1,
    hp INT NOT NULL,
    max_hp INT NOT NULL,
    ranking JSONB NOT NULL DEFAULT '{}',
    msg_chat_id BIGINT,
    msg_id BIGINT,
    starts_at BIGINT NOT NULL,
    ends_at BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_date BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS boss_hits (
    id SERIAL PRIMARY KEY,
    event_id INT NOT NULL,
    player_id BIGINT NOT NULL,
    dmg INT NOT NULL,
    ts BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bosshits ON boss_hits(event_id, player_id);

CREATE TABLE IF NOT EXISTS worlds (
    chat_id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    region_unlocked INT NOT NULL DEFAULT 1,
    infection INT NOT NULL DEFAULT 0,
    created_date BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    starts_at BIGINT NOT NULL,
    ends_at BIGINT NOT NULL,
    announced BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS missions (
    id SERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL,
    mission_id TEXT NOT NULL,
    region TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    progress INT NOT NULL DEFAULT 0,
    created_date BIGINT NOT NULL,
    done_date BIGINT
);
CREATE INDEX IF NOT EXISTS idx_missions ON missions(player_id, status);

CREATE TABLE IF NOT EXISTS clans (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    leader_id BIGINT NOT NULL,
    points INT NOT NULL DEFAULT 0,
    created_date BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS clan_war (
    week TEXT NOT NULL,
    clan_id INT NOT NULL,
    points INT NOT NULL DEFAULT 0,
    PRIMARY KEY (week, clan_id)
);

CREATE TABLE IF NOT EXISTS clan_members (
    player_id BIGINT PRIMARY KEY,
    clan_id INT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member'
);

CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL,
    pack TEXT NOT NULL,
    charge_id TEXT NOT NULL UNIQUE,
    stars INT NOT NULL,
    ts BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL,
    kind TEXT NOT NULL,
    ref TEXT NOT NULL,
    amount INT NOT NULL DEFAULT 0,
    meta JSONB NOT NULL DEFAULT '{}',
    ts BIGINT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_ref ON transactions(ref);

CREATE TABLE IF NOT EXISTS story_log (
    id SERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL,
    node TEXT NOT NULL,
    choice TEXT,
    ts BIGINT NOT NULL
);
"""

TABLES = ["players", "npc_rel", "player_rel", "friends", "inventory", "battles",
          "boss_events", "boss_hits", "worlds", "events", "missions", "clans",
          "clan_war", "clan_members", "purchases", "transactions", "story_log", "config"]


async def init():
    global _pool
    # اتصال با تلاش مجدد (منتظر بالا آمدن postgres می‌مونیم)
    for i in range(30):
        try:
            _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=2, max_size=10,
                                               command_timeout=30)
            break
        except Exception as e:
            log.warning("Postgres در دسترس نیست (%s/30): %s", i + 1, e)
            await asyncio.sleep(10)
    assert _pool, "اتصال PostgreSQL برقرار نشد — DATABASE_URL چک کن"
    if os.getenv("RESET_DB") == "1":
        async with _pool.acquire() as c:
            await c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        log.warning("RESET_DB=1 → کل دیتابیس ریست شد")
    async with _pool.acquire() as c:
        await c.execute(SCHEMA)
    log.info("PostgreSQL آماده — اسکیما اعمال شد")


async def pool() -> asyncpg.Pool:
    assert _pool is not None, "db not initialised"
    return _pool


async def close():
    if _pool:
        await _pool.close()


async def lock(key: str) -> asyncio.Lock:
    """قفل per-entity برای جلوگیری از Race Condition — بدون Redis هم امن (یک پروسه)."""
    async with _locks_guard:
        if key not in _locks:
            _locks[key] = asyncio.Lock()
        return _locks[key]


async def get_config(key: str, default=None):
    async with _pool.acquire() as c:
        v = await c.fetchval("SELECT value FROM config WHERE key=$1", key)
        return v if v is not None else default


async def set_config(key: str, value):
    async with _pool.acquire() as c:
        await c.execute("INSERT INTO config VALUES ($1,$2) ON CONFLICT (key) DO UPDATE SET value=$2",
                        key, str(value))


async def tx_operation(coro_fn):
    """اجرای اتمیک چند مرحله‌ای داخل یک تراکنش."""
    async with _pool.acquire() as c:
        async with c.transaction():
            return await coro_fn(c)
