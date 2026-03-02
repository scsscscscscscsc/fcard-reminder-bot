import logging
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен берется из переменных окружения Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

REMINDER_DELAY = 4200  # 1 час 10 минут

# Хранилище активных напоминаний (в памяти)
user_reminders = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для напоминаний о матчах в @F_CardBot 🎮\n\n"
        "Команды:\n"
        "/remind - запустить таймер на 1 час 10 минут\n"
        "/cancel - отменить текущее напоминание\n"
        "/status - проверить статус"
    )

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"Получена команда /remind от {chat_id}")

    if chat_id in user_reminders:
        keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel")]]
        await update.message.reply_text(
            "⚠️ У вас уже есть активное напоминание!\n"
            "Хотите отменить его и создать новое?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Удаляем старую задачу если была
    if 'reminder_job' in context.chat_data:
        context.chat_data['reminder_job'].schedule_removal()

    # Создаём новую задачу
    try:
        job = context.job_queue.run_once(
            send_reminder,
            REMINDER_DELAY,
            chat_id=chat_id,
            name=str(chat_id)
        )
        logger.info(f"Задача создана для {chat_id}, сработает через {REMINDER_DELAY} сек")
    except Exception as e:
        logger.error(f"Ошибка при создании задачи: {e}")
        await update.message.reply_text("❌ Не удалось создать напоминание.")
        return

    context.chat_data['reminder_job'] = job
    user_reminders[chat_id] = {
        'job': job,
        'start_time': datetime.now(),
        'remind_time': datetime.now() + timedelta(seconds=REMINDER_DELAY)
    }

    remind_time_str = (datetime.now() + timedelta(seconds=REMINDER_DELAY)).strftime("%H:%M:%S")
    keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel")]]
    await update.message.reply_text(
        f"✅ Напоминание установлено!\n"
        f"⏰ Я напомню тебе в {remind_time_str}\n"
        f"📝 Текст: Ребята, через час можно будет сыграть матч!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    logger.info(f"Сработал таймер для {chat_id}")

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔔 НАПОМИНАНИЕ!\n\nРебята, через час можно будет сыграть матч!"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке: {e}")

    if chat_id in user_reminders:
        del user_reminders[chat_id]
    if 'reminder_job' in context.chat_data:
        del context.chat_data['reminder_job']

async def cancel_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
        chat_id = query.message.chat_id
    else:
        message = update.message
        chat_id = update.effective_chat.id

    logger.info(f"Запрос отмены от {chat_id}")

    if chat_id not in user_reminders:
        await message.reply_text("❌ У вас нет активных напоминаний")
        return

    if 'reminder_job' in context.chat_data:
        context.chat_data['reminder_job'].schedule_removal()
        del context.chat_data['reminder_job']

    del user_reminders[chat_id]
    await message.reply_text("✅ Напоминание отменено")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"Запрос статуса от {chat_id}")

    if chat_id not in user_reminders:
        await update.message.reply_text("❌ Нет активных напоминаний")
        return

    reminder_info = user_reminders[chat_id]
    remaining = reminder_info['remind_time'] - datetime.now()

    if remaining.total_seconds() > 0:
        minutes = int(remaining.total_seconds() // 60)
        seconds = int(remaining.total_seconds() % 60)
        await update.message.reply_text(
            f"⏳ Напоминание активно\n"
            f"⏰ Осталось: {minutes} мин {seconds} сек"
        )
    else:
        await update.message.reply_text("⚠️ Напоминание должно было уже сработать")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data == "cancel":
        await cancel_reminder(update, context)

def main():
    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("remind", remind))
    application.add_handler(CommandHandler("cancel", cancel_reminder))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Запускаем бота (polling режим)
    logger.info("Бот запущен, жду команды...")
    application.run_polling()

if __name__ == "__main__":
    main()
