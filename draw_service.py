# draw_service.py
import random
import time
from typing import List, Tuple, Optional
from config import (
    MATCH_RULES, PLAYER_SHARE, MAX_TICKETS_PER_USER,
    NUMBERS_COUNT, NUMBERS_RANGE, DRAWN_COUNT, SALES_CLOSE_BEFORE,
    DEFAULT_GLOBAL_PAYOUT_PERCENT, BRAND
)
import db


def generate_ticket_numbers() -> List[int]:
    return sorted(random.sample(range(1, NUMBERS_RANGE + 1), NUMBERS_COUNT))


def format_ticket(numbers: List[int], drawn: List[int] = None, title: str = "") -> str:
    drawn = drawn or []
    cells = []
    for n in numbers:
        if n in drawn:
            cells.append(f"✅{n:02d}")
        else:
            cells.append(f"⬜{n:02d}")
    row = " ".join(cells)
    hdr = f"🎫 {title}" if title else "🎫"
    return f"{hdr}\n{row}"


def format_all_tickets(tickets: list, drawn: list = None) -> str:
    drawn = drawn or []
    lines = [f"╔══ 🎟 {BRAND} ══╗"]
    for i, t in enumerate(tickets, 1):
        nums = t if isinstance(t, list) else t.get("numbers", [])
        lines.append(format_ticket(nums, drawn, f"Билет {i}"))
    lines.append("╚══════════════╝")
    return "\n".join(lines)


def min_matches_for_price(price: int) -> int:
    for max_p, need in MATCH_RULES:
        if price <= max_p:
            return need
    return 5


def player_share_percent(price: int) -> int:
    for max_p, pct in PLAYER_SHARE:
        if price <= max_p:
            return pct
    return 60


async def can_buy(user_id: int, room_price: int, qty: int) -> Tuple[bool, str]:
    user = await db.get_user(user_id)
    if not user:
        return False, "Пользователь не найден"
    if user["is_banned"]:
        return False, "Вы заблокированы"

    # Нельзя покупать другой номинал пока есть активный билет
    active_price = await db.get_user_active_draw_price(user_id)
    if active_price is not None and active_price != room_price:
        return False, f"У вас уже есть билет на тираж {active_price} 🪙. Дождитесь окончания."

    draw_id = await db.get_or_create_draw(room_price)
    draw = await db.get_draw(draw_id)
    now = time.time()

    if draw["status"] != "registration":
        return False, "Регистрация на этот тираж закрыта."

    # За 30 сек до старта продажа закрыта
    if now >= draw["reg_end"] - SALES_CLOSE_BEFORE:
        return False, "До старта меньше 30 сек — продажа билетов закрыта."

    current = await db.get_user_tickets_in_draw(user_id, draw_id)
    if current + qty > MAX_TICKETS_PER_USER:
        return False, f"Максимум {MAX_TICKETS_PER_USER} билета. У вас уже {current}."

    total = room_price * qty
    if user["balance"] < total:
        return False, f"Недостаточно средств. Нужно: {total} 🪙"

    return True, draw_id


async def buy_tickets(user_id: int, room_price: int, qty: int) -> Tuple[bool, str]:
    can, msg = await can_buy(user_id, room_price, qty)
    if not can:
        return False, msg
    draw_id = msg
    tickets_nums = [generate_ticket_numbers() for _ in range(qty)]
    ok = await db.add_tickets(user_id, room_price, draw_id, tickets_nums)
    if not ok:
        return False, "Ошибка списания баланса"

    draw = await db.get_draw(draw_id)
    left = max(0, int(draw["reg_end"] - time.time()))
    ticket_view = format_all_tickets(tickets_nums)
    return True, (
        f"✅ <b>Билеты куплены!</b> (x{qty})\n\n"
        f"{ticket_view}\n\n"
        f"💰 Сумма: {room_price * qty} 🪙\n"
        f"👥 В тираже билетов: {draw['participants_count']}\n"
        f"⏱ До розыгрыша: ~{left} сек.\n\n"
        f"<i>Числа будут выпадать одно за другим.</i>"
    )


async def process_draw_step(draw_id: str, bot) -> bool:
    draw = await db.get_draw(draw_id)
    if not draw or draw["status"] not in ("drawing", "registration"):
        return False

    # Переводим в drawing если время пришло
    now = time.time()
    if draw["status"] == "registration" and now >= draw["draw_start"]:
        await db.set_draw_status(draw_id, "drawing")
        draw = await db.get_draw(draw_id)

    if draw["status"] != "drawing":
        return True

    drawn = list(draw["drawn_numbers"])
    step = draw["draw_step"] or 0

    if step >= DRAWN_COUNT:
        await finalize_draw(draw_id, bot)
        return False

    available = [n for n in range(1, NUMBERS_RANGE + 1) if n not in drawn]
    if not available:
        await finalize_draw(draw_id, bot)
        return False

    new_number = random.choice(available)
    drawn.append(new_number)
    step += 1
    await db.update_draw_numbers(draw_id, drawn, step)

    tickets = await db.get_tickets_for_draw(draw_id)
    by_user = {}
    for t in tickets:
        by_user.setdefault(t["user_id"], []).append(t)

    for uid, user_tickets in by_user.items():
        lines = [f"🎱 <b>Выпал номер: {new_number}</b>  ({step}/{DRAWN_COUNT})\n"]
        lines.append(format_all_tickets(user_tickets, drawn))
        if any(new_number in t["numbers"] for t in user_tickets):
            lines.append(f"\n✅ У вас есть число <b>{new_number}</b>!")
        try:
            await bot.send_message(uid, "\n".join(lines), parse_mode="HTML")
        except Exception:
            pass

    if step >= DRAWN_COUNT:
        await finalize_draw(draw_id, bot)
        return False
    return True


async def finalize_draw(draw_id: str, bot):
    draw = await db.get_draw(draw_id)
    if not draw or draw["status"] == "finished":
        return

    drawn = draw["drawn_numbers"]
    tickets = await db.get_tickets_for_draw(draw_id)
    pot = draw["total_pot"]
    price = draw["room_price"]
    need = min_matches_for_price(price)
    share = player_share_percent(price)
    win_amount = round(pot * share / 100, 2)

    scored = []
    for t in tickets:
        matches = len([n for n in t["numbers"] if n in drawn])
        await db.set_ticket_matches(t["id"], matches)
        scored.append({**t, "matches": matches})

    real_users = len(set(t["user_id"] for t in tickets))
    result_is_bot = True
    winner_id = None

    # Меньше 2 реальных игроков → касса
    if real_users >= 2 and pot > 0 and scored:
        eligible = [t for t in scored if t["matches"] >= need]
        if eligible:
            # Побеждает билет с наибольшим числом совпадений
            max_m = max(t["matches"] for t in eligible)
            top = [t for t in eligible if t["matches"] == max_m]
            winner = random.choice(top)
            winner_id = winner["user_id"]
            result_is_bot = False

            # Глобальный лимит выплат
            bank = await db.get_house_bank()
            payout_pct = float(await db.get_setting("global_payout_percent", str(DEFAULT_GLOBAL_PAYOUT_PERCENT)))
            max_payout = bank["balance"] * payout_pct / 100
            actual_win = min(win_amount, max_payout) if max_payout > 0 else win_amount
            actual_win = max(0, actual_win)

            if actual_win > 0:
                await db.change_balance(winner_id, actual_win, "win", f"Выигрыш SazLoto ({price} 🪙, {max_m} совп.)")
                await db.house_pay(actual_win)
            win_amount = actual_win
            await db.finish_draw(draw_id, winner_id, win_amount, False)
        else:
            await db.finish_draw(draw_id, None, 0, True)
    else:
        await db.finish_draw(draw_id, None, 0, True)

    drawn_str = " ".join(f"{n:02d}" for n in drawn)
    for t in scored:
        uid = t["user_id"]
        view = format_all_tickets([t], drawn)
        matches = t["matches"]
        if not result_is_bot and uid == winner_id:
            text = (
                f"🏆 <b>ВЫ ВЫИГРАЛИ!</b>\n\n"
                f"🎱 Числа тиража: {drawn_str}\n\n"
                f"{view}\n\n"
                f"✅ Совпадений: <b>{matches}</b> (нужно было ≥{need})\n"
                f"💰 Выигрыш: <b>{win_amount:.0f} 🪙</b>\n\n"
                f"Поздравляем от {BRAND}!"
            )
        else:
            text = (
                f"🏁 <b>Тираж завершён</b>\n\n"
                f"🎱 Числа тиража: {drawn_str}\n\n"
                f"{view}\n\n"
                f"Совпадений: <b>{matches}</b> (для выигрыша нужно ≥{need})\n"
                f"{'В этот раз без выигрыша.' if matches < need else 'Было близко!'}"
            )
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
        except Exception:
            pass

    if real_users > 0:
        from config import ADMIN_IDS
        msg = (f"🤖 Касса | {price} 🪙 | банк={pot:.0f} | игроков={real_users}"
               if result_is_bot else
               f"🏆 {winner_id} | +{win_amount:.0f} 🪙 | банк={pot:.0f} | игроков={real_users}")
        for aid in ADMIN_IDS:
            try:
                await bot.send_message(aid, msg)
            except:
                pass
