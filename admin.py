# handlers/admin.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database import db
from keyboards.inline import admin_panel_kb, main_menu_kb, back_main_kb

router = Router()


class AdminAddBalance(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(F.text == "🛠 Admin Panel")
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Sizin icazəniz yoxdur.")
        return
    await message.answer("🛠 <b>Admin Panel</b>\n\nSeçim edin:", reply_markup=admin_panel_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    users = await db.get_all_users(30)
    if not users:
        await callback.message.edit_text("İstifadəçi yoxdur.", reply_markup=admin_panel_kb())
        return

    text = "👥 <b>Son aktiv istifadəçilər:</b>\n\n"
    for u in users:
        text += (
            f"• <code>{u['user_id']}</code> @{u['username'] or '-'}\n"
            f"  Balans: {u['balance']:.0f} | Uduş: {u['total_won']:.0f} | Uduzma: {u['total_lost']:.0f}\n\n"
        )
    await callback.message.edit_text(text[:4000], reply_markup=admin_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_withdraws")
async def admin_withdraws(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    reqs = await db.get_pending_withdraws()
    if not reqs:
        await callback.message.edit_text("Gözləyən çıxarış tələbi yoxdur.", reply_markup=admin_panel_kb())
        await callback.answer()
        return

    text = "💸 <b>Gözləyən çıxarışlar:</b>\n\n"
    for r in reqs:
        text += (
            f"#{r['id']} | User: <code>{r['user_id']}</code>\n"
            f"Məbləğ: {r['amount']:.0f} → Net: {r['net_amount']:.0f}\n"
            f"Kart: <code>{r['card_number']}</code>\n"
            f"Sahib: {r['card_holder']}\n"
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

    import aiosqlite
    import time
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
                    await bot.send_message(row[0], f"✅ Çıxarış tələbiniz #{req_id} təsdiqləndi!\n{row[1]:.0f} 🪙 göndərildi.")
                except:
                    pass
    await message.answer(f"✅ #{req_id} təsdiqləndi.")


@router.message(F.text.startswith("/reject_"))
async def reject_withdraw(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    try:
        req_id = int(message.text.split("_")[1])
    except:
        return

    import aiosqlite
    from config import DB_PATH
    import time
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT user_id, amount FROM withdraw_requests WHERE id = ?", (req_id,)) as cur:
            row = await cur.fetchone()
        if row:
            # Pulu geri qaytar
            await db.change_balance(row[0], row[1], "admin_add", f"Çıxarış rədd edildi #{req_id}")
            await conn.execute(
                "UPDATE withdraw_requests SET status = 'rejected', processed_at = ? WHERE id = ?",
                (time.time(), req_id)
            )
            await conn.commit()
            try:
                await bot.send_message(row[0], f"❌ Çıxarış tələbiniz #{req_id} rədd edildi. Məbləğ geri qaytarıldı.")
            except:
                pass
    await message.answer(f"❌ #{req_id} rədd edildi.")


@router.callback_query(F.data == "admin_add_balance")
async def admin_add_balance_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminAddBalance.waiting_user_id)
    await callback.message.edit_text("İstifadəçi ID-sini yazın:")
    await callback.answer()


@router.message(AdminAddBalance.waiting_user_id)
async def admin_add_user_id(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except:
        await message.answer("Düzgün ID yazın.")
        return
    await state.update_data(user_id=uid)
    await state.set_state(AdminAddBalance.waiting_amount)
    await message.answer("Məbləği yazın (müsbət = artır, mənfi = azaldır):")


@router.message(AdminAddBalance.waiting_amount)
async def admin_add_amount(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text.replace(",", ".").strip())
    except:
        await message.answer("Düzgün rəqəm yazın.")
        return

    data = await state.get_data()
    await state.clear()
    uid = data["user_id"]

    ok = await db.change_balance(uid, amount, "admin_add" if amount > 0 else "admin_remove", "Admin tərəfindən")
    if ok:
        await message.answer(f"✅ {uid} istifadəçisinə {amount:+.0f} 🪙 tətbiq olundu.")
        try:
            await bot.send_message(uid, f"💰 Admin balansınıza <b>{amount:+.0f} 🪙</b> dəyişiklik etdi.", parse_mode="HTML")
        except:
            pass
    else:
        await message.answer("Xəta baş verdi (istifadəçi yoxdur və ya balans mənfi ola bilməz).")


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    # Sadə statistika
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT COUNT(*), SUM(balance), SUM(total_won), SUM(total_lost) FROM users") as cur:
            row = await cur.fetchone()
        async with conn.execute("SELECT COUNT(*) FROM draws WHERE status = 'finished'") as cur:
            draws = (await cur.fetchone())[0]

    text = (
        f"📊 <b>Ümumi statistika</b>\n\n"
        f"👥 İstifadəçi sayı: {row[0] or 0}\n"
        f"💰 Ümumi balanslar: {row[1] or 0:.0f} 🪙\n"
        f"🏆 Ümumi uduşlar: {row[2] or 0:.0f} 🪙\n"
        f"📉 Ümumi uduzmalar: {row[3] or 0:.0f} 🪙\n"
        f"🎯 Bitmiş tirajlar: {draws}"
    )
    await callback.message.edit_text(text, reply_markup=admin_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚙️ Tiraj tənzimləmələri hələlik config.py faylından dəyişilir.\n"
        "Gələcəkdə bot daxilindən dəyişmək mümkün olacaq.",
        reply_markup=admin_panel_kb()
    )
    await callback.answer()
