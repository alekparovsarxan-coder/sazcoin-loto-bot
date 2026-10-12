# user.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, MIN_TOPUP, MIN_WITHDRAW, WITHDRAW_FEE_PERCENT, CURRENCY_SYMBOL, DAILY_TICKET
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


# ====================== START ======================

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    await db.create_user(
        user_id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )
    await db.update_user_activity(user_id, message.from_user.username, message.from_user.full_name)

    is_admin = user_id in ADMIN_IDS
    text = (
        f"👋 Salam, <b>{message.from_user.first_name}</b>!\n\n"
        f"🎟 <b>SazCoin Loto</b>-ya xoş gəlmisiniz!\n\n"
        f"Burada siz sazcoin ilə tirajlarda iştirak edə, uduş qazana və çıxara bilərsiniz.\n\n"
        f"💰 Balansınızı artırın, bilet alın və şansınızı sınayın!\n\n"
        f"Aşağıdakı düymələrdən istifadə edin 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb(is_admin), parse_mode="HTML")


# ====================== BALANS ======================

@router.message(F.text == "💰 Balansım")
async def show_balance(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Xəta baş verdi. /start yazın.")
        return

    text = (
        f"💰 <b>Sizin balansınız</b>\n\n"
        f"🪙 Cari balans: <b>{user['balance']:.0f} sazcoin</b>\n\n"
        f"📈 Ümumi uduş: {user['total_won']:.0f} 🪙\n"
        f"📉 Ümumi uduzma: {user['total_lost']:.0f} 🪙\n"
        f"⬇️ Ümumi çıxarış: {user['total_withdrawn']:.0f} 🪙\n"
        f"⬆️ Ümumi artırma: {user['total_deposited']:.0f} 🪙"
    )
    await message.answer(text, parse_mode="HTML")


# ====================== BİLET AL ======================

@router.message(F.text == "🎟 Bilet Al")
async def show_rooms(message: Message):
    text = (
        "🎟 <b>Bilet seçin</b>\n\n"
        "• 1 dəqiqəlik tirajlar — kiçik məbləğlər\n"
        "• 5 dəqiqəlik — orta\n"
        "• 10 dəqiqəlik — yüksək\n"
        "• Gündəlik 20000 — böyük tiraj (hər gün 21:00)\n\n"
        "Bir tirajda maksimum <b>3 bilet</b> ala bilərsiniz."
    )
    await message.answer(text, reply_markup=rooms_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("buy_"))
async def process_buy_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Xəta")
        return

    try:
        price = int(parts[1])
        interval = parts[2]
        if interval == "daily":
            interval_sec = 86400  # gündəlik üçün xüsusi
        else:
            interval_sec = int(interval)
    except:
        await callback.answer("Xəta")
        return

    can, msg = await can_buy_ticket(callback.from_user.id, price, interval_sec if interval != "daily" else 86400)
    if not can:
        await callback.answer(msg, show_alert=True)
        return

    text = (
        f"🎟 <b>Bilet təsdiqi</b>\n\n"
        f"Qiymət: <b>{price} 🪙</b>\n"
        f"Tiraj: {'Gündəlik' if interval == 'daily' else f'{interval_sec // 60} dəqiqə'}\n\n"
        f"Təsdiqləyirsiniz?"
    )
    await callback.message.edit_text(text, reply_markup=confirm_buy_kb(price, interval_sec if interval != "daily" else 86400), parse_mode="HTML")
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
    await callback.message.edit_text(
        "🎟 <b>Bilet seçin</b>",
        reply_markup=rooms_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ====================== BALANS ARTIR ======================

@router.message(F.text == "➕ Balans Artır")
async def topup_menu(message: Message):
    text = (
        f"➕ <b>Balans artırma</b>\n\n"
        f"Minimum məbləğ: <b>{MIN_TOPUP} 🪙</b>\n\n"
        f"İstədiyiniz üsulu seçin:"
    )
    await message.answer(text, reply_markup=topup_kb(), parse_mode="HTML")


@router.callback_query(F.data == "topup_stars")
async def topup_stars(callback: CallbackQuery, bot: Bot):
    # Telegram Stars ilə ödəniş (XTR)
    # 1 Star ≈ bir qədər, amma sadəlik üçün 1 Star = 100 sazcoin kimi qoyuruq (istəyə görə dəyişin)
    prices = [LabeledPrice(label="1000 sazcoin", amount=10)]  # 10 Stars = 1000 sazcoin nümunə
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="SazCoin Balans Artırma",
        description="1000 sazcoin balansınıza əlavə olunacaq",
        payload="topup_1000",
        provider_token="",  # Stars üçün boş
        currency="XTR",
        prices=prices,
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    # Sadə nümunə: 10 Stars = 1000 sazcoin
    amount = 1000
    await db.change_balance(message.from_user.id, amount, "topup", "Telegram Stars ilə artırma")
    await message.answer(f"✅ <b>{amount} 🪙</b> balansınıza əlavə olundu!", parse_mode="HTML")


@router.callback_query(F.data == "topup_admin")
async def topup_admin(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupAdminStates.waiting_message)
    await callback.message.edit_text(
        "👤 Adminə mesaj yazın.\n\n"
        "Nümunə: <i>Salam, 5000 sazcoin artırın, zəhmət olmasa.</i>\n\n"
        "Mesajınız adminə göndəriləcək.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(TopupAdminStates.waiting_message)
async def process_topup_admin_msg(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    text = (
        f"📩 <b>Yeni balans artırma tələbi</b>\n\n"
        f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
        f"ID: <code>{message.from_user.id}</code>\n\n"
        f"Mesaj:\n{message.text}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except:
            pass
    await message.answer("✅ Mesajınız adminə göndərildi. Tezliklə cavab verəcəklər.", reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS))


# ====================== ÇIXARIŞ ======================

@router.message(F.text == "💳 Çıxarış")
async def withdraw_start(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        return

    available = user["total_won"] - user["total_withdrawn"]  # yalnız uduşdan çıxara bilər
    if available < MIN_WITHDRAW:
        await message.answer(
            f"❌ Çıxarış üçün kifayət qədər uduşunuz yoxdur.\n\n"
            f"Minimum çıxarış: {MIN_WITHDRAW} 🪙\n"
            f"Sizin çıxara biləcəyiniz: {max(0, available):.0f} 🪙"
        )
        return

    await state.set_state(WithdrawStates.waiting_amount)
    await message.answer(
        f"💳 <b>Çıxarış</b>\n\n"
        f"Çıxara biləcəyiniz məbləğ: <b>{available:.0f} 🪙</b>\n"
        f"Minimum: {MIN_WITHDRAW} 🪙\n"
        f"Xidmət haqqı: {WITHDRAW_FEE_PERCENT}%\n\n"
        f"Çıxarmaq istədiyiniz məbləği yazın:",
        parse_mode="HTML"
    )


@router.message(WithdrawStates.waiting_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").strip())
    except:
        await message.answer("Düzgün rəqəm yazın.")
        return

    user = await db.get_user(message.from_user.id)
    available = user["total_won"] - user["total_withdrawn"]

    if amount < MIN_WITHDRAW:
        await message.answer(f"Minimum çıxarış {MIN_WITHDRAW} 🪙-dir.")
        return
    if amount > available:
        await message.answer(f"Siz maksimum {available:.0f} 🪙 çıxara bilərsiniz.")
        return
    if amount > user["balance"]:
        await message.answer("Balansınızda kifayət qədər vəsait yoxdur.")
        return

    fee = round(amount * WITHDRAW_FEE_PERCENT / 100, 2)
    net = amount - fee

    await state.update_data(amount=amount, fee=fee, net=net)
    await state.set_state(WithdrawStates.waiting_card)
    await message.answer(
        f"Məbləğ: <b>{amount:.0f} 🪙</b>\n"
        f"Xidmət haqqı ({WITHDRAW_FEE_PERCENT}%): <b>{fee:.0f} 🪙</b>\n"
        f"Sizə çatacaq: <b>{net:.0f} 🪙</b>\n\n"
        f"Kart nömrəsini yazın (16 rəqəm):",
        parse_mode="HTML"
    )


@router.message(WithdrawStates.waiting_card)
async def withdraw_card(message: Message, state: FSMContext):
    card = message.text.strip().replace(" ", "")
    if not card.isdigit() or len(card) < 16:
        await message.answer("Düzgün kart nömrəsi yazın (16 rəqəm).")
        return
    await state.update_data(card=card)
    await state.set_state(WithdrawStates.waiting_holder)
    await message.answer("Kart sahibinin adını və soyadını yazın:")


@router.message(WithdrawStates.waiting_holder)
async def withdraw_holder(message: Message, state: FSMContext, bot: Bot):
    holder = message.text.strip()
    data = await state.get_data()
    await state.clear()

    # Balansdan tut
    ok = await db.change_balance(
        message.from_user.id,
        -data["amount"],
        "withdraw",
        f"Çıxarış tələbi (xalis: {data['net']})"
    )
    if not ok:
        await message.answer("Xəta baş verdi. Balans yoxlanılsın.")
        return

    req_id = await db.create_withdraw_request(
        user_id=message.from_user.id,
        amount=data["amount"],
        fee=data["fee"],
        net_amount=data["net"],
        card_number=data["card"],
        card_holder=holder
    )

    # Adminə bildiriş
    text = (
        f"💸 <b>Yeni çıxarış tələbi #{req_id}</b>\n\n"
        f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
        f"ID: <code>{message.from_user.id}</code>\n\n"
        f"Məbləğ: <b>{data['amount']:.0f} 🪙</b>\n"
        f"Xidmət haqqı: {data['fee']:.0f} 🪙\n"
        f"Göndəriləcək: <b>{data['net']:.0f} 🪙</b>\n\n"
        f"Kart: <code>{data['card']}</code>\n"
        f"Sahib: {holder}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except:
            pass

    await message.answer(
        f"✅ Çıxarış tələbiniz qəbul olundu!\n\n"
        f"Sizə <b>{data['net']:.0f} 🪙</b> göndəriləcək.\n"
        f"Admin tezliklə emal edəcək.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS)
    )


# ====================== QAYDALAR ======================

@router.message(F.text == "📖 Qaydalar")
async def rules(message: Message):
    text = (
        "📖 <b>Oyun qaydaları</b>\n\n"
        "1️⃣ Balansınızı artırın (minimum 1000 🪙)\n"
        "2️⃣ Bilet alın (bir tirajda max 3 bilet)\n"
        "3️⃣ Tiraj vaxtı bitəndə qalib müəyyən olunur\n\n"
        "<b>Uduş qaydaları:</b>\n"
        "• 500-ə qədər → kassanın 60%-i (min 3 real iştirakçı)\n"
        "• 501–2500 → kassanın 50%-i (min 5 real iştirakçı)\n"
        "• 2501+ → kassanın 40%-i (min 5 real iştirakçı)\n\n"
        "Minimum iştirakçı olmazsa bot qazanır.\n\n"
        "Çıxarış yalnız uduşlarınızdan mümkündür. Xidmət haqqı 10%."
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🆘 Dəstək")
async def support(message: Message):
    await message.answer("Dəstək üçün adminə yazın və ya /admin əmrindən istifadə edin.")


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.delete()
    await callback.message.answer("Əsas menyu:", reply_markup=main_menu_kb(is_admin))
    await callback.answer()
