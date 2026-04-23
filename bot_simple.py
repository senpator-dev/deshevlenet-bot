import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==============================
# Укажи здесь свои данные
TOKEN = "8794525614:AAHieX4XlvtVhH2flA9KiTxyfNZQAvJ3RlY"
GROUP_ID = -1003721350098  # Замени на свой ID (должен начинаться с -100)
THREAD_ID = 1            # Замени на ID темы, иначе уйдет в "General"
# ==============================

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Приветствие юзеру
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        f"Скинь ссылку на товар - купим на 20% дешевле.\n"
        f"Работаем с Wildberries, Ozon и любыми другими магазинами.\n\n"
    )

    # Отправка в группу в конкретную тему
    await context.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=THREAD_ID, 
        text=(
            f"🔔 Новый клиент написал /start\n\n"
            f"👤 {user.first_name} {user.last_name or ''}\n"
            f"🆔 ID: {user.id}\n"
            f"🔗 @{user.username or 'нет username'}\n\n"
            f"Написать ему: tg://user?id={user.id}"
        )
    )

def main():
    # Передаем переменную TOKEN, в которой лежит твой ключ
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()