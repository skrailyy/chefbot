import os
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8742257256:AAH5mVfZqZcO5IzT-1cLjeipnRq_Z272A4I"  # Вставь свой токен

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect('test_profile.db')
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
    cursor.execute('''
    INSERT OR REPLACE INTO profiles (user_id, current_weight, target_weight)
    VALUES (?, ?, ?)
    ''', (user_id, current, target))
    conn.commit()

def get_profile(user_id):
    cursor.execute('SELECT current_weight, target_weight FROM profiles WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        return {'current': row[0], 'target': row[1]}
    return None

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я тестовый бот.\n\n"
        "Используй:\n"
        "/set 70 75 - установить вес (текущий и целевой)\n"
        "/show - показать сохранённый вес"
    )

async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        current = float(context.args[0])
        target = float(context.args[1])
        user_id = update.effective_user.id
        save_profile(user_id, current, target)
        await update.message.reply_text(f"✅ Сохранено: текущий {current} кг, целевой {target} кг")
    except:
        await update.message.reply_text("❌ Ошибка. Используй: /set 70 75")

async def show_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_profile(user_id)
    if profile:
        await update.message.reply_text(f"📊 Текущий вес: {profile['current']} кг\n🎯 Целевой вес: {profile['target']} кг")
    else:
        await update.message.reply_text("❌ Нет данных. Используй /set 70 75")

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set", set_weight))
    app.add_handler(CommandHandler("show", show_weight))
    print("✅ Тестовый бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()