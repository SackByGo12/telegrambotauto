from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from pymongo import MongoClient
import logging
import os
from dotenv import load_dotenv

# Загрузка конфигурации из .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME')

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Подключение к MongoDB
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
users_collection = db["users"]  # Коллекция для хранения пользователей

# Этапы разговора
ASK_NAME, ASK_PHONE = range(2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Стартовая команда /start."""
    await update.message.reply_text("Добро пожаловать! Пожалуйста, отправьте свое ФИО.")
    return ASK_NAME


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ФИО."""
    context.user_data["full_name"] = update.message.text
    reply_keyboard = [[KeyboardButton("Отправить номер телефона", request_contact=True)]]
    await update.message.reply_text(
        "Теперь отправьте свой номер телефона.",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
    )
    return ASK_PHONE


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка номера телефона."""
    contact = update.message.contact
    if contact:
        full_name = context.user_data["full_name"]
        phone_number = contact.phone_number

        # Сохранение пользователя в MongoDB
        try:
            users_collection.insert_one({"full_name": full_name, "phone_number": phone_number})
            await update.message.reply_text(f"Спасибо, {full_name}! Ваши данные сохранены.")
        except Exception as e:
            logger.error(f"Ошибка при сохранении пользователя: {e}")
            await update.message.reply_text(
                "Произошла ошибка при сохранении ваших данных. Попробуйте еще раз."
            )
        return ConversationHandler.END
    else:
        await update.message.reply_text("Пожалуйста, отправьте номер телефона через кнопку.")
        return ASK_PHONE


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /users для просмотра всех пользователей."""
    try:
        users = list(users_collection.find({}, {"_id": 0, "full_name": 1, "phone_number": 1}))
        if users:
            message = "Список пользователей:\n"
            for i, user in enumerate(users, start=1):
                message += f"{i}. {user['full_name']} - {user['phone_number']}\n"
        else:
            message = "Пока нет сохраненных пользователей."
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Ошибка при получении пользователей: {e}")
        await update.message.reply_text("Произошла ошибка при получении данных.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /cancel для отмены текущей операции."""
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END


def main():
    """Основная функция для запуска бота."""
    # Создание приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработчик разговоров
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_PHONE: [MessageHandler(filters.CONTACT, ask_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Обработчик команды /users
    application.add_handler(CommandHandler("users", list_users))

    # Запуск бота
    application.run_polling()


if __name__ == "__main__":
    main()