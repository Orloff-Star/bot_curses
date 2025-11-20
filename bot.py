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


async def send_scheduled_welcome():
    """Отправка запланированных приветственных сообщений"""
    try:
        pending_messages = await db.get_pending_messages()
        logger.info(f"Найдено сообщений для отправки: {len(pending_messages)}")

        for message in pending_messages:
            message_id, user_id, message_stage, username = message

            if message_stage < len(db.WELCOME_MESSAGES):
                msg_data = db.WELCOME_MESSAGES[message_stage]

                # Создаем клавиатуру с кнопкой если есть
                keyboard = None
                if msg_data.get('button_text') and msg_data.get('button_url'):
                    builder = InlineKeyboardBuilder()
                    builder.button(
                        text=msg_data['button_text'],
                        url=msg_data['button_url']
                    )
                    keyboard = builder.as_markup()

                try:
                    # Отправляем сообщение
                    await bot.send_message(
                        chat_id=user_id,
                        text=msg_data['text'],
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )

                    # Отмечаем сообщение как отправленное
                    await db.mark_message_sent(message_id)
                    await db.update_welcome_stage(user_id, message_stage)

                    logger.info(f"✅ Отправлено сообщение {message_stage} пользователю {user_id}")

                except Exception as e:
                    logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка в send_scheduled_welcome: {e}")


async def manual_mailing():
    """Функция для ручной рассылки всем подписчикам"""
    subscribers = await db.get_all_subscribers()

    # Пример сообщения для рассылки
    text = """🔥 <b>Новый курс по Machine Learning!</b>

Освойте одну из самых востребованных профессий!

🎯 Что вы получите:
• Практические навыки ML
• Реальные проекты в портфолио
• Поддержку ментора
• Сертификат о завершении

Не упустите шанс стать специалистом в области ИИ!"""

    # Создаем кнопку
    builder = InlineKeyboardBuilder()
    builder.button(text="Записаться на курс", url="https://example.com/ml-course")
    keyboard = builder.as_markup()

    success_count = 0
    for user_id in subscribers:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
            success_count += 1
            logger.info(f"✅ Рассылка отправлена пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")

    logger.info(f"📨 Рассылка завершена. Успешно отправлено: {success_count}/{len(subscribers)}")
    return success_count


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
        await message.answer(first_message["text"])

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
        "/stats - статистика бота\n"
        "/mailing - сделать рассылку (только для администратора)\n\n"
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


@dp.message(Command("mailing"))
async def cmd_mailing(message: types.Message):
    """Ручная рассылка (только для администратора)"""
    # Можно добавить проверку на администратора по user_id
    ADMIN_IDS = [1231038897]  # Замените на ваш user_id

    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для этой команды")
        return

    await message.answer("🔄 Начинаю рассылку...")
    success_count = await manual_mailing()
    await message.answer(f"✅ Рассылка завершена! Отправлено: {success_count}")


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
    print("/mailing - рассылка (для администратора)")
    print("=" * 50)

    asyncio.run(main())