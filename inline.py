# inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import ROOMS, DAILY_TICKET


def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🎟 Купить билет"), KeyboardButton(text="💰 Мой баланс")],
        [KeyboardButton(text="📊 Активные тиражи"), KeyboardButton(text="📜 История")],
        [KeyboardButton(text="💳 Вывод"), KeyboardButton(text="➕ Пополнить баланс")],
        [KeyboardButton(text="📖 Правила"), KeyboardButton(text="🆘 Поддержка")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="🛠 Админ панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def rooms_kb() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for price in ROOMS[60]:
        row.append(InlineKeyboardButton(text=f"{price} 🪙 (1м)", callback_data=f"buy_{price}_60"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    row = []
    for price in ROOMS[300]:
        row.append(InlineKeyboardButton(text=f"{price} 🪙 (5м)", callback_data=f"buy_{price}_300"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    row = []
    for price in ROOMS[600]:
        row.append(InlineKeyboardButton(text=f"{price} 🪙 (10м)", callback_data=f"buy_{price}_600"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text=f"🌟 {DAILY_TICKET} 🪙 (Ежедневно 21:00)", callback_data=f"buy_{DAILY_TICKET}_daily")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_buy_kb(price: int, interval: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_buy_{price}_{interval}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_rooms")
        ]
    ])


def topup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Через Telegram Stars", callback_data="topup_stars")],
        [InlineKeyboardButton(text="👤 Написать админу", callback_data="topup_admin")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="admin_withdraws")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ Настройки тиражей", callback_data="admin_settings")],
        [InlineKeyboardButton(text="➕ Добавить баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="⬅️ Выход", callback_data="back_main")]
    ])


def back_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")]
    ])
