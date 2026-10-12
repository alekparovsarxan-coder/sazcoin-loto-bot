# db.py — полная версия
import aiosqlite, time, json
from typing import Optional, List, Dict
from config import DB_PATH

async def init_db():
    from pathlib import Path
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT, full_name TEXT,
            balance REAL DEFAULT 0,
            total_won REAL DEFAULT 0, total_lost REAL DEFAULT 0,
            total_deposited REAL DEFAULT 0, total_withdrawn REAL DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            referrer_id INTEGER,
            streak INTEGER DEFAULT 0,
            last_daily REAL DEFAULT 0,
            near_win INTEGER DEFAULT 0,
            created_at REAL, last_active REAL
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, room_price INTEGER, amount REAL,
            numbers TEXT, created_at REAL, draw_id TEXT,
            is_winner INTEGER DEFAULT 0, win_amount REAL DEFAULT 0, matches INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS draws (
            draw_id TEXT PRIMARY KEY, room_price INTEGER,
            reg_start REAL, reg_end REAL, draw_start REAL, draw_end REAL,
            total_pot REAL DEFAULT 0, participants_count INTEGER DEFAULT 0,
            winner_user_id INTEGER, winner_amount REAL DEFAULT 0, is_bot_win INTEGER DEFAULT 0,
            drawn_numbers TEXT DEFAULT '[]', draw_step INTEGER DEFAULT 0,
            status TEXT DEFAULT 'registration', draw_number INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, type TEXT, amount REAL, description TEXT,
            created_at REAL, status TEXT DEFAULT 'done'
        );
        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, amount REAL, fee REAL, net_amount REAL,
            card_number TEXT, card_holder TEXT, status TEXT DEFAULT 'pending',
            admin_note TEXT, created_at REAL, processed_at REAL
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS house_bank (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance REAL DEFAULT 0, total_in REAL DEFAULT 0, total_out REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY, amount REAL, max_uses INTEGER DEFAULT 100,
            used_count INTEGER DEFAULT 0, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS promo_uses (
            code TEXT, user_id INTEGER, used_at REAL,
            PRIMARY KEY (code, user_id)
        );
        CREATE TABLE IF NOT EXISTS jackpot (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            pool REAL DEFAULT 0, draws_count INTEGER DEFAULT 0
        );
        """)
        await db.execute("INSERT OR IGNORE INTO house_bank (id, balance, total_in, total_out) VALUES (1,0,0,0)")
        await db.execute("INSERT OR IGNORE INTO jackpot (id, pool, draws_count) VALUES (1,0,0)")
        await db.commit()
        for sql in [
            "ALTER TABLE users ADD COLUMN referrer_id INTEGER",
            "ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_daily REAL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN near_win INTEGER DEFAULT 0",
            "ALTER TABLE draws ADD COLUMN drawn_numbers TEXT DEFAULT '[]'",
            "ALTER TABLE draws ADD COLUMN draw_step INTEGER DEFAULT 0",
            "ALTER TABLE draws ADD COLUMN reg_start REAL",
            "ALTER TABLE draws ADD COLUMN reg_end REAL",
            "ALTER TABLE draws ADD COLUMN draw_start REAL",
            "ALTER TABLE draws ADD COLUMN draw_end REAL",
            "ALTER TABLE draws ADD COLUMN draw_number INTEGER DEFAULT 0",
            "ALTER TABLE tickets ADD COLUMN numbers TEXT",
            "ALTER TABLE tickets ADD COLUMN matches INTEGER DEFAULT 0",
        ]:
            try:
                await db.execute(sql); await db.commit()
            except: pass

async def get_setting(key, default=""):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as c:
            r = await c.fetchone(); return r[0] if r else default

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=?", (key,value,value))
        await db.commit()

async def get_house_bank():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM house_bank WHERE id=1") as c:
            r = await c.fetchone(); return dict(r) if r else {"balance":0,"total_in":0,"total_out":0}

async def house_add(amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE house_bank SET balance=balance+?, total_in=total_in+? WHERE id=1", (amount,amount))
        await db.commit()

async def house_pay(amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE house_bank SET balance=balance-?, total_out=total_out+? WHERE id=1", (amount,amount))
        await db.commit()

async def get_jackpot():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jackpot WHERE id=1") as c:
            r = await c.fetchone(); return dict(r) if r else {"pool":0,"draws_count":0}

async def jackpot_add(amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE jackpot SET pool=pool+?, draws_count=draws_count+1 WHERE id=1", (amount,))
        await db.commit()

async def jackpot_reset():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT pool FROM jackpot WHERE id=1") as c:
            r = await c.fetchone(); pool = r[0] if r else 0
        await db.execute("UPDATE jackpot SET pool=0 WHERE id=1")
        await db.commit()
        return pool

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
            r = await c.fetchone(); return dict(r) if r else None

async def create_user(user_id, username=None, full_name=None, referrer_id=None):
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id,username,full_name,referrer_id,created_at,last_active) VALUES (?,?,?,?,?,?)",
            (user_id, username, full_name, referrer_id, now, now))
        await db.commit()

async def update_user_activity(user_id, username=None, full_name=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_active=?, username=COALESCE(?,username), full_name=COALESCE(?,full_name) WHERE user_id=?",
            (time.time(), username, full_name, user_id))
        await db.commit()

async def change_balance(user_id, amount, tx_type, description="") -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)) as c:
            r = await c.fetchone()
            if not r: return False
            nb = r["balance"] + amount
            if nb < 0: return False
        await db.execute("UPDATE users SET balance=? WHERE user_id=?", (nb, user_id))
        if tx_type == "win":
            await db.execute("UPDATE users SET total_won=total_won+? WHERE user_id=?", (amount, user_id))
        elif tx_type == "ticket":
            await db.execute("UPDATE users SET total_lost=total_lost+? WHERE user_id=?", (abs(amount), user_id))
        elif tx_type == "topup":
            await db.execute("UPDATE users SET total_deposited=total_deposited+? WHERE user_id=?", (amount, user_id))
        elif tx_type == "withdraw":
            await db.execute("UPDATE users SET total_withdrawn=total_withdrawn+? WHERE user_id=?", (abs(amount), user_id))
        await db.execute("INSERT INTO transactions (user_id,type,amount,description,created_at) VALUES (?,?,?,?,?)",
                         (user_id, tx_type, amount, description, time.time()))
        await db.commit()
        return True

async def set_streak(user_id, streak):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET streak=? WHERE user_id=?", (streak, user_id))
        await db.commit()

async def set_near_win(user_id, val):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET near_win=? WHERE user_id=?", (val, user_id))
        await db.commit()

async def claim_daily(user_id) -> tuple:
    from config import DAILY_BONUS
    user = await get_user(user_id)
    if not user: return False, "Ошибка"
    now = time.time()
    if now - (user.get("last_daily") or 0) < 86400:
        left = 86400 - (now - (user.get("last_daily") or 0))
        return False, f"Уже получали. Через {int(left//3600)}ч {int((left%3600)//60)}м"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET last_daily=? WHERE user_id=?", (now, user_id))
        await db.commit()
    await change_balance(user_id, DAILY_BONUS, "bonus", "Ежедневный бонус")
    return True, f"+{DAILY_BONUS} 🪙 ежедневный бонус!"

async def use_promo(user_id, code) -> tuple:
    code = code.upper().strip()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM promocodes WHERE code=? AND active=1", (code,)) as c:
            promo = await c.fetchone()
        if not promo: return False, "Промокод не найден"
        if promo["used_count"] >= promo["max_uses"]: return False, "Промокод исчерпан"
        async with db.execute("SELECT 1 FROM promo_uses WHERE code=? AND user_id=?", (code, user_id)) as c:
            if await c.fetchone(): return False, "Вы уже использовали этот код"
        await db.execute("INSERT INTO promo_uses (code,user_id,used_at) VALUES (?,?,?)", (code, user_id, time.time()))
        await db.execute("UPDATE promocodes SET used_count=used_count+1 WHERE code=?", (code,))
        await db.commit()
    await change_balance(user_id, promo["amount"], "promo", f"Промокод {code}")
    return True, f"Промокод активирован! +{promo['amount']:.0f} 🪙"

async def create_promo(code, amount, max_uses=100):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO promocodes (code,amount,max_uses,used_count,active) VALUES (?,?,?,0,1)",
                         (code.upper(), amount, max_uses))
        await db.commit()

async def get_leaderboard(limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, full_name, total_won, balance FROM users ORDER BY total_won DESC LIMIT ?", (limit,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

async def get_user_active_draw_price(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT t.room_price FROM tickets t JOIN draws d ON t.draw_id=d.draw_id
            WHERE t.user_id=? AND d.status IN ('registration','drawing') LIMIT 1
        """, (user_id,)) as c:
            r = await c.fetchone(); return r[0] if r else None

async def get_or_create_draw(room_price):
    from config import REGISTRATION_SEC, DRAW_DURATION_SEC
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT draw_id FROM draws WHERE room_price=? AND status IN ('registration','drawing') AND draw_end>?
            ORDER BY reg_start DESC LIMIT 1
        """, (room_price, now)) as c:
            r = await c.fetchone()
            if r: return r["draw_id"]
        import uuid
        draw_id = str(uuid.uuid4())
        reg_start = now
        reg_end = now + REGISTRATION_SEC
        draw_start = reg_end
        draw_end = draw_start + DRAW_DURATION_SEC
        async with db.execute("SELECT COALESCE(MAX(draw_number),0)+1 FROM draws") as c:
            num = (await c.fetchone())[0]
        await db.execute("""
            INSERT INTO draws (draw_id,room_price,reg_start,reg_end,draw_start,draw_end,status,drawn_numbers,draw_step,draw_number)
            VALUES (?,?,?,?,?,?,'registration','[]',0,?)
        """, (draw_id, room_price, reg_start, reg_end, draw_start, draw_end, num))
        await db.commit()
        return draw_id

async def get_draw(draw_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM draws WHERE draw_id=?", (draw_id,)) as c:
            r = await c.fetchone()
            if not r: return None
            d = dict(r); d["drawn_numbers"] = json.loads(d["drawn_numbers"] or "[]"); return d

async def get_active_draws():
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM draws WHERE status IN ('registration','drawing') AND draw_end>? ORDER BY room_price", (now,)
        ) as c:
            return [{**dict(r), "drawn_numbers": json.loads(r["drawn_numbers"] or "[]")} for r in await c.fetchall()]

async def add_tickets(user_id, room_price, draw_id, tickets_numbers):
    total = room_price * len(tickets_numbers)
    user = await get_user(user_id)
    discount = 0
    if user and user.get("near_win"):
        from config import NEAR_WIN_DISCOUNT_PCT
        discount = total * NEAR_WIN_DISCOUNT_PCT / 100
        await set_near_win(user_id, 0)
    pay = total - discount
    ok = await change_balance(user_id, -pay, "ticket", f"Билеты x{len(tickets_numbers)}" + (f" (скидка {discount:.0f})" if discount else ""))
    if not ok: return False
    async with aiosqlite.connect(DB_PATH) as db:
        for nums in tickets_numbers:
            await db.execute(
                "INSERT INTO tickets (user_id,room_price,amount,numbers,created_at,draw_id) VALUES (?,?,?,?,?,?)",
                (user_id, room_price, room_price, json.dumps(nums), time.time(), draw_id))
        await db.execute("UPDATE draws SET total_pot=total_pot+?, participants_count=participants_count+? WHERE draw_id=?",
                         (total, len(tickets_numbers), draw_id))
        await db.commit()
    await house_add(pay)
    await jackpot_add(pay * 0.02)  # 2% в джекпот
    return True

async def get_user_tickets_in_draw(user_id, draw_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM tickets WHERE user_id=? AND draw_id=?", (user_id, draw_id)) as c:
            return (await c.fetchone())[0]

async def get_tickets_for_draw(draw_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tickets WHERE draw_id=?", (draw_id,)) as c:
            return [{**dict(r), "numbers": json.loads(r["numbers"] or "[]")} for r in await c.fetchall()]

async def get_user_tickets_history(user_id, limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.*, d.status as draw_status, d.drawn_numbers, d.is_bot_win
            FROM tickets t LEFT JOIN draws d ON t.draw_id=d.draw_id
            WHERE t.user_id=? ORDER BY t.created_at DESC LIMIT ?
        """, (user_id, limit)) as c:
            return [{**dict(r), "numbers": json.loads(r["numbers"] or "[]"),
                     "drawn_numbers": json.loads(r["drawn_numbers"] or "[]")} for r in await c.fetchall()]

async def update_draw_numbers(draw_id, drawn, step):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE draws SET drawn_numbers=?, draw_step=? WHERE draw_id=?", (json.dumps(drawn), step, draw_id))
        await db.commit()

async def set_draw_status(draw_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE draws SET status=? WHERE draw_id=?", (status, draw_id))
        await db.commit()

async def finish_draw(draw_id, winner_user_id, win_amount, is_bot_win):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE draws SET status='finished', winner_user_id=?, winner_amount=?, is_bot_win=? WHERE draw_id=?",
            (winner_user_id, win_amount, 1 if is_bot_win else 0, draw_id))
        if winner_user_id and not is_bot_win and win_amount > 0:
            await db.execute("UPDATE tickets SET is_winner=1, win_amount=? WHERE draw_id=? AND user_id=?",
                             (win_amount, draw_id, winner_user_id))
        await db.commit()

async def set_ticket_matches(ticket_id, matches):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tickets SET matches=? WHERE id=?", (matches, ticket_id))
        await db.commit()

async def get_draw_participants(draw_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT DISTINCT user_id FROM tickets WHERE draw_id=?", (draw_id,)) as c:
            return [dict(r) for r in await c.fetchall()]

async def create_withdraw_request(user_id, amount, fee, net_amount, card_number, card_holder):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO withdraw_requests (user_id,amount,fee,net_amount,card_number,card_holder,created_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, amount, fee, net_amount, card_number, card_holder, time.time()))
        await db.commit(); return cur.lastrowid

async def get_pending_withdraws():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdraw_requests WHERE status='pending' ORDER BY created_at") as c:
            return [dict(r) for r in await c.fetchall()]

async def get_all_users(limit=50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY last_active DESC LIMIT ?", (limit,)) as c:
            return [dict(r) for r in await c.fetchall()]

async def get_heavy_losers(min_loss=5000):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE total_lost - total_won > ? ORDER BY (total_lost-total_won) DESC LIMIT 20", (min_loss,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]
