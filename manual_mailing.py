import asyncio
import os
import sys
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Добавляем путь для импорта database
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import database as db

# Загрузка переменных окружения
load_dotenv()


async def send_media_message(bot: Bot, chat_id: int, message_data: dict):
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

        print(f"📤 Отправка пользователю {chat_id}: тип={media_type}, URL={media_url}")

        # Если указан video, но URL не работает, отправляем как текст с пояснением
        if media_type == 'video':
            try:
                await bot.send_video(
                    chat_id=chat_id,
                    video=media_url,
                    caption=message_data['text'],
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
                return True
            except Exception as video_error:
                print(f"⚠️ Не удалось отправить видео, пробую отправить как фото: {video_error}")
                # Пробуем отправить как фото с другим URL
                try:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo="https://picsum.photos/800/600",
                        caption=f"🎬 {message_data['text']}\n\n(Видео временно недоступно)",
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                    return True
                except Exception as photo_error:
                    print(f"❌ Не удалось отправить и фото: {photo_error}")
                    # Отправляем просто текст
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message_data['text'],
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                    return True

        elif media_type == 'photo' and media_url:
            await bot.send_photo(
                chat_id=chat_id,
                photo=media_url,
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
        print(f"❌ Ошибка отправки пользователю {chat_id}: {e}")
        # Пробуем отправить просто текстовое сообщение без медиа
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message_data['text'],
                parse_mode=ParseMode.HTML
            )
            print(f"✅ Отправлен текст без медиа пользователю {chat_id}")
            return True
        except Exception as text_error:
            print(f"❌ Не удалось отправить даже текст пользователю {chat_id}: {text_error}")
            return False


async def manual_mailing(template=None):
    """Ручная рассылка всем подписчикам с поддержкой медиа"""
    # Проверяем токен бота
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден в .env файле")
        return

    # Инициализируем базу данных
    await db.create_tables()
    print("✅ База данных инициализирована")

    bot = Bot(token=BOT_TOKEN)

    try:
        # Получаем всех подписчиков
        subscribers = await db.get_all_subscribers()
        print(f"📋 Найдено подписчиков: {len(subscribers)}")

        if not subscribers:
            print("❌ Нет подписчиков для рассылки")
            return

        # Данные для рассылки (по умолчанию или переданный шаблон)
        if template is None:
            mailing_data = {
                "text": """🔥 <b>НОВЫЙ КУРС ПО MACHINE LEARNING!</b>

🎯 Освойте одну из самых востребованных профессий 2024 года!

✅ Практические навыки ML и AI
✅ Реальные проекты в портфолио  
✅ Поддержка опытного ментора
✅ Сертификат о завершении

🚀 Не упустите шанс стать специалистом в области ИИ!""",

                # Используем фото по умолчанию (более надежно)
                "media_type": "photo",
                "media_url": "https://picsum.photos/800/600",

                "button_text": "🚀 Записаться на курс",
                "button_url": "https://example.com/ml-course"
            }
        else:
            mailing_data = template

        print("=" * 50)
        print("📨 НАСТРОЙКИ РАССЫЛКИ:")
        print(f"Текст: {mailing_data['text'][:100]}...")
        print(f"Тип медиа: {mailing_data.get('media_type', 'Текст')}")
        print(f"URL медиа: {mailing_data.get('media_url', 'Не указан')}")
        print(f"Кнопка: {mailing_data.get('button_text', 'Нет')}")
        print(f"Ссылка кнопки: {mailing_data.get('button_url', 'Нет')}")
        print("=" * 50)

        # Подтверждение
        confirm = input("✅ Начать рассылку? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Рассылка отменена")
            return

        print("🔄 Начинаю рассылку...")

        success_count = 0
        for user_id in subscribers:
            try:
                success = await send_media_message(bot, user_id, mailing_data)
                if success:
                    success_count += 1
                    print(f"✅ Отправлено пользователю {user_id}")
                else:
                    print(f"❌ Ошибка у пользователя {user_id}")

                # Небольшая задержка чтобы не превысить лимиты Telegram
                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"❌ Критическая ошибка у пользователя {user_id}: {e}")

        print("=" * 50)
        print(f"📊 РАССЫЛКА ЗАВЕРШЕНА!")
        print(f"✅ Успешно отправлено: {success_count}/{len(subscribers)}")
        print(f"❌ Не отправлено: {len(subscribers) - success_count}")
        print("=" * 50)

    except Exception as e:
        print(f"❌ Ошибка при рассылке: {e}")
    finally:
        await bot.session.close()


def edit_mailing_template():
    """Функция для редактирования шаблона рассылки прямо в консоли"""
    print("✏️  РЕДАКТИРОВАНИЕ ШАБЛОНА РАССЫЛКИ")
    print("=" * 50)

    # Текущий шаблон с надежными настройками по умолчанию
    template = {
        "text": """🔥 <b>НОВЫЙ КУРС ПО MACHINE LEARNING!</b>

🎯 Освойте одну из самых востребованных профессий 2024 года!

✅ Практические навыки ML и AI
✅ Реальные проекты в портфолио  
✅ Поддержка опытного ментора
✅ Сертификат о завершении

🚀 Не упустите шанс стать специалистом в области ИИ!""",

        "media_type": "photo",  # Фото по умолчанию (более надежно)
        "media_url": "https://picsum.photos/800/600",  # Рабочий URL по умолчанию

        "button_text": "🚀 Записаться на курс",
        "button_url": "https://example.com/ml-course"
    }

    print("Текущий текст:")
    print(template["text"])
    print("\n" + "=" * 50)

    edit = input("Редактировать текст? (y/n): ")
    if edit.lower() == 'y':
        print("Введите новый текст (для завершения введите END на новой строке):")
        lines = []
        while True:
            line = input()
            if line.strip() == 'END':
                break
            lines.append(line)
        new_text = '\n'.join(lines)
        template["text"] = new_text

    print(f"\nТип медиа: {template['media_type']}")
    edit_media = input("Изменить тип медиа? (y/n): ")
    if edit_media.lower() == 'y':
        print("Доступные типы: photo, video")
        print("⚠️  Video может не работать с некоторыми URL")
        new_type = input("Новый тип: ").strip().lower()
        if new_type in ['photo', 'video']:
            template["media_type"] = new_type
            if template["media_type"] == 'photo':
                template["media_url"] = "https://picsum.photos/800/600"
                print("✅ Установлено стандартное фото")
            else:
                # Предлагаем надежные видео URL
                print("\nВыберите видео URL:")
                print("1 - Тестовое видео (может не работать)")
                print("2 - Без видео (отправить только текст)")
                video_choice = input("Ваш выбор: ")
                if video_choice == "1":
                    template[
                        "media_url"] = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
                else:
                    template["media_type"] = None
                    template["media_url"] = None

    print(f"\nТекст кнопки: {template['button_text']}")
    edit_button = input("Изменить кнопку? (y/n): ")
    if edit_button.lower() == 'y':
        new_button_text = input("Текст кнопки: ")
        template["button_text"] = new_button_text
        new_button_url = input("URL кнопки: ")
        template["button_url"] = new_button_url

    return template


async def manual_mailing_with_template(template):
    """Алиас для совместимости с существующим кодом"""
    await manual_mailing(template)


if __name__ == "__main__":
    print("=" * 50)
    print("📨 РУЧНАЯ РАССЫЛКА СООБЩЕНИЙ")
    print("=" * 50)

    # Даем выбор: редактировать шаблон или использовать готовый
    choice = input("Выберите действие:\n1 - Использовать готовый шаблон\n2 - Редактировать шаблон\nВаш выбор: ")

    if choice == "2":
        # Редактируем шаблон
        template = edit_mailing_template()
        asyncio.run(manual_mailing_with_template(template))
    else:
        # Используем готовый шаблон
        asyncio.run(manual_mailing())