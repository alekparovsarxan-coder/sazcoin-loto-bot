# admin.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, DEFAULT_GLOBAL_PAYOUT_PERCENT, BRAND
import db
from inline import admin_panel_kb, main_menu_kb

router = Router()


class AdminAddBalance(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()


class AdminPayoutPct(StatesGroup):
    waiting_pct = State()


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


@router.message(F.text == "🛠 Админ панель")
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(f"🛠 <b>Админ {BRAND}</b>", reply_markup=admin_panel_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin_bank")
async def admin_bank(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    bank = await db.get_house_bank()
    pct = await db.get_setting("global_payout_percent", str(DEFAULT_GLOBAL_PAYOUT_PERCENT))
    text = (
        f"💰 <b>Касса {BRAND}</b>\n\n"
        f"Текущий баланс кассы: <b>{bank['balance']:.0f} 🪙</b>\n"
        f"Всего принято: {bank['total_in']:.0f} 🪙\n"
        f"Всего выплачено: {bank['total_out']:.0f} 🪙\n"
        f"Лимит выплат игрокам: <b>{pct}%</b> от кассы"
    )
    await callback.message.edit_text(text, reply_markup=admin_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_payout_pct")
async def admin_payout_pct(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    cur = await db.get_setting("global_payout_percent", str(DEFAULT_GLOBAL_PAYOUT_PERCENT))
    await state.set_state(AdminPayoutPct.waiting_pct)
    await callback.message.edit_text(f"Текущий % выплат: <b>{cur}</b>\nВведите новое значение (10–80):", parse_mode="HTML")
    await callback.answer()


@router.message(AdminPayoutPct.waiting_pct)
async def set_payout_pct(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        pct = int(message.text.strip())
        if not 10 <= pct <= 80:
            raise ValueError()
    except:
        await message.answer("Число от 10 до 80.")
        return
    await state.clear()
    await db.set_setting("global_payout_percent", str(pct))
    await message.answer(f"✅ Лимит выплат установлен: <b>{pct}%</b>", parse_mode="HTML",
                         reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    users = await db.get_all_users(25)
    text = "👥 <b>Пользователи</b>\n\n"
    for u in users:
        text += f"<code>{u['user_id']}</code> @{u['username'] or '—'} | {u['balance']:.0f} | W:{u['total_won']:.0f}\n"
    await callback.message.edit_text(text[:4000], reply_markup=admin_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_withdraws")
async def admin_withdraws(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    reqs = await db.get_pending_withdraws()
    if not reqs:
        await callback.message.edit_text("Нет заявок.", reply_markup=admin_panel_kb())
        await callback.answer()
        return
    text = "💸 <b>Выводы</b>\n\n"
    for r in reqs:
        text += (f"#{r['id']} <code>{r['user_id']}</code>\n"
                 f"{r['amount']:.0f}→{r['net_amount']:.0f} | {r['card_number']}\n"
                 f"/approve_{r['id']} /reject_{r['id']}\n\n")
    await callback.message.edit_text(text[:4000], reply_markup=admin_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.message(F.text.startswith("/approve_"))
async def approve_w(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    try:
        rid = int(message.text.split("_")[1])
    except:
        return
    import aiosqlite, time
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("UPDATE withdraw_requests SET status='approved', processed_at=? WHERE id=?", (time.time(), rid))
        await conn.commit()
        async with conn.execute("SELECT user_id, net_amount FROM withdraw_requests WHERE id=?", (rid,)) as cur:
            row = await cur.fetchone()
            if row:
                try:
                    await bot.send_message(row[0], f"✅ Вывод #{rid} одобрен. {row[1]:.0f} 🪙")
                except:
                    pass
    await message.answer(f"✅ #{rid}")


@router.message(F.text.startswith("/reject_"))
async def reject_w(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    try:
        rid = int(message.text.split("_")[1])
    except:
        return
    import aiosqlite, time
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT user_id, amount FROM withdraw_requests WHERE id=?", (rid,)) as cur:
            row = await cur.fetchone()
        if row:
            await db.change_balance(row[0], row[1], "admin_add", f"Вывод отклонён #{rid}")
            await conn.execute("UPDATE withdraw_requests SET status='rejected', processed_at=? WHERE id=?", (time.time(), rid))
            await conn.commit()
            try:
                await bot.send_message(row[0], f"❌ Вывод #{rid} отклонён. Средства возвращены.")
            except:
                pass
    await message.answer(f"❌ #{rid}")


@router.message(Command("addbal"))
async def cmd_addbal(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("/addbal USER_ID СУММА")
        return
    try:
        uid, amount = int(parts[1]), float(parts[2])
    except:
        await message.answer("Формат: /addbal 123456 5000")
        return
    ok = await db.change_balance(uid, amount, "admin_add" if amount > 0 else "admin_remove", "Админ")
    if ok:
        await message.answer(f"✅ {uid}: {amount:+.0f} 🪙")
        try:
            await bot.send_message(uid, f"💰 Баланс изменён на <b>{amount:+.0f} 🪙</b>", parse_mode="HTML")
        except:
            pass
    else:
        await message.answer("Ошибка")


@router.callback_query(F.data == "admin_add_balance")
async def admin_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminAddBalance.waiting_user_id)
    await callback.message.edit_text("User ID:")
    await callback.answer()


@router.message(AdminAddBalance.waiting_user_id)
async def admin_add_uid(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except:
        await message.answer("ID числом")
        return
    await state.update_data(user_id=uid)
    await state.set_state(AdminAddBalance.waiting_amount)
    await message.answer("Сумма (+/-):")


@router.message(AdminAddBalance.waiting_amount)
async def admin_add_amt(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text.replace(",", "."))
    except:
        await message.answer("Число")
        return
    data = await state.get_data()
    await state.clear()
    uid = data["user_id"]
    ok = await db.change_balance(uid, amount, "admin_add" if amount > 0 else "admin_remove", "Админ")
    if ok:
        await message.answer(f"✅ {uid}: {amount:+.0f}")
        try:
            await bot.send_message(uid, f"💰 Баланс: <b>{amount:+.0f} 🪙</b>", parse_mode="HTML")
        except:
            pass
    else:
        await message.answer("Ошибка")


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    import aiosqlite
    from config import DB_PATH
    bank = await db.get_house_bank()
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT COUNT(*), SUM(balance) FROM users") as cur:
            u = await cur.fetchone()
        async with conn.execute("SELECT COUNT(*) FROM draws WHERE status='finished'") as cur:
            d = (await cur.fetchone())[0]
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"Пользователей: {u[0] or 0}\n"
        f"Балансы игроков: {u[1] or 0:.0f} 🪙\n"
        f"Касса: {bank['balance']:.0f} 🪙\n"
        f"Тиражей: {d}"
    )
    await callback.message.edit_text(text, reply_markup=admin_panel_kb(), parse_mode="HTML")
    await callback.answer()
