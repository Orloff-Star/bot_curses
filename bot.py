import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


async def send_media_message(chat_id: int, message_data: dict):
    """Универсальная функция отправки сообщения с медиа или без"""
    try:
        # Создаем клавиатуру если есть кнопка
        keyboard = None
        if message_data.get('button_text') and message_data.get('button_url'):
            builder = InlineKeyboardBuilder()
            builder.button(
                text=message_data['button_text'],
                url=message_data['button_url']
            )
            keyboard = builder.as_markup()

        # Отправляем сообщение в зависимости от типа медиа
        media_type = message_data.get('media_type')
        media_url = message_data.get('media_url')

        if media_type == 'photo' and media_url:
            await bot.send_photo(
                chat_id=chat_id,
                photo=media_url,
                caption=message_data['text'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        elif media_type == 'video' and media_url:
            await bot.send_video(
                chat_id=chat_id,
                video=media_url,
                caption=message_data['text'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        else:
            # Просто текстовое сообщение
            await bot.send_message(
                chat_id=chat_id,
                text=message_data['text'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка отправки медиа сообщения: {e}")
        return False


async def send_scheduled_welcome():
    """Отправка запланированных приветственных сообщений"""
    try:
        pending_messages = await db.get_pending_messages()
        logger.info(f"Найдено сообщений для отправки: {len(pending_messages)}")

        for message in pending_messages:
            message_id, user_id, message_stage, username = message

            if message_stage < len(db.WELCOME_MESSAGES):
                msg_data = db.WELCOME_MESSAGES[message_stage]

                # Отправляем сообщение
                success = await send_media_message(user_id, msg_data)

                if success:
                    # Отмечаем сообщение как отправленное
                    await db.mark_message_sent(message_id)
                    await db.update_welcome_stage(user_id, message_stage)
                    logger.info(f"✅ Отправлено сообщение {message_stage} пользователю {user_id}")
                else:
                    logger.error(f"❌ Не удалось отправить сообщение {message_stage} пользователю {user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка в send_scheduled_welcome: {e}")


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    try:
        user = message.from_user
        logger.info(f"🎯 /start от {user.id} ({user.first_name})")

        # Добавляем пользователя в базу
        await db.add_subscriber(user.id, user.username or "No username", user.first_name or "No name")

        # Отправляем первое сообщение сразу
        first_message = db.WELCOME_MESSAGES[0]
        await send_media_message(user.id, first_message)

        # Планируем остальные сообщения
        scheduled_count = 0
        for i, msg_data in enumerate(db.WELCOME_MESSAGES[1:], 1):
            await db.add_scheduled_message(user.id, i, msg_data["delay_minutes"])
            scheduled_count += 1

        await message.answer("✅ Вы успешно подписались! Ожидайте новые курсы 📚")
        logger.info(f"⏰ Запланировано {scheduled_count} сообщений для {user.id}")

    except Exception as e:
        logger.error(f"❌ Ошибка в /start: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = (
        "🤖 <b>IT Courses Bot - Помощь</b>\n\n"
        "Я присылаю лучшие курсы по программированию и ИИ.\n\n"
        "<b>Команды:</b>\n"
        "/start - подписаться на рассылку\n"
        "/help - эта справка\n"
        "/stats - статистика бота\n\n"
        "После подписки вы получите серию сообщений с курсами!"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показать статистику бота"""
    try:
        subscribers = await db.get_all_subscribers()
        pending_messages = await db.get_pending_messages()

        stats_text = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Подписчиков: {len(subscribers)}\n"
            f"📨 Ожидающих сообщений: {len(pending_messages)}\n"
            f"🕒 Сообщений в расписании: {len(db.WELCOME_MESSAGES)}"
        )
        await message.answer(stats_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await message.answer("❌ Ошибка получения статистики")


@dp.message()
async def handle_other_messages(message: types.Message):
    """Обработчик всех остальных сообщений"""
    await message.answer("Используйте /start для подписки или /help для справки")


async def main():
    """Основная функция запуска бота"""
    try:
        # Инициализируем базу данных
        await db.create_tables()
        logger.info("✅ База данных инициализирована")

        # Запускаем планировщик
        scheduler = AsyncIOScheduler()

        # Задача для приветственных сообщений (каждую минуту)
        scheduler.add_job(
            send_scheduled_welcome,
            'interval',
            minutes=1,
            id='welcome_messages'
        )

        # Задача для очистки старых сообщений (раз в день)
        scheduler.add_job(
            db.cleanup_old_messages,
            'interval',
            hours=24,
            id='cleanup'
        )

        scheduler.start()
        logger.info("✅ Планировщик запущен")

        # Запускаем бота
        logger.info("🚀 Бот запускается...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == "__main__":
    print("=" * 50)
    print("🤖 IT Courses Bot - Локальная версия")
    print("=" * 50)
    print("Команды:")
    print("/start - подписаться на рассылку")
    print("/help - справка по боту")
    print("/stats - статистика бота")
    print("=" * 50)
    print("💡 Для ручной рассылки запустите: python manual_mailing.py")
    print("=" * 50)

    asyncio.run(main())