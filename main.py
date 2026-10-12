# main.py
import sys
import os
from pathlib import Path

# ====================== CRITICAL PATH FIX FOR RAILWAY ======================
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)  # working directory-ni də düzəldirik

# Debug (Railway log-da görünəcək)
print("=" * 50)
print(f"BASE_DIR: {BASE_DIR}")
print(f"Files in BASE_DIR: {os.listdir(BASE_DIR)}")
print(f"sys.path[0]: {sys.path[0]}")
print("=" * 50)

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN, ROOMS, DAILY_TICKET, DAILY_HOUR, DAILY_MINUTE, ADMIN_IDS

# database import
try:
    from database.db import init_db
    from database import db
except ModuleNotFoundError as e:
    print(f"IMPORT ERROR: {e}")
    print("Trying alternative import...")
    # Alternativ yol
    import importlib.util
    db_path = BASE_DIR / "database" / "db.py"
    if not db_path.exists():
        print(f"database/db.py NOT FOUND at {db_path}")
        print(f"Contents of BASE_DIR: {list(BASE_DIR.iterdir())}")
        raise
    spec = importlib.util.spec_from_file_location("database.db", db_path)
    db_module = importlib.util.module_from_spec(spec)
    sys.modules["database.db"] = db_module
    spec.loader.exec_module(db_module)
    init_db = db_module.init_db
    db = db_module

from handlers import user, admin
from services.draw_service import process_draw, generate_fake_winner_text, generate_real_winner_text
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()


async def check_and_finish_draws():
    """Aktiv tirajları yoxlayır və vaxtı bitənləri yekunlaşdırır."""
    import aiosqlite
    from config import DB_PATH
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT draw_id, room_price FROM draws WHERE status = 'active' AND end_time <= ?",
            (now,)
        ) as cursor:
            draws = await cursor.fetchall()

    for d in draws:
        draw_id = d["draw_id"]
        result = await process_draw(draw_id)
        if not result:
            continue

        participants = await db.get_draw_participants(draw_id)
        if result["is_bot_win"]:
            text = generate_fake_winner_text(result["fake_name"], result["win_amount"], result["pot"])
        else:
            winner = await db.get_user(result["winner_id"])
            name = f"@{winner['username']}" if winner and winner['username'] else f"ID{result['winner_id']}"
            text = generate_real_winner_text(name, result["win_amount"], result["pot"], result["percent"])

        for p in participants:
            try:
                await bot.send_message(p["user_id"], text)
            except Exception as e:
                logger.warning(f"Bildiriş göndərilmədi {p['user_id']}: {e}")

        if result["is_bot_win"]:
            admin_text = f"🤖 Bot qazandı | {d['room_price']} 🪙 | Kassa: {result['pot']:.0f}"
        else:
            admin_text = f"🏆 Real qalib: {result['winner_id']} | {result['win_amount']:.0f} 🪙 | Kassa: {result['pot']:.0f}"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text)
            except:
                pass


async def ensure_active_draws():
    """Hər otaq üçün aktiv tiraj olduğundan əmin olur."""
    for interval, prices in ROOMS.items():
        for price in prices:
            await db.get_or_create_active_draw(price, interval)


async def create_daily_draw():
    """Hər gün 21:00-da 20000-lik tiraj yaradır."""
    await db.get_or_create_active_draw(DAILY_TICKET, 86400)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"🌟 Gündəlik {DAILY_TICKET} 🪙 tirajı yaradıldı!")
        except:
            pass


async def on_startup():
    await init_db()
    logger.info("Database initialized")

    scheduler.add_job(check_and_finish_draws, IntervalTrigger(seconds=15))
    scheduler.add_job(ensure_active_draws, IntervalTrigger(seconds=30))
    scheduler.add_job(create_daily_draw, CronTrigger(hour=DAILY_HOUR, minute=DAILY_MINUTE))

    scheduler.start()
    logger.info("Scheduler started")
    await ensure_active_draws()


async def main():
    dp.include_router(user.router)
    dp.include_router(admin.router)
    dp.startup.register(on_startup)

    logger.info("Bot işə düşür...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
