# keyboards/inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import ROOMS, DAILY_TICKET


def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🎟 Bilet Al"), KeyboardButton(text="💰 Balansım")],
        [KeyboardButton(text="📊 Aktiv Tirajlar"), KeyboardButton(text="📜 Tarixçə")],
        [KeyboardButton(text="💳 Çıxarış"), KeyboardButton(text="➕ Balans Artır")],
        [KeyboardButton(text="📖 Qaydalar"), KeyboardButton(text="🆘 Dəstək")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="🛠 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def rooms_kb() -> InlineKeyboardMarkup:
    """Bütün otaqları göstərir."""
    buttons = []
    # 1 dəqiqə
    row = []
    for price in ROOMS[60]:
        row.append(InlineKeyboardButton(text=f"{price} 🪙 (1d)", callback_data=f"buy_{price}_60"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # 5 dəqiqə
    row = []
    for price in ROOMS[300]:
        row.append(InlineKeyboardButton(text=f"{price} 🪙 (5d)", callback_data=f"buy_{price}_300"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # 10 dəqiqə
    row = []
    for price in ROOMS[600]:
        row.append(InlineKeyboardButton(text=f"{price} 🪙 (10d)", callback_data=f"buy_{price}_600"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Gündəlik
    buttons.append([InlineKeyboardButton(text=f"🌟 {DAILY_TICKET} 🪙 (Gündəlik 21:00)", callback_data=f"buy_{DAILY_TICKET}_daily")])

    buttons.append([InlineKeyboardButton(text="⬅️ Geri", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_buy_kb(price: int, interval: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Təsdiqlə", callback_data=f"confirm_buy_{price}_{interval}"),
            InlineKeyboardButton(text="❌ Ləğv et", callback_data="back_rooms")
        ]
    ])


def topup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars ilə", callback_data="topup_stars")],
        [InlineKeyboardButton(text="👤 Adminə yaz", callback_data="topup_admin")],
        [InlineKeyboardButton(text="⬅️ Geri", callback_data="back_main")]
    ])


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 İstifadəçilər", callback_data="admin_users")],
        [InlineKeyboardButton(text="💸 Çıxarış tələbləri", callback_data="admin_withdraws")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ Tiraj tənzimləmələri", callback_data="admin_settings")],
        [InlineKeyboardButton(text="➕ Balans əlavə et", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="⬅️ Çıx", callback_data="back_main")]
    ])


def back_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Əsas menyu", callback_data="back_main")]
    ])
