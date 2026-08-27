"""
موتور قالب‌بندی متمرکز رابط کاربری (UI Formatter Engine)
مسئول: استانداردسازی راست‌چین (RTL)، تبدیل اعداد به فارسی، و ساخت کارت‌های منظم برای تلگرام
"""

from typing import Any, Optional


_PERSIAN_DIGITS_MAP = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(val: Any) -> str:
    """تبدیل تمام ارقام انگلیسی به فارسی"""
    if val is None:
        return ""
    return str(val).translate(_PERSIAN_DIGITS_MAP)


def format_stat_row(icon: str, label: str, value: Any, lang: str = "fa") -> str:
    """تولید یک سطر آماری استاندارد با ایموجی و برچسب راست‌چین"""
    formatted_val = to_persian_digits(value) if lang == "fa" else str(value)
    return f"{icon} **{label}:** `{formatted_val}`"


def format_divider() -> str:
    """خط جداکننده مینیمال و استاندارد برای پیام‌های تلگرام"""
    return "━━━━━━━━━━━━━━"


def format_mode_badge(mode: str, lang: str = "fa") -> str:
    """ساخت نشان خوانا برای مود بازی"""
    mode_lower = (mode or "").lower()
    if lang == "fa":
        if mode_lower in ("br", "battle_royale"):
            return "بتل رویال (BR)"
        elif mode_lower in ("mp", "multiplayer"):
            return "مولتی‌پلیر (MP)"
        elif mode_lower == "zombies":
            return "زامبی (Zombies)"
        return mode.upper()
    else:
        if mode_lower in ("br", "battle_royale"):
            return "Battle Royale (BR)"
        elif mode_lower in ("mp", "multiplayer"):
            return "Multiplayer (MP)"
        elif mode_lower == "zombies":
            return "Zombies"
        return mode.upper()


def format_weapon_card(
    weapon_name: str,
    category_name: str,
    mode: str,
    all_count: int,
    top_count: int,
    lang: str = "fa",
) -> str:
    """
    ساخت کارت مشخصات و آمار سلاح به صورت کاملاً راست‌چین و بدون بهم‌ریختگی BiDi
    """
    mode_title = format_mode_badge(mode, lang)

    if lang == "fa":
        header = f"🔫 **سلاح:** `{weapon_name}`\n"
        if category_name:
            header += f"📂 **دسته:** {category_name}\n"
        header += f"🎮 **مود بازی:** {mode_title}\n"
        header += f"{format_divider()}\n"

        if all_count == 0:
            header += "⚠️ هیچ اتچمنتی برای این سلاح در این مود ثبت نشده است."
        else:
            p_all = to_persian_digits(all_count)
            p_top = to_persian_digits(top_count)
            header += f"📊 **کل اتچمنت‌ها:** {p_all}\n"
            header += f"⭐ **اتچمنت‌های برتر:** {p_top}"
        return header
    else:
        header = f"🔫 **Weapon:** `{weapon_name}`\n"
        if category_name:
            header += f"📂 **Category:** {category_name}\n"
        header += f"🎮 **Game Mode:** {mode_title}\n"
        header += f"{format_divider()}\n"

        if all_count == 0:
            header += "⚠️ No attachments found for this weapon in this mode."
        else:
            header += f"📊 **Total Attachments:** {all_count}\n"
            header += f"⭐ **Top Attachments:** {top_count}"
        return header


def format_button_label(
    text: str, count: Optional[int] = None, lang: str = "fa"
) -> str:
    """
    تولید برچسب دکمه با شمارنده عددی درون پرانتز با سازگاری کامل RTL
    """
    if count is None:
        return text
    formatted_count = to_persian_digits(count) if lang == "fa" else str(count)
    return f"{text} ({formatted_count})"
