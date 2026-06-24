import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
import config
from database import SessionLocal, Application, Vote
from keyboards import get_moderation_keys
from states import CastingForm

# ===== ДОБАВЛЯЕМ ДЛЯ ВЕБ-СЕРВЕРА =====
from aiohttp import web
import aiohttp
# ======================================

# Настройка логирования
logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

print("=" * 50)
print("🚀 БОТ ДЛЯ КАСТИНГА С ВИДЕО ЗАПУЩЕН!")
print("=" * 50)

# ============================================
# 1. КОМАНДА /start
# ============================================
@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    print(f"✅ Получена команда /start от {message.from_user.id}")
    await message.answer(
        "🎬 **Привет! Ты хочешь пройти кастинг?**\n\n"
        "📝 Я задам тебе несколько вопросов:\n"
        "1️⃣ Твоё имя и фамилия\n"
        "2️⃣ Возраст\n"
        "3️⃣ Город\n"
        "4️⃣ **Видео-визитка** (пришли видеофайлом)\n\n"
        "Готов? Напиши своё **Имя и Фамилию**:",
        parse_mode="Markdown"
    )
    await state.set_state(CastingForm.waiting_for_name)

# ============================================
# 2. ПОЛУЧЕНИЕ ИМЕНИ
# ============================================
@dp.message(CastingForm.waiting_for_name)
async def get_name(message: Message, state: FSMContext):
    print(f"📝 Получено имя: {message.text}")
    await state.update_data(name=message.text)
    await message.answer("📅 Сколько тебе лет? (Напиши число)")
    await state.set_state(CastingForm.waiting_for_age)

# ============================================
# 3. ПОЛУЧЕНИЕ ВОЗРАСТА
# ============================================
@dp.message(CastingForm.waiting_for_age)
async def get_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Пожалуйста, напиши число!")
        return
    await state.update_data(age=int(message.text))
    await message.answer("📍 Из какого ты города?")
    await state.set_state(CastingForm.waiting_for_city)

# ============================================
# 4. ПОЛУЧЕНИЕ ГОРОДА
# ============================================
@dp.message(CastingForm.waiting_for_city)
async def get_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer(
        "🎥 **Теперь самое важное!**\n\n"
        "Отправь **видео-файл** с твоей визиткой.\n"
        "Видео должно быть с твоей озвучкой.\n\n"
        "📤 Просто прикрепи видеофайл к сообщению:",
        parse_mode="Markdown"
    )
    await state.set_state(CastingForm.waiting_for_video)

# ============================================
# 5. ПОЛУЧЕНИЕ ВИДЕО И ОТПРАВКА ЗАЯВКИ
# ============================================
@dp.message(CastingForm.waiting_for_video)
async def get_video(message: Message, state: FSMContext):
    # Проверяем, что это видео
    if not message.video:
        await message.answer(
            "❌ Это не видео!\n"
            "Пожалуйста, отправь видео-файл (MP4, AVI и т.д.)"
        )
        return
    
    # Получаем данные о видео
    video = message.video
    file_id = video.file_id
    
    print(f"🎥 Получено видео: {video.file_size} байт, {video.duration} сек")
    
    # Сохраняем данные из состояния
    data = await state.get_data()
    
    # ===== СОЗДАЁМ ССЫЛКУ НА ПОЛЬЗОВАТЕЛЯ =====
    user_id = message.from_user.id
    username = message.from_user.username
    
    if username:
        user_link = f"@{username}"
        user_display = f"@{username}"
    else:
        user_link = f"[Пользователь](tg://user?id={user_id})"
        user_display = f"ID: {user_id}"
    
    user_username = username if username else "Не указан"
    # ============================================
    
    # Сохраняем в базу
    session = SessionLocal()
    new_app = Application(
        user_id=user_id,
        username=user_username,
        name=data['name'],
        age=data['age'],
        city=data['city'],
        video_file_id=file_id,
        status='pending'
    )
    session.add(new_app)
    session.commit()
    app_id = new_app.id
    session.close()
    
    # ===== ОТПРАВЛЯЕМ ЗАЯВКУ МОДЕРАТОРАМ =====
    text = (
        f"🔔 **НОВАЯ ЗАЯВКА #{app_id}**\n"
        f"👤 Имя: {data['name']}\n"
        f"📅 Возраст: {data['age']}\n"
        f"📍 Город: {data['city']}\n"
        f"🆔 От: {user_link}\n"
        f"📹 Видео прикреплено ниже"
    )
    
    await bot.send_video(
        chat_id=config.MODERATION_CHAT_ID,
        video=file_id,
        caption=text,
        reply_markup=get_moderation_keys(app_id),
        parse_mode="Markdown"
    )
    
    await message.answer(
        "✅ **Заявка отправлена на проверку!**\n\n"
        "Модераторы посмотрят твоё видео и дадут ответ.\n"
        "Жди уведомления в этом чате. Удачи! 🍀",
        parse_mode="Markdown"
    )
    await state.clear()

# ============================================
# 6. ОДОБРЕНИЕ ЗАЯВКИ
# ============================================
@dp.callback_query(F.data.startswith("approve_"))
async def approve_app(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[1])
    print(f"✅ Одобрена заявка #{app_id}")
    
    session = SessionLocal()
    app = session.query(Application).filter_by(id=app_id).first()
    
    if not app:
        await callback.answer("❌ Заявка не найдена!")
        return
    
    app.status = 'approved'
    session.commit()
    
    # ===== ФОРМИРУЕМ ТЕКСТ С ЮЗЕРНЕЙМОМ =====
    user_link = f"[{app.name}](tg://user?id={app.user_id})"
    
    if app.username and app.username != "Не указан":
        username_display = f"(@{app.username})"
    else:
        username_display = ""
    
    text_for_channel = (
        f"🎭 **Участник кастинга #{app.id}**\n"
        f"👤 {user_link} {username_display}\n"
        f"📅 {app.age} лет, г. {app.city}\n\n"
        f"📹 Видео-визитка участника\n\n"
        f"🗳 **Голосование будет проходить позже!**\n"
        f"Администраторы начнут опрос, и вы сможете проголосовать за того или иного участника.\n\n"
        f"Следите за новостями в канале! 👀"
    )
    # ==========================================
    
    # Отправляем видео в канал
    await bot.send_video(
        chat_id=config.CHANNEL_ID,
        video=app.video_file_id,
        caption=text_for_channel,
        parse_mode="Markdown"
    )
    
    session.close()
    
    # Обновляем сообщение модератора
    await callback.message.edit_caption(
        caption=callback.message.caption + f"\n\n✅ **ОДОБРЕНО И ОПУБЛИКОВАНО В КАНАЛЕ**\n🔗 {config.CHANNEL_LINK}",
        parse_mode="Markdown",
        reply_markup=None
    )
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            app.user_id,
            f"🎉 **Поздравляем, {user_link}!**\n\n"
            f"Твоя заявка #{app_id} одобрена!\n\n"
            f"👉 Твоё видео опубликовано в канале:\n"
            f"{config.CHANNEL_LINK}\n\n"
            f"🗳 Голосование начнётся позже, когда администраторы объявят опрос.\n"
            f"Следи за новостями! 👀",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Не удалось уведомить пользователя: {e}")
    
    await callback.answer("✅ Заявка опубликована в канале!")

# ============================================
# 7. ОТКЛОНЕНИЕ ЗАЯВКИ
# ============================================
@dp.callback_query(F.data.startswith("reject_"))
async def reject_app(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[1])
    print(f"❌ Отклонена заявка #{app_id}")
    
    session = SessionLocal()
    app = session.query(Application).filter_by(id=app_id).first()
    
    if app:
        app.status = 'rejected'
        session.commit()
        
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n❌ **ОТКЛОНЕНО**",
            parse_mode="Markdown",
            reply_markup=None
        )
        
        try:
            await bot.send_message(
                app.user_id,
                f"❌ К сожалению, твоя заявка #{app_id} не прошла кастинг.\n"
                f"Не расстраивайся, попробуй в следующий раз! 💪",
                parse_mode="Markdown"
            )
        except:
            pass
    
    session.close()
    await callback.answer("Заявка отклонена.")

# ============================================
# 8. УДАЛЕНИЕ СООБЩЕНИЯ
# ============================================
@dp.callback_query(F.data.startswith("delete_"))
async def delete_app(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("🗑 Сообщение удалено.")

# ============================================
# 9. ГОЛОСОВАНИЕ
# ============================================
@dp.message(F.text.lower().startswith("голосую за"))
async def handle_vote(message: Message):
    try:
        parts = message.text.split()
        app_id = int(parts[2])
    except:
        await message.answer(
            "❌ Напиши: `Голосую за 1`\n"
            "(где 1 - номер участника из канала)",
            parse_mode="Markdown"
        )
        return
    
    print(f"🗳 Голос от {message.from_user.id} за #{app_id}")
    
    session = SessionLocal()
    
    app = session.query(Application).filter_by(id=app_id, status='approved').first()
    if not app:
        await message.answer("❌ Участник с таким ID не найден.")
        session.close()
        return
    
    existing = session.query(Vote).filter_by(
        user_id=message.from_user.id,
        application_id=app_id
    ).first()
    
    if existing:
        await message.answer("⚠️ Ты уже голосовал за этого участника!")
        session.close()
        return
    
    new_vote = Vote(user_id=message.from_user.id, application_id=app_id)
    session.add(new_vote)
    session.commit()
    
    count = session.query(Vote).filter_by(application_id=app_id).count()
    session.close()
    
    await message.answer(
        f"✅ Твой голос засчитан!\n"
        f"Участник #{app_id} теперь имеет **{count}** голосов.",
        parse_mode="Markdown"
    )

# ============================================
# 10. СТАТИСТИКА (только для админов)
# ============================================
@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ У тебя нет прав для этой команды.")
        return
    
    session = SessionLocal()
    total = session.query(Application).count()
    approved = session.query(Application).filter_by(status='approved').count()
    pending = session.query(Application).filter_by(status='pending').count()
    session.close()
    
    await message.answer(
        f"📊 **Статистика кастинга:**\n"
        f"Всего заявок: {total}\n"
        f"Одобрено: {approved}\n"
        f"Ожидают проверки: {pending}",
        parse_mode="Markdown"
    )

# ============================================
# 11. КОМАНДА ДЛЯ АДМИНОВ: ПОСМОТРЕТЬ ВИДЕО
# ============================================
@dp.message(Command("video"))
async def get_video_by_id(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Нет прав.")
        return
    
    try:
        parts = message.text.split()
        app_id = int(parts[1])
    except:
        await message.answer("❌ Используй: `/video 5` (где 5 - ID заявки)", parse_mode="Markdown")
        return
    
    session = SessionLocal()
    app = session.query(Application).filter_by(id=app_id).first()
    
    if not app:
        await message.answer("❌ Заявка не найдена.")
        session.close()
        return
    
    if not app.video_file_id:
        await message.answer("❌ У заявки нет видео.")
        session.close()
        return
    
    await message.answer_video(
        video=app.video_file_id,
        caption=f"🎥 Видео участника #{app_id}\n👤 {app.name}"
    )
    session.close()

# ============================================
# 12. ВЕБ-СЕРВЕР ДЛЯ HEALTH CHECK (для Render)
# ============================================
async def health_check(request):
    """Эндпоинт для проверки, что бот жив"""
    return web.Response(text="✅ Бот работает!")

async def start_web_server():
    """Запускает веб-сервер на порту из переменной PORT"""
    port = int(os.environ.get('PORT', 10000))
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Веб-сервер для health check запущен на порту {port}")

# ============================================
# 13. ЗАПУСК БОТА
# ============================================
async def main():
    # Запускаем веб-сервер в фоне для health check
    await start_web_server()
    
    # Запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook сброшен")
    print("🔄 Бот готов к работе!")
    print("=" * 50)
    
    # Запускаем polling в бесконечном цикле
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹ Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
