# inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import TICKET_PRICES, BRAND

def main_menu_kb(is_admin=False):
    buttons = [
        [KeyboardButton(text="🎟 Купить билет"), KeyboardButton(text="💰 Мой баланс")],
        [KeyboardButton(text="📊 Активные тиражи"), KeyboardButton(text="📜 История")],
        [KeyboardButton(text="🎁 Бонусы"), KeyboardButton(text="🏆 Топ игроков")],
        [KeyboardButton(text="💳 Вывод"), KeyboardButton(text="➕ Пополнить")],
        [KeyboardButton(text="📖 Правила"), KeyboardButton(text="🔗 Реферал")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="🛠 Админ панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def rooms_kb():
    buttons, row = [], []
    for p in TICKET_PRICES:
        row.append(InlineKeyboardButton(text=f"{p} 🪙", callback_data=f"price_{p}"))
        if len(row) == 3:
            buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def qty_kb(price):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="1", callback_data=f"qty_{price}_1"),
        InlineKeyboardButton(text="2", callback_data=f"qty_{price}_2"),
        InlineKeyboardButton(text="3", callback_data=f"qty_{price}_3"),
    ], [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_rooms")]])

def bonuses_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ежедневный бонус", callback_data="daily_bonus")],
        [InlineKeyboardButton(text="🏷 Промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ])

def topup_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="topup_stars")],
        [InlineKeyboardButton(text="👤 Написать админу", callback_data="topup_admin")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ])

def admin_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Касса", callback_data="admin_bank")],
        [InlineKeyboardButton(text="👥 Юзеры", callback_data="admin_users")],
        [InlineKeyboardButton(text="💸 Выводы", callback_data="admin_withdraws")],
        [InlineKeyboardButton(text="📊 Стата", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ % выплат", callback_data="admin_payout_pct")],
        [InlineKeyboardButton(text="🏷 Создать промо", callback_data="admin_promo")],
        [InlineKeyboardButton(text="🎯 Force-win", callback_data="admin_forcewin")],
        [InlineKeyboardButton(text="⚠️ Убыточные", callback_data="admin_losers")],
        [InlineKeyboardButton(text="➕ Баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="⬅️ Выход", callback_data="back_main")],
    ])

def back_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Меню", callback_data="back_main")]])
