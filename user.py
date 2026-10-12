# user.py — полная версия с 30 функциями
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import (ADMIN_IDS, MIN_TOPUP, MIN_WITHDRAW, WITHDRAW_FEE_PERCENT, BRAND,
                    SALES_CLOSE_BEFORE, BOT_USERNAME, REFERRAL_BONUS, REFERRAL_BONUS_NEW,
                    FIRST_DEPOSIT_BONUS_PCT)
import db
from inline import main_menu_kb, rooms_kb, qty_kb, topup_kb, bonuses_kb, back_main_kb
from draw_service import buy_tickets, can_buy, format_all_tickets

router = Router()

class WithdrawStates(StatesGroup):
    waiting_amount = State(); waiting_card = State(); waiting_holder = State()
class TopupAdminStates(StatesGroup):
    waiting_message = State()
class PromoStates(StatesGroup):
    waiting_code = State()

@router.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    # Реферал: /start ref_123456
    ref = None
    if message.text and " " in message.text:
        part = message.text.split()[1]
        if part.startswith("ref_"):
            try: ref = int(part[4:])
            except: pass
            if ref == uid: ref = None
    existing = await db.get_user(uid)
    await db.create_user(uid, message.from_user.username, message.from_user.full_name, ref if not existing else None)
    await db.update_user_activity(uid, message.from_user.username, message.from_user.full_name)
    if ref and not existing:
        await db.change_balance(ref, REFERRAL_BONUS, "referral", f"Реферал {uid}")
        await db.change_balance(uid, REFERRAL_BONUS_NEW, "referral", "Бонус за регистрацию")
        try:
            await message.bot.send_message(ref, f"🎉 Новый реферал! +{REFERRAL_BONUS} 🪙")
        except: pass
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"🎟 Добро пожаловать в <b>{BRAND}</b>!\n"
        f"Живые тиражи, числа одно за другим, реальные выигрыши.\n\n"
        f"Кнопки ниже 👇",
        reply_markup=main_menu_kb(uid in ADMIN_IDS), parse_mode="HTML")

@router.message(F.text == "💰 Мой баланс")
async def show_balance(message: Message):
    u = await db.get_user(message.from_user.id)
    if not u: return
    jp = await db.get_jackpot()
    await message.answer(
        f"💰 <b>Баланс</b>\n🪙 <b>{u['balance']:.0f}</b> sazcoin\n\n"
        f"📈 Выиграно: {u['total_won']:.0f}\n📉 Потрачено: {u['total_lost']:.0f}\n"
        f"🔥 Серия: {u.get('streak') or 0}\n🎰 Джекпот пул: {jp['pool']:.0f} 🪙",
        parse_mode="HTML")

@router.message(F.text == "🎟 Купить билет")
async def show_rooms(message: Message):
    active = await db.get_user_active_draw_price(message.from_user.id)
    extra = f"\n⚠️ Уже есть билет на <b>{active} 🪙</b>" if active else ""
    await message.answer(f"🎟 <b>Номинал билета</b>{extra}", reply_markup=rooms_kb(), parse_mode="HTML")

@router.callback_query(F.data.startswith("price_"))
async def choose_price(cb: CallbackQuery):
    price = int(cb.data.split("_")[1])
    can, msg = await can_buy(cb.from_user.id, price, 1)
    if not can and "билет на" in msg:
        await cb.answer(msg, show_alert=True); return
    await cb.message.edit_text(f"Билет <b>{price} 🪙</b>\nСколько? (1–3)", reply_markup=qty_kb(price), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("qty_"))
async def choose_qty(cb: CallbackQuery):
    p = cb.data.split("_"); price, qty = int(p[1]), int(p[2])
    ok, msg = await buy_tickets(cb.from_user.id, price, qty)
    if ok: await cb.message.edit_text(msg, parse_mode="HTML")
    else: await cb.answer(msg, show_alert=True)
    await cb.answer()

@router.callback_query(F.data == "back_rooms")
async def back_rooms(cb: CallbackQuery):
    await cb.message.edit_text("🎟 Номинал:", reply_markup=rooms_kb()); await cb.answer()

@router.message(F.text == "📊 Активные тиражи")
async def active_draws(message: Message):
    draws = await db.get_active_draws()
    if not draws:
        await message.answer("Нет активных тиражей."); return
    now = time.time(); lines = [f"📊 <b>Активные тиражи {BRAND}</b>\n"]
    for d in draws:
        if d["status"] == "registration":
            left = max(0, int(d["reg_end"]-now))
            sales = max(0, int(d["reg_end"]-SALES_CLOSE_BEFORE-now))
            phase = f"📝 Набор {left}с" + (" 🔒" if sales<=0 else f" · продажа {sales}с")
        else:
            left = max(0, int(d["draw_end"]-now)); step = d.get("draw_step") or 0
            phase = f"🎱 Розыгрыш {step}/5 · {left}с"
        lines.append(f"━━━━━━━━━━\n💰 <b>{d['room_price']} 🪙</b> | Касса {d['total_pot']:.0f} | Билетов {d['participants_count']}\n{phase}")
    lines.append(f"\n🔗 Пригласи друга: t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}")
    await message.answer("\n".join(lines), parse_mode="HTML")

@router.message(F.text == "📜 История")
async def history(message: Message):
    tickets = await db.get_user_tickets_history(message.from_user.id, 15)
    if not tickets: await message.answer("История пуста."); return
    lines = ["📜 <b>История</b>\n"]
    for t in tickets:
        nums = " ".join(f"{n:02d}" for n in t["numbers"])
        drawn = " ".join(f"{n:02d}" for n in (t.get("drawn_numbers") or [])) or "—"
        mark = "🏆" if t.get("is_winner") else ("⏳" if t.get("draw_status") in ("registration","drawing") else "—")
        win = t.get("win_amount") or 0
        lines.append(f"{mark} {t['room_price']}🪙 | {nums}\n   →{drawn} | совп:{t.get('matches') or 0}" + (f" | +{int(win)}" if win else ""))
    await message.answer("\n".join(lines[:25]), parse_mode="HTML")

@router.message(F.text == "🎁 Бонусы")
async def bonuses(message: Message):
    await message.answer("🎁 <b>Бонусы</b>", reply_markup=bonuses_kb(), parse_mode="HTML")

@router.callback_query(F.data == "daily_bonus")
async def daily_bonus(cb: CallbackQuery):
    ok, msg = await db.claim_daily(cb.from_user.id)
    await cb.answer(msg, show_alert=True)

@router.callback_query(F.data == "enter_promo")
async def enter_promo(cb: CallbackQuery, state: FSMContext):
    await state.set_state(PromoStates.waiting_code)
    await cb.message.edit_text("Введите промокод:"); await cb.answer()

@router.message(PromoStates.waiting_code)
async def process_promo(message: Message, state: FSMContext):
    await state.clear()
    ok, msg = await db.use_promo(message.from_user.id, message.text)
    await message.answer(msg, reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS))

@router.message(F.text == "🏆 Топ игроков")
async def leaderboard(message: Message):
    top = await db.get_leaderboard(10)
    if not top: await message.answer("Пока пусто."); return
    lines = [f"🏆 <b>Топ {BRAND}</b>\n"]
    medals = ["🥇","🥈","🥉"]
    for i, u in enumerate(top):
        m = medals[i] if i < 3 else f"{i+1}."
        name = u.get("username") or u.get("full_name") or str(u["user_id"])
        lines.append(f"{m} {name} — <b>{u['total_won']:.0f}</b> 🪙")
    await message.answer("\n".join(lines), parse_mode="HTML")

@router.message(F.text == "🔗 Реферал")
async def referral(message: Message):
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"
    await message.answer(
        f"🔗 <b>Ваша ссылка</b>\n<code>{link}</code>\n\n"
        f"Друг получит +{REFERRAL_BONUS_NEW} 🪙\nВы получите +{REFERRAL_BONUS} 🪙",
        parse_mode="HTML")

@router.message(F.text == "➕ Пополнить")
async def topup_menu(message: Message):
    await message.answer(f"➕ Мин. {MIN_TOPUP} 🪙", reply_markup=topup_kb())

@router.callback_query(F.data == "topup_stars")
async def topup_stars(cb: CallbackQuery, bot: Bot):
    await bot.send_invoice(cb.from_user.id, title=f"{BRAND}", description="1000 sazcoin",
        payload="topup_1000", provider_token="", currency="XTR",
        prices=[LabeledPrice(label="1000", amount=10)])
    await cb.answer()

@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@router.message(F.successful_payment)
async def ok_pay(message: Message):
    amount = 1000
    bonus = int(amount * FIRST_DEPOSIT_BONUS_PCT / 100)
    u = await db.get_user(message.from_user.id)
    first = u and u["total_deposited"] == 0
    await db.change_balance(message.from_user.id, amount, "topup", "Stars")
    extra = ""
    if first:
        await db.change_balance(message.from_user.id, bonus, "bonus", "Первый депозит")
        extra = f"\n🎁 Бонус первого пополнения +{bonus} 🪙!"
    await message.answer(f"✅ +{amount} 🪙{extra}", parse_mode="HTML")

@router.callback_query(F.data == "topup_admin")
async def topup_admin(cb: CallbackQuery, state: FSMContext):
    await state.set_state(TopupAdminStates.waiting_message)
    await cb.message.edit_text("Напишите админу сумму:"); await cb.answer()

@router.message(TopupAdminStates.waiting_message)
async def topup_admin_msg(message: Message, state: FSMContext, bot: Bot):
    await state.clear(); uid = message.from_user.id
    text = (f"📩 <b>Пополнение</b>\n🆔 <code>{uid}</code> @{message.from_user.username or '—'}\n"
            f"{message.from_user.full_name}\n💬 {message.text}\n\n<code>/addbal {uid} СУММА</code>")
    for a in ADMIN_IDS:
        try: await bot.send_message(a, text, parse_mode="HTML")
        except: pass
    await message.answer("✅ Отправлено", reply_markup=main_menu_kb(uid in ADMIN_IDS))

@router.message(F.text == "💳 Вывод")
async def withdraw_start(message: Message, state: FSMContext):
    u = await db.get_user(message.from_user.id)
    if not u: return
    av = u["total_won"] - u["total_withdrawn"]
    if av < MIN_WITHDRAW:
        await message.answer(f"❌ Мин {MIN_WITHDRAW}. Доступно {max(0,av):.0f}"); return
    await state.set_state(WithdrawStates.waiting_amount)
    await message.answer(f"💳 Доступно <b>{av:.0f}</b>\nКомиссия {WITHDRAW_FEE_PERCENT}%\nСумма:", parse_mode="HTML")

@router.message(WithdrawStates.waiting_amount)
async def w_amount(message: Message, state: FSMContext):
    try: amount = float(message.text.replace(",","."))
    except: await message.answer("Число"); return
    u = await db.get_user(message.from_user.id)
    av = u["total_won"] - u["total_withdrawn"]
    if amount < MIN_WITHDRAW or amount > av or amount > u["balance"]:
        await message.answer("Неверная сумма"); return
    fee = round(amount * WITHDRAW_FEE_PERCENT/100, 2)
    await state.update_data(amount=amount, fee=fee, net=amount-fee)
    await state.set_state(WithdrawStates.waiting_card)
    await message.answer(f"К выдаче <b>{amount-fee:.0f}</b>\nКарта 16 цифр:", parse_mode="HTML")

@router.message(WithdrawStates.waiting_card)
async def w_card(message: Message, state: FSMContext):
    card = message.text.strip().replace(" ","")
    if not card.isdigit() or len(card)<16: await message.answer("16 цифр"); return
    await state.update_data(card=card); await state.set_state(WithdrawStates.waiting_holder)
    await message.answer("ФИО:")

@router.message(WithdrawStates.waiting_holder)
async def w_holder(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data(); await state.clear()
    ok = await db.change_balance(message.from_user.id, -data["amount"], "withdraw", "Вывод")
    if not ok: await message.answer("Ошибка"); return
    rid = await db.create_withdraw_request(message.from_user.id, data["amount"], data["fee"], data["net"], data["card"], message.text.strip())
    text = (f"💸 Вывод #{rid}\n<code>{message.from_user.id}</code>\n{data['amount']:.0f}→{data['net']:.0f}\n"
            f"<code>{data['card']}</code> {message.text}\n/approve_{rid} /reject_{rid}")
    for a in ADMIN_IDS:
        try: await bot.send_message(a, text, parse_mode="HTML")
        except: pass
    await message.answer(f"✅ Заявка. К переводу {data['net']:.0f} 🪙", reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS))

@router.message(F.text == "📖 Правила")
async def rules(message: Message):
    await message.answer(
        f"📖 <b>Правила {BRAND}</b>\n\n"
        f"• 5 мин набор, за 30 сек продажа стоп, 1 мин розыгрыш\n"
        f"• 1–3 билета одного номинала\n"
        f"• Совпадения: ≤500→4, ≤2500→3, >2500→5 чисел\n"
        f"• <2 игроков → касса\n"
        f"• Вывод с выигрышей, комиссия {WITHDRAW_FEE_PERCENT}%\n"
        f"• Ежедневный бонус, рефералы, промокоды, джекпот",
        parse_mode="HTML")

@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery):
    try: await cb.message.delete()
    except: pass
    await cb.message.answer("Меню:", reply_markup=main_menu_kb(cb.from_user.id in ADMIN_IDS))
    await cb.answer()
