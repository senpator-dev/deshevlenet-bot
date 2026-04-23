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

def send_pixel_event(user_id, event_name, user_data=None):
    """Отправка события в Facebook Conversions API"""
    if not PIXEL_ID or not ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v18.0/{PIXEL_ID}/events"
    external_id = hashlib.sha256(str(user_id).encode()).hexdigest()
    data = {
        "data": [{
            "event_name": event_name,
            "event_time": int(time.time()),
            "action_source": "chat",
            "user_data": {"external_id": [external_id]},
            "custom_data": user_data or {}
        }],
        "access_token": ACCESS_TOKEN
    }
    try:
        requests.post(url, json=data, timeout=5)
    except Exception as e:
        logging.error(f"Pixel Error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.HTML)
    
    # Трекинг события Lead в Facebook
    send_pixel_event(user.id, "Lead", {"content_name": "Start Bot"})

    # Создание топика в группе
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
        logging.error(f"Topic Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Юзер -> Группа"""
    if not update.message or update.message.chat.type != "private": return
    user = update.effective_user
    thread_id = context.bot_data.get(f"topic_{user.id}")

    if not thread_id:
        topic = await context.bot.create_forum_topic(chat_id=GROUP_ID, name=f"{user.first_name} ({user.id})")
        thread_id = topic.message_thread_id
        context.bot_data[f"topic_{user.id}"] = thread_id
        context.bot_data[f"user_{thread_id}"] = user.id

    await update.message.forward(chat_id=GROUP_ID, message_thread_id=thread_id)
    # Трекинг события контакта
    send_pixel_event(user.id, "Contact")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ -> Юзер"""
    if not update.message.reply_to_message or update.message.chat_id != GROUP_ID: return
    thread_id = update.message.message_thread_id
    user_id = context.bot_data.get(f"user_{thread_id}")
    if user_id:
        await context.bot.copy_message(chat_id=user_id, from_chat_id=GROUP_ID, message_id=update.message.message_id)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID) & filters.REPLY, handle_admin_reply))
    app.run_polling()

if __name__ == "__main__":
    main()
