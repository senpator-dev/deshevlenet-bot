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

# Состояния
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

async def create_admin_topic(update: Update, context: ContextTypes.DEFAULT_TYPE, platform="Ожидает выбора..."):
    user = update.effective_user
    thread_id = context.bot_data.get(f"topic_{user.id}")
    
    if not thread_id:
        try:
            # Создаем топик ПРИ ПЕРВОМ КАСАНИИ (команда /start)
            topic = await context.bot.create_forum_topic(chat_id=GROUP_ID, name=f"{user.first_name} ({user.id})")
            thread_id = topic.message_thread_id
            context.bot_data[f"topic_{user.id}"] = thread_id
            context.bot_data[f"user_{thread_id}"] = user.id
            
            await context.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=thread_id,
                text=(
                    f"🔔 <b>Новая заявка создана!</b>\n\n"
                    f"👤 Юзер: {user.first_name}\n"
                    f"🔗 Логин: @{user.username or 'скрыт'}\n"
                    f"🆔 ID: <code>{user.id}</code>\n"
                    f"🎯 Статус: {platform}"
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Ошибка создания топика: {e}")
    return thread_id

# --- Обработчики ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["state"] = STATE_START
    
    # СОЗДАЕМ ЗАЯВКУ СРАЗУ ПРИ ЗАПУСКЕ БОТА
    await create_admin_topic(update, context)
    
    keyboard = [
        [InlineKeyboardButton("🟦 1XBET", callback_data="plat_1XBET")],
        [InlineKeyboardButton("🟥 FONBET", callback_data="plat_FONBET")],
        [InlineKeyboardButton("🟩 BETERA", callback_data="plat_BETERA")],
        [InlineKeyboardButton("⬜️ Другое", callback_data="plat_Other")]
    ]
    await update.message.reply_text(WELCOME_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))
    send_pixel_event(user.id, "StartChat")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    platform = query.data.replace("plat_", "")
    user = query.from_user
    await query.answer()
    
    # Находим существующий топик и обновляем в нем инфу о выборе площадки
    thread_id = context.bot_data.get(f"topic_{user.id}")
    if thread_id:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=thread_id,
            text=f"✅ <b>Клиент выбрал площадку:</b> {platform}",
            parse_mode=ParseMode.HTML
        )
    
    context.user_data["state"] = STATE_WAITING_SUM
    await query.edit_message_text(ASK_SUM_TEXT)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != "private": return
    
    user = update.effective_user
    current_state = context.user_data.get("state")
    thread_id = context.bot_data.get(f"topic_{user.id}")

    # Если топика почему-то нет (например, бот перезагрузился), создаем
    if not thread_id:
        thread_id = await create_admin_topic(update, context)

    # ЛОГИКА ПЕРЕХОДА НА ОПЕРАТОРА
    if current_state == STATE_WAITING_SUM:
        await update.message.reply_text(OPERATOR_TEXT)
        context.user_data["state"] = STATE_IN_CHAT
        send_pixel_event(user.id, "Lead")
        
        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=thread_id,
            text=f"💰 <b>Сумма/сообщение от клиента:</b>\n{update.message.text}",
            parse_mode=ParseMode.HTML
        )

    # Пересылка в топик админу
    await update.message.forward(chat_id=GROUP_ID, message_thread_id=thread_id)

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != GROUP_ID or not update.message.message_thread_id: return
    if update.message.from_user.is_bot: return
    
    thread_id = update.message.message_thread_id
    user_id = context.bot_data.get(f"user_{thread_id}")
    
    if user_id:
        try:
            await context.bot.copy_message(
                chat_id=user_id, 
                from_chat_id=GROUP_ID, 
                message_id=update.message.id
            )
        except: pass

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^plat_"))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_user_message))
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID), handle_admin_reply))
    
    app.run_polling()

if __name__ == "__main__":
    main()
