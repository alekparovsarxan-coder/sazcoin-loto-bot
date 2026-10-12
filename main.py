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
from draw_service import process_draw_step, DRAWN_COUNT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()


async def run_live_draws():
    """
    Каждые несколько секунд проверяем активные тиражи
    и выбрасываем следующее число (если пришло время).
    """
    import aiosqlite
    from config import DB_PATH
    now = time.time()

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM draws WHERE status = 'active'"
        ) as cursor:
            draws = await cursor.fetchall()

    for d in draws:
        draw_id = d["draw_id"]
        start = d["start_time"]
        end = d["end_time"]
        interval = d["interval_sec"]
        step = d["draw_step"] or 0

        if now < start:
            continue

        # Сколько чисел уже должно было выпасть к этому моменту
        # Равномерно распределяем DRAWN_COUNT чисел по времени тиража
        elapsed = now - start
        duration = end - start
        if duration <= 0:
            duration = interval

        # Каждое число примерно через (duration / DRAWN_COUNT) секунд
        step_duration = max(8, duration / (DRAWN_COUNT + 1))  # минимум 8 сек между числами
        expected_step = min(DRAWN_COUNT, int(elapsed / step_duration))

        # Если тираж уже закончился по времени — дорисовываем оставшиеся числа и завершаем
        if now >= end:
            while step < DRAWN_COUNT:
                still_going = await process_draw_step(draw_id, bot)
                if not still_going:
                    break
                step += 1
                await asyncio.sleep(0.3)
            continue

        # Обычный шаг: выпало ли уже следующее число
        if expected_step > step:
            await process_draw_step(draw_id, bot)


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

    # Каждые 5 секунд проверяем и выбрасываем числа
    scheduler.add_job(run_live_draws, IntervalTrigger(seconds=5))
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
