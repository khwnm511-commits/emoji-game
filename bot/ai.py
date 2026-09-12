"""AI دستیار بازیکن — فقط تحلیل و پیشنهاد. هرگز خودش اقدام نمی‌کنه.
(جدا از Game AI مربوط به NPCها — این ماژول صرفاً تحلیل وضعیت از دادهٔ واقعی دیتابیسه.)"""
from . import gamedata, config


def battle_hint(p: dict, st: dict) -> str:
    """یک خط پیشنهاد تاکتیکی براساس وضعیت واقعی نبرد."""
    me, foe = st["p1"], st.get("p2") or st["enemy"]
    hp_frac = me["hp"] / max(1, me["max_hp"])
    if hp_frac < 0.25:
        if "field_medic" in p["abilities"] and st.get("cds", {}).get("field_medic", 0) == 0:
            return "🩹 شفای سریع لازمه — توانایی پزشک میدانی"
        if foe.get("danger", 2) >= 2:
            return "❤️ HP خطرناکه — دفاع کن یا فرار کن"
        return "🛡 دفاع کن و فرصت شفا بگیر"
    if foe["hp"] <= me["atk"]:
        return "⚔️ دشمن روک‌کششه — حمله نهایی!"
    if hp_frac > 0.7 and me["atk"] > foe.get("def", 0) * 2:
        return "⚔️ برتری داری — حمله کن"
    return "🔍 اول دشمن رو بررسی کن"


def situation(p: dict, companion: str | None = None) -> str:
    """تحلیل کلی وضعیت بازیکن — منابع، ویروس، تجهیزات."""
    tips = []
    if p["infection_stage"] >= 1 and p["infection_virus"]:
        v = gamedata.VIRUSES[p["infection_virus"]]
        tips.append(f"🧬 آلودگی ({v['name']}) مرحله {p['infection_stage']} — "
                    + ("واکسن کافیه" if p["infection_stage"] < 3 else "آنتی‌ویروس لازمه — فوری!"))
    if not p["weapon"]:
        tips.append("🔫 بدون سلاحی — حداقل یه چاقو از فروشگاه بخر")
    if not p["armor"]:
        tips.append("🦺 زره نداری — جلیقه تو RPD loot می‌شه")
    if p["energy"] < 20:
        tips.append("⚡️ انرژی کمه — مأموریت زمان‌بر نگیر")
    reg = gamedata.REGIONS[p["region"]]
    if reg["danger"] >= p["level"] // 2 + 1:
        tips.append(f"⚠️ منطقهٔ فعلی ({reg['name']}) نسبت به سطحت خطرناکه")
    if p["hp"] < p["max_hp"] * 0.5:
        tips.append("❤️ اول درمان کن بعد بجنگ")
    if not tips:
        tips.append("✅ وضعیتت متعادله — مأموریت یا باس گیرت نمیاد")
    return "\n".join(tips[:4])
