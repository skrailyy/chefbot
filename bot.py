import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database import add_recipe, get_recipes, find_recipe_by_name, delete_recipe, get_recipes_by_category, get_recipes_by_type

BOT_TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
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
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ========== КНОПКИ ДЛЯ ИЗБРАННОГО И УДАЛЕНИЯ ==========
def favorite_keyboard(recipe_id, is_favorite):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Удалить из избранного" if is_favorite else "⭐ Добавить в избранное", callback_data=f"fav_{recipe_id}")],
        [InlineKeyboardButton(text="🗑 Удалить рецепт", callback_data=f"del_{recipe_id}")]
    ])
    return keyboard

# ========== КОМАНДА /start ==========
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
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

# ========== ДОБАВЛЕНИЕ РЕЦЕПТА ==========
@dp.message(lambda msg: msg.text == "📝 Добавить рецепт")
async def add_recipe_start(message: types.Message):
    user_states[message.from_user.id] = {"step": "name"}
    await message.answer("Шаг 1/8: Напиши название блюда")

# ========== СПИСОК ПОКУПОК ==========
@dp.message(lambda msg: msg.text == "🛒 Список покупок")
async def shopping_list(message: types.Message):
    recipes = get_recipes(message.from_user.id)
    if not recipes:
        await message.answer("📭 Сначала добавь рецепты через «Добавить рецепт»")
        return
    
    ingredients = {}
    for r in recipes:
        items = r[4].split(',')
        for item in items:
            item = item.strip().lower()
            if item:
                ingredients[item] = ingredients.get(item, 0) + 1
    
    if not ingredients:
        await message.answer("📝 В рецептах нет ингредиентов. Добавь их при создании рецепта")
        return
    
    response = "🛒 **Общий список покупок:**\n\n"
    for ing, count in sorted(ingredients.items()):
        response += f"• {ing}\n"
    
    response += f"\n📊 Всего позиций: {len(ingredients)}"
    await message.answer(response, parse_mode="Markdown")

# ========== ЧТО ИЗ ОСТАТКОВ? ==========
@dp.message(lambda msg: msg.text == "🥗 Что из остатков?")
async def from_fridge(message: types.Message):
    await message.answer(
        "🥗 Напиши продукты, которые у тебя есть в холодильнике, через запятую.\n\n"
        "📝 Пример: яйца, помидоры, сыр, хлеб"
    )
    user_states[message.from_user.id] = {"step": "fridge"}

# ========== ИЗБРАННОЕ ==========
@dp.message(lambda msg: msg.text == "⭐ Избранное")
async def show_favorites(message: types.Message):
    user_id = message.from_user.id
    favorites = user_favorites.get(user_id, set())
    
    if not favorites:
        await message.answer("⭐ У тебя пока нет избранных рецептов. Добавь их через кнопки под рецептом!")
        return
    
    response = "⭐ **Твои избранные рецепты:**\n\n"
    for fav_id in favorites:
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == fav_id:
                response += f"🍽 {r[2]} ({r[3]}) - {r[6]} мин | 🔥 {r[7]} ккал\n"
                break
    
    await message.answer(response, parse_mode="Markdown")

# ========== ТОП РЕЦЕПТОВ ==========
@dp.message(lambda msg: msg.text == "🔥 Топ рецептов")
async def top_recipes(message: types.Message):
    user_id = message.from_user.id
    recipes = get_recipes(user_id)
    
    if not recipes:
        await message.answer("📭 Сначала добавь рецепты!")
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
    
    await message.answer(response, parse_mode="Markdown")

# ========== БАЗОВЫЕ РЕЦЕПТЫ ==========
@dp.message(lambda msg: msg.text == "📚 Базовые рецепты")
async def show_base_recipes(message: types.Message):
    from database import cursor
    cursor.execute('SELECT * FROM recipes WHERE user_id = 0 ORDER BY id')
    recipes = cursor.fetchall()
    
    if not recipes:
        await message.answer("📚 Базовые рецепты временно недоступны")
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
    await message.answer(response, parse_mode="Markdown")

# ========== МОИ РЕЦЕПТЫ ==========
@dp.message(lambda msg: msg.text == "📖 Мои рецепты")
async def show_my_recipes(message: types.Message):
    recipes = get_recipes(message.from_user.id)
    user_recipes = [r for r in recipes if r[1] != 0]
    
    if not user_recipes:
        await message.answer("📭 У тебя пока нет своих рецептов. Добавь через «Добавить рецепт»\n\n📚 Чтобы посмотреть базовые рецепты, нажми «Базовые рецепты»")
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
    await message.answer(response, parse_mode="Markdown")

# ========== ПРАЗДНИЧНЫЕ РЕЦЕПТЫ ==========
@dp.message(lambda msg: msg.text == "🎉 Праздничные")
async def show_holiday_recipes(message: types.Message):
    recipes = get_recipes_by_type(message.from_user.id, "праздничное")
    
    if not recipes:
        await message.answer("🎉 Праздничные рецепты:\n\n• Оливье (380 ккал)\n• Сельдь под шубой (420 ккал)\n• Мимоза (340 ккал)\n• Наполеон (520 ккал)\n• Тирамису (480 ккал)\n\n✨ Нажми «Базовые рецепты», чтобы увидеть их все!")
        return
    
    response = "🎉 **Праздничные рецепты:**\n\n"
    for r in recipes:
        response += f"🍽 {r[2]}\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
    await message.answer(response, parse_mode="Markdown", reply_markup=main_keyboard())

# ========== СПОРТИВНОЕ ПИТАНИЕ ==========
@dp.message(lambda msg: msg.text == "🏋️ Спортивное питание")
async def show_sport_recipes(message: types.Message):
    recipes = get_recipes_by_type(message.from_user.id, "спортивное")
    
    if not recipes:
        await message.answer("🏋️ Рецепты спортивного питания:\n\n• Куриное филе с гречкой (420 ккал, 200г)\n• Омлет с овощами (320 ккал, 150г)\n• Творог с ягодами (280 ккал, 250г)\n• Салат с тунцом (290 ккал, 300г)\n• Рис с лососем (480 ккал, 300г)\n• Протеиновый смузи (450 ккал, 400мл)\n• Запечённая индейка (420 ккал, 350г)\n• Овсяноблин (350 ккал, 180г)\n\n💪 Все рецепты содержат белок, подходят для набора массы или похудения!")
        return
    
    response = "🏋️ **Спортивное питание (ПП, высокий белок):**\n\n"
    for r in recipes:
        response += f"🍽 {r[2]}\n"
        response += f"   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n"
        response += f"   📝 {r[4][:60]}...\n"
        response += "   ─────────────\n"
    await message.answer(response, parse_mode="Markdown")

# ========== ПО ТИПУ ПИТАНИЯ ==========
@dp.message(lambda msg: msg.text == "🥗 По типу питания")
async def by_type_start(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🥗 Диетическое")],
            [KeyboardButton(text="🌱 Постное")],
            [KeyboardButton(text="🍳 Обычное")],
            [KeyboardButton(text="🔙 Назад в меню")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выбери тип питания:", reply_markup=keyboard)

@dp.message(lambda msg: msg.text in ["🥗 Диетическое", "🌱 Постное", "🍳 Обычное"])
async def show_by_type(message: types.Message):
    type_map = {
        "🥗 Диетическое": "диетическое",
        "🌱 Постное": "постное",
        "🍳 Обычное": "обычное"
    }
    recipe_type = type_map[message.text]
    recipes = get_recipes_by_type(message.from_user.id, recipe_type)
    
    if not recipes:
        await message.answer(f"❌ Нет рецептов в категории {message.text}")
        await message.answer("🔙 Вернуться в меню", reply_markup=main_keyboard())
        return
    
    response = f"🥗 **Рецепты ({message.text}):**\n\n"
    for r in recipes[:15]:
        response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n"
        if r[8] != "обычное" and r[8] != "":
            response += f"   🏷 {r[8]}\n"
        response += "   ─────────────\n"
    await message.answer(response, parse_mode="Markdown", reply_markup=main_keyboard())

@dp.message(lambda msg: msg.text == "🔙 Назад в меню")
async def back_to_menu(message: types.Message):
    await message.answer("🔙 Возвращаюсь в главное меню", reply_markup=main_keyboard())

# ========== ПОИСК РЕЦЕПТА ==========
@dp.message(lambda msg: msg.text == "🔍 Найти рецепт")
async def find_recipe_start(message: types.Message):
    await message.answer("🔍 Напиши название блюда, которое хочешь найти:")

# ========== МЕНЮ НА СЕГОДНЯ ==========
@dp.message(lambda msg: msg.text == "🍽 Меню на сегодня")
async def menu_today(message: types.Message):
    recipes = get_recipes(message.from_user.id)
    if len(recipes) < 3:
        await message.answer(f"❌ Нужно минимум 3 рецепта. Сейчас: {len(recipes)}\nДобавь ещё через «Добавить рецепт»")
        return
    
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
    await message.answer(response, parse_mode="Markdown")

# ========== ПОМОЩЬ ==========
@dp.message(lambda msg: msg.text == "❓ Помощь")
async def help_command(message: types.Message):
    await message.answer(
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
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ПРОЦЕСС ДОБАВЛЕНИЯ РЕЦЕПТА ==========
async def add_recipe_process(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]
    step = state["step"]
    
    if step == "name":
        state["name"] = message.text
        state["step"] = "category"
        await message.answer("Шаг 2/8: Напиши категорию (завтрак, обед, ужин, салат, десерт)")
    
    elif step == "category":
        state["category"] = message.text.lower()
        state["step"] = "ingredients"
        await message.answer("Шаг 3/8: Напиши ингредиенты через запятую\nПример: яйца 2 шт, молоко 100 мл, соль по вкусу")
    
    elif step == "ingredients":
        state["ingredients"] = message.text
        state["step"] = "instructions"
        await message.answer("Шаг 4/8: Напиши инструкцию приготовления")
    
    elif step == "instructions":
        state["instructions"] = message.text
        state["step"] = "time"
        await message.answer("Шаг 5/8: Напиши время приготовления в минутах")
    
    elif step == "time":
        try:
            state["cook_time"] = int(message.text)
            state["step"] = "calories"
            await message.answer("Шаг 6/8: Сколько калорий в одной порции? (или 0, если не знаешь)")
        except:
            await message.answer("❌ Ошибка! Введи число минут")
    
    elif step == "calories":
        try:
            state["calories"] = int(message.text)
            state["step"] = "type"
            await message.answer("Шаг 7/8: Выбери тип питания (диетическое, постное, обычное, праздничное, спортивное)")
        except:
            await message.answer("❌ Ошибка! Введи число калорий")
    
    elif step == "type":
        valid_types = ["диетическое", "постное", "обычное", "праздничное", "спортивное"]
        if message.text.lower() in valid_types:
            state["recipe_type"] = message.text.lower()
            state["step"] = "tags"
            await message.answer("Шаг 8/8: Напиши теги через запятую (например: быстрый, сытный, завтрак) или «нет»")
        else:
            await message.answer(f"❌ Неверный тип. Выбери из: {', '.join(valid_types)}")
    
    elif step == "tags":
        tags = "" if message.text.lower() == "нет" else message.text
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
        
        await message.answer(response, parse_mode="Markdown", reply_markup=main_keyboard())
        del user_states[user_id]

# ========== ОБРАБОТКА ОСТАТКОВ ==========
async def process_fridge(message: types.Message):
    user_id = message.from_user.id
    products = [p.strip().lower() for p in message.text.split(',')]
    
    recipes = get_recipes(user_id)
    if not recipes:
        await message.answer("📭 У тебя пока нет рецептов. Добавь их через кнопку ниже!", reply_markup=main_keyboard())
        del user_states[user_id]
        return
    
    matches = []
    for r in recipes:
        ingredients = r[4].lower()
        match_count = sum(1 for p in products if p in ingredients)
        if match_count > 0:
            matches.append((r, match_count))
    
    matches.sort(key=lambda x: x[1], reverse=True)
    
    if not matches:
        await message.answer("🥗 Из этих продуктов ничего не приготовить. Попробуй добавить больше ингредиентов!", reply_markup=main_keyboard())
    else:
        response = "🥗 **Что можно приготовить из остатков:**\n\n"
        for r, count in matches[:5]:
            response += f"🍽 {r[2]}\n"
            response += f"   ✅ Совпадений: {count}\n"
            response += f"   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n\n"
        await message.answer(response, parse_mode="Markdown", reply_markup=main_keyboard())
    
    del user_states[user_id]

# ========== ОБРАБОТЧИК ПОИСКА ==========
async def process_search(message: types.Message):
    user_id = message.from_user.id
    recipes = find_recipe_by_name(user_id, message.text)
    
    for r in recipes:
        key = (user_id, r[0])
        recipe_stats[key] = recipe_stats.get(key, 0) + 1
    
    if not recipes:
        await message.answer(f"❌ Рецепт «{message.text}» не найден", reply_markup=main_keyboard())
    else:
        for r in recipes:
            is_fav = (user_id, r[0]) in user_favorites.get(user_id, set())
            response = f"🍽 **{r[2]}**\n\n"
            response += f"📂 Категория: {r[3]}\n"
            response += f"🛒 Ингредиенты: {r[4]}\n"
            response += f"👨‍🍳 Приготовление: {r[5]}\n"
            response += f"⏰ Время: {r[6]} мин\n"
            response += f"🔥 Калории: {r[7]} ккал\n"
            if r[8] and r[8] != "обычное":
                response += f"🏷 Тип: {r[8]}\n"
            if r[9]:
                response += f"📝 Теги: {r[9]}\n"
            await message.answer(response, parse_mode="Markdown", reply_markup=favorite_keyboard(r[0], is_fav))

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    text = message.text
    
    if user_id in user_states:
        state = user_states[user_id]
        if state.get("step") == "fridge":
            await process_fridge(message)
        else:
            await add_recipe_process(message)
        return
    
    if not text.startswith('/') and text not in [
        "📝 Добавить рецепт", "📖 Мои рецепты", "📚 Базовые рецепты", "🔍 Найти рецепт", 
        "🍽 Меню на сегодня", "🛒 Список покупок", "🥗 Что из остатков?", 
        "⭐ Избранное", "🔥 Топ рецептов", "🎉 Праздничные", "🏋️ Спортивное питание",
        "🥗 По типу питания", "❓ Помощь", "🔙 Назад в меню",
        "🥗 Диетическое", "🌱 Постное", "🍳 Обычное"
    ]:
        await process_search(message)
        return

# ========== ОБРАБОТКА INLINE КНОПОК ==========
@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    
    if data.startswith("fav_"):
        recipe_id = int(data.split("_")[1])
        if user_id not in user_favorites:
            user_favorites[user_id] = set()
        
        if recipe_id in user_favorites[user_id]:
            user_favorites[user_id].remove(recipe_id)
            await callback.answer("⭐ Рецепт удалён из избранного")
        else:
            user_favorites[user_id].add(recipe_id)
            await callback.answer("⭐ Рецепт добавлен в избранное")
        
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == recipe_id:
                is_fav = recipe_id in user_favorites[user_id]
                await callback.message.edit_reply_markup(reply_markup=favorite_keyboard(recipe_id, is_fav))
                break
    
    elif data.startswith("del_"):
        recipe_id = int(data.split("_")[1])
        if delete_recipe(recipe_id, user_id):
            await callback.answer("🗑 Рецепт удалён!")
            await callback.message.delete()
        else:
            await callback.answer("❌ Нельзя удалить стандартный рецепт")

# ========== ВЕБ-КОСТЫЛЬ ДЛЯ RENDER ==========
from aiohttp import web

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    print("🌐 Веб-сервер запущен на порту 10000")

# ========== ЗАПУСК БОТА ==========
async def main():
    asyncio.create_task(start_web())
    print("🤖 Бот ChefMind с 50+ рецептами запущен!")
    print("✅ В базе: завтраки, супы, салаты, основные блюда, десерты")
    print("✅ Праздничные: Оливье, Сельдь под шубой, Мимоза, Наполеон, Тирамису")
    print("✅ Спортивное питание: 8 ПП-рецептов с белком")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())