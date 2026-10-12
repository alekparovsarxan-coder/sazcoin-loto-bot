# services/draw_service.py
import random
import time
from typing import Optional, Tuple, List
from config import WIN_RULES, MAX_TICKETS_PER_USER
from database import db


def get_win_rule(price: int) -> Tuple[int, int]:
    """Qiymətə görə (winner_percent, min_real_players) qaytarır."""
    for min_p, max_p, percent, min_players in WIN_RULES:
        if min_p <= price <= max_p:
            return percent, min_players
    return 40, 5  # default


async def can_buy_ticket(user_id: int, room_price: int, interval_sec: int) -> Tuple[bool, str]:
    """Bilet alına bilərmi yoxlayır."""
    user = await db.get_user(user_id)
    if not user:
        return False, "İstifadəçi tapılmadı"
    if user["is_banned"]:
        return False, "Siz bloklanmısınız"
    if user["balance"] < room_price:
        return False, f"Balansınız kifayət etmir. Lazım: {room_price} 🪙"

    draw_id = await db.get_or_create_active_draw(room_price, interval_sec)
    current_tickets = await db.get_user_tickets_in_draw(user_id, draw_id)
    if current_tickets >= MAX_TICKETS_PER_USER:
        return False, f"Bu tirajda maksimum {MAX_TICKETS_PER_USER} bilet ala bilərsiniz"

    return True, draw_id


async def buy_ticket(user_id: int, room_price: int, interval_sec: int) -> Tuple[bool, str]:
    can, msg = await can_buy_ticket(user_id, room_price, interval_sec)
    if not can:
        return False, msg

    draw_id = msg  # can_buy_ticket uğurlu olanda draw_id qaytarır
    success = await db.add_ticket(user_id, room_price, interval_sec, draw_id)
    if success:
        draw = await db.get_draw(draw_id)
        remaining = int(draw["end_time"] - time.time())
        return True, f"✅ Bilet alındı!\n\n💰 Qiymət: {room_price} 🪙\n👥 İştirakçılar: {draw['participants_count']}\n⏱ Qalan vaxt: {remaining} saniyə"
    return False, "Xəta baş verdi, yenidən cəhd edin"


async def process_draw(draw_id: str) -> dict:
    """
    Tirajı yekunlaşdırır.
    Qaytarır: {
        "is_bot_win": bool,
        "winner_id": int | None,
        "win_amount": float,
        "pot": float,
        "real_users": int,
        "fake_name": str | None
    }
    """
    draw = await db.get_draw(draw_id)
    if not draw or draw["status"] != "active":
        return None

    participants = await db.get_draw_participants(draw_id)
    real_users_count = len(participants)
    pot = draw["total_pot"]
    price = draw["room_price"]

    percent, min_players = get_win_rule(price)
    win_amount = round(pot * (percent / 100), 2)

    result = {
        "is_bot_win": True,
        "winner_id": None,
        "win_amount": 0,
        "pot": pot,
        "real_users": real_users_count,
        "fake_name": None,
        "percent": percent
    }

    if real_users_count >= min_players and pot > 0:
        # Real qalib seç
        winner = random.choice(participants)
        winner_id = winner["user_id"]
        result.update({
            "is_bot_win": False,
            "winner_id": winner_id,
            "win_amount": win_amount
        })
        # Balansa əlavə et
        await db.change_balance(winner_id, win_amount, "win", f"Tiraj uduşu ({price} 🪙)")
        await db.finish_draw(draw_id, winner_id, win_amount, is_bot_win=False)
    else:
        # Bot qazanır — saxta ad göstər
        fake_names = [
            "Aysel_92", "ElvinCasino", "Nurlan_Win", "GunelLucky", "RashadPro",
            "LeylaStar", "TuralKing", "Sevinc_77", "KamranBet", "NarminGold",
            "OrxanVIP", "AytacQueen", "FaridAce", "SabinaLuck", "MuradBoss"
        ]
        fake = random.choice(fake_names)
        result["fake_name"] = fake
        await db.finish_draw(draw_id, None, 0, is_bot_win=True)

    return result


def generate_fake_winner_text(fake_name: str, win_amount: float, pot: float) -> str:
    return (
        f"🏆 <b>Tiraj yekunlaşdı!</b>\n\n"
        f"🎉 Qalib: <b>@{fake_name}</b>\n"
        f"💰 Uduş: <b>{win_amount:.0f} 🪙</b>\n"
        f"📦 Ümumi kassa: {pot:.0f} 🪙\n\n"
        f"<i>Növbəti tiraj artıq başladı!</i>"
    )


def generate_real_winner_text(winner_name: str, win_amount: float, pot: float, percent: int) -> str:
    return (
        f"🏆 <b>Tiraj yekunlaşdı!</b>\n\n"
        f"🎉 Qalib: <b>{winner_name}</b>\n"
        f"💰 Uduş: <b>{win_amount:.0f} 🪙</b> (kassanın {percent}%)\n"
        f"📦 Ümumi kassa: {pot:.0f} 🪙\n\n"
        f"<i>Təbriklər! Növbəti tiraj artıq başladı!</i>"
    )
