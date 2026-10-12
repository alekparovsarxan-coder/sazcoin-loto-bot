# user.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, MIN_TOPUP, MIN_WITHDRAW, WITHDRAW_FEE_PERCENT, DAILY_TICKET
import db
from inline import main_menu_kb, rooms_kb, confirm_buy_kb, topup_kb, back_main_kb
from draw_service import buy_ticket, can_buy_ticket

router = Router()


class WithdrawStates(StatesGroup):
    waiting_amount = State()
    waiting_card = State()
    waiting_holder = State()


class TopupAdminStates(StatesGroup):
    waiting_message = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    await db.create_user(user_id, username=message.from_user.username, full_name=message.from_user.full_name)
    await db.update_user_activity(user_id, message.from_user.username, message.from_user.full_name)

    is_admin = user_id in ADMIN_IDS
    text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"🎟 Добро пожаловать в <b>SazLoto</b>!\n\n"
        f"Здесь вы можете участвовать в тиражах, выигрывать и выводить средства.\n\n"
        f"💰 Пополните баланс, купите билет и попробуйте удачу!\n\n"
        f"Используйте кнопки ниже 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb(is_admin), parse_mode="HTML")


@router.message(F.text == "💰 Мой баланс")
async def show_balance(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Ошибка. Напишите /start")
        return
    text = (
        f"💰 <b>Ваш баланс</b>\n\n"
        f"🪙 Текущий баланс: <b>{user['balance']:.0f} sazcoin</b>\n\n"
        f"📈 Всего выиграно: {user['total_won']:.0f} 🪙\n"
        f"📉 Всего проиграно: {user['total_lost']:.0f} 🪙\n"
        f"⬇️ Всего выведено: {user['total_withdrawn']:.0f} 🪙\n"
        f"⬆️ Всего пополнено: {user['total_deposited']:.0f} 🪙"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🎟 Купить билет")
async def show_rooms(message: Message):
    text = (
        "🎟 <b>Выберите билет</b>\n\n"
        "• 1 минута — небольшие суммы\n"
        "• 5 минут — средние\n"
        "• 10 минут — высокие\n"
        "• Ежедневный 20000 — большой тираж (каждый день в 21:00)\n\n"
        "Максимум <b>3 билета</b> в одном тираже."
    )
    await message.answer(text, reply_markup=rooms_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("buy_"))
async def process_buy_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка")
        return
    try:
        price = int(parts[1])
        interval = parts[2]
        interval_sec = 86400 if interval == "daily" else int(interval)
    except:
        await callback.answer("Ошибка")
        return

    can, msg = await can_buy_ticket(callback.from_user.id, price, interval_sec)
    if not can:
        await callback.answer(msg, show_alert=True)
        return

    text = (
        f"🎟 <b>Подтверждение покупки</b>\n\n"
        f"Цена: <b>{price} 🪙</b>\n"
        f"Тираж: {'Ежедневный' if interval == 'daily' else f'{interval_sec // 60} мин'}\n\n"
        f"Подтверждаете?"
    )
    await callback.message.edit_text(text, reply_markup=confirm_buy_kb(price, interval_sec), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_buy(callback: CallbackQuery):
    parts = callback.data.split("_")
    price = int(parts[2])
    interval_sec = int(parts[3])
    success, msg = await buy_ticket(callback.from_user.id, price, interval_sec)
    if success:
        await callback.message.edit_text(msg, parse_mode="HTML")
    else:
        await callback.answer(msg, show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "back_rooms")
async def back_to_rooms(callback: CallbackQuery):
    await callback.message.edit_text("🎟 <b>Выберите билет</b>", reply_markup=rooms_kb(), parse_mode="HTML")
    await callback.answer()


@router.message(F.text == "➕ Пополнить баланс")
async def topup_menu(message: Message):
    text = (
        f"➕ <b>Пополнение баланса</b>\n\n"
        f"Минимальная сумма: <b>{MIN_TOPUP} 🪙</b>\n\n"
        f"Выберите способ:"
    )
    await message.answer(text, reply_markup=topup_kb(), parse_mode="HTML")


@router.callback_query(F.data == "topup_stars")
async def topup_stars(callback: CallbackQuery, bot: Bot):
    prices = [LabeledPrice(label="1000 sazcoin", amount=10)]
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Пополнение SazLoto",
        description="1000 sazcoin будут добавлены на ваш баланс",
        payload="topup_1000",
        provider_token="",
        currency="XTR",
        prices=prices,
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    amount = 1000
    await db.change_balance(message.from_user.id, amount, "topup", "Пополнение через Telegram Stars")
    await message.answer(f"✅ <b>{amount} 🪙</b> добавлено на ваш баланс!", parse_mode="HTML")


@router.callback_query(F.data == "topup_admin")
async def topup_admin(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupAdminStates.waiting_message)
    await callback.message.edit_text(
        "👤 Напишите сообщение админу.\n\n"
        "Пример: <i>Здравствуйте, пополните 5000 sazcoin, пожалуйста.</i>\n\n"
        "Ваше сообщение будет отправлено админу.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(TopupAdminStates.waiting_message)
async def process_topup_admin_msg(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    uid = message.from_user.id
    uname = message.from_user.username or "—"
    text = (
        f"📩 <b>Заявка на пополнение баланса</b>\n\n"
        f"👤 Имя: {message.from_user.full_name}\n"
        f"🆔 <b>User ID: <code>{uid}</code></b>\n"
        f"🔗 @{uname}\n\n"
        f"💬 Сообщение:\n{message.text}\n\n"
        f"➡️ Чтобы пополнить, используйте:\n"
        f"<code>/addbal {uid} СУММА</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except:
            pass
    await message.answer(
        "✅ Ваше сообщение отправлено админу. Ожидайте ответа.",
        reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS)
    )


@router.message(F.text == "💳 Вывод")
async def withdraw_start(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    available = user["total_won"] - user["total_withdrawn"]
    if available < MIN_WITHDRAW:
        await message.answer(
            f"❌ Недостаточно выигрышей для вывода.\n\n"
            f"Минимум: {MIN_WITHDRAW} 🪙\n"
            f"Доступно к выводу: {max(0, available):.0f} 🪙"
        )
        return
    await state.set_state(WithdrawStates.waiting_amount)
    await message.answer(
        f"💳 <b>Вывод средств</b>\n\n"
        f"Доступно: <b>{available:.0f} 🪙</b>\n"
        f"Минимум: {MIN_WITHDRAW} 🪙\n"
        f"Комиссия: {WITHDRAW_FEE_PERCENT}%\n\n"
        f"Введите сумму для вывода:",
        parse_mode="HTML"
    )


@router.message(WithdrawStates.waiting_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").strip())
    except:
        await message.answer("Введите корректное число.")
        return
    user = await db.get_user(message.from_user.id)
    available = user["total_won"] - user["total_withdrawn"]
    if amount < MIN_WITHDRAW:
        await message.answer(f"Минимальная сумма вывода — {MIN_WITHDRAW} 🪙")
        return
    if amount > available:
        await message.answer(f"Максимум можно вывести {available:.0f} 🪙")
        return
    if amount > user["balance"]:
        await message.answer("Недостаточно средств на балансе.")
        return
    fee = round(amount * WITHDRAW_FEE_PERCENT / 100, 2)
    net = amount - fee
    await state.update_data(amount=amount, fee=fee, net=net)
    await state.set_state(WithdrawStates.waiting_card)
    await message.answer(
        f"Сумма: <b>{amount:.0f} 🪙</b>\n"
        f"Комиссия ({WITHDRAW_FEE_PERCENT}%): <b>{fee:.0f} 🪙</b>\n"
        f"К получению: <b>{net:.0f} 🪙</b>\n\n"
        f"Введите номер карты (16 цифр):",
        parse_mode="HTML"
    )


@router.message(WithdrawStates.waiting_card)
async def withdraw_card(message: Message, state: FSMContext):
    card = message.text.strip().replace(" ", "")
    if not card.isdigit() or len(card) < 16:
        await message.answer("Введите корректный номер карты (16 цифр).")
        return
    await state.update_data(card=card)
    await state.set_state(WithdrawStates.waiting_holder)
    await message.answer("Введите ФИО владельца карты:")


@router.message(WithdrawStates.waiting_holder)
async def withdraw_holder(message: Message, state: FSMContext, bot: Bot):
    holder = message.text.strip()
    data = await state.get_data()
    await state.clear()
    ok = await db.change_balance(message.from_user.id, -data["amount"], "withdraw", f"Заявка на вывод (нетто: {data['net']})")
    if not ok:
        await message.answer("Ошибка. Проверьте баланс.")
        return
    req_id = await db.create_withdraw_request(
        user_id=message.from_user.id, amount=data["amount"], fee=data["fee"],
        net_amount=data["net"], card_number=data["card"], card_holder=holder
    )
    text = (
        f"💸 <b>Новая заявка на вывод #{req_id}</b>\n\n"
        f"👤 {message.from_user.full_name} (@{message.from_user.username or '—'})\n"
        f"🆔 User ID: <code>{message.from_user.id}</code>\n\n"
        f"Сумма: <b>{data['amount']:.0f} 🪙</b>\n"
        f"Комиссия: {data['fee']:.0f} 🪙\n"
        f"К переводу: <b>{data['net']:.0f} 🪙</b>\n\n"
        f"Карта: <code>{data['card']}</code>\n"
        f"Владелец: {holder}\n\n"
        f"/approve_{req_id}  — одобрить\n"
        f"/reject_{req_id}  — отклонить"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except:
            pass
    await message.answer(
        f"✅ Заявка на вывод принята!\n\nВам будет переведено <b>{data['net']:.0f} 🪙</b>.\nАдмин скоро обработает заявку.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS)
    )


@router.message(F.text == "📖 Правила")
async def rules(message: Message):
    text = (
        "📖 <b>Правила игры</b>\n\n"
        "1️⃣ Пополните баланс (минимум 1000 🪙)\n"
        "2️⃣ Купите билет (макс. 3 в одном тираже)\n"
        "3️⃣ После окончания тиража определяется победитель\n\n"
        "<b>Правила выигрыша:</b>\n"
        "• До 500 → 60% кассы (мин. 3 реальных игрока)\n"
        "• 501–2500 → 50% кассы (мин. 5 реальных игроков)\n"
        "• 2501+ → 40% кассы (мин. 5 реальных игроков)\n\n"
        "Если игроков меньше минимума — побеждает бот.\n\n"
        "Вывод только с выигранных средств. Комиссия 10%."
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🆘 Поддержка")
async def support(message: Message):
    await message.answer("По вопросам пишите администратору.")


@router.message(F.text == "📊 Активные тиражи")
async def active_draws(message: Message):
    await message.answer("Функция активных тиражей скоро будет доступна. Пока покупайте билеты через «Купить билет».")


@router.message(F.text == "📜 История")
async def history(message: Message):
    await message.answer("История операций скоро будет доступна.")


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb(is_admin))
    await callback.answer()
