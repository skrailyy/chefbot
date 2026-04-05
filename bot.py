import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from starlette.applications import Starlette
from starlette.responses import Response, PlainTextResponse
from starlette.requests import Request
from starlette.routing import Route
import uvicorn

# ========== ИМПОРТЫ ИЗ ТВОИХ ФАЙЛОВ ==========
from database import add_recipe, get_recipes, find_recipe_by_name, delete_recipe, get_recipes_by_category, get_recipes_by_type

# ========== НАСТРОЙКИ ==========
TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
user_states = {}
user_favorites = {}
recipe_stats = {}

# ========== ГЛАВНОЕ МЕНЮ ==========
def main_keyboard():
    buttons = [
        [KeyboardButton(text="📝 Добавить рецепт")],
        [KeyboardButton(text="📖 Мои рецепты")],
        [KeyboardButton(text="📚 Базовые рецепты")],
        [KeyboardButton(text="🔍 Найти рецепт")],
        [KeyboardButton(text="🍽 Меню на сегодня")],
        [KeyboardButton(text="🛒 Список покупок")],
        [KeyboardButton(text="🥗 Что из остатков?")],
        [KeyboardButton(text="⭐ Избранное")],
        [KeyboardButton(text="🔥 Топ рецептов")],
        [KeyboardButton(text="🎉 Праздничные")],
        [KeyboardButton(text="🏋️ Спортивное питание")],
        [KeyboardButton(text="🥗 По типу питания")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def favorite_keyboard(recipe_id, is_favorite):
    keyboard = [
        [InlineKeyboardButton("❌ Удалить из избранного" if is_favorite else "⭐ Добавить в избранное", callback_data=f"fav_{recipe_id}")],
        [InlineKeyboardButton("🗑 Удалить рецепт", callback_data=f"del_{recipe_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== ОСНОВНЫЕ ХЕНДЛЕРЫ ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍🍳 Привет! Я ChefMind — твой кулинарный помощник!\n\n👇 Выбирай кнопки внизу!",
        reply_markup=main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "📝 Добавить рецепт":
        user_states[user_id] = {"step": "name"}
        await update.message.reply_text("Шаг 1/8: Напиши название блюда")
    elif text == "📖 Мои рецепты":
        recipes = get_recipes(user_id)
        user_recipes = [r for r in recipes if r[1] != 0]
        if not user_recipes:
            await update.message.reply_text("📭 Нет своих рецептов")
            return
        resp = "📖 **Мои рецепты:**\n\n"
        for r in user_recipes[:20]:
            resp += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n"
        await update.message.reply_text(resp)
    elif text == "📚 Базовые рецепты":
        from database import cursor
        cursor.execute('SELECT * FROM recipes WHERE user_id = 0')
        recipes = cursor.fetchall()
        resp = "📚 **Базовые рецепты:**\n\n"
        for r in recipes[:25]:
            resp += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n"
        await update.message.reply_text(resp)
    elif text == "🔍 Найти рецепт":
        context.user_data['search'] = True
        await update.message.reply_text("🔍 Напиши название:")
    elif text == "🍽 Меню на сегодня":
        recipes = get_recipes(user_id)
        if len(recipes) < 3:
            await update.message.reply_text(f"❌ Нужно минимум 3 рецепта. Сейчас: {len(recipes)}")
            return
        import random
        selected = random.sample(recipes, 3)
        resp = "🍽 **Меню на сегодня:**\n\n"
        names = ["Завтрак", "Обед", "Ужин"]
        for i, r in enumerate(selected):
            resp += f"{names[i]}: {r[2]} ({r[6]} мин | {r[7]} ккал)\n"
        await update.message.reply_text(resp)
    elif text == "🛒 Список покупок":
        recipes = get_recipes(user_id)
        ings = {}
        for r in recipes:
            for i in r[4].split(','):
                i = i.strip().lower()
                if i:
                    ings[i] = ings.get(i, 0) + 1
        if not ings:
            await update.message.reply_text("📝 Нет ингредиентов")
            return
        resp = "🛒 **Список покупок:**\n\n" + "\n".join(f"• {i}" for i in sorted(ings.keys()))
        await update.message.reply_text(resp)
    elif text == "🥗 Что из остатков?":
        context.user_data['fridge'] = True
        await update.message.reply_text("🥗 Напиши продукты через запятую:")
    elif text == "⭐ Избранное":
        favs = user_favorites.get(user_id, set())
        if not favs:
            await update.message.reply_text("⭐ Нет избранного")
            return
        resp = "⭐ **Избранное:**\n\n"
        for fid in favs:
            for r in get_recipes(user_id):
                if r[0] == fid:
                    resp += f"🍽 {r[2]}\n"
                    break
        await update.message.reply_text(resp)
    elif text == "🔥 Топ рецептов":
        recipes = get_recipes(user_id)
        stats = [(r[2], recipe_stats.get((user_id, r[0]), 0)) for r in recipes]
        stats.sort(key=lambda x: x[1], reverse=True)
        resp = "🔥 **Топ рецептов:**\n\n"
        for i, (n, v) in enumerate(stats[:5], 1):
            resp += f"{i}. {n} ({v} просмотров)\n"
        await update.message.reply_text(resp)
    elif text == "🎉 Праздничные":
        recipes = get_recipes_by_type(user_id, "праздничное")
        if not recipes:
            await update.message.reply_text("🎉 Праздничные рецепты появятся позже")
            return
        resp = "🎉 **Праздничные рецепты:**\n\n" + "\n".join(f"🍽 {r[2]} ({r[6]} мин | {r[7]} ккал)" for r in recipes)
        await update.message.reply_text(resp)
    elif text == "🏋️ Спортивное питание":
        recipes = get_recipes_by_type(user_id, "спортивное")
        if not recipes:
            await update.message.reply_text("🏋️ Рецепты спортивного питания появятся позже")
            return
        resp = "🏋️ **Спортивное питание:**\n\n" + "\n".join(f"🍽 {r[2]} ({r[6]} мин | {r[7]} ккал)" for r in recipes)
        await update.message.reply_text(resp)
    elif text == "🥗 По типу питания":
        kb = ReplyKeyboardMarkup([[KeyboardButton("🥗 Диетическое")], [KeyboardButton("🌱 Постное")], [KeyboardButton("🍳 Обычное")], [KeyboardButton("🔙 Назад")]], resize_keyboard=True)
        await update.message.reply_text("Выбери тип:", reply_markup=kb)
    elif text in ["🥗 Диетическое", "🌱 Постное", "🍳 Обычное"]:
        tmap = {"🥗 Диетическое": "диетическое", "🌱 Постное": "постное", "🍳 Обычное": "обычное"}
        recipes = get_recipes_by_type(user_id, tmap[text])
        if not recipes:
            await update.message.reply_text("❌ Нет рецептов")
            return
        resp = f"🥗 **{text}:**\n\n" + "\n".join(f"🍽 {r[2]} ({r[6]} мин | {r[7]} ккал)" for r in recipes[:15])
        await update.message.reply_text(resp, reply_markup=main_keyboard())
    elif text == "🔙 Назад":
        await update.message.reply_text("Главное меню", reply_markup=main_keyboard())
    elif text == "❓ Помощь":
        await update.message.reply_text("📖 **Помощь:**\nВсе функции доступны через кнопки внизу!", reply_markup=main_keyboard())
    elif context.user_data.get('search'):
        recipes = find_recipe_by_name(user_id, text)
        for r in recipes:
            recipe_stats[(user_id, r[0])] = recipe_stats.get((user_id, r[0]), 0) + 1
        if not recipes:
            await update.message.reply_text(f"❌ Рецепт «{text}» не найден")
        else:
            for r in recipes:
                is_fav = r[0] in user_favorites.get(user_id, set())
                resp = f"🍽 **{r[2]}**\n\n📂 {r[3]}\n🛒 {r[4]}\n👨‍🍳 {r[5]}\n⏰ {r[6]} мин\n🔥 {r[7]} ккал"
                await update.message.reply_text(resp, reply_markup=favorite_keyboard(r[0], is_fav))
        context.user_data['search'] = False
    elif context.user_data.get('fridge'):
        products = [p.strip().lower() for p in text.split(',')]
        recipes = get_recipes(user_id)
        matches = []
        for r in recipes:
            cnt = sum(1 for p in products if p in r[4].lower())
            if cnt:
                matches.append((r, cnt))
        matches.sort(key=lambda x: x[1], reverse=True)
        if not matches:
            await update.message.reply_text("🥗 Ничего не найдено")
        else:
            resp = "🥗 **Из остатков:**\n\n"
            for r, cnt in matches[:5]:
                resp += f"🍽 {r[2]} (совпадений: {cnt})\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n\n"
            await update.message.reply_text(resp)
        context.user_data['fridge'] = False
    elif user_id in user_states:
        state = user_states[user_id]
        step = state.get("step")
        if step == "name":
            state["name"] = text
            state["step"] = "category"
            await update.message.reply_text("Шаг 2/8: Категория (завтрак, обед, ужин, салат, десерт)")
        elif step == "category":
            state["category"] = text.lower()
            state["step"] = "ingredients"
            await update.message.reply_text("Шаг 3/8: Ингредиенты через запятую")
        elif step == "ingredients":
            state["ingredients"] = text
            state["step"] = "instructions"
            await update.message.reply_text("Шаг 4/8: Инструкция")
        elif step == "instructions":
            state["instructions"] = text
            state["step"] = "time"
            await update.message.reply_text("Шаг 5/8: Время в минутах")
        elif step == "time":
            try:
                state["cook_time"] = int(text)
                state["step"] = "calories"
                await update.message.reply_text("Шаг 6/8: Калории (или 0)")
            except:
                await update.message.reply_text("❌ Введи число")
        elif step == "calories":
            try:
                state["calories"] = int(text)
                state["step"] = "type"
                await update.message.reply_text("Шаг 7/8: Тип (диетическое, постное, обычное, праздничное, спортивное)")
            except:
                await update.message.reply_text("❌ Введи число")
        elif step == "type":
            if text.lower() in ["диетическое", "постное", "обычное", "праздничное", "спортивное"]:
                state["recipe_type"] = text.lower()
                state["step"] = "tags"
                await update.message.reply_text("Шаг 8/8: Теги через запятую (или «нет»)")
            else:
                await update.message.reply_text("❌ Неверный тип")
        elif step == "tags":
            tags = "" if text.lower() == "нет" else text
            add_recipe(user_id, state["name"], state["category"], state["ingredients"], state["instructions"], state["cook_time"], state["calories"], state["recipe_type"], tags)
            await update.message.reply_text(f"✅ Рецепт «{state['name']}» сохранён!", reply_markup=main_keyboard())
            del user_states[user_id]

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    if data.startswith("fav_"):
        rid = int(data.split("_")[1])
        if user_id not in user_favorites:
            user_favorites[user_id] = set()
        if rid in user_favorites[user_id]:
            user_favorites[user_id].remove(rid)
        else:
            user_favorites[user_id].add(rid)
        await query.edit_message_reply_markup(reply_markup=favorite_keyboard(rid, rid in user_favorites[user_id]))
    elif data.startswith("del_"):
        rid = int(data.split("_")[1])
        if delete_recipe(rid, user_id):
            await query.message.delete()
            await query.message.reply_text("🗑 Рецепт удалён")

# ========== ЗАПУСК WEBHOOK ==========
async def start_webhook():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    webhook_url = f"{WEBHOOK_URL}/webhook"
    await app.bot.set_webhook(webhook_url)
    logger.info(f"Webhook установлен на {webhook_url}")
    
    async def tg_webhook(request: Request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return Response()
    
    async def health(request: Request):
        return PlainTextResponse("ok")
    
    starlette_app = Starlette(routes=[
        Route("/webhook", tg_webhook, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ])
    
    config = uvicorn.Config(app=starlette_app, host="0.0.0.0", port=PORT)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(start_webhook())