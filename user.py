# user.py
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, MIN_TOPUP, MIN_WITHDRAW, WITHDRAW_FEE_PERCENT, BRAND, SALES_CLOSE_BEFORE
import db
from inline import main_menu_kb, rooms_kb, qty_kb, topup_kb, back_main_kb
from draw_service import buy_tickets, can_buy, format_all_tickets, min_matches_for_price

router = Router()


class WithdrawStates(StatesGroup):
    waiting_amount = State()
    waiting_card = State()
    waiting_holder = State()


class TopupAdminStates(StatesGroup):
    waiting_message = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    await db.create_user(uid, message.from_user.username, message.from_user.full_name)
    await db.update_user_activity(uid, message.from_user.username, message.from_user.full_name)
    text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"🎟 Добро пожаловать в <b>{BRAND}</b>!\n\n"
        f"Покупайте билеты, следите за выпадением чисел в прямом эфире и выигрывайте!\n\n"
        f"Используйте кнопки ниже 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb(uid in ADMIN_IDS), parse_mode="HTML")


@router.message(F.text == "💰 Мой баланс")
async def show_balance(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Ошибка. /start")
        return
    text = (
        f"💰 <b>Ваш баланс</b>\n\n"
        f"🪙 Текущий: <b>{user['balance']:.0f} sazcoin</b>\n"
        f"📈 Выиграно: {user['total_won']:.0f} 🪙\n"
        f"📉 Потрачено: {user['total_lost']:.0f} 🪙\n"
        f"⬇️ Выведено: {user['total_withdrawn']:.0f} 🪙\n"
        f"⬆️ Пополнено: {user['total_deposited']:.0f} 🪙"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🎟 Купить билет")
async def show_rooms(message: Message):
    active = await db.get_user_active_draw_price(message.from_user.id)
    extra = f"\n\n⚠️ У вас уже есть билет на тираж <b>{active} 🪙</b>. Можно докупить только туда." if active else ""
    await message.answer(
        f"🎟 <b>Выберите номинал билета</b>{extra}\n\n"
        f"После выбора укажите количество (1–3).",
        reply_markup=rooms_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("price_"))
async def choose_price(callback: CallbackQuery):
    price = int(callback.data.split("_")[1])
    can, msg = await can_buy(callback.from_user.id, price, 1)
    if not can and "уже есть билет" in msg:
        await callback.answer(msg, show_alert=True)
        return
    await callback.message.edit_text(
        f"Билет <b>{price} 🪙</b>\n\nСколько билетов купить? (макс. 3)",
        reply_markup=qty_kb(price), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qty_"))
async def choose_qty(callback: CallbackQuery):
    parts = callback.data.split("_")
    price, qty = int(parts[1]), int(parts[2])
    success, msg = await buy_tickets(callback.from_user.id, price, qty)
    if success:
        await callback.message.edit_text(msg, parse_mode="HTML")
    else:
        await callback.answer(msg, show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "back_rooms")
async def back_rooms(callback: CallbackQuery):
    await callback.message.edit_text("🎟 <b>Выберите номинал</b>", reply_markup=rooms_kb(), parse_mode="HTML")
    await callback.answer()


@router.message(F.text == "📊 Активные тиражи")
async def active_draws(message: Message):
    draws = await db.get_active_draws()
    if not draws:
        await message.answer("Сейчас нет активных тиражей. Скоро появятся!")
        return
    now = time.time()
    lines = [f"📊 <b>Активные тиражи {BRAND}</b>\n"]
    for d in draws:
        price = d["room_price"]
        pot = d["total_pot"]
        cnt = d["participants_count"]
        status = d["status"]
        if status == "registration":
            left = max(0, int(d["reg_end"] - now))
            sales_left = max(0, int(d["reg_end"] - SALES_CLOSE_BEFORE - now))
            phase = f"📝 Набор · осталось {left} сек"
            if sales_left <= 0:
                phase += " · 🔒 продажа закрыта"
            else:
                phase += f" · продажа ещё {sales_left} сек"
        else:
            left = max(0, int(d["draw_end"] - now))
            step = d.get("draw_step") or 0
            phase = f"🎱 Розыгрыш · число {step}/5 · {left} сек"
        lines.append(
            f"━━━━━━━━━━━━━━\n"
            f"💰 <b>{price} 🪙</b> | Касса: {pot:.0f} | Билетов: {cnt}\n"
            f"{phase}"
        )
    lines.append("\n🎟 Чтобы участвовать — «Купить билет»")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📜 История")
async def history(message: Message):
    tickets = await db.get_user_tickets_history(message.from_user.id, 15)
    if not tickets:
        await message.answer("История пуста. Сыграйте первый тираж!")
        return
    lines = [f"📜 <b>Ваша история</b>\n"]
    for t in tickets:
        nums = " ".join(f"{n:02d}" for n in t["numbers"])
        drawn = t.get("drawn_numbers") or []
        drawn_s = " ".join(f"{n:02d}" for n in drawn) if drawn else "—"
        status = t.get("draw_status") or "?"
        win = t.get("win_amount") or 0
        matches = t.get("matches") or 0
        mark = "🏆" if t.get("is_winner") else ("⏳" if status in ("registration", "drawing") else "—")
        lines.append(
            f"{mark} {t['room_price']} 🪙 | {nums}\n"
            f"   Выпало: {drawn_s} | Совп: {matches} | "
            f"{'Выигрыш +'+str(int(win)) if win else status}"
        )
    await message.answer("\n".join(lines[:30]), parse_mode="HTML")


@router.message(F.text == "➕ Пополнить баланс")
async def topup_menu(message: Message):
    await message.answer(
        f"➕ <b>Пополнение</b>\n\nМинимум: <b>{MIN_TOPUP} 🪙</b>",
        reply_markup=topup_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data == "topup_stars")
async def topup_stars(callback: CallbackQuery, bot: Bot):
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Пополнение {BRAND}",
        description="1000 sazcoin",
        payload="topup_1000",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="1000 sazcoin", amount=10)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    await db.change_balance(message.from_user.id, 1000, "topup", "Telegram Stars")
    await message.answer("✅ <b>1000 🪙</b> зачислено!", parse_mode="HTML")


@router.callback_query(F.data == "topup_admin")
async def topup_admin(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupAdminStates.waiting_message)
    await callback.message.edit_text(
        "Напишите сообщение админу.\nПример: <i>Пополните 5000 sazcoin</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(TopupAdminStates.waiting_message)
async def process_topup_admin(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    uid = message.from_user.id
    text = (
        f"📩 <b>Заявка на пополнение</b>\n\n"
        f"👤 {message.from_user.full_name}\n"
        f"🆔 <b>User ID: <code>{uid}</code></b>\n"
        f"🔗 @{message.from_user.username or '—'}\n\n"
        f"💬 {message.text}\n\n"
        f"➡️ <code>/addbal {uid} СУММА</code>"
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, parse_mode="HTML")
        except:
            pass
    await message.answer("✅ Отправлено админу.", reply_markup=main_menu_kb(uid in ADMIN_IDS))


@router.message(F.text == "💳 Вывод")
async def withdraw_start(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    available = user["total_won"] - user["total_withdrawn"]
    if available < MIN_WITHDRAW:
        await message.answer(f"❌ Мало выигрышей. Мин: {MIN_WITHDRAW} 🪙. Доступно: {max(0,available):.0f}")
        return
    await state.set_state(WithdrawStates.waiting_amount)
    await message.answer(
        f"💳 <b>Вывод</b>\nДоступно: <b>{available:.0f}</b>\nМин: {MIN_WITHDRAW}\nКомиссия: {WITHDRAW_FEE_PERCENT}%\n\nВведите сумму:",
        parse_mode="HTML"
    )


@router.message(WithdrawStates.waiting_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").strip())
    except:
        await message.answer("Число, пожалуйста.")
        return
    user = await db.get_user(message.from_user.id)
    available = user["total_won"] - user["total_withdrawn"]
    if amount < MIN_WITHDRAW or amount > available or amount > user["balance"]:
        await message.answer("Некорректная сумма.")
        return
    fee = round(amount * WITHDRAW_FEE_PERCENT / 100, 2)
    await state.update_data(amount=amount, fee=fee, net=amount - fee)
    await state.set_state(WithdrawStates.waiting_card)
    await message.answer(f"К получению: <b>{amount-fee:.0f} 🪙</b>\nНомер карты (16 цифр):", parse_mode="HTML")


@router.message(WithdrawStates.waiting_card)
async def withdraw_card(message: Message, state: FSMContext):
    card = message.text.strip().replace(" ", "")
    if not card.isdigit() or len(card) < 16:
        await message.answer("16 цифр карты.")
        return
    await state.update_data(card=card)
    await state.set_state(WithdrawStates.waiting_holder)
    await message.answer("ФИО владельца карты:")


@router.message(WithdrawStates.waiting_holder)
async def withdraw_holder(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    holder = message.text.strip()
    ok = await db.change_balance(message.from_user.id, -data["amount"], "withdraw", "Вывод")
    if not ok:
        await message.answer("Ошибка баланса.")
        return
    req_id = await db.create_withdraw_request(
        message.from_user.id, data["amount"], data["fee"], data["net"], data["card"], holder
    )
    text = (
        f"💸 <b>Вывод #{req_id}</b>\n"
        f"🆔 <code>{message.from_user.id}</code> @{message.from_user.username or '—'}\n"
        f"Сумма: {data['amount']:.0f} → {data['net']:.0f}\n"
        f"Карта: <code>{data['card']}</code>\n{holder}\n"
        f"/approve_{req_id}  /reject_{req_id}"
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, parse_mode="HTML")
        except:
            pass
    await message.answer(f"✅ Заявка принята. К переводу: <b>{data['net']:.0f} 🪙</b>", parse_mode="HTML",
                         reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS))


@router.message(F.text == "📖 Правила")
async def rules(message: Message):
    text = (
        f"📖 <b>Правила {BRAND}</b>\n\n"
        f"1️⃣ Пополните баланс (мин. {MIN_TOPUP} 🪙)\n"
        f"2️⃣ Купите 1–3 билета одного номинала\n"
        f"3️⃣ 5 мин — набор игроков, за 30 сек продажа закрывается\n"
        f"4️⃣ 1 мин — числа выпадают одно за другим\n\n"
        f"<b>Для выигрыша нужно совпадений:</b>\n"
        f"• до 500 🪙 → минимум <b>4</b> числа\n"
        f"• до 2500 🪙 → минимум <b>3</b> числа\n"
        f"• выше 2500 🪙 → все <b>5</b> чисел\n\n"
        f"Меньше 2 игроков — побеждает касса.\n"
        f"Вывод только с выигрышей, комиссия {WITHDRAW_FEE_PERCENT}%."
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🆘 Поддержка")
async def support(message: Message):
    await message.answer("По вопросам — напишите администратору.")


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb(callback.from_user.id in ADMIN_IDS))
    await callback.answer()
