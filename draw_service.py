# draw_service.py
import random, time
from typing import List, Tuple
from config import (
    MATCH_RULES, PLAYER_SHARE, MAX_TICKETS_PER_USER, NUMBERS_COUNT, NUMBERS_RANGE,
    DRAWN_COUNT, SALES_CLOSE_BEFORE, DEFAULT_GLOBAL_PAYOUT_PERCENT, BRAND,
    STREAK_BONUS_EVERY, STREAK_BONUS_AMOUNT, MINI_JACKPOT_EVERY
)
import db

def generate_ticket_numbers():
    return sorted(random.sample(range(1, NUMBERS_RANGE+1), NUMBERS_COUNT))

def format_ticket(numbers, drawn=None, title=""):
    drawn = drawn or []
    cells = [f"✅{n:02d}" if n in drawn else f"⬜{n:02d}" for n in numbers]
    return f"🎫 {title}\n" + " ".join(cells) if title else " ".join(cells)

def format_all_tickets(tickets, drawn=None):
    drawn = drawn or []
    lines = [f"╔══ 🎟 {BRAND} ══╗"]
    for i, t in enumerate(tickets, 1):
        nums = t if isinstance(t, list) else t.get("numbers", [])
        lines.append(format_ticket(nums, drawn, f"Билет {i}"))
    lines.append("╚══════════════╝")
    return "\n".join(lines)

def min_matches_for_price(price):
    for max_p, need in MATCH_RULES:
        if price <= max_p: return need
    return 5

def player_share_percent(price):
    for max_p, pct in PLAYER_SHARE:
        if price <= max_p: return pct
    return 60

async def can_buy(user_id, room_price, qty) -> Tuple[bool, str]:
    user = await db.get_user(user_id)
    if not user: return False, "Пользователь не найден"
    if user["is_banned"]: return False, "Вы заблокированы"
    active = await db.get_user_active_draw_price(user_id)
    if active is not None and active != room_price:
        return False, f"У вас билет на {active} 🪙. Дождитесь окончания."
    draw_id = await db.get_or_create_draw(room_price)
    draw = await db.get_draw(draw_id)
    now = time.time()
    if draw["status"] != "registration":
        return False, "Регистрация закрыта."
    if now >= draw["reg_end"] - SALES_CLOSE_BEFORE:
        return False, "До старта <30 сек — продажа закрыта."
    current = await db.get_user_tickets_in_draw(user_id, draw_id)
    if current + qty > MAX_TICKETS_PER_USER:
        return False, f"Макс {MAX_TICKETS_PER_USER} билета. У вас {current}."
    total = room_price * qty
    if user.get("near_win"):
        total = total * 0.9
    if user["balance"] < total:
        return False, f"Нужно ~{total:.0f} 🪙"
    return True, draw_id

async def buy_tickets(user_id, room_price, qty) -> Tuple[bool, str]:
    can, msg = await can_buy(user_id, room_price, qty)
    if not can: return False, msg
    draw_id = msg
    tickets_nums = [generate_ticket_numbers() for _ in range(qty)]
    ok = await db.add_tickets(user_id, room_price, draw_id, tickets_nums)
    if not ok: return False, "Ошибка баланса"
    draw = await db.get_draw(draw_id)
    left = max(0, int(draw["reg_end"] - time.time()))
    user = await db.get_user(user_id)
    streak = (user.get("streak") or 0) + 1
    await db.set_streak(user_id, streak)
    extra = ""
    if streak > 0 and streak % STREAK_BONUS_EVERY == 0:
        await db.change_balance(user_id, STREAK_BONUS_AMOUNT, "bonus", f"Серия {streak}")
        extra = f"\n🔥 Серия {streak} игр! Бонус +{STREAK_BONUS_AMOUNT} 🪙"
    return True, (
        f"✅ <b>Билеты куплены!</b> (x{qty})\n\n"
        f"{format_all_tickets(tickets_nums)}\n\n"
        f"💰 {room_price * qty} 🪙 | 👥 {draw['participants_count']} | ⏱ ~{left} сек"
        f"{extra}\n\n<i>Числа выпадут одно за другим!</i>"
    )

async def process_draw_step(draw_id, bot) -> bool:
    draw = await db.get_draw(draw_id)
    if not draw or draw["status"] not in ("drawing", "registration"): return False
    now = time.time()
    if draw["status"] == "registration" and now >= draw["draw_start"]:
        await db.set_draw_status(draw_id, "drawing")
        draw = await db.get_draw(draw_id)
    if draw["status"] != "drawing": return True
    drawn = list(draw["drawn_numbers"])
    step = draw["draw_step"] or 0
    if step >= DRAWN_COUNT:
        await finalize_draw(draw_id, bot); return False
    available = [n for n in range(1, NUMBERS_RANGE+1) if n not in drawn]
    if not available:
        await finalize_draw(draw_id, bot); return False
    new_number = random.choice(available)
    drawn.append(new_number); step += 1
    await db.update_draw_numbers(draw_id, drawn, step)
    tickets = await db.get_tickets_for_draw(draw_id)
    by_user = {}
    for t in tickets:
        by_user.setdefault(t["user_id"], []).append(t)
    effects = ["🥁", "🎱", "✨", "🎯", "💫"]
    for uid, uts in by_user.items():
        lines = [f"{effects[step%5]} <b>Выпал номер: {new_number}</b>  ({step}/{DRAWN_COUNT})\n"]
        lines.append(format_all_tickets(uts, drawn))
        if any(new_number in t["numbers"] for t in uts):
            lines.append(f"\n✅ У вас есть <b>{new_number}</b>!")
        try: await bot.send_message(uid, "\n".join(lines), parse_mode="HTML")
        except: pass
    if step >= DRAWN_COUNT:
        await finalize_draw(draw_id, bot); return False
    return True

async def finalize_draw(draw_id, bot):
    draw = await db.get_draw(draw_id)
    if not draw or draw["status"] == "finished": return
    drawn = draw["drawn_numbers"]
    tickets = await db.get_tickets_for_draw(draw_id)
    pot = draw["total_pot"]; price = draw["room_price"]
    need = min_matches_for_price(price)
    share = player_share_percent(price)
    win_amount = round(pot * share / 100, 2)
    scored = []
    for t in tickets:
        m = len([n for n in t["numbers"] if n in drawn])
        await db.set_ticket_matches(t["id"], m)
        scored.append({**t, "matches": m})
    real_users = len(set(t["user_id"] for t in tickets))
    result_is_bot = True; winner_id = None; max_m = 0

    if real_users >= 2 and pot > 0 and scored:
        eligible = [t for t in scored if t["matches"] >= need]
        if eligible:
            max_m = max(t["matches"] for t in eligible)
            top = [t for t in eligible if t["matches"] == max_m]
            winner = random.choice(top)
            winner_id = winner["user_id"]
            result_is_bot = False
            bank = await db.get_house_bank()
            pct = float(await db.get_setting("global_payout_percent", str(DEFAULT_GLOBAL_PAYOUT_PERCENT)))
            max_payout = bank["balance"] * pct / 100
            actual = min(win_amount, max_payout) if max_payout > 0 else win_amount
            actual = max(0, actual)
            # Мини-джекпот каждые N тиражей
            jp = await db.get_jackpot()
            if jp["draws_count"] > 0 and jp["draws_count"] % MINI_JACKPOT_EVERY == 0 and jp["pool"] > 0:
                pool = await db.jackpot_reset()
                actual += pool
                try: await bot.send_message(winner_id, f"🎰 <b>МИНИ-ДЖЕКПОТ!</b> +{pool:.0f} 🪙", parse_mode="HTML")
                except: pass
            if actual > 0:
                await db.change_balance(winner_id, actual, "win", f"Выигрыш {BRAND}")
                await db.house_pay(min(actual, win_amount))
            win_amount = actual
            await db.finish_draw(draw_id, winner_id, win_amount, False)
            await db.set_streak(winner_id, 0)
        else:
            await db.finish_draw(draw_id, None, 0, True)
    else:
        await db.finish_draw(draw_id, None, 0, True)

    drawn_str = " ".join(f"{n:02d}" for n in drawn)
    for t in scored:
        uid = t["user_id"]; view = format_all_tickets([t], drawn); matches = t["matches"]
        if not result_is_bot and uid == winner_id:
            text = (f"🏆 <b>ВЫ ВЫИГРАЛИ!</b>\n\n🎱 {drawn_str}\n\n{view}\n\n"
                    f"✅ Совпадений: <b>{matches}</b> (≥{need})\n💰 <b>{win_amount:.0f} 🪙</b>\n\nПоздравляем от {BRAND}!")
        else:
            near = matches >= need - 1 and matches < need
            if near:
                await db.set_near_win(uid, 1)
            text = (f"🏁 <b>Тираж завершён</b>\n\n🎱 {drawn_str}\n\n{view}\n\n"
                    f"Совпадений: <b>{matches}</b> (нужно ≥{need})\n")
            if near:
                text += f"💫 Почти! Следующий билет со скидкой 10%."
            else:
                text += "В этот раз без выигрыша."
        try: await bot.send_message(uid, text, parse_mode="HTML")
        except: pass

    if real_users > 0:
        from config import ADMIN_IDS
        msg = (f"🤖 Касса | {price} | банк={pot:.0f} | игр={real_users}" if result_is_bot
               else f"🏆 {winner_id} | +{win_amount:.0f} | банк={pot:.0f} | игр={real_users}")
        for aid in ADMIN_IDS:
            try: await bot.send_message(aid, msg)
            except: pass
