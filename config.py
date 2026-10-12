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

REGISTRATION_SEC = 300
DRAW_DURATION_SEC = 60
SALES_CLOSE_BEFORE = 30

TICKET_PRICES = [20, 50, 100, 200, 500, 800, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 10000, 20000]
MAX_TICKETS_PER_USER = 3

MATCH_RULES = [(500, 4), (2500, 3), (999999, 5)]
PLAYER_SHARE = [(2500, 80), (999999, 60)]
DEFAULT_GLOBAL_PAYOUT_PERCENT = 40

NUMBERS_COUNT = 5
NUMBERS_RANGE = 36
DRAWN_COUNT = 5

# Бонусы и акции
DAILY_BONUS = 50
REFERRAL_BONUS = 100          # пригласившему
REFERRAL_BONUS_NEW = 50      # новому
FIRST_DEPOSIT_BONUS_PCT = 10
STREAK_BONUS_EVERY = 3       # каждые 3 тиража подряд
STREAK_BONUS_AMOUNT = 30
MINI_JACKPOT_EVERY = 10       # каждые 10 тиражей
NEAR_WIN_DISCOUNT_PCT = 10   # скидка если почти выиграл

CURRENCY = "sazcoin"
CURRENCY_SYMBOL = "🪙"
BRAND = "SazLoto"
BOT_USERNAME = os.getenv("BOT_USERNAME", "SazLotoBot")  # без @
