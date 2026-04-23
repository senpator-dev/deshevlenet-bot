import logging
import os  # Этот импорт обязателен
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==============================
# Теперь берем данные из Variables Railway
TOKEN = os.getenv("TOKEN")
# Преобразуем ID в числа, так как из переменных окружения они приходят как строки
GROUP_ID = int(os.getenv("GROUP_ID")) if os.getenv("GROUP_ID") else 0
THREAD_ID = int(os.getenv("THREAD_ID")) if os.getenv("THREAD_ID") else 1
# ==============================

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Отправка уведомления в группу
    await context.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=THREAD_ID, 
        text=(
            f"🔔 Новый клиент в боте!\n\n"
            f"👤 {user.first_name} {user.last_name or ''}\n"
            f"🆔 ID: {user.id}\n"
            f"🔗 @{user.username or 'нет username'}\n\n"
            f"Написать ему: tg://user?id={user.id}"
        )
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
