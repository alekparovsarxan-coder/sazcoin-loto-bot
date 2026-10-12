# inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import TICKET_PRICES, BRAND


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
    for price in TICKET_PRICES:
        row.append(InlineKeyboardButton(text=f"{price} 🪙", callback_data=f"price_{price}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def qty_kb(price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 билет", callback_data=f"qty_{price}_1"),
            InlineKeyboardButton(text="2 билета", callback_data=f"qty_{price}_2"),
            InlineKeyboardButton(text="3 билета", callback_data=f"qty_{price}_3"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_rooms")]
    ])


def topup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="topup_stars")],
        [InlineKeyboardButton(text="👤 Написать админу", callback_data="topup_admin")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Касса (банк)", callback_data="admin_bank")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="admin_withdraws")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ % выплат", callback_data="admin_payout_pct")],
        [InlineKeyboardButton(text="➕ Добавить баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="⬅️ Выход", callback_data="back_main")]
    ])


def back_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")]
    ])
