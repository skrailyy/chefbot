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
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://chefbot.onrender.com")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
user_states = {}
user_favorites = {}
recipe_stats = {}

# ========== ГЛАВНОЕ МЕНЮ С КНОПКАМИ ==========
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

# ========== КНОПКИ ДЛЯ ИЗБРАННОГО И УДАЛЕНИЯ ==========
def favorite_keyboard(recipe_id, is_favorite):
    keyboard = [
        [InlineKeyboardButton("❌ Удалить из избранного" if is_favorite else "⭐ Добавить в избранное", callback_data=f"fav_{recipe_id}")],
        [InlineKeyboardButton("🗑 Удалить рецепт", callback_data=f"del_{recipe_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== КОМАНДА /start ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍🍳 Привет! Я ChefMind — твой умный кулинарный помощник!\n\n"
        "🎯 Что я умею:\n"
        "✅ Хранить твои рецепты\n"
        "✅ Составлять меню на день\n"
        "✅ Формировать список покупок\n"
        "✅ Предлагать блюда из остатков\n"
        "✅ Отслеживать любимые рецепты\n"
        "✅ Показывать топ популярных блюд\n"
        "🎉 Праздничные рецепты (Оливье, Сельдь под шубой и другие)\n"
        "🏋️ Спортивное питание (ПП, высокий белок)\n"
        "🥗 Фильтр по типу питания (диетическое/постное/обычное)\n\n"
        "👇 Выбирай кнопки внизу!",
        reply_markup=main_keyboard()
    )

# ========== ПОМОЩЬ ==========
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Как пользоваться ботом:**\n\n"
        "📝 **Добавить рецепт** — создай новое блюдо\n"
        "📖 **Мои рецепты** — только твои рецепты\n"
        "📚 **Базовые рецепты** — 50+ стандартных рецептов\n"
        "🔍 **Найти рецепт** — поиск по названию\n"
        "🍽 **Меню на сегодня** — случайный план питания\n"
        "🛒 **Список покупок** — все ингредиенты из всех рецептов\n"
        "🥗 **Что из остатков?** — напиши продукты, я подберу рецепт\n"
        "⭐ **Избранное** — сохраняй любимые рецепты\n"
        "🔥 **Топ рецептов** — самые популярные блюда\n"
        "🎉 **Праздничные** — Оливье, Сельдь под шубой, Тирамису\n"
        "🏋️ **Спортивное питание** — ПП рецепты с белком\n"
        "🥗 **По типу питания** — диетическое, постное, обычное\n\n"
        "💡 **Совет:** В базе уже есть 50+ рецептов!",
        reply_markup=main_keyboard()
    )

# ========== ДОБАВЛЕНИЕ РЕЦЕПТА (НАЧАЛО) ==========
async def add_recipe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"step": "name"}
    await update.message.reply_text("Шаг 1/8: Напиши название блюда")

# ========== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ (ДЛЯ ДОБАВЛЕНИЯ РЕЦЕПТА И ДРУГИХ ФУНКЦИЙ) ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Проверяем, находится ли пользователь в процессе добавления рецепта
    if user_id in user_states:
        state = user_states[user_id]
        step = state["step"]
        
        if step == "name":
            state["name"] = text
            state["step"] = "category"
            await update.message.reply_text("Шаг 2/8: Напиши категорию (завтрак, обед, ужин, салат, десерт)")
        
        elif step == "category":
            state["category"] = text.lower()
            state["step"] = "ingredients"
            await update.message.reply_text("Шаг 3/8: Напиши ингредиенты через запятую\nПример: яйца 2 шт, молоко 100 мл, соль по вкусу")
        
        elif step == "ingredients":
            state["ingredients"] = text
            state["step"] = "instructions"
            await update.message.reply_text("Шаг 4/8: Напиши инструкцию приготовления")
        
        elif step == "instructions":
            state["instructions"] = text
            state["step"] = "time"
            await update.message.reply_text("Шаг 5/8: Напиши время приготовления в минутах")
        
        elif step == "time":
            try:
                state["cook_time"] = int(text)
                state["step"] = "calories"
                await update.message.reply_text("Шаг 6/8: Сколько калорий в одной порции? (или 0, если не знаешь)")
            except:
                await update.message.reply_text("❌ Ошибка! Введи число минут")
        
        elif step == "calories":
            try:
                state["calories"] = int(text)
                state["step"] = "type"
                await update.message.reply_text("Шаг 7/8: Выбери тип питания (диетическое, постное, обычное, праздничное, спортивное)")
            except:
                await update.message.reply_text("❌ Ошибка! Введи число калорий")
        
        elif step == "type":
            valid_types = ["диетическое", "постное", "обычное", "праздничное", "спортивное"]
            if text.lower() in valid_types:
                state["recipe_type"] = text.lower()
                state["step"] = "tags"
                await update.message.reply_text("Шаг 8/8: Напиши теги через запятую (например: быстрый, сытный, завтрак) или «нет»")
            else:
                await update.message.reply_text(f"❌ Неверный тип. Выбери из: {', '.join(valid_types)}")
        
        elif step == "tags":
            tags = "" if text.lower() == "нет" else text
            add_recipe(
                user_id, 
                state["name"], 
                state["category"], 
                state["ingredients"], 
                state["instructions"], 
                state["cook_time"],
                state["calories"],
                state["recipe_type"],
                tags
            )
            response = f"✅ **Рецепт «{state['name']}» сохранён!**\n\n"
            response += f"📂 Категория: {state['category']}\n"
            response += f"⏰ Время: {state['cook_time']} мин\n"
            response += f"🔥 Калорий: {state['calories']} ккал\n"
            response += f"🏷 Тип: {state['recipe_type']}\n"
            if tags:
                response += f"📝 Теги: {tags}\n"
            await update.message.reply_text(response, reply_markup=main_keyboard())
            del user_states[user_id]
        
        return
    
    # Обработка кнопок и команд
    if text == "📝 Добавить рецепт":
        await add_recipe_start(update, context)
    
    elif text == "📖 Мои рецепты":
        recipes = get_recipes(user_id)
        user_recipes = [r for r in recipes if r[1] != 0]
        if not user_recipes:
            await update.message.reply_text("📭 У тебя пока нет своих рецептов. Добавь через «Добавить рецепт»\n\n📚 Чтобы посмотреть базовые рецепты, нажми «Базовые рецепты»")
            return
        response = "📖 **Мои рецепты (добавленные тобой):**\n\n"
        for r in user_recipes[:20]:
            emoji = ""
            if r[8] == "праздничное":
                emoji = "🎉 "
            elif r[8] == "диетическое":
                emoji = "🥗 "
            elif r[8] == "спортивное":
                emoji = "🏋️ "
            response += f"{emoji}🍽 {r[2]}\n"
            response += f"   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n"
            if r[9]:
                response += f"   🏷 {r[9]}\n"
            response += "   ─────────────\n"
        await update.message.reply_text(response)
    
    elif text == "📚 Базовые рецепты":
        from database import cursor
        cursor.execute('SELECT * FROM recipes WHERE user_id = 0 ORDER BY id')
        recipes = cursor.fetchall()
        if not recipes:
            await update.message.reply_text("📚 Базовые рецепты временно недоступны")
            return
        response = "📚 **Базовые рецепты (стандартные):**\n\n"
        for r in recipes[:25]:
            emoji = ""
            if r[8] == "праздничное":
                emoji = "🎉 "
            elif r[8] == "диетическое":
                emoji = "🥗 "
            elif r[8] == "спортивное":
                emoji = "🏋️ "
            response += f"{emoji}🍽 {r[2]}\n"
            response += f"   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n"
            response += "   ─────────────\n"
        await update.message.reply_text(response)
    
    elif text == "🔍 Найти рецепт":
        context.user_data['search_mode'] = True
        await update.message.reply_text("🔍 Напиши название блюда, которое хочешь найти:")
    
    elif text == "🍽 Меню на сегодня":
        recipes = get_recipes(user_id)
        if len(recipes) < 3:
            await update.message.reply_text(f"❌ Нужно минимум 3 рецепта. Сейчас: {len(recipes)}\nДобавь ещё через «Добавить рецепт»")
            return
        import random
        selected = random.sample(recipes, 3)
        response = "🍽 **Меню на сегодня:**\n\n"
        names = ["Завтрак ☀️", "Обед 🌤️", "Ужин 🌙"]
        total_calories = 0
        for i, r in enumerate(selected):
            response += f"{names[i]}: {r[2]}\n"
            response += f"   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n"
            response += "   ─────────────\n"
            total_calories += r[7]
        response += f"\n📊 Общая калорийность: {total_calories} ккал"
        await update.message.reply_text(response)
    
    elif text == "🛒 Список покупок":
        recipes = get_recipes(user_id)
        if not recipes:
            await update.message.reply_text("📭 Сначала добавь рецепты через «Добавить рецепт»")
            return
        ingredients = {}
        for r in recipes:
            items = r[4].split(',')
            for item in items:
                item = item.strip().lower()
                if item:
                    ingredients[item] = ingredients.get(item, 0) + 1
        if not ingredients:
            await update.message.reply_text("📝 В рецептах нет ингредиентов")
            return
        response = "🛒 **Общий список покупок:**\n\n"
        for ing, count in sorted(ingredients.items()):
            response += f"• {ing}\n"
        response += f"\n📊 Всего позиций: {len(ingredients)}"
        await update.message.reply_text(response)
    
    elif text == "🥗 Что из остатков?":
        context.user_data['fridge_mode'] = True
        await update.message.reply_text("🥗 Напиши продукты, которые у тебя есть в холодильнике, через запятую.\n\n📝 Пример: яйца, помидоры, сыр, хлеб")
    
    elif text == "⭐ Избранное":
        favorites = user_favorites.get(user_id, set())
        if not favorites:
            await update.message.reply_text("⭐ У тебя пока нет избранных рецептов. Добавь их через кнопки под рецептом!")
            return
        response = "⭐ **Твои избранные рецепты:**\n\n"
        for fav_id in favorites:
            recipes = get_recipes(user_id)
            for r in recipes:
                if r[0] == fav_id:
                    response += f"🍽 {r[2]} ({r[3]}) - {r[6]} мин | 🔥 {r[7]} ккал\n"
                    break
        await update.message.reply_text(response)
    
    elif text == "🔥 Топ рецептов":
        recipes = get_recipes(user_id)
        if not recipes:
            await update.message.reply_text("📭 Сначала добавь рецепты!")
            return
        stats = []
        for r in recipes:
            views = recipe_stats.get((user_id, r[0]), 0)
            stats.append((r[2], views, r[6], r[7]))
        stats.sort(key=lambda x: x[1], reverse=True)
        response = "🔥 **Топ рецептов по популярности:**\n\n"
        for i, (name, views, time, cal) in enumerate(stats[:5], 1):
            response += f"{i}. {name}\n   👁 {views} просмотров | ⏰ {time} мин | 🔥 {cal} ккал\n"
        if not any(s[1] > 0 for s in stats):
            response += "\n📊 Пока нет просмотров. Ищи рецепты через «Найти рецепт»!"
        await update.message.reply_text(response)
    
    elif text == "🎉 Праздничные":
        recipes = get_recipes_by_type(user_id, "праздничное")
        if not recipes:
            await update.message.reply_text("🎉 Праздничные рецепты:\n\n• Оливье (380 ккал)\n• Сельдь под шубой (420 ккал)\n• Мимоза (340 ккал)\n• Наполеон (520 ккал)\n• Тирамису (480 ккал)\n\n✨ Нажми «Базовые рецепты», чтобы увидеть их все!")
            return
        response = "🎉 **Праздничные рецепты:**\n\n"
        for r in recipes:
            response += f"🍽 {r[2]}\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
        await update.message.reply_text(response, reply_markup=main_keyboard())
    
    elif text == "🏋️ Спортивное питание":
        recipes = get_recipes_by_type(user_id, "спортивное")
        if not recipes:
            await update.message.reply_text("🏋️ Рецепты спортивного питания:\n\n• Куриное филе с гречкой (420 ккал, 200г)\n• Омлет с овощами (320 ккал, 150г)\n• Творог с ягодами (280 ккал, 250г)\n• Салат с тунцом (290 ккал, 300г)\n• Рис с лососем (480 ккал, 300г)\n• Протеиновый смузи (450 ккал, 400мл)\n• Запечённая индейка (420 ккал, 350г)\n• Овсяноблин (350 ккал, 180г)\n\n💪 Все рецепты содержат белок, подходят для набора массы или похудения!")
            return
        response = "🏋️ **Спортивное питание (ПП, высокий белок):**\n\n"
        for r in recipes:
            response += f"🍽 {r[2]}\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   📝 {r[4][:60]}...\n   ─────────────\n"
        await update.message.reply_text(response)
    
    elif text == "🥗 По типу питания":
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton(text="🥗 Диетическое")],
            [KeyboardButton(text="🌱 Постное")],
            [KeyboardButton(text="🍳 Обычное")],
            [KeyboardButton(text="🔙 Назад в меню")]
        ], resize_keyboard=True)
        await update.message.reply_text("Выбери тип питания:", reply_markup=keyboard)
    
    elif text in ["🥗 Диетическое", "🌱 Постное", "🍳 Обычное"]:
        type_map = {"🥗 Диетическое": "диетическое", "🌱 Постное": "постное", "🍳 Обычное": "обычное"}
        recipe_type = type_map[text]
        recipes = get_recipes_by_type(user_id, recipe_type)
        if not recipes:
            await update.message.reply_text(f"❌ Нет рецептов в категории {text}")
            await update.message.reply_text("🔙 Вернуться в меню", reply_markup=main_keyboard())
            return
        response = f"🥗 **Рецепты ({text}):**\n\n"
        for r in recipes[:15]:
            response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
        await update.message.reply_text(response, reply_markup=main_keyboard())
    
    elif text == "🔙 Назад в меню":
        await update.message.reply_text("🔙 Возвращаюсь в главное меню", reply_markup=main_keyboard())
    
    elif text == "❓ Помощь":
        await help_command(update, context)
    
    elif context.user_data.get('search_mode'):
        recipes = find_recipe_by_name(user_id, text)
        for r in recipes:
            key = (user_id, r[0])
            recipe_stats[key] = recipe_stats.get(key, 0) + 1
        if not recipes:
            await update.message.reply_text(f"❌ Рецепт «{text}» не найден", reply_markup=main_keyboard())
        else:
            for r in recipes:
                is_fav = (user_id, r[0]) in user_favorites.get(user_id, set())
                response = f"🍽 **{r[2]}**\n\n📂 Категория: {r[3]}\n🛒 Ингредиенты: {r[4]}\n👨‍🍳 Приготовление: {r[5]}\n⏰ Время: {r[6]} мин\n🔥 Калории: {r[7]} ккал"
                if r[8] and r[8] != "обычное":
                    response += f"\n🏷 Тип: {r[8]}"
                if r[9]:
                    response += f"\n📝 Теги: {r[9]}"
                await update.message.reply_text(response, reply_markup=favorite_keyboard(r[0], is_fav))
        context.user_data['search_mode'] = False
    
    elif context.user_data.get('fridge_mode'):
        products = [p.strip().lower() for p in text.split(',')]
        recipes = get_recipes(user_id)
        if not recipes:
            await update.message.reply_text("📭 У тебя пока нет рецептов", reply_markup=main_keyboard())
            context.user_data['fridge_mode'] = False
            return
        matches = []
        for r in recipes:
            ingredients = r[4].lower()
            match_count = sum(1 for p in products if p in ingredients)
            if match_count > 0:
                matches.append((r, match_count))
        matches.sort(key=lambda x: x[1], reverse=True)
        if not matches:
            await update.message.reply_text("🥗 Из этих продуктов ничего не приготовить. Попробуй добавить больше ингредиентов!", reply_markup=main_keyboard())
        else:
            response = "🥗 **Что можно приготовить из остатков:**\n\n"
            for r, count in matches[:5]:
                response += f"🍽 {r[2]}\n   ✅ Совпадений: {count}\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n\n"
            await update.message.reply_text(response, reply_markup=main_keyboard())
        context.user_data['fridge_mode'] = False

# ========== ОБРАБОТЧИК INLINE КНОПОК ==========
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    
    if data.startswith("fav_"):
        recipe_id = int(data.split("_")[1])
        if user_id not in user_favorites:
            user_favorites[user_id] = set()
        if recipe_id in user_favorites[user_id]:
            user_favorites[user_id].remove(recipe_id)
            await query.edit_message_reply_markup(reply_markup=favorite_keyboard(recipe_id, False))
            await query.message.reply_text("⭐ Рецепт удалён из избранного")
        else:
            user_favorites[user_id].add(recipe_id)
            await query.edit_message_reply_markup(reply_markup=favorite_keyboard(recipe_id, True))
            await query.message.reply_text("⭐ Рецепт добавлен в избранное")
    
    elif data.startswith("del_"):
        recipe_id = int(data.split("_")[1])
        if delete_recipe(recipe_id, user_id):
            await query.message.delete()
            await query.message.reply_text("🗑 Рецепт удалён!")
        else:
            await query.message.reply_text("❌ Нельзя удалить стандартный рецепт")

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER ==========
async def start_webhook():
    # Создаем приложение Telegram
    app = Application.builder().token(TOKEN).build()
    
    # Регистрируем хендлеры
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # Устанавливаем webhook
    webhook_url = f"{WEBHOOK_URL}/webhook"
    await app.bot.set_webhook(webhook_url)
    logger.info(f"Webhook установлен на {webhook_url}")
    
    # Создаем Starlette приложение для обработки запросов
    async def telegram_webhook(request: Request) -> Response:
        try:
            data = await request.json()
            update = Update.de_json(data, app.bot)
            await app.process_update(update)
            return Response()
        except Exception as e:
            logger.error(f"Ошибка webhook: {e}")
            return Response()
    
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")
    
    starlette_app = Starlette(routes=[
        Route("/webhook", telegram_webhook, methods=["POST"]),
        Route("/health", health_check, methods=["GET"]),
    ])
    
    # Запускаем сервер
    config = uvicorn.Config(app=starlette_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    
    async with app:
        await app.initialize()
        await server.serve()

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    asyncio.run(start_webhook())