import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

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

# ID администратора (замените на ваш user_id)
ADMIN_IDS = [1231038897]  # Замените на ваш user_id

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


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
    """Обработчик команды /start - показывает кнопку подписки"""
    user = message.from_user

    # Проверяем, является ли пользователь администратором
    if is_admin(user.id):
        # Показываем администратору панель управления
        admin_keyboard = ReplyKeyboardBuilder()
        admin_keyboard.button(text="📊 Статистика")
        admin_keyboard.button(text="📨 Сделать рассылку")
        admin_keyboard.button(text="💬 Просмотреть комментарии")
        admin_keyboard.adjust(2)

        await message.answer(
            "👋 Добро пожаловать в панель администратора!",
            reply_markup=admin_keyboard.as_markup(resize_keyboard=True)
        )
        return

    # Для обычных пользователей показываем кнопку подписки
    is_subscribed = await db.is_user_subscribed(user.id)

    if is_subscribed:
        # Если уже подписан, показываем информацию
        welcome_keyboard = ReplyKeyboardBuilder()
        welcome_keyboard.button(text="💬 Оставить комментарий")
        welcome_keyboard.button(text="📞 Связаться с поддержкой")

        await message.answer(
            "✅ Вы уже подписаны на рассылку!\n\n"
            "Вы будете получать уведомления о новых курсах автоматически.",
            reply_markup=welcome_keyboard.as_markup(resize_keyboard=True)
        )
    else:
        # Если не подписан, показываем кнопку подписки
        subscribe_keyboard = ReplyKeyboardBuilder()
        subscribe_keyboard.button(text="✅ Подписаться на рассылку")

        await message.answer(
            "👋 Добро пожаловать в IT Courses Bot!\n\n"
            "Подпишитесь на рассылку, чтобы получать лучшие курсы "
            "по программированию и искусственному интеллекту.",
            reply_markup=subscribe_keyboard.as_markup(resize_keyboard=True)
        )


@dp.message(F.text == "✅ Подписаться на рассылку")
async def subscribe_user(message: types.Message):
    """Обработчик подписки на рассылку"""
    user = message.from_user

    try:
        # Добавляем пользователя в базу
        await db.add_subscriber(user.id, user.username or "No username", user.first_name or "No name")

        # Отправляем первое приветственное сообщение сразу
        first_message = db.WELCOME_MESSAGES[0]
        await send_media_message(user.id, first_message)

        # Планируем остальные сообщения
        scheduled_count = 0
        for i, msg_data in enumerate(db.WELCOME_MESSAGES[1:], 1):
            await db.add_scheduled_message(user.id, i, msg_data["delay_minutes"])
            scheduled_count += 1

        # Меняем клавиатуру после подписки
        welcome_keyboard = ReplyKeyboardBuilder()
        welcome_keyboard.button(text="💬 Оставить комментарий")
        welcome_keyboard.button(text="📞 Связаться с поддержкой")

        await message.answer(
            "🎉 Отлично! Вы успешно подписались на рассылку!\n\n"
            "В ближайшее время вы получите подборки лучших IT-курсов. "
            "Оставайтесь на связи! 📚",
            reply_markup=welcome_keyboard.as_markup(resize_keyboard=True)
        )

        logger.info(f"✅ Пользователь {user.id} подписался на рассылку")

    except Exception as e:
        logger.error(f"❌ Ошибка при подписке пользователя {user.id}: {e}")
        await message.answer("❌ Произошла ошибка при подписке. Попробуйте позже.")


@dp.message(F.text == "💬 Оставить комментарий")
async def start_comment(message: types.Message):
    """Начало процесса комментирования"""
    user = message.from_user

    # Проверяем, подписан ли пользователь
    is_subscribed = await db.is_user_subscribed(user.id)

    if not is_subscribed:
        await message.answer("❌ Чтобы оставить комментарий, необходимо сначала подписаться на рассылку.")
        return

    await message.answer(
        "💬 Напишите ваш комментарий или отзыв:\n\n"
        "Мы ценим ваше мнение и учитываем все пожелания!"
    )


@dp.message(F.text == "📞 Связаться с поддержкой")
async def contact_support(message: types.Message):
    """Связь с поддержкой"""
    await message.answer(
        "📞 Связь с поддержкой:\n\n"
        "Если у вас возникли вопросы или проблемы, "
        "напишите нам на email: ii-sys@mail.ru\n\n"
        "Мы ответим в ближайшее время! ⏰"
    )


@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    """Показать статистику (только для администратора)"""
    user = message.from_user

    if not is_admin(user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    try:
        subscribers = await db.get_all_subscribers()
        all_users = await db.get_all_users()
        comments = await db.get_all_comments()

        stats_text = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Активных подписчиков: {len(subscribers)}\n"
            f"👤 Всего пользователей: {len(all_users)}\n"
            f"💬 Комментариев: {len(comments)}\n"
            f"🕒 Сообщений в расписании: {len(db.WELCOME_MESSAGES)}"
        )
        await message.answer(stats_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await message.answer("❌ Ошибка получения статистики")


@dp.message(F.text == "📨 Сделать рассылку")
async def start_mailing(message: types.Message):
    """Запуск ручной рассылки (только для администратора)"""
    user = message.from_user

    if not is_admin(user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    await message.answer(
        "📨 Для запуска рассылки выполните команду:\n\n"
        "<code>python manual_mailing.py</code>\n\n"
        "в отдельном окне терминала.",
        parse_mode=ParseMode.HTML
    )


@dp.message(F.text == "💬 Просмотреть комментарии")
async def show_comments(message: types.Message):
    """Просмотр комментариев (только для администратора)"""
    user = message.from_user

    if not is_admin(user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    try:
        comments = await db.get_all_comments()

        if not comments:
            await message.answer("📝 Комментариев пока нет.")
            return

        # Показываем последние 5 комментариев
        comments_text = "💬 <b>Последние комментарии:</b>\n\n"
        for i, comment in enumerate(comments[:5], 1):
            id, user_id, username, first_name, message_text, created_at = comment
            comments_text += (
                f"{i}. <b>{first_name}</b> (@{username})\n"
                f"   📝 {message_text}\n"
                f"   ⏰ {created_at}\n\n"
            )

        if len(comments) > 5:
            comments_text += f"... и еще {len(comments) - 5} комментариев"

        await message.answer(comments_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Ошибка получения комментариев: {e}")
        await message.answer("❌ Ошибка получения комментариев")


# Обработчик всех текстовых сообщений (для комментариев)
@dp.message(F.text)
async def handle_user_message(message: types.Message):
    """Обработчик всех текстовых сообщений от пользователей"""
    user = message.from_user

    # Проверяем, является ли пользователь администратором
    if is_admin(user.id):
        # Администраторы могут использовать команды через клавиатуру
        # Их сообщения не сохраняются как комментарии
        return

    # Проверяем, подписан ли пользователь
    is_subscribed = await db.is_user_subscribed(user.id)

    if not is_subscribed:
        # Если не подписан, показываем кнопку подписки
        subscribe_keyboard = ReplyKeyboardBuilder()
        subscribe_keyboard.button(text="✅ Подписаться на рассылку")

        await message.answer(
            "❌ Чтобы отправлять сообщения, необходимо подписаться на рассылку.",
            reply_markup=subscribe_keyboard.as_markup(resize_keyboard=True)
        )
        return

    # Сохраняем сообщение как комментарий
    try:
        await db.add_comment(
            user.id,
            user.username or "No username",
            user.first_name or "No name",
            message.text
        )

        await message.answer(
            "✅ Ваш комментарий сохранен!\n\n"
            "Спасибо за ваше мнение! Мы обязательно его учтем. 💫"
        )
        logger.info(f"💬 Сохранен комментарий от пользователя {user.id}")

    except Exception as e:
        logger.error(f"❌ Ошибка сохранения комментария: {e}")
        await message.answer("❌ Произошла ошибка при сохранении комментария.")


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
    print("🤖 IT Courses Bot - Обновленная версия")
    print("=" * 50)
    print("📋 Возможности:")
    print("• Кнопка подписки для новых пользователей")
    print("• Автоматическая рассылка курсов")
    print("• Комментарии от подписчиков")
    print("• Панель администратора")
    print("=" * 50)

    asyncio.run(main())