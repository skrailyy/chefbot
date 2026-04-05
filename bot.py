import os
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from starlette.applications import Starlette
from starlette.responses import Response, PlainTextResponse
from starlette.requests import Request
from starlette.routing import Route
import uvicorn
from database import add_recipe, get_recipes, find_recipe_by_name, delete_recipe, get_recipes_by_category, get_recipes_by_type

# ========== НАСТРОЙКИ ==========
TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = os.environ["RENDER_EXTERNAL_URL"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
user_states = {}
user_favorites = {}
recipe_stats = {}
user_cart = {}  # Для хранения выбранных рецептов для списка покупок

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    buttons = [
        [KeyboardButton("📝 Добавить рецепт")],
        [KeyboardButton("📖 Мои рецепты")],
        [KeyboardButton("📚 Базовые рецепты")],
        [KeyboardButton("🔍 Найти рецепт")],
        [KeyboardButton("🍽 Меню на сегодня")],
        [KeyboardButton("🛒 Список покупок")],
        [KeyboardButton("🥗 Что из остатков?")],
        [KeyboardButton("⭐ Избранное")],
        [KeyboardButton("🔥 Топ рецептов")],
        [KeyboardButton("🎉 Праздничные")],
        [KeyboardButton("🏋️ Спортивное питание")],
        [KeyboardButton("🥗 По типу питания")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def favorite_keyboard(recipe_id, is_favorite):
    keyboard = [
        [InlineKeyboardButton("❌ Удалить из избранного" if is_favorite else "⭐ Добавить в избранное", callback_data=f"fav_{recipe_id}")],
        [InlineKeyboardButton("➕ Добавить в список покупок", callback_data=f"cart_{recipe_id}")],
        [InlineKeyboardButton("🗑 Удалить рецепт", callback_data=f"del_{recipe_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def cart_keyboard(recipe_id):
    keyboard = [[InlineKeyboardButton("✅ Готово, показать список", callback_data="show_cart")]]
    return InlineKeyboardMarkup(keyboard)

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍🍳 Привет! Я ChefMind — твой умный кулинарный помощник!\n\n"
        "🎯 Что я умею:\n"
        "✅ Хранить твои рецепты\n"
        "✅ Составлять умное меню на день (завтрак→обед→ужин)\n"
        "✅ Формировать список покупок из выбранных блюд\n"
        "✅ Предлагать блюда из остатков\n"
        "✅ Отслеживать любимые рецепты\n"
        "🎉 Праздничные и 🏋️ Спортивное питание\n\n"
        "👇 Выбирай кнопки внизу!",
        reply_markup=main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Как пользоваться ботом:**\n\n"
        "📝 **Добавить рецепт** — создай новое блюдо\n"
        "📖 **Мои рецепты** — только твои рецепты\n"
        "📚 **Базовые рецепты** — 50+ стандартных рецептов\n"
        "🔍 **Найти рецепт** — поиск по названию\n"
        "🍽 **Меню на сегодня** — умный план питания (завтрак→обед→ужин)\n"
        "🛒 **Список покупок** — только из выбранных тобой рецептов\n"
        "🥗 **Что из остатков?** — напиши продукты, я подберу рецепт\n"
        "⭐ **Избранное** — сохраняй любимые рецепты\n"
        "🔥 **Топ рецептов** — самые популярные блюда\n"
        "🎉 **Праздничные** — Оливье, Сельдь под шубой, Тирамису\n"
        "🏋️ **Спортивное питание** — ПП рецепты с белком\n"
        "🥗 **По типу питания** — диетическое, постное, обычное\n\n"
        "💡 **Совет:** В базе уже есть 50+ рецептов!",
        reply_markup=main_keyboard()
    )

# ========== УМНОЕ МЕНЮ НА СЕГОДНЯ ==========
async def menu_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes(user_id)
    
    # Разделяем рецепты по категориям
    breakfast = [r for r in recipes if r[3].lower() == "завтрак"]
    lunch = [r for r in recipes if r[3].lower() == "обед"]
    dinner = [r for r in recipes if r[3].lower() == "ужин"]
    
    # Проверяем наличие рецептов в каждой категории
    missing = []
    if not breakfast:
        missing.append("завтрак")
    if not lunch:
        missing.append("обед")
    if not dinner:
        missing.append("ужин")
    
    if missing:
        await update.message.reply_text(
            f"❌ Нет рецептов в категориях: {', '.join(missing)}\n\n"
            f"📝 Добавь рецепты через кнопку «Добавить рецепт»\n"
            f"📚 Или посмотри базовые рецепты в «Базовые рецепты»"
        )
        return
    
    # Выбираем случайные рецепты из каждой категории
    selected = {
        "завтрак": random.choice(breakfast),
        "обед": random.choice(lunch),
        "ужин": random.choice(dinner)
    }
    
    # Сохраняем выбранные рецепты для списка покупок
    user_cart[user_id] = list(selected.values())
    
    response = "🍽 **Умное меню на сегодня:**\n\n"
    response += f"☀️ **Завтрак:** {selected['завтрак'][2]}\n"
    response += f"   ⏰ {selected['завтрак'][6]} мин | 🔥 {selected['завтрак'][7]} ккал\n\n"
    response += f"🌤️ **Обед:** {selected['обед'][2]}\n"
    response += f"   ⏰ {selected['обед'][6]} мин | 🔥 {selected['обед'][7]} ккал\n\n"
    response += f"🌙 **Ужин:** {selected['ужин'][2]}\n"
    response += f"   ⏰ {selected['ужин'][6]} мин | 🔥 {selected['ужин'][7]} ккал\n\n"
    
    total_cal = selected['завтрак'][7] + selected['обед'][7] + selected['ужин'][7]
    response += f"📊 **Общая калорийность:** {total_cal} ккал\n\n"
    response += "🛒 Нажми «Список покупок», чтобы получить список ингредиентов для этих блюд!"
    
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== СПИСОК ПОКУПОК ИЗ ВЫБРАННЫХ РЕЦЕПТОВ ==========
async def shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Получаем рецепты, выбранные пользователем
    cart = user_cart.get(user_id, [])
    
    if not cart:
        await update.message.reply_text(
            "🛒 Сначала сгенерируй меню на день (кнопка «Меню на сегодня»)\n"
            "Или найди рецепты через «Найти рецепт» и добавь их в корзину кнопкой «Добавить в список покупок»"
        )
        return
    
    # Собираем все ингредиенты из выбранных рецептов
    ingredients = {}
    for recipe in cart:
        items = recipe[4].split(',')
        for item in items:
            item = item.strip().lower()
            if item and item not in ["соль", "перец", "сахар", "масло"]:
                ingredients[item] = ingredients.get(item, 0) + 1
    
    if not ingredients:
        await update.message.reply_text("📝 В выбранных рецептах нет ингредиентов")
        return
    
    response = "🛒 **Список покупок (из выбранных блюд):**\n\n"
    for ing, count in sorted(ingredients.items()):
        response += f"• {ing}\n"
    
    response += f"\n📊 **Всего позиций:** {len(ingredients)}"
    response += f"\n🍽 **Выбрано блюд:** {len(cart)}"
    
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ДОБАВЛЕНИЕ РЕЦЕПТА В КОРЗИНУ ==========
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE, recipe):
    user_id = update.effective_user.id
    if user_id not in user_cart:
        user_cart[user_id] = []
    if recipe not in user_cart[user_id]:
        user_cart[user_id].append(recipe)
        await update.callback_query.answer("✅ Рецепт добавлен в список покупок!")
    else:
        await update.callback_query.answer("⚠️ Рецепт уже в списке")

# ========== ПОИСК РЕЦЕПТА ==========
async def find_recipe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Напиши название блюда, которое хочешь найти:")

async def process_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text):
    user_id = update.effective_user.id
    recipes = find_recipe_by_name(user_id, query_text)
    
    for r in recipes:
        recipe_stats[(user_id, r[0])] = recipe_stats.get((user_id, r[0]), 0) + 1
    
    if not recipes:
        await update.message.reply_text(f"❌ Рецепт «{query_text}» не найден")
    else:
        for r in recipes:
            is_fav = r[0] in user_favorites.get(user_id, set())
            response = f"🍽 **{r[2]}**\n\n"
            response += f"📂 Категория: {r[3]}\n"
            response += f"🛒 Ингредиенты: {r[4]}\n"
            response += f"👨‍🍳 Приготовление: {r[5]}\n"
            response += f"⏰ Время: {r[6]} мин\n"
            response += f"🔥 Калории: {r[7]} ккал\n"
            if r[8] and r[8] != "обычное":
                response += f"🏷 Тип: {r[8]}"
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=favorite_keyboard(r[0], is_fav))

# ========== МОИ РЕЦЕПТЫ ==========
async def my_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes(user_id)
    user_recipes = [r for r in recipes if r[1] != 0]
    
    if not user_recipes:
        await update.message.reply_text("📭 У тебя пока нет своих рецептов. Добавь через «Добавить рецепт»")
        return
    
    response = "📖 **Мои рецепты (добавленные тобой):**\n\n"
    for r in user_recipes[:20]:
        response += f"🍽 {r[2]}\n"
        response += f"   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n"
        response += "   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== БАЗОВЫЕ РЕЦЕПТЫ ==========
async def base_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import cursor
    cursor.execute('SELECT * FROM recipes WHERE user_id = 0 ORDER BY id')
    recipes = cursor.fetchall()
    
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
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ИЗБРАННОЕ ==========
async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    favs = user_favorites.get(user_id, set())
    
    if not favs:
        await update.message.reply_text("⭐ У тебя пока нет избранных рецептов")
        return
    
    response = "⭐ **Избранные рецепты:**\n\n"
    for fid in favs:
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == fid:
                response += f"🍽 {r[2]} ({r[3]}) - {r[6]} мин | 🔥 {r[7]} ккал\n"
                break
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ТОП РЕЦЕПТОВ ==========
async def top_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
    
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ПРАЗДНИЧНЫЕ РЕЦЕПТЫ ==========
async def holiday_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes_by_type(user_id, "праздничное")
    
    if not recipes:
        await update.message.reply_text("🎉 Праздничные рецепты:\n\n• Оливье (380 ккал)\n• Сельдь под шубой (420 ккал)\n• Мимоза (340 ккал)\n• Наполеон (520 ккал)\n• Тирамису (480 ккал)")
        return
    
    response = "🎉 **Праздничные рецепты:**\n\n"
    for r in recipes:
        response += f"🍽 {r[2]}\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== СПОРТИВНОЕ ПИТАНИЕ ==========
async def sport_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes_by_type(user_id, "спортивное")
    
    if not recipes:
        await update.message.reply_text("🏋️ Рецепты спортивного питания:\n\n• Куриное филе с гречкой (420 ккал, 200г)\n• Омлет с овощами (320 ккал, 150г)\n• Творог с ягодами (280 ккал, 250г)\n• Салат с тунцом (290 ккал, 300г)")
        return
    
    response = "🏋️ **Спортивное питание (ПП, высокий белок):**\n\n"
    for r in recipes:
        response += f"🍽 {r[2]}\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ПО ТИПУ ПИТАНИЯ ==========
async def by_type_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("🥗 Диетическое")],
        [KeyboardButton("🌱 Постное")],
        [KeyboardButton("🍳 Обычное")],
        [KeyboardButton("🔙 Назад в меню")]
    ], resize_keyboard=True)
    await update.message.reply_text("Выбери тип питания:", reply_markup=keyboard)

async def show_by_type(update: Update, context: ContextTypes.DEFAULT_TYPE, type_text):
    type_map = {
        "🥗 Диетическое": "диетическое",
        "🌱 Постное": "постное",
        "🍳 Обычное": "обычное"
    }
    recipe_type = type_map.get(type_text)
    if not recipe_type:
        return
    
    user_id = update.effective_user.id
    recipes = get_recipes_by_type(user_id, recipe_type)
    
    if not recipes:
        await update.message.reply_text(f"❌ Нет рецептов в категории {type_text}")
        return
    
    response = f"🥗 **Рецепты ({type_text}):**\n\n"
    for r in recipes[:15]:
        response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=main_keyboard())

# ========== ЧТО ИЗ ОСТАТКОВ? ==========
async def from_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🥗 Напиши продукты, которые у тебя есть в холодильнике, через запятую.\n\n📝 Пример: яйца, помидоры, сыр, хлеб")
    context.user_data['fridge_mode'] = True

async def process_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE, products_text):
    user_id = update.effective_user.id
    products = [p.strip().lower() for p in products_text.split(',')]
    
    recipes = get_recipes(user_id)
    if not recipes:
        await update.message.reply_text("📭 У тебя пока нет рецептов")
        return
    
    matches = []
    for r in recipes:
        ingredients = r[4].lower()
        match_count = sum(1 for p in products if p in ingredients)
        if match_count > 0:
            matches.append((r, match_count))
    
    matches.sort(key=lambda x: x[1], reverse=True)
    
    if not matches:
        await update.message.reply_text("🥗 Из этих продуктов ничего не приготовить. Попробуй добавить больше ингредиентов!")
    else:
        response = "🥗 **Что можно приготовить из остатков:**\n\n"
        for r, count in matches[:5]:
            response += f"🍽 {r[2]}\n"
            response += f"   ✅ Совпадений: {count}\n"
            response += f"   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n\n"
        await update.message.reply_text(response, parse_mode="Markdown")

# ========== ДОБАВЛЕНИЕ РЕЦЕПТА ==========
async def add_recipe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"step": "name"}
    await update.message.reply_text("Шаг 1/8: Напиши название блюда")

async def add_recipe_process(update: Update, context: ContextTypes.DEFAULT_TYPE, text):
    user_id = update.effective_user.id
    state = user_states[user_id]
    step = state["step"]
    
    if step == "name":
        state["name"] = text
        state["step"] = "category"
        await update.message.reply_text("Шаг 2/8: Напиши категорию (завтрак, обед, ужин, салат, десерт)")
    elif step == "category":
        state["category"] = text.lower()
        state["step"] = "ingredients"
        await update.message.reply_text("Шаг 3/8: Напиши ингредиенты через запятую")
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
            await update.message.reply_text("Шаг 6/8: Сколько калорий в одной порции? (или 0)")
        except:
            await update.message.reply_text("❌ Ошибка! Введи число")
    elif step == "calories":
        try:
            state["calories"] = int(text)
            state["step"] = "type"
            await update.message.reply_text("Шаг 7/8: Тип (диетическое, постное, обычное, праздничное, спортивное)")
        except:
            await update.message.reply_text("❌ Ошибка! Введи число")
    elif step == "type":
        valid = ["диетическое", "постное", "обычное", "праздничное", "спортивное"]
        if text.lower() in valid:
            state["recipe_type"] = text.lower()
            state["step"] = "tags"
            await update.message.reply_text("Шаг 8/8: Теги через запятую (или «нет»)")
        else:
            await update.message.reply_text(f"❌ Неверный тип. Выбери из: {', '.join(valid)}")
    elif step == "tags":
        tags = "" if text.lower() == "нет" else text
        add_recipe(
            user_id, state["name"], state["category"], state["ingredients"],
            state["instructions"], state["cook_time"], state["calories"],
            state["recipe_type"], tags
        )
        await update.message.reply_text(f"✅ Рецепт «{state['name']}» сохранён!", reply_markup=main_keyboard())
        del user_states[user_id]

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Обработка состояний
    if user_id in user_states:
        await add_recipe_process(update, context, text)
        return
    
    if context.user_data.get('fridge_mode'):
        await process_fridge(update, context, text)
        context.user_data['fridge_mode'] = False
        return
    
    if context.user_data.get('search_mode'):
        await process_search(update, context, text)
        context.user_data['search_mode'] = False
        return
    
    # Обработка кнопок
    if text == "📝 Добавить рецепт":
        await add_recipe_start(update, context)
    elif text == "📖 Мои рецепты":
        await my_recipes(update, context)
    elif text == "📚 Базовые рецепты":
        await base_recipes(update, context)
    elif text == "🔍 Найти рецепт":
        context.user_data['search_mode'] = True
        await find_recipe_start(update, context)
    elif text == "🍽 Меню на сегодня":
        await menu_today(update, context)
    elif text == "🛒 Список покупок":
        await shopping_list(update, context)
    elif text == "🥗 Что из остатков?":
        await from_fridge(update, context)
    elif text == "⭐ Избранное":
        await show_favorites(update, context)
    elif text == "🔥 Топ рецептов":
        await top_recipes(update, context)
    elif text == "🎉 Праздничные":
        await holiday_recipes(update, context)
    elif text == "🏋️ Спортивное питание":
        await sport_recipes(update, context)
    elif text == "🥗 По типу питания":
        await by_type_start(update, context)
    elif text in ["🥗 Диетическое", "🌱 Постное", "🍳 Обычное"]:
        await show_by_type(update, context, text)
    elif text == "🔙 Назад в меню":
        await update.message.reply_text("Главное меню", reply_markup=main_keyboard())
    elif text == "❓ Помощь":
        await help_command(update, context)
    else:
        await update.message.reply_text("Используй кнопки внизу 👇", reply_markup=main_keyboard())

# ========== ОБРАБОТКА INLINE КНОПОК ==========
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
        else:
            user_favorites[user_id].add(recipe_id)
            await query.edit_message_reply_markup(reply_markup=favorite_keyboard(recipe_id, True))
    
    elif data.startswith("cart_"):
        recipe_id = int(data.split("_")[1])
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == recipe_id:
                if user_id not in user_cart:
                    user_cart[user_id] = []
                if r not in user_cart[user_id]:
                    user_cart[user_id].append(r)
                    await query.answer("✅ Рецепт добавлен в список покупок!")
                else:
                    await query.answer("⚠️ Рецепт уже в списке")
                break
    
    elif data == "show_cart":
        await shopping_list(update, context)
    
    elif data.startswith("del_"):
        recipe_id = int(data.split("_")[1])
        if delete_recipe(recipe_id, user_id):
            await query.message.delete()
            await query.message.reply_text("🗑 Рецепт удалён!")

# ========== ЗАПУСК WEBHOOK ==========
async def start_webhook():
    app = Application.builder().token(TOKEN).build()
    await app.initialize()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    webhook_url = f"{WEBHOOK_URL}/webhook"
    await app.bot.set_webhook(webhook_url)
    logger.info(f"Webhook установлен на {webhook_url}")
    
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