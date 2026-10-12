# config.py
import os
from typing import List

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
_admin_raw = os.getenv("ADMIN_IDS", "123456789")
ADMIN_IDS: List[int] = [int(x.strip()) for x in _admin_raw.split(",") if x.strip().isdigit()]

DB_PATH = os.getenv("DB_PATH", "/data/sazcoin.db")

MIN_TOPUP = 1000
MIN_WITHDRAW = 2000
WITHDRAW_FEE_PERCENT = 10

# === НОВАЯ СИСТЕМА ТИРАЖЕЙ ===
# Регистрация 5 минут, розыгрыш 1 минута, за 30 сек до старта продажа закрывается
REGISTRATION_SEC = 300      # 5 минут набор
DRAW_DURATION_SEC = 60      # 1 минута розыгрыш чисел
SALES_CLOSE_BEFORE = 30     # за 30 сек до старта продажа стоп

# Цены билетов (все в одном цикле 5+1 мин)
TICKET_PRICES = [20, 50, 100, 200, 500, 800, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 10000, 20000]

MAX_TICKETS_PER_USER = 3

# Правила совпадений для выигрыша:
# (max_price, min_matches_needed)
MATCH_RULES = [
    (500, 4),      # до 500 → минимум 4 совпадения
    (2500, 3),     # до 2500 → минимум 3
    (999999, 5),   # выше 2500 → все 5
]

# Доля банка игрокам (остальное кассе)
# до 2500: игрокам 80%, кассе 20%
# выше 2500: игрокам 60%, кассе 40%
PLAYER_SHARE = [
    (2500, 80),
    (999999, 60),
]

# Глобальный лимит: максимум X% от ВСЕЙ кассы можно отдать игрокам
DEFAULT_GLOBAL_PAYOUT_PERCENT = 40

NUMBERS_COUNT = 5
NUMBERS_RANGE = 36
DRAWN_COUNT = 5

CURRENCY = "sazcoin"
CURRENCY_SYMBOL = "🪙"
BRAND = "SazLoto"
