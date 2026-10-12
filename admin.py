# admin.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import ADMIN_IDS, DEFAULT_GLOBAL_PAYOUT_PERCENT, BRAND
import db
from inline import admin_panel_kb

router = Router()

class AdminAddBalance(StatesGroup):
    waiting_user_id = State(); waiting_amount = State()
class AdminPayoutPct(StatesGroup):
    waiting_pct = State()
class AdminPromo(StatesGroup):
    waiting_data = State()
class AdminForceWin(StatesGroup):
    waiting_uid = State()

def is_admin(uid): return uid in ADMIN_IDS

@router.message(F.text == "🛠 Админ панель")
@router.message(Command("admin"))
async def panel(message: Message):
    if not is_admin(message.from_user.id): return
    await message.answer(f"🛠 <b>{BRAND} Admin</b>", reply_markup=admin_panel_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_bank")
async def bank(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    b = await db.get_house_bank(); jp = await db.get_jackpot()
    pct = await db.get_setting("global_payout_percent", str(DEFAULT_GLOBAL_PAYOUT_PERCENT))
    await cb.message.edit_text(
        f"💰 <b>Касса</b>\nБаланс: <b>{b['balance']:.0f}</b>\nПринято: {b['total_in']:.0f}\n"
        f"Выплачено: {b['total_out']:.0f}\n% выплат: {pct}%\n🎰 Джекпот: {jp['pool']:.0f} (тиражей: {jp['draws_count']})",
        reply_markup=admin_panel_kb(), parse_mode="HTML"); await cb.answer()

@router.callback_query(F.data == "admin_payout_pct")
async def pct_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return
    await state.set_state(AdminPayoutPct.waiting_pct)
    cur = await db.get_setting("global_payout_percent", str(DEFAULT_GLOBAL_PAYOUT_PERCENT))
    await cb.message.edit_text(f"Сейчас {cur}%. Введите 10–80:"); await cb.answer()

@router.message(AdminPayoutPct.waiting_pct)
async def pct_set(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        p = int(message.text); assert 10 <= p <= 80
    except:
        await message.answer("10–80"); return
    await state.clear(); await db.set_setting("global_payout_percent", str(p))
    await message.answer(f"✅ {p}%", reply_markup=admin_panel_kb())

@router.callback_query(F.data == "admin_promo")
async def promo_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return
    await state.set_state(AdminPromo.waiting_data)
    await cb.message.edit_text("Формат: КОД СУММА [лимит]\nПример: SALE50 500 100"); await cb.answer()

@router.message(AdminPromo.waiting_data)
async def promo_create(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    parts = message.text.split()
    try:
        code, amount = parts[0], float(parts[1])
        limit = int(parts[2]) if len(parts)>2 else 100
    except:
        await message.answer("КОД СУММА [лимит]"); return
    await state.clear(); await db.create_promo(code, amount, limit)
    await message.answer(f"✅ Промо {code.upper()} = {amount:.0f} 🪙 (лимит {limit})", reply_markup=admin_panel_kb())

@router.callback_query(F.data == "admin_forcewin")
async def fw_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return
    await state.set_state(AdminForceWin.waiting_uid)
    await cb.message.edit_text("User ID для force-win (следующий тираж где он участвует — приоритет):\nПока: используйте ручное /addbal для компенсации"); await cb.answer()
    await state.clear()

@router.callback_query(F.data == "admin_losers")
async def losers(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    rows = await db.get_heavy_losers(3000)
    if not rows:
        await cb.message.edit_text("Нет крупных лузеров", reply_markup=admin_panel_kb()); await cb.answer(); return
    text = "⚠️ <b>Много проиграли</b>\n\n"
    for u in rows:
        loss = u["total_lost"] - u["total_won"]
        text += f"<code>{u['user_id']}</code> @{u.get('username') or '—'} | −{loss:.0f}\n"
    await cb.message.edit_text(text[:4000], reply_markup=admin_panel_kb(), parse_mode="HTML"); await cb.answer()

@router.callback_query(F.data == "admin_users")
async def users(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    rows = await db.get_all_users(20)
    text = "👥\n" + "\n".join(f"<code>{u['user_id']}</code> @{u.get('username') or '—'} | {u['balance']:.0f} | W{u['total_won']:.0f}" for u in rows)
    await cb.message.edit_text(text[:4000], reply_markup=admin_panel_kb(), parse_mode="HTML"); await cb.answer()

@router.callback_query(F.data == "admin_withdraws")
async def withdraws(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    reqs = await db.get_pending_withdraws()
    if not reqs:
        await cb.message.edit_text("Нет заявок", reply_markup=admin_panel_kb()); await cb.answer(); return
    text = "💸\n" + "\n".join(
        f"#{r['id']} <code>{r['user_id']}</code> {r['amount']:.0f}→{r['net_amount']:.0f}\n{r['card_number']}\n/approve_{r['id']} /reject_{r['id']}\n" for r in reqs)
    await cb.message.edit_text(text[:4000], reply_markup=admin_panel_kb(), parse_mode="HTML"); await cb.answer()

@router.message(F.text.startswith("/approve_"))
async def approve(message: Message, bot: Bot):
    if not is_admin(message.from_user.id): return
    try: rid = int(message.text.split("_")[1])
    except: return
    import aiosqlite, time
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("UPDATE withdraw_requests SET status='approved', processed_at=? WHERE id=?", (time.time(), rid))
        await conn.commit()
        async with conn.execute("SELECT user_id, net_amount FROM withdraw_requests WHERE id=?", (rid,)) as c:
            r = await c.fetchone()
            if r:
                try: await bot.send_message(r[0], f"✅ Вывод #{rid} одобрен: {r[1]:.0f} 🪙")
                except: pass
    await message.answer(f"✅ #{rid}")

@router.message(F.text.startswith("/reject_"))
async def reject(message: Message, bot: Bot):
    if not is_admin(message.from_user.id): return
    try: rid = int(message.text.split("_")[1])
    except: return
    import aiosqlite, time
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT user_id, amount FROM withdraw_requests WHERE id=?", (rid,)) as c:
            r = await c.fetchone()
        if r:
            await db.change_balance(r[0], r[1], "admin_add", f"Отклонён #{rid}")
            await conn.execute("UPDATE withdraw_requests SET status='rejected', processed_at=? WHERE id=?", (time.time(), rid))
            await conn.commit()
            try: await bot.send_message(r[0], f"❌ Вывод #{rid} отклонён")
            except: pass
    await message.answer(f"❌ #{rid}")

@router.message(Command("addbal"))
async def addbal(message: Message, bot: Bot):
    if not is_admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts)!=3: await message.answer("/addbal ID SUM"); return
    try: uid, amt = int(parts[1]), float(parts[2])
    except: await message.answer("Формат"); return
    ok = await db.change_balance(uid, amt, "admin_add" if amt>0 else "admin_remove", "Админ")
    if ok:
        await message.answer(f"✅ {uid}: {amt:+.0f}")
        try: await bot.send_message(uid, f"💰 Баланс {amt:+.0f} 🪙", parse_mode="HTML")
        except: pass
    else: await message.answer("Ошибка")

@router.callback_query(F.data == "admin_add_balance")
async def add_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return
    await state.set_state(AdminAddBalance.waiting_user_id)
    await cb.message.edit_text("User ID:"); await cb.answer()

@router.message(AdminAddBalance.waiting_user_id)
async def add_uid(message: Message, state: FSMContext):
    try: uid = int(message.text)
    except: await message.answer("ID"); return
    await state.update_data(user_id=uid); await state.set_state(AdminAddBalance.waiting_amount)
    await message.answer("Сумма:")

@router.message(AdminAddBalance.waiting_amount)
async def add_amt(message: Message, state: FSMContext, bot: Bot):
    try: amt = float(message.text.replace(",","."))
    except: await message.answer("Число"); return
    data = await state.get_data(); await state.clear(); uid = data["user_id"]
    ok = await db.change_balance(uid, amt, "admin_add" if amt>0 else "admin_remove", "Админ")
    if ok:
        await message.answer(f"✅ {uid}: {amt:+.0f}", reply_markup=admin_panel_kb())
        try: await bot.send_message(uid, f"💰 {amt:+.0f} 🪙", parse_mode="HTML")
        except: pass
    else: await message.answer("Ошибка")

@router.callback_query(F.data == "admin_stats")
async def stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    import aiosqlite
    from config import DB_PATH
    b = await db.get_house_bank()
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT COUNT(*), COALESCE(SUM(balance),0) FROM users") as c:
            u = await c.fetchone()
        async with conn.execute("SELECT COUNT(*) FROM draws WHERE status='finished'") as c:
            d = (await c.fetchone())[0]
    await cb.message.edit_text(
        f"📊 Юзеров: {u[0]}\nБалансы: {u[1]:.0f}\nКасса: {b['balance']:.0f}\nТиражей: {d}",
        reply_markup=admin_panel_kb()); await cb.answer()
