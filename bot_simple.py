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

WELCOME_TEXT = (
    "Привет! 👋\n"
    "Хочешь пополниться со скидкой 20%?\n\n"
    "Выбирай площадку, а мы сделаем твой депозит дешевле всего за 15 минут! 🚀"
)
ASK_SUM_TEXT = "На какую сумму пополнение? 💵"
OPERATOR_TEXT = "Подключаем оператора... ⏳"

# Состояния чата
STATE_START = "START"
STATE_WAITING_SUM = "WAITING_SUM"
STATE_IN_CHAT = "IN_CHAT"

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
    # Используем bot_data для хранения связки топиков, чтобы данные не терялись при перезагрузке
    thread_id = context.bot_data.get(f"topic_{user.id}")
    
    if not thread_id:
        try:
            topic = await context.bot.create_forum_topic(chat_id=GROUP_ID, name=f"{user.first_name} | {platform}")
            thread_id = topic.message_thread_id
            context.bot_data[f"topic_{user.id}"] = thread_id
            context.bot_data[f"user_{thread_id}"] = user.id
            
            await context.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=thread_id,
                text=f"🔔 <b>Новая заявка!</b>\n👤 Юзер: @{user.username or 'скрыт'}\n🆔 ID: <code>{user.id}</code>\n🎯 Площадка: {platform}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Ошибка создания топика: {e}")
    return thread_id

# --- Обработчики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = STATE_START
    keyboard = [
        [InlineKeyboardButton("🟦 1XBET", callback_data="plat_1XBET")],
        [InlineKeyboardButton("🟥 FONBET", callback_data="plat_FONBET")],
        [InlineKeyboardButton("🟩 BETERA", callback_data="plat_BETERA")],
        [InlineKeyboardButton("⬜️ Другое", callback_data="plat_Other")]
    ]
    await update.message.reply_text(WELCOME_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))
    send_pixel_event(update.effective_user.id, "StartChat")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    platform = query.data.replace("plat_", "")
    await query.answer()
    
    # Создаем топик сразу при выборе площадки
    await create_admin_topic(update, context, platform)
    
    # Меняем статус — теперь бот ждет сумму
    context.user_data["state"] = STATE_WAITING_SUM
    
    await query.edit_message_text(ASK_SUM_TEXT)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != "private": return
    
    user = update.effective_user
    current_state = context.user_data.get("state")

    # Получаем или создаем топик
    thread_id = context.bot_data.get(f"topic_{user.id}")
    if not thread_id:
        thread_id = await create_admin_topic(update, context)

    # ЛОГИКА ПЕРЕХОДА НА ОПЕРАТОРА
    if current_state == STATE_WAITING_SUM:
        # Это первое сообщение после выбора площадки (сумма)
        await update.message.reply_text(OPERATOR_TEXT)
        context.user_data["state"] = STATE_IN_CHAT
        send_pixel_event(user.id, "Lead")
        
        # Уведомляем админа в топике, что юзер прислал сумму
        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=thread_id,
            text=f"💰 <b>Клиент указал сумму/реквизиты:</b>\n{update.message.text}",
            parse_mode=ParseMode.HTML
        )

    # Просто пересылаем сообщение в топик (для всех состояний)
    await update.message.forward(chat_id=GROUP_ID, message_thread_id=thread_id)

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Работаем только в группе и только в топиках
    if update.message.chat_id != GROUP_ID or not update.message.message_thread_id: return
    if update.message.from_user.is_bot: return
    
    thread_id = update.message.message_thread_id
    user_id = context.bot_data.get(f"user_{thread_id}")
    
    if user_id:
        # Копируем сообщение админа пользователю
        try:
            await context.bot.copy_message(
                chat_id=user_id, 
                from_chat_id=GROUP_ID, 
                message_id=update.message.message_id
            )
        except Exception as e:
            logging.error(f"Не удалось отправить ответ юзеру: {e}")

def main():
    # Используем Defaults для упрощения
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^plat_"))
    
    # Обработка сообщений от юзера (в личке)
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_user_message))
    
    # Обработка ответов админа (в группе)
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID), handle_admin_reply))
    
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
