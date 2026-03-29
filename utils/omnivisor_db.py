import aiosqlite

DB_PATH = "omnivisor.db" # База появится в корне проекта

async def init_db():
    """Создает таблицы, если их еще нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица основного досье
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dossier (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                nickname TEXT,
                created_at INTEGER,
                joined_at INTEGER,
                status TEXT DEFAULT 'Нет',
                source TEXT DEFAULT 'Вопроса не было',
                community_role TEXT DEFAULT 'Нет данных',
                suspicion_level TEXT DEFAULT '🟢Нет подозрений'
            )
        """)
        
        # Таблица комментариев
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                moderator_id INTEGER,
                note_text TEXT,
                timestamp INTEGER,
                FOREIGN KEY (user_id) REFERENCES dossier (user_id)
            )
        """)
        await db.commit()


async def sync_members(members_data: list):
    """Синхронизация списка участников с базой данных."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany("""
            INSERT OR IGNORE INTO dossier (user_id, username, nickname, created_at, joined_at)
            VALUES (?, ?, ?, ?, ?)
    """, members_data)
        await db.commit()

async def get_dossier(user_id: int):
    """Получает все данные об участнике из таблицы dossier."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Указываем, что хотим получать данные в виде словаря (по именам колонок)
        db.row_factory = aiosqlite.Row 
        async with db.execute("SELECT * FROM dossier WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
        
async def update_suspicion(user_id: int, level: str):
    """Обновляет уровень подозрительности в основной таблице."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE dossier SET suspicion_level = ? WHERE user_id = ?",
            (level, user_id)
        )
        await db.commit()

async def get_notes(user_id: int):
    """Получает все комментарии для пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Исправлено: ORDER BY timestamp DESC вместо created_at
        async with db.execute(
            "SELECT * FROM notes WHERE user_id = ? ORDER BY timestamp DESC", 
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()
        
async def add_note(user_id: int, moderator_id: int, note_text: str, timestamp: int):
    """Добавляет новый комментарий в досье."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO notes (user_id, moderator_id, note_text, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, moderator_id, note_text, timestamp)
        )
        await db.commit()

async def delete_note(note_id: int):
    """Удаляет комментарий по его ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
        await db.commit()

async def get_all_data_for_export():
    """Выгружает все досье и все заметки для экспорта."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        async with db.execute("SELECT * FROM dossier") as cursor:
            dossiers = [dict(row) for row in await cursor.fetchall()]
            
        # Сортируем заметки по времени (от старых к новым)
        async with db.execute("SELECT * FROM notes ORDER BY timestamp ASC") as cursor:
            notes = [dict(row) for row in await cursor.fetchall()]
            
        return dossiers, notes

async def update_nickname(user_id: int, new_nickname: str):
    """Обновляет никнейм участника в основном досье."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE dossier SET nickname = ? WHERE user_id = ?",
            (new_nickname, user_id)
        )
        await db.commit()

async def add_new_member(user_id: int, username: str, nickname: str, created_at: int, joined_at: int) -> str:
    """Добавляет новичка или обновляет возвращенца. Возвращает 'new' или 'returning'."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, есть ли уже такой юзер
        async with db.execute("SELECT 1 FROM dossier WHERE user_id = ?", (user_id,)) as cursor:
            exists = await cursor.fetchone()

        if not exists:
            # Новый участник
            await db.execute("""
                INSERT INTO dossier (user_id, username, nickname, created_at, joined_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, nickname, created_at, joined_at))
            result = 'new'
        else:
            # Старый участник (возвращенец)
            await db.execute("""
                UPDATE dossier 
                SET status = 'Нет', 
                    nickname = ?,
                    joined_at = CASE WHEN joined_at = 0 THEN ? ELSE joined_at END
                WHERE user_id = ?
            """, (nickname, joined_at, user_id))
            result = 'returning'
            
        await db.commit()
        return result

async def update_field(user_id: int, field: str, value: str):
    """Универсальная функция для обновления текстовых полей (например, роли в сообществе)."""
    async with aiosqlite.connect(DB_PATH) as db:
        # field жестко задается в коде бота, так что это безопасно
        await db.execute(f"UPDATE dossier SET {field} = ? WHERE user_id = ?", (value, user_id))
        await db.commit()

async def sync_banned_users(bans_data: list):
    """Синхронизирует забаненных пользователей."""
    async with aiosqlite.connect(DB_PATH) as db:
        for user_id, username, created_at in bans_data:
            # Если юзера не было, создаем с нулями и статусом Бан
            await db.execute("""
                INSERT OR IGNORE INTO dossier (user_id, username, nickname, created_at, joined_at, status)
                VALUES (?, ?, 'Отсутствует', ?, 0, 'Бан')
            """, (user_id, username, created_at))
            # Если юзер был, просто ставим статус Бан
            await db.execute("UPDATE dossier SET status = 'Бан' WHERE user_id = ?", (user_id,))
        await db.commit()