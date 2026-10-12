# config.py
import os
from dataclasses import dataclass, field
from typing import List, Dict

# ====================== BOT SETTINGS ======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")  # BotFather-dən götürün
ADMIN_IDS = [123456789]  # Öz Telegram ID-nizi yazın (bir neçə ola bilər)

# ====================== DATABASE ======================
DB_PATH = "database/sazcoin.db"

# ====================== BALANCE & WITHDRAWAL ======================
MIN_TOPUP = 1000          # Minimum balans artırma (sazcoin)
MIN_WITHDRAW = 2000       # Minimum çıxarış
WITHDRAW_FEE_PERCENT = 10 # Çıxarış xidmət haqqı (%)

# ====================== TICKETS & ROOMS ======================
# Format: {interval_seconds: [ticket_prices]}
ROOMS = {
    60:   [20, 50, 100, 200, 500],                    # 1 dəqiqə
    300:  [800, 1000, 1500, 2000, 2500],              # 5 dəqiqə
    600:  [3000, 4000, 5000, 10000],                  # 10 dəqiqə
}

# Gündəlik böyük tiraj
DAILY_TICKET = 20000
DAILY_HOUR = 21   # 21:00
DAILY_MINUTE = 0

# Bir istifadəçi eyni anda maksimum neçə bilet ala bilər
MAX_TICKETS_PER_USER = 3

# ====================== WIN RULES ======================
# (min_price, max_price, winner_percent, min_real_players)
# winner_percent = kassanın neçə faizi qalibə verilir
WIN_RULES = [
    (0,     500,   60, 3),   # 500-ə qədər → 60%, minimum 3 real müştəri
    (501,   2500,  50, 5),   # 501-2500 → 50%, minimum 5 real müştəri
    (2501,  999999,40, 5),   # 2501+ → 40%, minimum 5 real müştəri
]

# ====================== TEXTS ======================
CURRENCY = "sazcoin"
CURRENCY_SYMBOL = "🪙"
