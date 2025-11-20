import aiosqlite
import logging

logger = logging.getLogger(__name__)

# Обновленная схема сообщений с поддержкой медиа
WELCOME_MESSAGES = [
    {
        "delay_minutes": 0,
        "text": "👋 Добро пожаловать в IT Courses Bot!\n\nЯ буду присылать вам лучшие курсы по программированию и ИИ. Оставайтесь на связи! 🚀",
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
    """Создание таблиц базы данных"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                welcome_stage INTEGER DEFAULT 0
            )
        ''')

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

        await db.commit()
    logger.info("Таблицы базы данных созданы/проверены")


async def add_subscriber(user_id: int, username: str, first_name: str):
    """Добавление нового подписчика"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute(
            """INSERT OR REPLACE INTO subscribers 
               (user_id, username, first_name, welcome_stage) 
               VALUES (?, ?, ?, 0)""",
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
    """Получение всех подписчиков"""
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute("SELECT user_id FROM subscribers")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def cleanup_old_messages():
    """Очистка старых отправленных сообщений"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute(
            "DELETE FROM scheduled_messages WHERE sent = TRUE AND created_at < datetime('now', '-7 days')"
        )
        await db.commit()
    logger.info("Очищены старые отправленные сообщения")