"""امنیت — Cooldown، Rate Limit، Idempotency و Lock. همه سرور-ساید."""
import asyncio, time, unicodedata
from . import db

_now = time.time

class Cooldown:
    """cooldown per (player, action) — حافظهٔ درون‌پروسه (یک نمونهٔ ربات)."""
    def __init__(self):
        self._t: dict[tuple, float] = {}
        self._gc = 0

    def check(self, pid: int, action: str, sec: float) -> float:
        """باقی‌ماندهٔ cooldown؛ ۰ یعنی آزاد. اگر آزاد بود، استارت می‌خوره."""
        key = (pid, action)
        left = self._t.get(key, 0) - _now()
        if left <= 0:
            self._t[key] = _now() + sec
            # GC سبک هر ۱۰۰۰ چک
            self._gc += 1
            if self._gc > 1000:
                self._gc = 0
                cutoff = _now() - 60
                self._t = {k: v for k, v in self._t.items() if v > cutoff}
            return 0.0
        return left

    def peek(self, pid: int, action: str) -> float:
        return max(0.0, self._t.get((pid, action), 0) - _now())


class RateLimit:
    """توکن‌بکت per player برای جلوگیری از اسپم کال‌بک."""
    def __init__(self, rate: float = 0.5, burst: int = 4):
        self.rate, self.burst = rate, burst
        self._b: dict[int, tuple[float, float]] = {}  # pid -> (tokens, ts)

    def allow(self, pid: int) -> bool:
        now = _now()
        tok, ts = self._b.get(pid, (self.burst, now))
        tok = min(self.burst, tok + (now - ts) * self.rate)
        if tok < 1:
            self._b[pid] = (tok, now)
            return False
        self._b[pid] = (tok - 1, now)
        return True


cd = Cooldown()
rl = RateLimit()

async def idempotent(player_id: int, kind: str, ref: str, amount: int = 0, meta: dict | None = None) -> bool:
    """ثبت یکتای تراکنش — True یعنی اولین‌بار (مجاز)، False یعنی تکراری (رد)."""
    try:
        async with db.pool().acquire() as c:
            await c.execute(
                "INSERT INTO transactions (player_id, kind, ref, amount, meta, ts) VALUES ($1,$2,$3,$4,$5,$6)",
                player_id, kind, ref, amount, meta or {}, int(_now()))
        return True
    except Exception:
        return False  # unique violation → دابل‌کلیک/پاداش تکراری

def norm(text: str) -> str:
    """نرمال‌سازی متن فارسی برای مقایسهٔ امن."""
    return unicodedata.normalize("NFKC", text).strip()
