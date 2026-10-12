# main.py
import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN, ROOMS, DAILY_TICKET, DAILY_HOUR, DAILY_MINUTE, ADMIN_IDS
import db
from db import init_db
import user
import admin
from draw_service import process_draw, generate_fake_winner_text, generate_real_winner_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()


async def check_and_finish_draws():
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

        # Только если были реальные участники — уведомляем
        if result["real_users"] == 0:
            continue

        participants = await db.get_draw_participants(draw_id)
        if result["is_bot_win"]:
            text = generate_fake_winner_text(result["fake_name"], result["win_amount"], result["pot"])
        else:
            winner = await db.get_user(result["winner_id"])
            name = f"@{winner['username']}" if winner and winner.get('username') else f"ID{result['winner_id']}"
            text = generate_real_winner_text(name, result["win_amount"], result["pot"], result["percent"])

        for p in participants:
            try:
                await bot.send_message(p["user_id"], text)
            except Exception as e:
                logger.warning(f"Не удалось отправить: {p['user_id']}: {e}")

        # Уведомление админу только когда были игроки
        if result["is_bot_win"]:
            admin_text = f"🤖 Бот выиграл | {d['room_price']} 🪙 | Касса: {result['pot']:.0f} | Игроков: {result['real_users']}"
        else:
            admin_text = f"🏆 Победитель: {result['winner_id']} | {result['win_amount']:.0f} 🪙 | Касса: {result['pot']:.0f}"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text)
            except:
                pass


async def ensure_active_draws():
    for interval, prices in ROOMS.items():
        for price in prices:
            await db.get_or_create_active_draw(price, interval)


async def create_daily_draw():
    await db.get_or_create_active_draw(DAILY_TICKET, 86400)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"🌟 Ежедневный тираж {DAILY_TICKET} 🪙 создан!")
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
    logger.info("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
