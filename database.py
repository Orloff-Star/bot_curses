import aiosqlite
import logging

logger = logging.getLogger(__name__)

# Схема приветственных сообщений для новых подписчиков
WELCOME_MESSAGES = [
    {
        "delay_minutes": 0,
        "text": "👋 Добро пожаловать в IT Courses Bot!\n\nТеперь вы будете получать лучшие курсы по программированию и ИИ. Оставайтесь на связи! 🚀",
        "media_type": None,
        "media_url": None,
    },
    {
        "delay_minutes": 1,
        "text": "📚 Первая рекомендация!\n\nКурс 'Python для начинающих' - идеальный старт в программировании.\nОсвойте основы за 2 недели!",
        "media_type": "photo",
        "media_url": "https://picsum.photos/400/300?random=1",
        "button_text": "Посмотреть курс",
        "button_url": "https://example.com/python-course"
    },
    {
        "delay_minutes": 2,
        "text": "🤖 Вторая рекомендация!\n\nКурс 'Машинное обучение на Python' - станьте специалистом в ИИ!\nПрактические проекты и поддержка ментора.",
        "media_type": "photo",
        "media_url": "https://picsum.photos/400/300?random=2",
        "button_text": "Узнать подробнее",
        "button_url": "https://example.com/ml-course"
    },
    {
        "delay_minutes": 5,
        "text": "🚀 Специальное предложение!\n\nПолучите скидку 20% на все наши курсы по промокоду WELCOME20!\nНе упустите шанс начать карьеру в IT!",
        "media_type": "photo",
        "media_url": "https://picsum.photos/400/300?random=3",
        "button_text": "Получить скидку",
        "button_url": "https://example.com/special-offer"
    }
]


async def create_tables():
    """Создание таблиц базы данных с автоматической миграцией"""
    async with aiosqlite.connect('bot_database.db') as db:
        # Таблица подписчиков
        await db.execute('''
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                welcome_stage INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')

        # Таблица запланированных сообщений
        await db.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message_stage INTEGER,
                scheduled_for TIMESTAMP,
                sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица комментариев
        await db.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                message_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ✅ МИГРАЦИЯ: Добавляем столбец is_active если его нет
        try:
            await db.execute("ALTER TABLE subscribers ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
            logger.info("Миграция: добавлен столбец is_active")
        except aiosqlite.OperationalError as e:
            if "duplicate column name" in str(e):
                # Столбец уже существует - это нормально
                logger.debug("Столбец is_active уже существует")
            else:
                logger.warning(f"Ошибка при миграции is_active: {e}")

        await db.commit()
    logger.info("Таблицы базы данных созданы/проверены")


async def add_subscriber(user_id: int, username: str, first_name: str):
    """Добавление нового подписчика"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute(
            """INSERT OR REPLACE INTO subscribers 
               (user_id, username, first_name, welcome_stage, is_active) 
               VALUES (?, ?, ?, 0, TRUE)""",
            (user_id, username, first_name)
        )
        await db.commit()
    logger.info(f"Добавлен подписчик: {user_id}")


async def add_scheduled_message(user_id: int, message_stage: int, delay_minutes: int):
    """Добавление запланированного сообщения"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute(
            """INSERT INTO scheduled_messages 
               (user_id, message_stage, scheduled_for) 
               VALUES (?, ?, datetime('now', ?))""",
            (user_id, message_stage, f"+{delay_minutes} minutes")
        )
        await db.commit()


async def get_pending_messages():
    """Получение сообщений, готовых к отправке"""
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute('''
            SELECT sm.id, sm.user_id, sm.message_stage, s.username
            FROM scheduled_messages sm
            JOIN subscribers s ON sm.user_id = s.user_id
            WHERE sm.sent = FALSE AND sm.scheduled_for <= datetime('now')
            ORDER BY sm.scheduled_for ASC
        ''')
        rows = await cursor.fetchall()
        return rows


async def mark_message_sent(message_id: int):
    """Отметка сообщения как отправленного"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute(
            "UPDATE scheduled_messages SET sent = TRUE WHERE id = ?",
            (message_id,)
        )
        await db.commit()


async def update_welcome_stage(user_id: int, new_stage: int):
    """Обновление стадии приветственных сообщений"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute(
            "UPDATE subscribers SET welcome_stage = ? WHERE user_id = ?",
            (new_stage, user_id)
        )
        await db.commit()


async def get_all_subscribers():
    """Получение всех активных подписчиков"""
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute("SELECT user_id FROM subscribers WHERE is_active = TRUE")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_all_users():
    """Получение всех пользователей (включая неактивных)"""
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute("SELECT user_id, username, first_name, subscribed_at, is_active FROM subscribers")
        rows = await cursor.fetchall()
        return rows


async def is_user_subscribed(user_id: int):
    """Проверка, подписан ли пользователь"""
    async with aiosqlite.connect('bot_database.db') as db:
        try:
            cursor = await db.execute("SELECT user_id FROM subscribers WHERE user_id = ? AND is_active = TRUE",
                                      (user_id,))
            row = await cursor.fetchone()
            return row is not None
        except aiosqlite.OperationalError as e:
            if "no such column: is_active" in str(e):
                # Если столбца еще нет, используем старую логику
                logger.warning("Столбец is_active не найден, используем старую логику")
                cursor = await db.execute("SELECT user_id FROM subscribers WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                return row is not None
            else:
                raise


async def add_comment(user_id: int, username: str, first_name: str, message_text: str):
    """Добавление комментария от пользователя"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute(
            """INSERT INTO comments 
               (user_id, username, first_name, message_text) 
               VALUES (?, ?, ?, ?)""",
            (user_id, username, first_name, message_text)
        )
        await db.commit()
    logger.info(f"Добавлен комментарий от пользователя: {user_id}")


async def get_all_comments():
    """Получение всех комментариев"""
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute(
            "SELECT id, user_id, username, first_name, message_text, created_at FROM comments ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return rows


async def cleanup_old_messages():
    """Очистка старых отправленных сообщений"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute(
            "DELETE FROM scheduled_messages WHERE sent = TRUE AND created_at < datetime('now', '-7 days')"
        )
        await db.commit()
    logger.info("Очищены старые отправленные сообщения")