# draw_service.py
import random
import time
from typing import Optional, Tuple, List
from config import WIN_RULES, MAX_TICKETS_PER_USER
import db


def get_win_rule(price: int) -> Tuple[int, int]:
    for min_p, max_p, percent, min_players in WIN_RULES:
        if min_p <= price <= max_p:
            return percent, min_players
    return 40, 5


async def can_buy_ticket(user_id: int, room_price: int, interval_sec: int) -> Tuple[bool, str]:
    user = await db.get_user(user_id)
    if not user:
        return False, "Пользователь не найден"
    if user["is_banned"]:
        return False, "Вы заблокированы"
    if user["balance"] < room_price:
        return False, f"Недостаточно средств. Нужно: {room_price} 🪙"

    draw_id = await db.get_or_create_active_draw(room_price, interval_sec)
    current_tickets = await db.get_user_tickets_in_draw(user_id, draw_id)
    if current_tickets >= MAX_TICKETS_PER_USER:
        return False, f"Максимум {MAX_TICKETS_PER_USER} билета в одном тираже"

    return True, draw_id


async def buy_ticket(user_id: int, room_price: int, interval_sec: int) -> Tuple[bool, str]:
    can, msg = await can_buy_ticket(user_id, room_price, interval_sec)
    if not can:
        return False, msg

    draw_id = msg
    success = await db.add_ticket(user_id, room_price, interval_sec, draw_id)
    if success:
        draw = await db.get_draw(draw_id)
        remaining = int(draw["end_time"] - time.time())
        return True, (
            f"✅ Билет куплен!\n\n"
            f"💰 Цена: {room_price} 🪙\n"
            f"👥 Участников: {draw['participants_count']}\n"
            f"⏱ Осталось: {remaining} сек."
        )
    return False, "Ошибка, попробуйте снова"


async def process_draw(draw_id: str) -> dict:
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
        winner = random.choice(participants)
        winner_id = winner["user_id"]
        result.update({
            "is_bot_win": False,
            "winner_id": winner_id,
            "win_amount": win_amount
        })
        await db.change_balance(winner_id, win_amount, "win", f"Выигрыш в тираже ({price} 🪙)")
        await db.finish_draw(draw_id, winner_id, win_amount, is_bot_win=False)
    else:
        fake_names = [
            "Aysel_92", "ElvinCasino", "Nurlan_Win", "GunelLucky", "RashadPro",
            "LeylaStar", "TuralKing", "Sevinc_77", "KamranBet", "NarminGold",
            "OrxanVIP", "AytacQueen", "FaridAce", "SabinaLuck", "MuradBoss"
        ]
        result["fake_name"] = random.choice(fake_names)
        await db.finish_draw(draw_id, None, 0, is_bot_win=True)

    return result


def generate_fake_winner_text(fake_name: str, win_amount: float, pot: float) -> str:
    return (
        f"🏆 <b>Тираж завершён!</b>\n\n"
        f"🎉 Победитель: <b>@{fake_name}</b>\n"
        f"💰 Выигрыш: <b>{win_amount:.0f} 🪙</b>\n"
        f"📦 Общая касса: {pot:.0f} 🪙\n\n"
        f"<i>Следующий тираж уже начался!</i>"
    )


def generate_real_winner_text(winner_name: str, win_amount: float, pot: float, percent: int) -> str:
    return (
        f"🏆 <b>Тираж завершён!</b>\n\n"
        f"🎉 Победитель: <b>{winner_name}</b>\n"
        f"💰 Выигрыш: <b>{win_amount:.0f} 🪙</b> ({percent}% кассы)\n"
        f"📦 Общая касса: {pot:.0f} 🪙\n\n"
        f"<i>Поздравляем! Следующий тираж уже начался!</i>"
    )
