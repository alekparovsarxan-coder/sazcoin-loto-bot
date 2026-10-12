# db.py
import aiosqlite
import time
import json
from typing import Optional, List, Dict, Any
from config import DB_PATH


async def init_db():
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
            amount REAL,
            numbers TEXT,
            created_at REAL,
            draw_id TEXT,
            is_winner INTEGER DEFAULT 0,
            win_amount REAL DEFAULT 0,
            matches INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS draws (
            draw_id TEXT PRIMARY KEY,
            room_price INTEGER,
            reg_start REAL,
            reg_end REAL,
            draw_start REAL,
            draw_end REAL,
            total_pot REAL DEFAULT 0,
            participants_count INTEGER DEFAULT 0,
            winner_user_id INTEGER,
            winner_amount REAL DEFAULT 0,
            is_bot_win INTEGER DEFAULT 0,
            drawn_numbers TEXT DEFAULT '[]',
            draw_step INTEGER DEFAULT 0,
            status TEXT DEFAULT 'registration'
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            description TEXT,
            created_at REAL,
            status TEXT DEFAULT 'done'
        );

        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            fee REAL,
            net_amount REAL,
            card_number TEXT,
            card_holder TEXT,
            status TEXT DEFAULT 'pending',
            admin_note TEXT,
            created_at REAL,
            processed_at REAL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS house_bank (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance REAL DEFAULT 0,
            total_in REAL DEFAULT 0,
            total_out REAL DEFAULT 0
        );
        """)
        await db.execute("INSERT OR IGNORE INTO house_bank (id, balance, total_in, total_out) VALUES (1, 0, 0, 0)")
        await db.commit()

        migrations = [
            "ALTER TABLE draws ADD COLUMN drawn_numbers TEXT DEFAULT '[]'",
            "ALTER TABLE draws ADD COLUMN draw_step INTEGER DEFAULT 0",
            "ALTER TABLE draws ADD COLUMN reg_start REAL",
            "ALTER TABLE draws ADD COLUMN reg_end REAL",
            "ALTER TABLE draws ADD COLUMN draw_start REAL",
            "ALTER TABLE draws ADD COLUMN draw_end REAL",
            "ALTER TABLE tickets ADD COLUMN numbers TEXT",
            "ALTER TABLE tickets ADD COLUMN matches INTEGER DEFAULT 0",
        ]
        for sql in migrations:
            try:
                await db.execute(sql)
                await db.commit()
            except Exception:
                pass


async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value)
        )
        await db.commit()


async def get_house_bank() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM house_bank WHERE id = 1") as cur:
            row = await cur.fetchone()
            return dict(row) if row else {"balance": 0, "total_in": 0, "total_out": 0}


async def house_add(amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE house_bank SET balance = balance + ?, total_in = total_in + ? WHERE id = 1",
            (amount, amount)
        )
        await db.commit()


async def house_pay(amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE house_bank SET balance = balance - ?, total_out = total_out + ? WHERE id = 1",
            (amount, amount)
        )
        await db.commit()


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
            """INSERT OR IGNORE INTO users (user_id, username, full_name, created_at, last_active) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, username, full_name, now, now)
        )
        await db.commit()


async def update_user_activity(user_id: int, username: str = None, full_name: str = None):
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE users SET last_active = ?, username = COALESCE(?, username), 
               full_name = COALESCE(?, full_name) WHERE user_id = ?""",
            (now, username, full_name, user_id)
        )
        await db.commit()


async def change_balance(user_id: int, amount: float, tx_type: str, description: str = "") -> bool:
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
        if tx_type == "win":
            await db.execute("UPDATE users SET total_won = total_won + ? WHERE user_id = ?", (amount, user_id))
        elif tx_type == "ticket":
            await db.execute("UPDATE users SET total_lost = total_lost + ? WHERE user_id = ?", (abs(amount), user_id))
        elif tx_type == "topup":
            await db.execute("UPDATE users SET total_deposited = total_deposited + ? WHERE user_id = ?", (amount, user_id))
        elif tx_type == "withdraw":
            await db.execute("UPDATE users SET total_withdrawn = total_withdrawn + ? WHERE user_id = ?", (abs(amount), user_id))
        await db.execute(
            "INSERT INTO transactions (user_id, type, amount, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, tx_type, amount, description, time.time())
        )
        await db.commit()
        return True


async def get_user_active_draw_price(user_id: int) -> Optional[int]:
    """Если пользователь уже купил билет в активном тираже — вернуть цену этого тиража."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT t.room_price FROM tickets t
            JOIN draws d ON t.draw_id = d.draw_id
            WHERE t.user_id = ? AND d.status IN ('registration', 'drawing')
            LIMIT 1
        """, (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def get_or_create_draw(room_price: int) -> str:
    """Цикл: 5 мин регистрация + 1 мин розыгрыш."""
    from config import REGISTRATION_SEC, DRAW_DURATION_SEC
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT draw_id FROM draws
            WHERE room_price = ? AND status IN ('registration', 'drawing')
            AND draw_end > ?
            ORDER BY reg_start DESC LIMIT 1
        """, (room_price, now)) as cur:
            row = await cur.fetchone()
            if row:
                return row["draw_id"]

        import uuid
        draw_id = str(uuid.uuid4())
        reg_start = now
        reg_end = now + REGISTRATION_SEC
        draw_start = reg_end
        draw_end = draw_start + DRAW_DURATION_SEC
        await db.execute("""
            INSERT INTO draws (draw_id, room_price, reg_start, reg_end, draw_start, draw_end,
                               status, drawn_numbers, draw_step, total_pot, participants_count)
            VALUES (?, ?, ?, ?, ?, ?, 'registration', '[]', 0, 0, 0)
        """, (draw_id, room_price, reg_start, reg_end, draw_start, draw_end))
        await db.commit()
        return draw_id


async def get_draw(draw_id: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM draws WHERE draw_id = ?", (draw_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["drawn_numbers"] = json.loads(d["drawn_numbers"]) if d.get("drawn_numbers") else []
            return d


async def get_active_draws() -> List[Dict]:
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM draws
            WHERE status IN ('registration', 'drawing') AND draw_end > ?
            ORDER BY room_price
        """, (now,)) as cur:
            rows = await cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["drawn_numbers"] = json.loads(d["drawn_numbers"]) if d.get("drawn_numbers") else []
                result.append(d)
            return result


async def add_tickets(user_id: int, room_price: int, draw_id: str, tickets_numbers: List[List[int]]) -> bool:
    total = room_price * len(tickets_numbers)
    ok = await change_balance(user_id, -total, "ticket", f"Билеты x{len(tickets_numbers)} по {room_price}")
    if not ok:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        for nums in tickets_numbers:
            await db.execute("""
                INSERT INTO tickets (user_id, room_price, amount, numbers, created_at, draw_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, room_price, room_price, json.dumps(nums), time.time(), draw_id))
        await db.execute("""
            UPDATE draws SET total_pot = total_pot + ?, participants_count = participants_count + ?
            WHERE draw_id = ?
        """, (total, len(tickets_numbers), draw_id))
        await db.commit()
    await house_add(total)
    return True


async def get_user_tickets_in_draw(user_id: int, draw_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM tickets WHERE user_id = ? AND draw_id = ?", (user_id, draw_id)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_tickets_for_draw(draw_id: str) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tickets WHERE draw_id = ?", (draw_id,)) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["numbers"] = json.loads(d["numbers"]) if d.get("numbers") else []
                result.append(d)
            return result


async def get_user_tickets_history(user_id: int, limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.*, d.status as draw_status, d.drawn_numbers, d.is_bot_win
            FROM tickets t LEFT JOIN draws d ON t.draw_id = d.draw_id
            WHERE t.user_id = ? ORDER BY t.created_at DESC LIMIT ?
        """, (user_id, limit)) as cur:
            rows = await cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["numbers"] = json.loads(d["numbers"]) if d.get("numbers") else []
                d["drawn_numbers"] = json.loads(d["drawn_numbers"]) if d.get("drawn_numbers") else []
                result.append(d)
            return result


async def update_draw_numbers(draw_id: str, drawn_numbers: list, step: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE draws SET drawn_numbers = ?, draw_step = ? WHERE draw_id = ?",
            (json.dumps(drawn_numbers), step, draw_id)
        )
        await db.commit()


async def set_draw_status(draw_id: str, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE draws SET status = ? WHERE draw_id = ?", (status, draw_id))
        await db.commit()


async def finish_draw(draw_id: str, winner_user_id: Optional[int], win_amount: float, is_bot_win: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE draws SET status = 'finished', winner_user_id = ?, winner_amount = ?, is_bot_win = ?
            WHERE draw_id = ?
        """, (winner_user_id, win_amount, 1 if is_bot_win else 0, draw_id))
        if winner_user_id and not is_bot_win and win_amount > 0:
            await db.execute(
                "UPDATE tickets SET is_winner = 1, win_amount = ? WHERE draw_id = ? AND user_id = ?",
                (win_amount, draw_id, winner_user_id)
            )
        await db.commit()


async def set_ticket_matches(ticket_id: int, matches: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tickets SET matches = ? WHERE id = ?", (matches, ticket_id))
        await db.commit()


async def get_draw_participants(draw_id: str) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT DISTINCT user_id FROM tickets WHERE draw_id = ?", (draw_id,)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def create_withdraw_request(user_id, amount, fee, net_amount, card_number, card_holder) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO withdraw_requests (user_id, amount, fee, net_amount, card_number, card_holder, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, amount, fee, net_amount, card_number, card_holder, time.time()))
        await db.commit()
        return cursor.lastrowid


async def get_pending_withdraws() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM withdraw_requests WHERE status = 'pending' ORDER BY created_at"
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_all_users(limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY last_active DESC LIMIT ?", (limit,)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]
