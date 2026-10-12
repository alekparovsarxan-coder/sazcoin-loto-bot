# draw_service.py
import random
import time
from typing import Optional, Tuple, List
from config import WIN_RULES, MAX_TICKETS_PER_USER
import db

NUMBERS_COUNT = 5          # сколько чисел на билете
NUMBERS_RANGE = 36         # числа от 1 до 36
DRAWN_COUNT = 5            # сколько чисел выпадает в тираже


def generate_ticket_numbers() -> List[int]:
    return sorted(random.sample(range(1, NUMBERS_RANGE + 1), NUMBERS_COUNT))


def format_ticket(numbers: List[int], drawn: List[int] = None) -> str:
    """Красивый билет. Совпавшие числа помечаются ✅"""
    drawn = drawn or []
    lines = []
    for n in numbers:
        if n in drawn:
            lines.append(f"✅ <b>{n:02d}</b>")
        else:
            lines.append(f"⬜ {n:02d}")
    return "  ".join(lines)


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
    numbers = generate_ticket_numbers()
    success = await db.add_ticket(user_id, room_price, interval_sec, draw_id, numbers)
    if success:
        draw = await db.get_draw(draw_id)
        remaining = max(0, int(draw["end_time"] - time.time()))
        ticket_view = format_ticket(numbers)
        return True, (
            f"✅ <b>Билет куплен!</b>\n\n"
            f"🎫 Ваш билет:\n{ticket_view}\n\n"
            f"💰 Цена: {room_price} 🪙\n"
            f"👥 Участников: {draw['participants_count']}\n"
            f"⏱ До начала розыгрыша: ~{remaining} сек.\n\n"
            f"<i>Числа будут выпадать одно за другим. Следите за обновлениями!</i>"
        )
    return False, "Ошибка, попробуйте снова"


async def process_draw_step(draw_id: str, bot) -> bool:
    """
    Один шаг розыгрыша: выпадает одно новое число.
    Возвращает True если тираж ещё идёт, False если закончился.
    """
    draw = await db.get_draw(draw_id)
    if not draw or draw["status"] != "active":
        return False

    drawn = list(draw["drawn_numbers"])
    step = draw["draw_step"]

    if step >= DRAWN_COUNT:
        # Все числа выпали — завершаем
        await finalize_draw(draw_id, bot)
        return False

    # Выбираем новое число
    available = [n for n in range(1, NUMBERS_RANGE + 1) if n not in drawn]
    if not available:
        await finalize_draw(draw_id, bot)
        return False

    new_number = random.choice(available)
    drawn.append(new_number)
    step += 1
    await db.update_draw_numbers(draw_id, drawn, step)

    # Отправляем обновление всем участникам
    tickets = await db.get_tickets_for_draw(draw_id)
    participants = {}
    for t in tickets:
        uid = t["user_id"]
        if uid not in participants:
            participants[uid] = []
        participants[uid].append(t)

    for uid, user_tickets in participants.items():
        texts = [f"🎱 <b>Выпал номер: {new_number}</b>  ({step}/{DRAWN_COUNT})\n"]
        for t in user_tickets:
            nums = t["numbers"]
            matched = [n for n in nums if n in drawn]
            ticket_view = format_ticket(nums, drawn)
            texts.append(f"🎫 Билет #{t['id']}:\n{ticket_view}")
            if new_number in nums:
                texts.append(f"✅ У вас есть число <b>{new_number}</b>!")
        texts.append(f"\nСовпадений: {len(matched)}/{NUMBERS_COUNT}")
        try:
            await bot.send_message(uid, "\n".join(texts), parse_mode="HTML")
        except Exception:
            pass

    if step >= DRAWN_COUNT:
        await finalize_draw(draw_id, bot)
        return False
    return True


async def finalize_draw(draw_id: str, bot):
    """Подводим итоги тиража."""
    draw = await db.get_draw(draw_id)
    if not draw or draw["status"] != "active":
        return

    drawn = draw["drawn_numbers"]
    tickets = await db.get_tickets_for_draw(draw_id)
    pot = draw["total_pot"]
    price = draw["room_price"]
    percent, min_players = get_win_rule(price)
    win_amount = round(pot * (percent / 100), 2)

    # Считаем совпадения
    scored = []
    for t in tickets:
        matches = len([n for n in t["numbers"] if n in drawn])
        await db.set_ticket_matches(t["id"], matches)
        scored.append({**t, "matches": matches})

    real_users = len(set(t["user_id"] for t in tickets))
    result_is_bot = True
    winner_id = None

    if real_users >= min_players and pot > 0 and scored:
        # Побеждает тот, у кого больше всего совпадений
        max_matches = max(t["matches"] for t in scored)
        if max_matches >= 2:  # минимум 2 совпадения для выигрыша
            top = [t for t in scored if t["matches"] == max_matches]
            winner = random.choice(top)
            winner_id = winner["user_id"]
            result_is_bot = False
            await db.change_balance(winner_id, win_amount, "win", f"Выигрыш в тираже ({price} 🪙, {max_matches} совп.)")
            await db.finish_draw(draw_id, winner_id, win_amount, is_bot_win=False)
        else:
            await db.finish_draw(draw_id, None, 0, is_bot_win=True)
    else:
        await db.finish_draw(draw_id, None, 0, is_bot_win=True)

    # Финальные сообщения участникам
    drawn_str = "  ".join(f"<b>{n:02d}</b>" for n in drawn)
    for t in scored:
        uid = t["user_id"]
        ticket_view = format_ticket(t["numbers"], drawn)
        matches = t["matches"]
        if not result_is_bot and uid == winner_id:
            text = (
                f"🏆 <b>Тираж завершён! ВЫ ВЫИГРАЛИ!</b>\n\n"
                f"🎱 Выпавшие числа:\n{drawn_str}\n\n"
                f"🎫 Ваш билет:\n{ticket_view}\n\n"
                f"✅ Совпадений: <b>{matches}</b>\n"
                f"💰 Выигрыш: <b>{win_amount:.0f} 🪙</b>\n\n"
                f"Поздравляем!"
            )
        else:
            text = (
                f"🏁 <b>Тираж завершён</b>\n\n"
                f"🎱 Выпавшие числа:\n{drawn_str}\n\n"
                f"🎫 Ваш билет:\n{ticket_view}\n\n"
                f"Совпадений: <b>{matches}</b>\n"
                f"{'К сожалению, в этот раз без выигрыша.' if matches < 2 else 'Было близко, но победил другой игрок.'}"
            )
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
        except Exception:
            pass

    # Уведомление админу только если были игроки
    if real_users > 0:
        from config import ADMIN_IDS
        if result_is_bot:
            admin_text = f"🤖 Бот | {price} 🪙 | Касса: {pot:.0f} | Игроков: {real_users}"
        else:
            admin_text = f"🏆 Победитель {winner_id} | {win_amount:.0f} 🪙 | Касса: {pot:.0f} | Игроков: {real_users}"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text)
            except:
                pass


async def process_draw(draw_id: str) -> dict:
    """Совместимость — вызывается если нужно сразу завершить."""
    draw = await db.get_draw(draw_id)
    if not draw:
        return None
    return {
        "is_bot_win": True,
        "winner_id": None,
        "win_amount": 0,
        "pot": draw["total_pot"],
        "real_users": 0,
        "fake_name": None,
        "percent": 40
    }


def generate_fake_winner_text(fake_name: str, win_amount: float, pot: float) -> str:
    return f"🏆 Тираж завершён!\nПобедитель: @{fake_name}"


def generate_real_winner_text(winner_name: str, win_amount: float, pot: float, percent: int) -> str:
    return f"🏆 Тираж завершён!\nПобедитель: {winner_name}\nВыигрыш: {win_amount:.0f} 🪙"
