import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN
from database import add_recipe, get_recipes, find_recipe_by_name, delete_recipe

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_states = {}

# ========== ГЛАВНОЕ МЕНЮ С КНОПКАМИ ==========
def main_keyboard():
    buttons = [
        [KeyboardButton(text="📝 Добавить рецепт")],
        [KeyboardButton(text="📖 Мои рецепты")],
        [KeyboardButton(text="🔍 Найти рецепт")],
        [KeyboardButton(text="🍽 Меню на сегодня")],
        [KeyboardButton(text="🛒 Список покупок")],
        [KeyboardButton(text="🥗 Что из остатков?")],
        [KeyboardButton(text="⭐ Избранное")],
        [KeyboardButton(text="🔥 Топ рецептов")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ========== КНОПКИ ДЛЯ ИЗБРАННОГО ==========
def favorite_keyboard(recipe_id, is_favorite):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Удалить из избранного" if is_favorite else "⭐ Добавить в избранное", callback_data=f"fav_{recipe_id}")],
        [InlineKeyboardButton(text="🗑 Удалить рецепт", callback_data=f"del_{recipe_id}")]
    ])
    return keyboard

# ========== ХРАНИЛИЩЕ ДЛЯ ИЗБРАННОГО (в реальном проекте лучше в БД) ==========
user_favorites = {}

# ========== ХРАНИЛИЩЕ ДЛЯ СТАТИСТИКИ ПОПУЛЯРНОСТИ ==========
recipe_stats = {}

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
        "✅ Показывать топ популярных блюд\n\n"
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
    
    # Собираем все ингредиенты из всех рецептов
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
                response += f"🍽 {r[2]} ({r[3]}) - {r[6]} мин\n"
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
    
    # Считаем просмотры для каждого рецепта
    stats = []
    for r in recipes:
        views = recipe_stats.get((user_id, r[0]), 0)
        stats.append((r[2], views, r[6], r[0]))
    
    stats.sort(key=lambda x: x[1], reverse=True)
    
    response = "🔥 **Топ рецептов по популярности:**\n\n"
    for i, (name, views, time, rid) in enumerate(stats[:5], 1):
        response += f"{i}. {name}\n   👁 {views} просмотров | ⏰ {time} мин\n"
    
    if not any(s[1] > 0 for s in stats):
        response += "\n📊 Пока нет просмотров. Ищи рецепты через «Найти рецепт»!"
    
    await message.answer(response, parse_mode="Markdown")

# ========== МОИ РЕЦЕПТЫ ==========
@dp.message(lambda msg: msg.text == "📖 Мои рецепты")
async def show_recipes(message: types.Message):
    recipes = get_recipes(message.from_user.id)
    if not recipes:
        await message.answer("📭 У тебя пока нет рецептов. Нажми «Добавить рецепт»")
        return
    
    response = "📖 **Твои рецепты:**\n\n"
    for r in recipes[:15]:
        response += f"🍽 {r[2]}\n   📂 {r[3]}\n   ⏰ {r[6]} мин\n   ─────────────\n"
    await message.answer(response, parse_mode="Markdown")

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
    
    import random
    selected = random.sample(recipes, 3)
    response = "🍽 **Меню на сегодня:**\n\n"
    names = ["Завтрак ☀️", "Обед 🌤️", "Ужин 🌙"]
    for i, r in enumerate(selected):
        response += f"{names[i]}: {r[2]} ({r[6]} мин)\n"
    await message.answer(response, parse_mode="Markdown")

# ========== ПОМОЩЬ ==========
@dp.message(lambda msg: msg.text == "❓ Помощь")
async def help_command(message: types.Message):
    await message.answer(
        "📖 **Как пользоваться ботом:**\n\n"
        "📝 **Добавить рецепт** — создай новое блюдо (8 шагов)\n"
        "📖 **Мои рецепты** — список всех твоих блюд\n"
        "🔍 **Найти рецепт** — поиск по названию\n"
        "🍽 **Меню на сегодня** — случайный план питания\n"
        "🛒 **Список покупок** — все ингредиенты из всех рецептов\n"
        "🥗 **Что из остатков?** — напиши продукты, я подберу рецепт\n"
        "⭐ **Избранное** — сохраняй любимые рецепты\n"
        "🔥 **Топ рецептов** — самые популярные блюда\n\n"
        "💡 **Совет:** Добавь 10+ рецептов для разнообразного меню!",
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
        await message.answer("Шаг 2/8: Напиши категорию (завтрак, обед, ужин, салат, суп, десерт)")
    
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
            state["step"] = "difficulty"
            await message.answer("Шаг 6/8: Напиши сложность (легко, средне, сложно)")
        except:
            await message.answer("❌ Ошибка! Введи число минут (например: 15)")
    
    elif step == "difficulty":
        state["difficulty"] = message.text.lower()
        state["step"] = "portions"
        await message.answer("Шаг 7/8: На сколько порций рассчитано блюдо?")
    
    elif step == "portions":
        try:
            state["portions"] = int(message.text)
            state["step"] = "notes"
            await message.answer("Шаг 8/8: Напиши дополнительные заметки (или «нет»)")
        except:
            await message.answer("❌ Ошибка! Введи число порций")
    
    elif step == "notes":
        state["notes"] = message.text if message.text.lower() != "нет" else ""
        
        # Сохраняем все данные
        add_recipe(
            user_id, 
            state["name"], 
            state["category"], 
            state["ingredients"], 
            state["instructions"], 
            state["cook_time"]
        )
        
        # Показываем результат
        response = f"✅ **Рецепт «{state['name']}» сохранён!**\n\n"
        response += f"📂 Категория: {state['category']}\n"
        response += f"⏰ Время: {state['cook_time']} мин\n"
        response += f"⚡ Сложность: {state['difficulty']}\n"
        response += f"🍽 Порций: {state['portions']}\n"
        if state['notes']:
            response += f"📝 Заметки: {state['notes']}\n"
        
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
            response += f"   ⏰ {r[6]} мин\n\n"
        await message.answer(response, parse_mode="Markdown", reply_markup=main_keyboard())
    
    del user_states[user_id]

# ========== ОБРАБОТЧИК ПОИСКА ==========
async def process_search(message: types.Message):
    user_id = message.from_user.id
    recipes = find_recipe_by_name(user_id, message.text)
    
    # Увеличиваем счётчик просмотров для статистики
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
            await message.answer(response, parse_mode="Markdown", reply_markup=favorite_keyboard(r[0], is_fav))

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    text = message.text
    
    # Проверяем состояние
    if user_id in user_states:
        state = user_states[user_id]
        if state.get("step") == "fridge":
            await process_fridge(message)
        else:
            await add_recipe_process(message)
        return
    
    # Обработка поиска (если пользователь ввел название без команды)
    if not text.startswith('/') and text not in ["📝 Добавить рецепт", "📖 Мои рецепты", "🔍 Найти рецепт", "🍽 Меню на сегодня", "🛒 Список покупок", "🥗 Что из остатков?", "⭐ Избранное", "🔥 Топ рецептов", "❓ Помощь"]:
        await process_search(message)
        return

# ========== ОБРАБОТКА INLINE КНОПОК (избранное/удаление) ==========
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
        
        # Обновляем кнопку
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
            await callback.answer("❌ Не удалось удалить рецепт")

# ========== ЗАПУСК БОТА ==========
async def main():
    print("🤖 Бот ChefMind с полным функционалом запущен!")
    print("✅ Кнопки: Добавление рецептов, Поиск, Меню, Список покупок")
    print("✅ Кнопки: Из остатков, Избранное, Топ рецептов")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())