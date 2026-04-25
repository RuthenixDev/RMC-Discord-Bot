import aiosqlite
import time

DB_PATH = "omnivisor.db"

async def init_db():
    """Создает таблицы для логов и синхронизации."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS action_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT,       -- Тип действия (Вход, Бан и т.д.)
                display_name TEXT,      -- Ник на сервере
                username TEXT,          -- Имя аккаунта (@handle)
                user_id INTEGER,        -- ID аккаунта
                timestamp INTEGER,      -- Дата действия
                joined_at INTEGER,      -- Дата захода на сервер
                moderator_id INTEGER,   -- Кто совершил действие (NULL если бот/система)
                reason TEXT             -- Причина
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sync_snapshot (
                action_type TEXT,
                display_name TEXT,
                username TEXT,
                user_id INTEGER PRIMARY KEY,
                created_at INTEGER,
                joined_at INTEGER,
                roles TEXT
            )
        ''')
        await db.commit()

async def log_action(action_type: str, display_name: str, username: str, user_id: int, timestamp: int = None, joined_at: int = 0, moderator_id: int = None, reason: str = "Не указана"):
    """Принимает данные: 
    action_type = , 
    display_name = , 
    username = , 
    user_id = , 
    timestamp = , 
    joined_at = , 
    moderator_id = , 
    reason = ,
    """
    if timestamp is None:
        timestamp = int(time.time())
        
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO action_logs (action_type, display_name, username, user_id, timestamp, joined_at, moderator_id, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (action_type, display_name, username, user_id, timestamp, joined_at, moderator_id, reason))
        await db.commit()

async def get_logs_for_export():
    """Получает все накопленные логи для выгрузки в Excel (Пункт 3)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM action_logs ORDER BY timestamp ASC') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def clear_action_logs():
    """Очищает базу данных логов после генерации отчета (Пункт 3)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM action_logs')
        await db.execute('DELETE FROM sqlite_sequence WHERE name="action_logs"')
        await db.commit()



async def sync_members(members_data: list):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM sync_snapshot')
        await db.executemany('''
            INSERT INTO sync_snapshot (action_type, display_name, username, user_id, created_at, joined_at, roles)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', members_data)
        await db.commit()

async def get_sync_snapshot():
    """Получает слепок сервера для выгрузки."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM sync_snapshot') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]