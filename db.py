# db.py
import aiosqlite
import time
from typing import Optional, List, Dict, Any
from config import DB_PATH


async def init_db():
    # Qovluğun mövcud olduğundan əmin oluruq (Railway Volume üçün vacibdir)
    from pathlib import Path
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance REAL DEFAULT 0,
            total_won REAL DEFAULT 0,
            total_lost REAL DEFAULT 0,
            total_deposited REAL DEFAULT 0,
            total_withdrawn REAL DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            created_at REAL,
            last_active REAL
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            room_price INTEGER,
            interval_sec INTEGER,
            amount REAL,
            created_at REAL,
            draw_id TEXT,
            is_winner INTEGER DEFAULT 0,
            win_amount REAL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS draws (
            draw_id TEXT PRIMARY KEY,
            room_price INTEGER,
            interval_sec INTEGER,
            start_time REAL,
            end_time REAL,
            total_pot REAL DEFAULT 0,
            participants_count INTEGER DEFAULT 0,
            real_users_count INTEGER DEFAULT 0,
            winner_user_id INTEGER,
            winner_amount REAL DEFAULT 0,
            is_bot_win INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'  -- active, finished
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,          -- topup, withdraw, ticket, win, admin_add, admin_remove, fee
            amount REAL,
            description TEXT,
            created_at REAL,
            status TEXT DEFAULT 'done'  -- done, pending, rejected
        );

        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            fee REAL,
            net_amount REAL,
            card_number TEXT,
            card_holder TEXT,
            status TEXT DEFAULT 'pending',  -- pending, approved, rejected
            admin_note TEXT,
            created_at REAL,
            processed_at REAL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        await db.commit()


# ====================== USER ======================

async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_user(user_id: int, username: str = None, full_name: str = None):
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO users 
               (user_id, username, full_name, created_at, last_active) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, username, full_name, now, now)
        )
        await db.commit()


async def update_user_activity(user_id: int, username: str = None, full_name: str = None):
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        if username or full_name:
            await db.execute(
                """UPDATE users SET last_active = ?, username = COALESCE(?, username), 
                   full_name = COALESCE(?, full_name) WHERE user_id = ?""",
                (now, username, full_name, user_id)
            )
        else:
            await db.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (now, user_id))
        await db.commit()


async def change_balance(user_id: int, amount: float, tx_type: str, description: str = "") -> bool:
    """Balansı dəyişir. Müsbət = artır, mənfi = azaldır. Uğurlu olarsa True qaytarır."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            new_balance = row["balance"] + amount
            if new_balance < 0:
                return False

        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        
        # Statistikalar
        if tx_type == "win":
            await db.execute("UPDATE users SET total_won = total_won + ? WHERE user_id = ?", (amount, user_id))
        elif tx_type == "ticket":
            await db.execute("UPDATE users SET total_lost = total_lost + ? WHERE user_id = ?", (abs(amount), user_id))
        elif tx_type == "topup":
            await db.execute("UPDATE users SET total_deposited = total_deposited + ? WHERE user_id = ?", (amount, user_id))
        elif tx_type == "withdraw":
            await db.execute("UPDATE users SET total_withdrawn = total_withdrawn + ? WHERE user_id = ?", (abs(amount), user_id))

        await db.execute(
            """INSERT INTO transactions (user_id, type, amount, description, created_at) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, tx_type, amount, description, time.time())
        )
        await db.commit()
        return True


async def get_balance(user_id: int) -> float:
    user = await get_user(user_id)
    return user["balance"] if user else 0.0


# ====================== TICKETS & DRAWS ======================

async def add_ticket(user_id: int, room_price: int, interval_sec: int, draw_id: str) -> bool:
    """Bilet alır. Balans kifayət etməsə False."""
    ok = await change_balance(user_id, -room_price, "ticket", f"Bilet: {room_price} {room_price}saz")
    if not ok:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO tickets (user_id, room_price, interval_sec, amount, created_at, draw_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, room_price, interval_sec, room_price, time.time(), draw_id)
        )
        # Draw pot və participant sayını yenilə
        await db.execute(
            """UPDATE draws SET total_pot = total_pot + ?, participants_count = participants_count + 1
               WHERE draw_id = ?""",
            (room_price, draw_id)
        )
        await db.commit()
    return True


async def get_user_tickets_in_draw(user_id: int, draw_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM tickets WHERE user_id = ? AND draw_id = ?",
            (user_id, draw_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_or_create_active_draw(room_price: int, interval_sec: int) -> str:
    """Aktiv tiraj varsa qaytarır, yoxdursa yeni yaradır."""
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT draw_id FROM draws 
               WHERE room_price = ? AND interval_sec = ? AND status = 'active' AND end_time > ?
               ORDER BY end_time LIMIT 1""",
            (room_price, interval_sec, now)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return row["draw_id"]

        # Yeni tiraj yarat
        import uuid
        draw_id = str(uuid.uuid4())
        end_time = now + interval_sec
        await db.execute(
            """INSERT INTO draws (draw_id, room_price, interval_sec, start_time, end_time, status)
               VALUES (?, ?, ?, ?, ?, 'active')""",
            (draw_id, room_price, interval_sec, now, end_time)
        )
        await db.commit()
        return draw_id


async def get_draw(draw_id: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM draws WHERE draw_id = ?", (draw_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_draw_participants(draw_id: str) -> List[Dict]:
    """Unikal real istifadəçiləri qaytarır."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT DISTINCT user_id FROM tickets WHERE draw_id = ?""",
            (draw_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def finish_draw(draw_id: str, winner_user_id: Optional[int], win_amount: float, is_bot_win: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE draws SET status = 'finished', winner_user_id = ?, winner_amount = ?, is_bot_win = ?
               WHERE draw_id = ?""",
            (winner_user_id, win_amount, 1 if is_bot_win else 0, draw_id)
        )
        if winner_user_id and not is_bot_win and win_amount > 0:
            await db.execute(
                "UPDATE tickets SET is_winner = 1, win_amount = ? WHERE draw_id = ? AND user_id = ?",
                (win_amount, draw_id, winner_user_id)
            )
        await db.commit()


# ====================== WITHDRAW ======================

async def create_withdraw_request(user_id: int, amount: float, fee: float, net_amount: float,
                                  card_number: str, card_holder: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO withdraw_requests 
               (user_id, amount, fee, net_amount, card_number, card_holder, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, amount, fee, net_amount, card_number, card_holder, time.time())
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_withdraws() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM withdraw_requests WHERE status = 'pending' ORDER BY created_at"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ====================== ADMIN STATS ======================

async def get_all_users(limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY last_active DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_stats(user_id: int) -> Dict:
    user = await get_user(user_id)
    return user or {}
