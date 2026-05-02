import logging
import os
import requests
import time
import hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CallbackQueryHandler
)

# ==============================
# НАСТРОЙКИ (RAILWAY VARIABLES)
TOKEN = os.getenv("TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID")) if os.getenv("GROUP_ID") else 0
PIXEL_ID = os.getenv("PIXEL_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
# ==============================

logging.basicConfig(level=logging.INFO)

# Тексты
WELCOME_TEXT = (
    "Привет! 👋\n"
    "Хочешь пополниться со скидкой 20%?\n\n"
    "Выбирай площадку, а мы сделаем твой депозит дешевле всего за 15 минут! 🚀"
)
ASK_SUM_TEXT = "На какую сумму пополнение? 💵"
REMINDER_TEXT = "Привет, ещё ждём твоего ответа! 😊"
OPERATOR_TEXT = "Подключаем оператора... ⏳"

# --- Вспомогательные функции ---

def send_pixel_event(user_id, event_name="Lead"):
    if not PIXEL_ID or not ACCESS_TOKEN: return
    url = f"https://graph.facebook.com/v18.0/{PIXEL_ID}/events"
    data = {
        "data": [{
            "event_name": event_name,
            "event_time": int(time.time()),
            "action_source": "chat",
            "user_data": {"external_id": hashlib.sha256(str(user_id).encode()).hexdigest()},
        }],
        "access_token": ACCESS_TOKEN
    }
    try: requests.post(url, json=data, timeout=5)
    except: pass

async def create_admin_topic(update: Update, context: ContextTypes.DEFAULT_TYPE, platform="Не выбрана"):
    user = update.effective_user
    thread_id = context.bot_data.get(f"topic_{user.id}")
    
    if not thread_id:
        try:
            # Создаем ветку в группе
            topic = await context.bot.create_forum_topic(chat_id=GROUP_ID, name=f"{user.first_name} | {platform}")
            thread_id = topic.message_thread_id
            context.bot_data[f"topic_{user.id}"] = thread_id
            context.bot_data[f"user_{thread_id}"] = user.id
            
            await context.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=thread_id,
                text=f"🔔 <b>Новое сообщение от @{user.username or 'NoUser'} - {user.first_name}</b>\nВыбранная площадка: {platform}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Ошибка создания топика: {e}")
    return thread_id

# --- Обработчики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Цветные кнопки через эмодзи-маркеры как в конструкторе
    keyboard = [
        [InlineKeyboardButton("1XBET", callback_data="plat_1XBET")],
        [InlineKeyboardButton("FONBET", callback_data="plat_FONBET")],
        [InlineKeyboardButton("BETERA", callback_data="plat_BETERA")],
        [InlineKeyboardButton("Другое", callback_data="plat_Other")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(WELCOME_TEXT, reply_markup=reply_markup)
    send_pixel_event(update.effective_user.id, "StartChat")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    platform = query.data.replace("plat_", "")
    
    await query.answer()
    
    # 1. Уведомление в админку (Действия 2)
    await create_admin_topic(update, context, platform)
    
    # 2. Запрос суммы
    await query.edit_message_text(ASK_SUM_TEXT)
    
    # Флаг, что мы ждем именно сумму
    context.user_data["waiting_for_sum"] = True
    
    # 3. Напоминание через 15 минут
    context.job_queue.run_once(send_reminder, 900, data=user_id, name=f"remind_{user_id}")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data
    try: await context.bot.send_message(chat_id=user_id, text=REMINDER_TEXT)
    except: pass

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != "private": return
    
    user = update.effective_user
    
    # Снимаем напоминание
    jobs = context.job_queue.get_jobs_by_name(f"remind_{user.id}")
    for job in jobs: job.schedule_removal()

    # Проверяем наличие топика
    thread_id = context.bot_data.get(f"topic_{user.id}")
    if not thread_id:
        thread_id = await create_admin_topic(update, context)

    # ЛОГИКА ПЕРЕХОДА НА ОПЕРАТОРА
    if context.user_data.get("waiting_for_sum"):
        await update.message.reply_text(OPERATOR_TEXT)
        context.user_data["waiting_for_sum"] = False # Сумма получена
        context.user_data["operator_mode"] = True
        send_pixel_event(user.id, "Lead")

    # Пересылка в админку
    await update.message.forward(chat_id=GROUP_ID, message_thread_id=thread_id)

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ответ только если сообщение в группе и внутри топика
    if update.message.chat_id != GROUP_ID or not update.message.message_thread_id: return
    if update.message.from_user.is_bot: return
    
    thread_id = update.message.message_thread_id
    user_id = context.bot_data.get(f"user_{thread_id}")
    
    if user_id:
        await context.bot.copy_message(chat_id=user_id, from_chat_id=GROUP_ID, message_id=update.message.message_id)

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^plat_"))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_user_message))
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID), handle_admin_reply))
    
    app.run_polling()

if __name__ == "__main__":
    main()
