import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from starlette.applications import Starlette
from starlette.responses import Response, PlainTextResponse
from starlette.requests import Request
from starlette.routing import Route
import uvicorn

# Настройки
TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = os.environ["RENDER_EXTERNAL_URL"]

logging.basicConfig(level=logging.INFO)

# Клавиатура
def main_keyboard():
    buttons = [
        [KeyboardButton("📝 Добавить рецепт")],
        [KeyboardButton("📖 Мои рецепты")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍🍳 Привет! Я ChefMind — твой кулинарный помощник!\n\n👇 Выбирай кнопки внизу!",
        reply_markup=main_keyboard()
    )

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Доступные команды:\n/start - начать\n/help - помощь\n\nКнопки внизу экрана тоже работают!"
    )

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📝 Добавить рецепт":
        await update.message.reply_text("📝 Функция добавления рецептов скоро появится!")
    elif text == "📖 Мои рецепты":
        await update.message.reply_text("📖 У вас пока нет рецептов")
    elif text == "❓ Помощь":
        await help_command(update, context)
    else:
        await update.message.reply_text(f"Вы написали: {text}\n\nИспользуйте кнопки внизу или команду /help")

# Запуск webhook
async def start_webhook():
    # Создаём приложение
    app = Application.builder().token(TOKEN).build()
    
    # Инициализируем приложение (ВАЖНО!)
    await app.initialize()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Устанавливаем webhook
    webhook_url = f"{WEBHOOK_URL}/webhook"
    await app.bot.set_webhook(webhook_url)
    logging.info(f"Webhook установлен на {webhook_url}")
    
    # Обработчик запросов от Telegram
    async def webhook_handler(request: Request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return Response()
    
    # Health check для Render
    async def health_check(request: Request):
        return PlainTextResponse("ok")
    
    # Starlette приложение
    starlette_app = Starlette(routes=[
        Route("/webhook", webhook_handler, methods=["POST"]),
        Route("/health", health_check, methods=["GET"]),
    ])
    
    # Запускаем сервер
    config = uvicorn.Config(app=starlette_app, host="0.0.0.0", port=PORT)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_webhook())