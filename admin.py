# admin.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
import db
from inline import admin_panel_kb, main_menu_kb, back_main_kb

router = Router()


class AdminAddBalance(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(F.text == "🛠 Админ панель")
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("🛠 <b>Админ панель</b>\n\nВыберите действие:", reply_markup=admin_panel_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    users = await db.get_all_users(30)
    if not users:
        await callback.message.edit_text("Пользователей нет.", reply_markup=admin_panel_kb())
        return
    text = "👥 <b>Последние пользователи:</b>\n\n"
    for u in users:
        text += (
            f"• <code>{u['user_id']}</code> @{u['username'] or '—'}\n"
            f"  Баланс: {u['balance']:.0f} | Выигрыш: {u['total_won']:.0f} | Проигрыш: {u['total_lost']:.0f}\n\n"
        )
    await callback.message.edit_text(text[:4000], reply_markup=admin_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_withdraws")
async def admin_withdraws(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    reqs = await db.get_pending_withdraws()
    if not reqs:
        await callback.message.edit_text("Нет заявок на вывод.", reply_markup=admin_panel_kb())
        await callback.answer()
        return
    text = "💸 <b>Заявки на вывод:</b>\n\n"
    for r in reqs:
        text += (
            f"#{r['id']} | User: <code>{r['user_id']}</code>\n"
            f"Сумма: {r['amount']:.0f} → Нетто: {r['net_amount']:.0f}\n"
            f"Карта: <code>{r['card_number']}</code>\n"
            f"Владелец: {r['card_holder']}\n"
            f"/approve_{r['id']}  /reject_{r['id']}\n\n"
        )
    await callback.message.edit_text(text[:4000], reply_markup=admin_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.message(F.text.startswith("/approve_"))
async def approve_withdraw(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    try:
        req_id = int(message.text.split("_")[1])
    except:
        return
    import aiosqlite, time
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE withdraw_requests SET status = 'approved', processed_at = ? WHERE id = ?",
            (time.time(), req_id)
        )
        await conn.commit()
        async with conn.execute("SELECT user_id, net_amount FROM withdraw_requests WHERE id = ?", (req_id,)) as cur:
            row = await cur.fetchone()
            if row:
                try:
                    await bot.send_message(row[0], f"✅ Заявка на вывод #{req_id} одобрена!\nВам переведено {row[1]:.0f} 🪙")
                except:
                    pass
    await message.answer(f"✅ #{req_id} одобрена.")


@router.message(F.text.startswith("/reject_"))
async def reject_withdraw(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    try:
        req_id = int(message.text.split("_")[1])
    except:
        return
    import aiosqlite, time
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT user_id, amount FROM withdraw_requests WHERE id = ?", (req_id,)) as cur:
            row = await cur.fetchone()
        if row:
            await db.change_balance(row[0], row[1], "admin_add", f"Вывод отклонён #{req_id}")
            await conn.execute(
                "UPDATE withdraw_requests SET status = 'rejected', processed_at = ? WHERE id = ?",
                (time.time(), req_id)
            )
            await conn.commit()
            try:
                await bot.send_message(row[0], f"❌ Заявка на вывод #{req_id} отклонена. Средства возвращены.")
            except:
                pass
    await message.answer(f"❌ #{req_id} отклонена.")


@router.message(Command("addbal"))
async def cmd_addbal(message: Message, bot: Bot):
    """Быстрое пополнение: /addbal USER_ID СУММА"""
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /addbal USER_ID СУММА\nПример: /addbal 123456789 5000")
        return
    try:
        uid = int(parts[1])
        amount = float(parts[2])
    except:
        await message.answer("Неверный формат. Пример: /addbal 123456789 5000")
        return
    ok = await db.change_balance(uid, amount, "admin_add" if amount > 0 else "admin_remove", "Админ")
    if ok:
        await message.answer(f"✅ Пользователю <code>{uid}</code> изменено на {amount:+.0f} 🪙", parse_mode="HTML")
        try:
            await bot.send_message(uid, f"💰 Админ изменил ваш баланс на <b>{amount:+.0f} 🪙</b>", parse_mode="HTML")
        except:
            pass
    else:
        await message.answer("Ошибка (пользователь не найден или баланс стал бы отрицательным).")


@router.callback_query(F.data == "admin_add_balance")
async def admin_add_balance_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminAddBalance.waiting_user_id)
    await callback.message.edit_text("Введите User ID:")
    await callback.answer()


@router.message(AdminAddBalance.waiting_user_id)
async def admin_add_user_id(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except:
        await message.answer("Введите корректный ID.")
        return
    await state.update_data(user_id=uid)
    await state.set_state(AdminAddBalance.waiting_amount)
    await message.answer("Введите сумму (положительная = пополнить, отрицательная = снять):")


@router.message(AdminAddBalance.waiting_amount)
async def admin_add_amount(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text.replace(",", ".").strip())
    except:
        await message.answer("Введите корректное число.")
        return
    data = await state.get_data()
    await state.clear()
    uid = data["user_id"]
    ok = await db.change_balance(uid, amount, "admin_add" if amount > 0 else "admin_remove", "Админ")
    if ok:
        await message.answer(f"✅ Пользователю {uid} изменено на {amount:+.0f} 🪙")
        try:
            await bot.send_message(uid, f"💰 Админ изменил ваш баланс на <b>{amount:+.0f} 🪙</b>", parse_mode="HTML")
        except:
            pass
    else:
        await message.answer("Ошибка.")


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT COUNT(*), SUM(balance), SUM(total_won), SUM(total_lost) FROM users") as cur:
            row = await cur.fetchone()
        async with conn.execute("SELECT COUNT(*) FROM draws WHERE status = 'finished'") as cur:
            draws = (await cur.fetchone())[0]
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {row[0] or 0}\n"
        f"💰 Общий баланс: {row[1] or 0:.0f} 🪙\n"
        f"🏆 Всего выиграно: {row[2] or 0:.0f} 🪙\n"
        f"📉 Всего проиграно: {row[3] or 0:.0f} 🪙\n"
        f"🎯 Завершённых тиражей: {draws}"
    )
    await callback.message.edit_text(text, reply_markup=admin_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚙️ Настройки тиражей пока меняются через config.py",
        reply_markup=admin_panel_kb()
    )
    await callback.answer()
