import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("8518040511:AAFgXk0MsGcaC_la4i9hg56CTFTWjkXoknU")

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect('simple.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY,
    current_weight REAL,
    target_weight REAL
)
''')
conn.commit()

def save_profile(user_id, current, target):
    cursor.execute('INSERT OR REPLACE INTO profiles (user_id, current_weight, target_weight) VALUES (?, ?, ?)',
                   (user_id, current, target))
    conn.commit()

def get_profile(user_id):
    cursor.execute('SELECT current_weight, target_weight FROM profiles WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    return row if row else None

# ========== КЛАВИАТУРА ==========
def main_keyboard():
    buttons = [[KeyboardButton("👤 Мой профиль")], [KeyboardButton("📊 Статус")]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Простой бот для проверки сохранения веса\n\n"
        "Используй /set 70 75 - установить вес\n"
        "Или /profile - показать профиль",
        reply_markup=main_keyboard()
    )

async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        current = float(context.args[0])
        target = float(context.args[1])
        user_id = update.effective_user.id
        save_profile(user_id, current, target)
        await update.message.reply_text(f"✅ Сохранено: текущий {current} кг, целевой {target} кг")
    except:
        await update.message.reply_text("❌ Используй: /set 70 75")

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_profile(user_id)
    if profile:
        await update.message.reply_text(f"📊 Текущий вес: {profile[0]} кг\n🎯 Целевой вес: {profile[1]} кг")
    else:
        await update.message.reply_text("❌ Нет данных. Используй /set 70 75")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "👤 Мой профиль":
        await show_profile(update, context)
    elif text == "📊 Статус":
        await show_profile(update, context)

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set", set_weight))
    app.add_handler(CommandHandler("profile", show_profile))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    print("✅ Простой бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()