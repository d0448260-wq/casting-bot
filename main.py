import asyncio
import logging
import os
import gc
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
import config
from database import get_session, Application
from keyboards import get_moderation_keys
from states import CastingForm
from aiohttp import web

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

logger.info("=" * 50)
logger.info("🚀 ОПТИМИЗИРОВАННЫЙ БОТ ДЛЯ КАСТИНГА ЗАПУЩЕН!")
logger.info("=" * 50)

# ============================================
# 1. КОМАНДА /start
# ============================================
@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    logger.info(f"✅ Получена команда /start от {message.from_user.id}")
    await message.answer(
        "🎬 **Привет! Ты хочешь пройти кастинг?**\n\n"
        "📝 Я задам тебе несколько вопросов:\n"
        "1️⃣ Твоё имя и фамилия или кличка\n"
        "2️⃣ Возраст\n"
        "3️⃣ Город (не обязательно)\n"
        "4️⃣ Роль\n"
        "5️⃣ **Видео-визитка** (пришли видеофайлом)\n\n"
        "Готов? Напиши своё **Имя или Кличку**:",
        parse_mode="Markdown"
    )
    await state.set_state(CastingForm.waiting_for_name)

# ============================================
# 2. ПОЛУЧЕНИЕ ИМЕНИ
# ============================================
@dp.message(CastingForm.waiting_for_name)
async def get_name(message: Message, state: FSMContext):
    logger.info(f"📝 Получено имя: {message.text}")
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
        "🎭 **На какую роль ты хочешь пройти кастинг?**\n\n"
        "Напиши название роли или направления:\n",
        parse_mode="Markdown"
    )
    await state.set_state(CastingForm.waiting_for_role)

# ============================================
# 5. ПОЛУЧЕНИЕ РОЛИ
# ============================================
@dp.message(CastingForm.waiting_for_role)
async def get_role(message: Message, state: FSMContext):
    role = message.text.strip()
    if not role:
        role = "Не указана"
    await state.update_data(role=role)
    
    await message.answer(
        "🎥 **Теперь самое важное!**\n\n"
        "Отправь **видео-файл** с твоей визиткой.\n"
        "Видео должно быть с твоей озвучкой.\n\n"
        "📤 Просто прикрепи видеофайл к сообщению:",
        parse_mode="Markdown"
    )
    await state.set_state(CastingForm.waiting_for_video)

# ============================================
# 6. ПОЛУЧЕНИЕ ВИДЕО
# ============================================
@dp.message(CastingForm.waiting_for_video)
async def get_video(message: Message, state: FSMContext):
    if not message.video:
        await message.answer("❌ Это не видео! Отправь видео-файл.")
        return
    
    video = message.video
    file_id = video.file_id
    
    logger.info(f"🎥 Получено видео (file_id): {file_id[:20]}... ({video.file_size} байт, {video.duration} сек)")
    
    data = await state.get_data()
    
    user_id = message.from_user.id
    username = message.from_user.username
    user_link = f"@{username}" if username else f"[Пользователь](tg://user?id={user_id})"
    user_username = username if username else "Не указан"
    
    with get_session() as session:
        new_app = Application(
            user_id=user_id,
            username=user_username,
            name=data['name'],
            age=data['age'],
            city=data['city'],
            role=data.get('role', 'Не указана'),
            video_file_id=file_id,
            status='pending'
        )
        session.add(new_app)
        session.flush()
        app_id = new_app.id
    
    logger.info(f"📝 Заявка #{app_id} создана для пользователя {user_id}")
    
    text = (
        f"🔔 **НОВАЯ ЗАЯВКА #{app_id}**\n"
        f"👤 Имя: {data['name']}\n"
        f"📅 Возраст: {data['age']}\n"
        f"📍 Город: {data['city']}\n"
        f"🎭 Роль: {data.get('role', 'Не указана')}\n"
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
    
    logger.info(f"📤 Заявка #{app_id} отправлена в группу модерации")
    
    await message.answer("✅ **Заявка отправлена на проверку!** Жди решения.")
    await state.clear()
    
    gc.collect()
    logger.info(f"🧹 Память очищена после заявки #{app_id}")

# ============================================
# 7. ОДОБРЕНИЕ ЗАЯВКИ
# ============================================
@dp.callback_query(F.data.startswith("approve_"))
async def approve_app(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[1])
    logger.info(f"✅ Одобрена заявка #{app_id}")
    
    with get_session() as session:
        app = session.query(Application).filter_by(id=app_id).first()
        if not app:
            await callback.answer("❌ Заявка не найдена!")
            return
        
        app.status = 'approved'
        session.flush()
        
        user_id = app.user_id
        user_name = app.name
        user_username = app.username
        user_age = app.age
        user_city = app.city
        user_role = app.role
        video_file_id = app.video_file_id
        created_at = app.created_at
    
    logger.info(f"📝 Данные заявки #{app_id} сохранены: {user_name}")
    
    user_link = f"[{user_name}](tg://user?id={user_id})"
    username_display = f"(@{user_username})" if user_username and user_username != "Не указан" else ""
    
    review_text = (
        f"📋 **ГОТОВАЯ АНКЕТА**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎭 **Участник #{app_id}**\n"
        f"👤 {user_link} {username_display}\n"
        f"📅 Возраст: {user_age} лет\n"
        f"📍 Город: {user_city}\n"
        f"🎯 Роль: {user_role}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📹 Видео прикреплено ниже\n"
        f"📌 Статус: ✅ Одобрен\n"
        f"📅 Дата: {created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    
    await bot.send_video(
        chat_id=config.REVIEW_CHAT_ID,
        video=video_file_id,
        caption=review_text,
        parse_mode="Markdown"
    )
    
    logger.info(f"📤 Заявка #{app_id} отправлена в группу проверяющих")
    
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ **ЗАЯВКА ОДОБРЕНА**",
        parse_mode="Markdown",
        reply_markup=None
    )
    
    try:
        await bot.send_message(
            user_id,
            f"🎉 **Поздравляем!** Твоя заявка #{app_id} на роль *{user_role}* одобрена!",
            parse_mode="Markdown"
        )
        logger.info(f"📨 Уведомление отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления: {e}")
    
    await callback.answer("✅ Заявка одобрена!")
    gc.collect()
    logger.info(f"🧹 Память очищена после одобрения #{app_id}")

# ============================================
# 8. ОТКЛОНЕНИЕ ЗАЯВКИ
# ============================================
@dp.callback_query(F.data.startswith("reject_"))
async def reject_app(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[1])
    logger.info(f"❌ Отклонена заявка #{app_id}")
    
    with get_session() as session:
        app = session.query(Application).filter_by(id=app_id).first()
        if app:
            user_id = app.user_id
            app.status = 'rejected'
            session.flush()
            logger.info(f"📝 Статус заявки #{app_id} изменён на 'rejected'")
    
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n❌ **ЗАЯВКА ОТКЛОНЕНА**",
        parse_mode="Markdown",
        reply_markup=None
    )
    
    try:
        await bot.send_message(
            user_id,
            f"❌ К сожалению, твоя заявка #{app_id} не прошла кастинг.",
            parse_mode="Markdown"
        )
        logger.info(f"📨 Уведомление об отклонении отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления: {e}")
    
    await callback.answer("Заявка отклонена.")
    gc.collect()

# ============================================
# 9. УДАЛЕНИЕ СООБЩЕНИЯ
# ============================================
@dp.callback_query(F.data.startswith("delete_"))
async def delete_app(callback: CallbackQuery):
    await callback.message.delete()
    logger.info("🗑 Сообщение удалено")
    await callback.answer("🗑 Сообщение удалено.")
    gc.collect()

# ============================================
# 10. СТАТИСТИКА
# ============================================
@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Нет прав.")
        return
    
    with get_session() as session:
        total = session.query(Application).count()
        approved = session.query(Application).filter_by(status='approved').count()
        pending = session.query(Application).filter_by(status='pending').count()
    
    logger.info(f"📊 Статистика запрошена: всего {total}, одобрено {approved}, ожидают {pending}")
    
    await message.answer(
        f"📊 **Статистика:**\n"
        f"Всего: {total}\n"
        f"Одобрено: {approved}\n"
        f"Ожидают: {pending}",
        parse_mode="Markdown"
    )

# ============================================
# 11. КОМАНДА /video
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
        await message.answer("❌ Используй: `/video 5`", parse_mode="Markdown")
        return
    
    with get_session() as session:
        app = session.query(Application).filter_by(id=app_id).first()
        if not app:
            await message.answer("❌ Заявка не найдена.")
            return
        if not app.video_file_id:
            await message.answer("❌ У заявки нет видео.")
            return
        
        video_id = app.video_file_id
        user_name = app.name
    
    logger.info(f"🎥 Видео #{app_id} отправлено админу")
    
    await message.answer_video(
        video=video_id,
        caption=f"🎥 Видео участника #{app_id}\n👤 {user_name}"
    )

# ============================================
# 12. ВЕБ-СЕРВЕР
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
    logger.info(f"✅ Веб-сервер запущен на порту {port}")

# ============================================
# 13. ЗАПУСК
# ============================================
async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Webhook сброшен")
    logger.info("🔄 Бот готов к работе!")
    logger.info("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹ Бот остановлен")
    except Exception as e:
        logger.error(f"\n❌ Ошибка: {e}")
