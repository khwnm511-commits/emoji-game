"""Game Engine — همهٔ محاسبات بازی اینجاست. هیچ اعدادبی از UI نمیاد."""
import json, random
from . import config, gamedata

# ——————————————— ساخت خودکار شخصیت ———————————————
NAMES_M = ["آرمان", "بهراد", "کاوه", "سامان", "پرهام", "ایمان", "بردیا", "مهدی", "هومن", "آرش"]
NAMES_F = ["نگار", "سارا", "الهام", "ترانه", "نیلوفر", "مریم", "رها", "پرنیان", "سحر", "آیدا"]
APPS = ["قد بلند و چشم‌های نافذ", "اندام ورزیده و نگاه سرد", "لاغر و چابک با چهرهٔ خسته",
        "قدمت با چهرهٔ آرام و مصمم", "موش‌کاشی با نگاه تیز و بی‌باک", "قدربلند با دستان زخم‌خورده"]
BGS = ["پرستار سابق بیمارستان رمورس", "افسر پلیس RPD", "دانشجوی میکروب‌شناسی",
       "رانندهٔ آمبولانس", "گاردهای سابق امنیتی آمبرلا", "خبرنگار جنایی",
       "تکنسین آزمایشگاه", "کوهنورد و راهنمای بقا"]

def gen_character(gender: str) -> dict:
    r = random.Random()
    return {
        "name": r.choice(NAMES_M if gender == "m" else NAMES_F),
        "appearance": r.choice(APPS),
        "background": r.choice(BGS),
    }


# ——————————————— آمار مؤثر ———————————————
def eff_stats(p: dict, companion: str | None = None) -> dict:
    """آمار واقعی = پایه + تجهیزات + ویروس + جهش + همراه."""
    atk, df, spd, luck = p["atk"], p["def"], p["spd"], p["luck"]
    if p.get("weapon") and p["weapon"] in gamedata.ITEMS:
        atk += gamedata.ITEMS[p["weapon"]].get("atk", 0)
    if p.get("armor") and p["armor"] in gamedata.ITEMS:
        df += gamedata.ITEMS[p["armor"]].get("def", 0)
    # ویروس
    v = gamedata.VIRUSES.get(p.get("infection_virus"), None)
    if v and p.get("infection_stage", 0) >= 1:
        for stat, delta in v["fx"].get(p["infection_stage"], {}).items():
            if stat == "atk": atk += delta
            elif stat == "def": df += delta
            elif stat == "spd": spd += delta
            elif stat == "luck": luck += delta
    ab = p.get("abilities", [])
    if "t_mut" in ab: atk = int(atk * 1.10)
    if "g_mut" in ab: pass  # max_hp بالاتر موقع شروع نبرد اعمال می‌شه
    # همراه NPC
    if companion == "leon": atk = int(atk * 1.10)
    elif companion == "barry": df = int(df * 1.10)
    elif companion == "jake": atk = int(atk * 1.05)
    elif companion == "hunk": luck += 5
    elif companion == "mia": luck += 2
    # بوسر استارز
    boost = p.get("boost") or {}
    if boost.get("dmg") and boost["dmg"] > 0: atk = int(atk * 1.20)
    return {"atk": max(1, atk), "def": max(0, df), "spd": max(1, spd), "luck": max(0, luck)}


# ——————————————— نبرد نوبتی ———————————————
def new_battle_state(p: dict, side: str, enemy: dict, region: str,
                     p2: dict | None = None, companion: str | None = None) -> dict:
    es = eff_stats(p, companion)
    max_hp = p["max_hp"] * 1.15 if "g_mut" in p["abilities"] else p["max_hp"]
    p1 = {"id": p["id"], "name": p["name"], "hp": p["hp"], "max_hp": max_hp}
    p1.update(es)
    st = {
        "region": region,
        "turn": 1,
        "statuses": {},           # side -> {stun: t, shield: t, crit_next: 0/1}
        "cds": {},                # ability -> remaining turns
        "rolls": [],              # RNG کنترل‌شده برای ممیزی
        "p1": p1,
        "enemy": {k: enemy[k] for k in ("name", "hp", "atk", "def", "spd", "xp", "coins", "danger", "infection")},
    }
    if p2:
        es2 = eff_stats(p2)
        st["p2"] = {"id": p2["id"], "name": p2["name"], "hp": p2["hp"], "max_hp": p2["max_hp"], **es2}
    return st


def _roll(st: dict, lo: float, hi: float) -> float:
    v = round(random.uniform(lo, hi), 2)
    st["rolls"].append(v)
    return v


def calc_dmg(st: dict, atk: float, dfn: float, crit_bonus: float = 0.0) -> dict:
    """دمیج کنترل‌شده: dmg = atk*roll - def*roll/2، کریتال ×۱.۸."""
    base = atk * _roll(st, 0.85, 1.15)
    base -= dfn * _roll(st, 0.3, 0.6)
    crit = _roll(st, 0, 1) < (config.CRIT_BASE + crit_bonus)
    if crit:
        base *= 1.8
    return {"dmg": max(1, int(base)), "crit": crit}


def player_action(st: dict, action: str, p_es: dict, item: dict | None = None,
                  ability_id: str | None = None, support_ok: bool = False) -> dict:
    """یک نوبت کامل بازیکن → خروجی برای نمایش + state جدید. None یعنی ناموفق."""
    side_key = "p1"
    foe = "p2" if "p2" in st else "enemy"
    me = st[side_key]
    enemy = st[foe]
    my_stat = st.get("statuses", {}).setdefault(side_key, {})
    foe_stat = st.setdefault("statuses", {}).setdefault(foe, {})
    out = {"events": []}

    if my_stat.get("stun", 0) > 0:
        my_stat["stun"] -= 1
        out["events"].append("💨 گیج شدی — این نوبت از دست رفت!")
        return _finish_turn(st, out, p_es, side_key, foe, me, enemy, foe_stat)

    if action == "atk":
        crit_b = 0.15 if my_stat.pop("crit_next", 0) else 0.0
        r = calc_dmg(st, me["atk"], enemy["def"], crit_b)
        if r["crit"]:
            out["events"].append(f"💥 کریتال! {r['dmg']} دمیج")
        else:
            out["events"].append(f"⚔️ حمله: {r['dmg']} دمیج")
        enemy["hp"] -= r["dmg"]
    elif action == "def":
        my_stat["shield"] = 2
        out["events"].append("🛡 دفاع آماده‌ای — ۵۰٪ دمیج کمتر و شانس کانتر")
    elif action == "insp":
        weak = {"zombie": "سر: شوت دقیق مؤثره", "dog": "سرعتش بالاست — دفاع مؤثره",
                "crimson": "آتش و فلش مؤثره", "licker": "چاقو و سرعت — سلاح سبک بهتره",
                "hunter": "زره لازمه — دفاع بدون زره خطرناکه",
                "molded": "گیاه سبزینه و آنتی‌ویروس مؤثره", "plagas": "شوت به بدن مرکزی",
                "t103": "فقط سلاح سنگین (شاتگان/ماگنوم) جواب می‌ده"}.get(
                    "zombie" if foe == "enemy" else "", "ضعفش رو با سلاح مناسب بزن")
        out["events"].append(f"🔍 بررسی: HP دشمن {enemy['hp']} | ATK {enemy['atk']} | {weak}")
        out["skip_enemy"] = True
    elif action == "flee":
        ok = _roll(st, 0, 1) < 0.5 + me["spd"] / 100
        out["fled"] = ok
        out["events"].append("🏃 فرار موفق!" if ok else "🚫 فرار ناموفق!")
        return out
    elif action == "item" and item:
        me["hp"] = min(me["max_hp"], me["hp"] + item.get("heal", 0))
        out["events"].append(f"💊 استفاده: +{item.get('heal', 0)} HP")
        if item.get("stun"):
            foe_stat["stun"] = item["stun"]
            out["events"].append("💡 فلش: دشمن گیج شد")
    elif action == "ability" and ability_id:
        a = gamedata.ABILITIES[ability_id]
        cd = st.setdefault("cds", {})
        if cd.get(ability_id, 0) > 0:
            out["events"].append(f"⏳ {a['name']} خالی نیست ({cd[ability_id]} نوبت)")
            out["skip_enemy"] = True
            return out
        if ability_id == "field_medic":
            me["hp"] = min(me["max_hp"], me["hp"] + int(me["max_hp"] * 0.3))
            out["events"].append("🩹 شفا ۳۰٪")
        elif ability_id == "precise":
            my_stat["crit_next"] = 1
            out["events"].append("🎯 شوت بعدی کریتال می‌شه")
        elif ability_id == "grenade_ab":
            r = calc_dmg(st, me["atk"] * 2.2, enemy["def"])
            enemy["hp"] -= r["dmg"]
            out["events"].append(f"💥 نارنجک: {r['dmg']} دمیج")
        elif ability_id == "burst":
            tot = 0
            for _ in range(3):
                r = calc_dmg(st, me["atk"] * 0.5, enemy["def"])
                enemy["hp"] -= r["dmg"]; tot += r["dmg"]
            out["events"].append(f"⚡ رگبار: {tot} دمیج")
        elif ability_id == "support" and support_ok:
            my_stat["shield"] = 2
            out["events"].append("🤝 سپر حمایت ۵۰٪")
        cd[ability_id] = a["cd"]

    if enemy["hp"] <= 0:
        out["win"] = True
        return out
    return _finish_turn(st, out, p_es, side_key, foe, me, enemy, foe_stat)


def _finish_turn(st, out, p_es=None, side_key="p1", foe="enemy", me=None, enemy=None, foe_stat=None):
    """نوبت دشمن (PvE) یا حریف (PvP)."""
    if out.get("skip_enemy"):
        return out
    e = st[foe]
    my_stat = st.setdefault("statuses", {}).setdefault(side_key, {})
    r = calc_dmg(st, e["atk"], me["def"] if me else 0)
    dmg = r["dmg"]
    if my_stat.get("shield", 0) > 0:
        my_stat["shield"] -= 1
        dmg = dmg // 2
        if random.random() < config.COUNTER_BASE:
            counter = max(1, dmg)
            e["hp"] -= counter
            out["events"].append(f"🔄 کانتر! {counter} دمیج به دشمن")
    if random.random() < config.DODGE_BASE + (p_es or {}).get("spd", 0) / 200:
        dmg = 0
        out["events"].append("💨 جاخالی دادی!")
    if dmg:
        me["hp"] -= dmg
        out["events"].append(f"🩸 دشمن زد: {dmg} دمیج")
    if me["hp"] <= 0:
        out["lose"] = True
    if e.get("hp", 0) <= 0 and "win" not in out:
        out["win"] = True
    return out


# ——————————————— نتیجهٔ PvE ———————————————
def pve_result(p: dict, st: dict, region_id: str, enemy_id: str, companion: str | None = None) -> dict:
    """لوت + آلودگی — فقط از جداول واقعی، سکه‌بونس همراه هم اعمال می‌شه."""
    reg = gamedata.REGIONS[region_id]
    e = gamedata.ENEMIES[enemy_id]
    out = {"coins": 0, "xp": 0, "item": None, "infected": False}
    coin_mult = 1.0
    xp_mult = 1.0
    if companion == "claire": coin_mult = 1.10
    if companion == "wesker": xp_mult = 1.15
    boost = p.get("boost") or {}
    if boost.get("xp") and boost["xp"] > 0: xp_mult *= 1.5
    out["coins"] = int(e["coins"] * coin_mult)
    out["xp"] = int(e["xp"] * xp_mult)
    if random.random() < 0.25 and reg["loot"]:
        out["item"] = random.choice(reg["loot"])
    # آلودگی — با واکسن/مقاومت کم می‌شه
    risk = reg["risk"] + 0.05 * e["danger"]
    if "resist" in p["abilities"]:
        risk *= 0.7
    if companion == "jill":
        risk *= 0.9
    if random.random() < risk:
        out["infected"] = e["infection"][1]
    return out


def boss_hit_dmg(p: dict, companion: str | None = None) -> int:
    es = eff_stats(p, companion)
    dmg = es["atk"] * random.uniform(0.8, 1.3)
    if companion == "chris":
        dmg *= 1.10
    return max(1, int(dmg))


# ——————————————— شکست ———————————————
def defeat_penalty(p: dict, enemy_danger: int) -> dict:
    """شکست همیشه پیامد داره — ولی منصفانه."""
    if enemy_danger >= 3 or random.random() < 0.25:
        return {"status": "hospitalized", "minutes": 30, "hp": 0}
    return {"status": "injury", "minutes": 10, "hp": max(1, p["max_hp"] // 5)}
