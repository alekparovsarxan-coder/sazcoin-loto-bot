# config.py
import os
from typing import List

# ====================== BOT SETTINGS ======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ADMIN_IDS - Railway-də "123456789" və ya "123,456,789" formatında yazın
_admin_raw = os.getenv("ADMIN_IDS", "123456789")
ADMIN_IDS: List[int] = [int(x.strip()) for x in _admin_raw.split(",") if x.strip().isdigit()]

# ====================== DATABASE ======================
# Railway Volume üçün /data istifadə edirik (persistent)
# Əgər lokal test edirsinizsə, "database/sazcoin.db" qalır
DB_PATH = os.getenv("DB_PATH", "/data/sazcoin.db")

# ====================== BALANCE & WITHDRAWAL ======================
MIN_TOPUP = 1000
MIN_WITHDRAW = 2000
WITHDRAW_FEE_PERCENT = 10

# ====================== TICKETS & ROOMS ======================
ROOMS = {
    60:   [20, 50, 100, 200, 500],          # 1 dəqiqə
    300:  [800, 1000, 1500, 2000, 2500],    # 5 dəqiqə
    600:  [3000, 4000, 5000, 10000],        # 10 dəqiqə
}

DAILY_TICKET = 20000
DAILY_HOUR = 21
DAILY_MINUTE = 0

MAX_TICKETS_PER_USER = 3

# ====================== WIN RULES ======================
# (min_price, max_price, winner_percent, min_real_players)
WIN_RULES = [
    (0,     500,   60, 3),
    (501,   2500,  50, 5),
    (2501,  999999,40, 5),
]

CURRENCY = "sazcoin"
CURRENCY_SYMBOL = "🪙"
