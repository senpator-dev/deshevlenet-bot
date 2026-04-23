import logging
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==============================
TOKEN = os.getenv("TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID")) if os.getenv("GROUP_ID") else 0
# ==============================

logging.basicConfig(level=logging.INFO)

# Приветственное сообщение
WELCOME_TEXT = (
    "<b>👋 Сделаем покупку на 20% дешевле?</b>\n\n"
    "Просто скидывай ссылку на товар или QR-код. Пока ты пьешь кофе <i>(минут 15)</i>, "
    "мы оформим <b>твою личную скидку.</b>\n\n"
    "<b>Работаем со всем:</b> от бензина до последних айфонов.\n\n"
    "Сложности с выбором? Напиши название — мы найдем, <b>выберем лучшее и скинем цену.</b>\n\n"
    "<b>Погнали? Деньги сами себя не сэкономят! 👇</b>"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # 1. Отправляем приветствие пользователю
    await update.message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.HTML)

    # 2. Создаем персональную тему в группе для этого юзера
    topic_name = f"{user.first_name} ({user.id})"
    try:
        topic = await context.bot.create_forum_topic(chat_id=GROUP_ID, name=topic_name)
        
        # 3. Уведомляем админов в новой теме
        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=topic.message_thread_id,
            text=(
                f"🔔 <b>Новый клиент!</b>\n\n"
                f"👤 {user.first_name} {user.last_name or ''}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"🔗 @{user.username or 'нет_username'}\n"
                f"────────────────────\n"
                f"Теперь все сообщения от юзера будут приходить сюда.\n"
                f"Чтобы ответить ему — просто пишите <b>ответом (Reply)</b> на его сообщение."
            ),
            parse_mode=ParseMode.HTML
        )
        
        # Сохраняем связь ID темы и ID юзера в памяти (на время работы бота)
        context.bot_data[f"topic_{user.id}"] = topic.message_thread_id
        context.bot_data[f"user_{topic.message_thread_id}"] = user.id

    except Exception as e:
        logging.error(f"Ошибка создания топика: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересылка сообщений: Юзер -> Группа (в нужный топик)"""
    user = update.effective_user
    if not update.message or update.message.chat.type != "private":
        return

    # Ищем ID темы для этого юзера
    thread_id = context.bot_data.get(f"topic_{user.id}")

    # Если топика нет (например, бот перезагрузился), создаем заново
    if not thread_id:
        topic = await context.bot.create_forum_topic(chat_id=GROUP_ID, name=f"{user.first_name} ({user.id})")
        thread_id = topic.message_thread_id
        context.bot_data[f"topic_{user.id}"] = thread_id
        context.bot_data[f"user_{thread_id}"] = user.id

    await update.message.forward(chat_id=GROUP_ID, message_thread_id=thread_id)

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересылка ответов: Админ в Группе -> Юзеру"""
    if not update.message.reply_to_message or update.message.chat_id != GROUP_ID:
        return

    thread_id = update.message.message_thread_id
    user_id = context.bot_data.get(f"user_{thread_id}")

    if user_id:
        try:
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=GROUP_ID,
                message_id=update.message.message_id
            )
        except Exception as e:
            logging.error(f"Ошибка отправки юзеру: {e}")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    
    # Хендлер для сообщений от юзеров (в личке)
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_message))
    
    # Хендлер для ответов админов (в группе)
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID) & filters.REPLY, handle_admin_reply))

    print("Бот-CRM запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
