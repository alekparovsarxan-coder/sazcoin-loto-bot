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

from config import BOT_TOKEN, TICKET_PRICES, ADMIN_IDS, DRAWN_COUNT, SALES_CLOSE_BEFORE
import db
from db import init_db
import user
import admin
from draw_service import process_draw_step

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()


async def run_live_draws():
    now = time.time()
    draws = await db.get_active_draws()
    for d in draws:
        draw_id = d["draw_id"]
        status = d["status"]
        step = d.get("draw_step") or 0

        # Переход registration → drawing
        if status == "registration" and now >= d["draw_start"]:
            await db.set_draw_status(draw_id, "drawing")
            # Уведомить участников о старте
            tickets = await db.get_tickets_for_draw(draw_id)
            users = set(t["user_id"] for t in tickets)
            for uid in users:
                try:
                    await bot.send_message(uid, "🎱 <b>Розыгрыш начался!</b>\nЧисла будут выпадать одно за другим...", parse_mode="HTML")
                except:
                    pass
            status = "drawing"

        if status != "drawing":
            continue

        start = d["draw_start"]
        end = d["draw_end"]
        duration = max(1, end - start)
        elapsed = now - start
        step_dur = max(8, duration / (DRAWN_COUNT + 0.5))
        expected = min(DRAWN_COUNT, int(elapsed / step_dur) + (1 if elapsed > 2 else 0))

        if now >= end:
            while step < DRAWN_COUNT:
                ok = await process_draw_step(draw_id, bot)
                if not ok:
                    break
                step += 1
                await asyncio.sleep(0.2)
            continue

        if expected > step:
            await process_draw_step(draw_id, bot)


async def ensure_draws():
    for price in TICKET_PRICES:
        await db.get_or_create_draw(price)


async def sales_close_notify():
    """За ~30 сек до старта предупредить участников."""
    now = time.time()
    draws = await db.get_active_draws()
    for d in draws:
        if d["status"] != "registration":
            continue
        left = d["reg_end"] - now
        if 28 <= left <= 35:
            tickets = await db.get_tickets_for_draw(d["draw_id"])
            users = set(t["user_id"] for t in tickets)
            for uid in users:
                try:
                    await bot.send_message(uid, f"🔒 <b>Продажа билетов закрыта!</b>\nЧерез ~30 сек начнётся розыгрыш {d['room_price']} 🪙", parse_mode="HTML")
                except:
                    pass


async def on_startup():
    await init_db()
    logger.info("DB ready")
    scheduler.add_job(run_live_draws, IntervalTrigger(seconds=4))
    scheduler.add_job(ensure_draws, IntervalTrigger(seconds=20))
    scheduler.add_job(sales_close_notify, IntervalTrigger(seconds=10))
    scheduler.start()
    await ensure_draws()
    logger.info("Scheduler started")


async def main():
    dp.include_router(user.router)
    dp.include_router(admin.router)
    dp.startup.register(on_startup)
    logger.info("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
