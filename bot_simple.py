import logging
import os
import requests
import time
import hashlib
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==============================
# НАСТРОЙКИ ИЗ VARIABLES RAILWAY
TOKEN = os.getenv("TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID")) if os.getenv("GROUP_ID") else 0
PIXEL_ID = os.getenv("PIXEL_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
# ==============================

logging.basicConfig(level=logging.INFO)

WELCOME_TEXT = (
    "<b>👋 Привет! Сделаем покупку на 20% дешевле?</b>\n\n"
    "Просто отправляй ссылку на товар или QR-код, "
    "всего за 15 минут мы оформим <b>твою личную скидку.</b>\n\n"
    "<b>Работаем со всем:</b> от бензина до последних айфонов.\n\n"
    "Сложности с выбором? Напиши название - мы найдем, <b>выберем лучшее и оплатим.</b>\n\n"
    "<b>Начинаем? Деньги сами себя не сэкономят! 👇</b>"
)

REMINDER_TEXT = (
    "⏰ <b>Привет! Мы ещё здесь!</b>\n\n"
    "Видим, что ты ещё не отправил товар 🤔\n\n"
    "Спеши! Отправляй ссылку или фото товара — "
    "мы <b>быстро найдём скидку и сэкономим твои деньги!</b> 💰\n\n"
    "<b>Вперёд, давай разберёмся вместе! 🚀</b>"
)

def send_pixel_lead(user_id):
    """Отправка события Lead в Facebook Conversions API"""
    if not PIXEL_ID or not ACCESS_TOKEN:
        logging.warning("PIXEL_ID или ACCESS_TOKEN не установлены")
        return
    
    url = f"https://graph.facebook.com/v18.0/{PIXEL_ID}/events"
    event_id = hashlib.sha256(f"{user_id}{time.time()}".encode()).hexdigest()
    
    # Хешируем external_id для безопасности (как рекомендует Meta)
    external_id_hashed = hashlib.sha256(str(user_id).encode()).hexdigest()
    
    data = {
        "data": [{
            "event_name": "Lead",
            "event_time": int(time.time()),
            "event_id": event_id,
            "action_source": "chat",
            "user_data": {
                "external_id": external_id_hashed,
            },
            "custom_data": {
                "content_name": "Bot Lead",
                "value": 0,
                "currency": "USD",
            }
        }],
        "access_token": ACCESS_TOKEN
    }
    
    try:
        response = requests.post(url, json=data, timeout=5)
        response.raise_for_status()
        logging.info(f"✅ Lead отправлен в Facebook для пользователя {user_id}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Ошибка пикселя: {e}")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминающего сообщения клиенту"""
    user_id = context.job.data
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=REMINDER_TEXT,
            parse_mode=ParseMode.HTML
        )
        logging.info(f"✅ Напоминание отправлено пользователю {user_id}")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки напоминания для {user_id}: {e}")

def schedule_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Запланировать напоминание на 2.5 часа (9000 секунд)"""
    # Удаляем старый job если он есть
    context.job_queue.scheduler.remove_job(f"reminder_{user_id}", None)
    
    # Добавляем новый job
    context.job_queue.run_once(
        send_reminder,
        when=9000,  # 2.5 часа = 9000 секунд
        data=user_id,
        job_id=f"reminder_{user_id}"
    )
    logging.info(f"⏲️ Напоминание запланировано для {user_id} на 2.5 часа")

def cancel_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Отменить напоминание для пользователя"""
    try:
        context.job_queue.scheduler.remove_job(f"reminder_{user_id}", None)
        logging.info(f"❌ Напоминание отменено для пользователя {user_id}")
    except:
        pass  # Job может не существовать, это нормально

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.HTML)
    
    # Отправляем Lead в Facebook
    send_pixel_lead(user.id)

    # Проверяем, существует ли уже ветка для этого юзера
    thread_id = context.bot_data.get(f"topic_{user.id}")
    
    if thread_id:
        # Ветка уже есть, не создаем новую
        # Но перезапланировываем напоминание
        schedule_reminder(context, user.id)
        return
    
    # Создание топика в группе (только если его нет)
    try:
        topic = await context.bot.create_forum_topic(chat_id=GROUP_ID, name=f"{user.first_name} ({user.id})")
        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic.message_thread_id,
            text=f"🔔 <b>Новый клиент!</b>\n\n👤 {user.first_name}\n🆔 ID: <code>{user.id}</code>\n🔗 @{user.username or 'нет'}\n\nЧтобы ответить — делай <b>Reply</b>.",
            parse_mode=ParseMode.HTML
        )
        context.bot_data[f"topic_{user.id}"] = topic.message_thread_id
        context.bot_data[f"user_{topic.message_thread_id}"] = user.id
    except Exception as e:
        logging.error(f"❌ Ошибка топика: {e}")
    
    # Запланировать напоминание через 2.5 часа
    schedule_reminder(context, user.id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Юзер -> Группа"""
    if not update.message or update.message.chat.type != "private": 
        return
    
    user = update.effective_user
    thread_id = context.bot_data.get(f"topic_{user.id}")

    # Отменяем напоминание, если клиент написал сообщение
    cancel_reminder(context, user.id)

    if not thread_id:
        topic = await context.bot.create_forum_topic(chat_id=GROUP_ID, name=f"{user.first_name} ({user.id})")
        thread_id = topic.message_thread_id
        context.bot_data[f"topic_{user.id}"] = thread_id
        context.bot_data[f"user_{thread_id}"] = user.id

    await update.message.forward(chat_id=GROUP_ID, message_thread_id=thread_id)

async def handle_group_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сообщение из группы -> Юзер"""
    if update.message.chat_id != GROUP_ID: 
        return
    
    # Игнорируем сообщения от бота (чтобы не было эхо)
    if update.message.from_user.is_bot:
        return
    
    thread_id = update.message.message_thread_id
    if not thread_id:  # если не в ветке, не отправляем
        return
    
    user_id = context.bot_data.get(f"user_{thread_id}")
    if user_id:
        # Отменяем напоминание, если админ написал клиенту
        cancel_reminder(context, user_id)
        
        await context.bot.copy_message(chat_id=user_id, from_chat_id=GROUP_ID, message_id=update.message.message_id)

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID), handle_group_to_user))
    
    app.run_polling()

if __name__ == "__main__":
    main()
