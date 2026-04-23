async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # ПРИВЕТСТВИЕ ЮЗЕРУ УДАЛЕНО, чтобы не дублировать Livegram

    # Отправка уведомления только тебе в группу/тему
    await context.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=THREAD_ID, 
        text=(
            f"🔔 Новый контакт в боте!\n\n"
            f"👤 {user.first_name} {user.last_name or ''}\n"
            f"🆔 ID: {user.id}\n"
            f"🔗 @{user.username or 'нет username'}\n\n"
            f"Написать ему через Livegram или напрямую: tg://user?id={user.id}"
        )
    )
