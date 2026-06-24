import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
import config
from database import SessionLocal, Application
from keyboards import get_moderation_keys
from states import CastingForm
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

print("=" * 50)
print("🚀 БОТ ДЛЯ КАСТИНГА ЗАПУЩЕН!")
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
        "1️⃣ Твоё имя и фамилия или кличка (прозвище)\n"
        "2️⃣ Возраст\n"
        "3️⃣ Город (не обязательно)\n"
        "4️⃣ **Видео-визитка** (пришли видеофайлом)\n\n"
        "Готов? Напиши своё **Имя или Кличку**:",
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
    await message.answer("📍 Из какого ты города? (можно пропустить, напиши 'нет')")
    await state.set_state(CastingForm.waiting_for_city)

# ============================================
# 4. ПОЛУЧЕНИЕ ГОРОДА
# ============================================
@dp.message(CastingForm.waiting_for_city)
async def get_city(message: Message, state: FSMContext):
    city = message.text
    if city.lower() in ["нет", "пропустить", "-"]:
        city = "Не указан"
    await state.update_data(city=city)
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
    if not message.video:
        await message.answer(
            "❌ Это не видео!\n"
            "Пожалуйста, отправь видео-файл (MP4, AVI и т.д.)"
        )
        return
    
    video = message.video
    file_id = video.file_id
    
    print(f"🎥 Получено видео: {video.file_size} байт, {video.duration} сек")
    
    data = await state.get_data()
    
    # Ссылка на пользователя
    user_id = message.from_user.id
    username = message.from_user.username
    user_link = f"@{username}" if username else f"[Пользователь](tg://user?id={user_id})"
    user_username = username if username else "Не указан"
    
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
    
    # Отправляем заявку модераторам
    text = (
        f"🔔 **НОВАЯ ЗАЯВКА #{app_id}**\n"
        f"👤 Имя: {data['name']}\n"
        f"📅 Возраст: {data['age']}\n"
        f"📍 Город: {data['city']}\n"
        f"🆔 От: {user_link}\n"
        f"📹 Видео прикреплено ниже\n\n"
        f"📌 **Что дальше?**\n"
        f"1️⃣ Посмотрите видео\n"
        f"2️⃣ Примите решение: Одобрить или Отклонить"
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
        "Модераторы посмотрят твоё видео и примут решение.\n"
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
    session.close()
    
    # Обновляем сообщение в группе
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ **ЗАЯВКА ОДОБРЕНА**",
        parse_mode="Markdown",
        reply_markup=None
    )
    
    # Уведомляем пользователя
    try:
        user_link = f"[{app.name}](tg://user?id={app.user_id})"
        await bot.send_message(
            app.user_id,
            f"🎉 **Поздравляем, {user_link}!**\n\n"
            f"Твоя заявка #{app_id} одобрена!\n\n"
            f"📌 Твоё видео прошло отбор.\n"
            f"Следи за новостями! 👀",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Не удалось уведомить пользователя: {e}")
    
    await callback.answer("✅ Заявка одобрена!")

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
            caption=callback.message.caption + "\n\n❌ **ЗАЯВКА ОТКЛОНЕНА**",
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
# 9. СТАТИСТИКА (только для админов)
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
# 10. КОМАНДА ДЛЯ АДМИНОВ: ПОСМОТРЕТЬ ВИДЕО
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
# 11. ВЕБ-СЕРВЕР ДЛЯ HEALTH CHECK (для Render)
# ============================================
async def health_check(request):
    return web.Response(text="✅ Бот работает!")

async def start_web_server():
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
# 12. ЗАПУСК БОТА
# ============================================
async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook сброшен")
    print("🔄 Бот готов к работе!")
    print("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹ Бот остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
