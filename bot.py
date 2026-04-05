import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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

# Простая клавиатура
def main_keyboard():
    buttons = [
        [KeyboardButton("📝 Добавить рецепт")],
        [KeyboardButton("📖 Мои рецепты")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# Обработчик /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я ChefMind. Нажми /help", reply_markup=main_keyboard())

# Обработчик /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Доступные команды: /start, /help")

# Обработчик сообщений
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📝 Добавить рецепт":
        await update.message.reply_text("Функция добавления рецептов скоро появится!")
    elif text == "📖 Мои рецепты":
        await update.message.reply_text("У вас пока нет рецептов")
    else:
        await update.message.reply_text(f"Вы написали: {text}")

# Запуск webhook
async def start_webhook():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    webhook_url = f"{WEBHOOK_URL}/webhook"
    await app.bot.set_webhook(webhook_url)
    logging.info(f"Webhook установлен на {webhook_url}")

    async def webhook_handler(request: Request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return Response()

    async def health_check(request: Request):
        return PlainTextResponse("ok")

    starlette_app = Starlette(routes=[
        Route("/webhook", webhook_handler, methods=["POST"]),
        Route("/health", health_check, methods=["GET"]),
    ])

    config = uvicorn.Config(app=starlette_app, host="0.0.0.0", port=PORT)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_webhook())