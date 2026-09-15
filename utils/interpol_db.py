import aiosqlite
import time

DB_PATH = "interpol.db"

async def init_db():
    """Инициализация базы данных и создание таблиц, если они отсутствуют."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS interpol_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                evidence TEXT NOT NULL,
                reporter_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                public_message_id INTEGER,
                public_channel_id INTEGER,
                created_at INTEGER NOT NULL
            )
        ''')
        await db.commit()

async def add_record(
    user_id: int,
    reason: str,
    evidence: str,
    reporter_id: int,
    moderator_id: int,
    public_message_id: int = None,
    public_channel_id: int = None
) -> int:
    """Добавляет запись о нарушителе в базу данных и возвращает ID созданной записи."""
    created_at = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO interpol_records (
                user_id, reason, evidence, reporter_id, moderator_id, public_message_id, public_channel_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, reason, evidence, reporter_id, moderator_id, public_message_id, public_channel_id, created_at))
        await db.commit()
        return cursor.lastrowid

async def update_public_message(record_id: int, public_channel_id: int, public_message_id: int):
    """Обновляет информацию о сообщении публичной карточки нарушителя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE interpol_records
            SET public_channel_id = ?, public_message_id = ?
            WHERE id = ?
        ''', (public_channel_id, public_message_id, record_id))
        await db.commit()

async def remove_record(identifier: int) -> list:
    """
    Удаляет записи из базы данных по ID записи (id) или Discord ID нарушителя (user_id).
    Возвращает список словарей удаленных записей.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM interpol_records WHERE id = ? OR user_id = ?',
            (identifier, identifier)
        ) as cursor:
            rows = await cursor.fetchall()
            removed = [dict(row) for row in rows]

        if removed:
            await db.execute(
                'DELETE FROM interpol_records WHERE id = ? OR user_id = ?',
                (identifier, identifier)
            )
            await db.commit()

        return removed

async def get_records_by_target(identifier: int) -> list:
    """
    Возвращает список записей нарушителей, найденных по ID записи (id) или Discord ID нарушителя (user_id).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM interpol_records WHERE id = ? OR user_id = ? ORDER BY id DESC',
            (identifier, identifier)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_all_records() -> list:
    """Возвращает все записи нарушителей из базы данных, отсортированные по убыванию ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM interpol_records ORDER BY id DESC') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
