import os
import logging
import random
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from starlette.applications import Starlette
from starlette.responses import Response, PlainTextResponse
from starlette.requests import Request
from starlette.routing import Route
import uvicorn
from database import (
    add_recipe, get_recipes, find_recipe_by_name, delete_recipe, 
    get_recipes_by_category, get_recipes_by_type, get_user_profile,
    save_user_profile, calculate_daily_calories, get_today_calories,
    get_today_macros, add_meal, clear_today_meals, adjust_by_portion
)

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
user_cart = {}

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    buttons = [
        [KeyboardButton("📝 Добавить рецепт")],
        [KeyboardButton("📖 Мои рецепты"), KeyboardButton("📚 Базовые рецепты")],
        [KeyboardButton("🔍 Найти рецепт"), KeyboardButton("🍽 Меню на сегодня")],
        [KeyboardButton("🧠 Умное меню"), KeyboardButton("📊 Статус питания")],
        [KeyboardButton("🛒 Список покупок"), KeyboardButton("🥗 Что из остатков?")],
        [KeyboardButton("⭐ Избранное"), KeyboardButton("🔥 Топ рецептов")],
        [KeyboardButton("🎉 Праздничные"), KeyboardButton("🏋️ Спортивное питание")],
        [KeyboardButton("🥗 По типу питания"), KeyboardButton("👤 Мой профиль")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def favorite_keyboard(recipe_id, is_favorite):
    keyboard = [
        [InlineKeyboardButton("❌ Удалить из избранного" if is_favorite else "⭐ Добавить в избранное", callback_data=f"fav_{recipe_id}")],
        [InlineKeyboardButton("🛒 Добавить в список покупок", callback_data=f"cart_{recipe_id}")],
        [InlineKeyboardButton("📝 Добавить в дневник", callback_data=f"eat_{recipe_id}")],
        [InlineKeyboardButton("🗑 Удалить рецепт", callback_data=f"del_{recipe_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def portion_keyboard(recipe_id, recipe_name):
    keyboard = [
        [InlineKeyboardButton("0.5x (половинная)", callback_data=f"portion_{recipe_id}_0.5")],
        [InlineKeyboardButton("1x (стандартная)", callback_data=f"portion_{recipe_id}_1.0")],
        [InlineKeyboardButton("1.5x (увеличенная)", callback_data=f"portion_{recipe_id}_1.5")],
        [InlineKeyboardButton("2x (двойная)", callback_data=f"portion_{recipe_id}_2.0")],
        [InlineKeyboardButton("🔙 Назад", callback_data=f"back_{recipe_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== КОМАНДА /start ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍🍳 **Привет! Я ChefMind — твой умный нутрициолог-помощник!**\n\n"
        "👇 **Начни с настройки профиля:** нажми «👤 Мой профиль»\n\n"
        "Или сразу попробуй «🧠 Умное меню»!",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ПОМОЩЬ ==========
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Помощь:**\n\n"
        "🧠 **Умное меню** — подбирает блюда под твой профиль\n"
        "📊 **Статус питания** — показывает прогресс за день\n"
        "👤 **Мой профиль** — настройка цели, веса, аллергий\n"
        "🛒 **Список покупок** — из выбранных рецептов\n\n"
        "📝 **Добавить рецепт** — создай новое блюдо с БЖУ\n"
        "🔍 **Найти рецепт** — поиск по названию\n"
        "⭐ **Избранное** — сохраняй любимые рецепты\n\n"
        "💡 **Совет:** Настрой профиль, чтобы бот подбирал идеальное меню!",
        reply_markup=main_keyboard()
    )

# ========== ПРОФИЛЬ (ПОКАЗАТЬ) ==========
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    
    if not profile:
        context.user_data['profile_setup'] = {'step': 'current_weight'}
        await update.message.reply_text(
            "👤 **Давай настроим твой профиль!**\n\n"
            "Шаг 1/7: Какой у тебя текущий вес? (в кг, например: 70)"
        )
        return
    
    goal_names = {'lose': '📉 Похудение', 'maintain': '📊 Поддержание', 'gain': '📈 Набор массы'}
    activity_names = {
        'sedentary': 'Сидячий (офисная работа)',
        'light': 'Лёгкая (1-2 тренировки в неделю)',
        'moderate': 'Умеренная (3-4 тренировки)',
        'active': 'Активная (5+ тренировок)',
        'very_active': 'Очень активная (физическая работа)'
    }
    
    await update.message.reply_text(
        f"📊 **Твой профиль:**\n\n"
        f"🎯 Цель: {goal_names.get(profile['goal'], 'Не указана')}\n"
        f"⚖️ Текущий вес: {profile['current_weight']} кг\n"
        f"🎯 Целевой вес: {profile['target_weight']} кг\n"
        f"📏 Рост: {profile['height']} см\n"
        f"🎂 Возраст: {profile['age']} лет\n"
        f"🚻 Пол: {'Мужской' if profile['gender'] == 'male' else 'Женский'}\n"
        f"🏃 Активность: {activity_names.get(profile['activity_level'], 'Не указана')}\n"
        f"🔥 Дневной лимит: {profile['daily_calorie_limit']} ккал\n\n"
        f"❌ Нелюбимые: {', '.join(profile['disliked_foods']) if profile['disliked_foods'] else 'Нет'}\n"
        f"⚠️ Аллергии: {', '.join(profile['allergies']) if profile['allergies'] else 'Нет'}\n\n"
        f"🔄 Чтобы изменить профиль, используй /setup",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== НАСТРОЙКА ПРОФИЛЯ ==========
async def setup_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['profile_setup'] = {'step': 'current_weight'}
    await update.message.reply_text(
        "🔄 **Настройка профиля**\n\n"
        "Шаг 1/7: Какой у тебя текущий вес? (в кг, например: 70)"
    )

async def process_profile_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    setup = context.user_data.get('profile_setup', {})
    step = setup.get('step')
    
    # Создаём новый профиль (не загружаем старый)
    profile = {
        'current_weight': 70.0,
        'target_weight': 70.0,
        'height': 170.0,
        'age': 30,
        'gender': 'male',
        'activity_level': 'moderate',
        'daily_calorie_limit': 2000,
        'disliked_foods': [],
        'allergies': []
    }
    
    # Шаг 1: Текущий вес
    if step == 'current_weight':
        try:
            profile['current_weight'] = float(text)
            setup['step'] = 'target_weight'
            await update.message.reply_text(
                f"✅ Текущий вес: {text} кг\n\n"
                f"Шаг 2/7: Какой вес ты хочешь достичь? (в кг)"
            )
        except:
            await update.message.reply_text("❌ Введи число, например: 70")
        return
    
    # Шаг 2: Целевой вес
    elif step == 'target_weight':
        try:
            target = float(text)
            profile['target_weight'] = target
            setup['step'] = 'gender'
            await update.message.reply_text(
                f"✅ Целевой вес: {target} кг\n\n"
                f"Шаг 3/7: Твой пол?\n1️⃣ Мужской\n2️⃣ Женский"
            )
        except:
            await update.message.reply_text("❌ Введи число, например: 75")
        return
    
    # Шаг 3: Пол
    elif step == 'gender':
        if text in ['1', 'мужской', 'муж', 'м']:
            profile['gender'] = 'male'
        elif text in ['2', 'женский', 'жен', 'ж']:
            profile['gender'] = 'female'
        else:
            await update.message.reply_text("❌ Напиши 1 (мужской) или 2 (женский)")
            return
        setup['step'] = 'age'
        await update.message.reply_text("Шаг 4/7: Сколько тебе лет?")
        return
    
    # Шаг 4: Возраст
    elif step == 'age':
        try:
            profile['age'] = int(text)
            setup['step'] = 'height'
            await update.message.reply_text("Шаг 5/7: Какой у тебя рост? (в см)")
        except:
            await update.message.reply_text("❌ Введи число, например: 30")
        return
    
    # Шаг 5: Рост
    elif step == 'height':
        try:
            profile['height'] = float(text)
            setup['step'] = 'activity'
            await update.message.reply_text(
                "🏃 Шаг 6/7: Твоя физическая активность?\n\n"
                "1️⃣ Сидячий (офис, мало движения)\n"
                "2️⃣ Лёгкая (1-2 тренировки в неделю)\n"
                "3️⃣ Умеренная (3-4 тренировки)\n"
                "4️⃣ Активная (5+ тренировок)\n"
                "5️⃣ Очень активная (физическая работа)\n\n"
                "Напиши номер:"
            )
        except:
            await update.message.reply_text("❌ Введи число, например: 170")
        return
    
    # Шаг 6: Активность и расчёт калорий
    elif step == 'activity':
        activity_map = {
            '1': 'sedentary',
            '2': 'light',
            '3': 'moderate',
            '4': 'active',
            '5': 'very_active'
        }
        if text in activity_map:
            profile['activity_level'] = activity_map[text]
            
            # Определяем цель
            if profile['target_weight'] > profile['current_weight']:
                goal = 'gain'
            elif profile['target_weight'] < profile['current_weight']:
                goal = 'lose'
            else:
                goal = 'maintain'
            
            # Рассчитываем калории
            profile['daily_calorie_limit'] = calculate_daily_calories(
                profile['current_weight'],
                profile['height'],
                profile['age'],
                profile['gender'],
                profile['activity_level'],
                goal
            )
            
            setup['step'] = 'disliked'
            await update.message.reply_text(
                f"✅ Активность выбрана\n\n"
                f"🔥 **Рекомендуемая дневная норма: {profile['daily_calorie_limit']} ккал**\n\n"
                f"Шаг 7/7: Есть ли у тебя нелюбимые продукты?\n"
                f"Напиши через запятую (например: печень, грибы)\n"
                f"Или напиши «нет»:"
            )
        else:
            await update.message.reply_text("❌ Введи номер от 1 до 5")
        return
    
    # Шаг 7: Нелюбимые продукты
    elif step == 'disliked':
        if text.lower() != 'нет':
            profile['disliked_foods'] = [x.strip() for x in text.split(',')]
        setup['step'] = 'allergies'
        await update.message.reply_text(
            "⚠️ Есть ли у тебя аллергии?\n"
            "Напиши через запятую (например: орехи, молоко)\n"
            "Или напиши «нет»:"
        )
        return
    
    # Шаг 8: Аллергии и сохранение
    elif step == 'allergies':
        if text.lower() != 'нет':
            profile['allergies'] = [x.strip() for x in text.split(',')]
        
        # Сохраняем профиль
        save_user_profile(user_id, profile)
        del context.user_data['profile_setup']
        
        # Определяем текст цели
        if profile['target_weight'] > profile['current_weight']:
            goal_text = "📈 Набор массы"
        elif profile['target_weight'] < profile['current_weight']:
            goal_text = "📉 Похудение"
        else:
            goal_text = "📊 Поддержание веса"
        
        await update.message.reply_text(
            f"✅ **Профиль сохранён!**\n\n"
            f"🎯 Цель: {goal_text}\n"
            f"⚖️ Текущий вес: {profile['current_weight']} кг\n"
            f"🎯 Целевой вес: {profile['target_weight']} кг\n"
            f"🔥 Дневной лимит: {profile['daily_calorie_limit']} ккал\n"
            f"❌ Нелюбимые: {', '.join(profile['disliked_foods']) if profile['disliked_foods'] else 'Нет'}\n"
            f"⚠️ Аллергии: {', '.join(profile['allergies']) if profile['allergies'] else 'Нет'}\n\n"
            f"Теперь бот будет подбирать рецепты с учётом твоей цели! 🧠",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return

# ========== СТАТУС ПИТАНИЯ ==========
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    
    if not profile:
        await update.message.reply_text("👤 Сначала настрой профиль через 👤 Мой профиль или /profile")
        return
    
    today_calories = get_today_calories(user_id)
    remaining = profile['daily_calorie_limit'] - today_calories
    macros = get_today_macros(user_id)
    
    percent = min(100, int((today_calories / profile['daily_calorie_limit']) * 100))
    bar = "█" * (percent // 5) + "░" * (20 - percent // 5)
    
    goal_names = {'lose': '📉 Похудение', 'maintain': '📊 Поддержание', 'gain': '📈 Набор массы'}
    
    await update.message.reply_text(
        f"📊 **Статус питания на сегодня:**\n\n"
        f"🎯 Цель: {goal_names.get(profile['goal'], 'Не указана')}\n"
        f"🔥 Калории: {today_calories} / {profile['daily_calorie_limit']} ккал\n"
        f"`{bar}` {percent}%\n\n"
        f"💪 **Осталось:** {remaining} ккал\n\n"
        f"🥩 **Белки:** {macros['protein']} г\n"
        f"🧈 **Жиры:** {macros['fat']} г\n"
        f"🍚 **Углеводы:** {macros['carbs']} г\n\n"
        f"🍽 Чтобы подобрать блюдо под остаток калорий, нажми «🧠 Умное меню»",
        parse_mode="Markdown"
    )

# ========== УМНОЕ МЕНЮ ==========
async def smart_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    
    if not profile:
        await update.message.reply_text("👤 Сначала настрой профиль через 👤 Мой профиль или /profile")
        return
    
    remaining = profile['daily_calorie_limit'] - get_today_calories(user_id)
    
    if remaining <= 0:
        await update.message.reply_text("🎉 Ты уже выполнил дневную норму калорий!")
        return
    
    recipes = get_recipes(user_id)
    
    # Фильтруем по аллергиям
    filtered = []
    for r in recipes:
        ingredients = r[4].lower()
        allergy_found = False
        for allergy in profile['allergies']:
            if allergy.lower() in ingredients:
                allergy_found = True
                break
        if allergy_found:
            continue
        disliked_found = False
        for disliked in profile['disliked_foods']:
            if disliked.lower() in ingredients:
                disliked_found = True
                break
        if disliked_found:
            continue
        if r[7] <= remaining:
            filtered.append(r)
    
    if not filtered:
        await update.message.reply_text("❌ Нет рецептов, подходящих под твои ограничения")
        return
    
    # Выбираем по категориям
    breakfasts = [r for r in filtered if r[3].lower() == "завтрак"]
    lunches = [r for r in filtered if r[3].lower() == "обед"]
    dinners = [r for r in filtered if r[3].lower() == "ужин"]
    
    selected = {}
    if breakfasts:
        selected['завтрак'] = random.choice(breakfasts)
    if lunches:
        selected['обед'] = random.choice(lunches)
    if dinners:
        selected['ужин'] = random.choice(dinners)
    
    if not selected:
        await update.message.reply_text("❌ Нет подходящих рецептов. Добавь новые!")
        return
    
    response = "🧠 **Умное меню:**\n\n"
    total = 0
    for meal_type, recipe in selected.items():
        response += f"🍽 **{meal_type.capitalize()}:** {recipe[2]}\n"
        response += f"   ⏰ {recipe[6]} мин | 🔥 {recipe[7]} ккал\n\n"
        total += recipe[7]
    
    response += f"📊 **Итого:** {total} ккал"
    response += f"\n💪 **Останется:** {remaining - total} ккал"
    
    await update.message.reply_text(response, parse_mode="Markdown")
    user_cart[user_id] = [(r, 1.0) for r in selected.values()]

# ========== МЕНЮ НА СЕГОДНЯ ==========
async def menu_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes(user_id)
    
    breakfasts = [r for r in recipes if r[3].lower() == "завтрак"]
    lunches = [r for r in recipes if r[3].lower() == "обед"]
    dinners = [r for r in recipes if r[3].lower() == "ужин"]
    
    if not breakfasts or not lunches or not dinners:
        await update.message.reply_text("❌ Нет рецептов в одной из категорий (завтрак, обед, ужин)")
        return
    
    selected = {
        "завтрак": random.choice(breakfasts),
        "обед": random.choice(lunches),
        "ужин": random.choice(dinners)
    }
    
    user_cart[user_id] = [(r, 1.0) for r in selected.values()]
    
    response = "🍽 **Меню на сегодня:**\n\n"
    for meal_type, recipe in selected.items():
        response += f"☀️ {meal_type.capitalize()}: {recipe[2]}\n"
        response += f"   ⏰ {recipe[6]} мин | 🔥 {recipe[7]} ккал\n\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== СПИСОК ПОКУПОК ==========
async def shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = user_cart.get(user_id, [])
    
    if not cart:
        await update.message.reply_text("🛒 Сначала сгенерируй меню")
        return
    
    ingredients = {}
    for recipe, portion in cart:
        items = recipe[4].split(',')
        for item in items:
            item = item.strip().lower()
            if item and len(item) > 2:
                ingredients[item] = ingredients.get(item, 0) + 1
    
    response = "🛒 **Список покупок:**\n\n"
    for ing in sorted(ingredients.keys()):
        response += f"• {ing}\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ПОИСК РЕЦЕПТА ==========
async def find_recipe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Напиши название блюда:")
    context.user_data['search_mode'] = True

async def process_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.message.text
    recipes = find_recipe_by_name(user_id, query)
    
    if not recipes:
        await update.message.reply_text(f"❌ Рецепт «{query}» не найден")
    else:
        for r in recipes:
            is_fav = r[0] in user_favorites.get(user_id, set())
            response = f"🍽 **{r[2]}**\n\n📂 {r[3]}\n🛒 {r[4]}\n👨‍🍳 {r[5]}\n⏰ {r[6]} мин\n🔥 {r[7]} ккал"
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=favorite_keyboard(r[0], is_fav))
    
    context.user_data['search_mode'] = False

# ========== МОИ РЕЦЕПТЫ ==========
async def my_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes(user_id)
    user_recipes = [r for r in recipes if r[1] != 0]
    
    if not user_recipes:
        await update.message.reply_text("📭 У тебя пока нет своих рецептов")
        return
    
    response = "📖 **Мои рецепты:**\n\n"
    for r in user_recipes[:20]:
        response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== БАЗОВЫЕ РЕЦЕПТЫ ==========
async def base_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import cursor
    cursor.execute('SELECT * FROM recipes WHERE user_id = 0 ORDER BY id')
    recipes = cursor.fetchall()
    
    response = "📚 **Базовые рецепты:**\n\n"
    for r in recipes[:25]:
        response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ИЗБРАННОЕ ==========
async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    favs = user_favorites.get(user_id, set())
    
    if not favs:
        await update.message.reply_text("⭐ Нет избранных рецептов")
        return
    
    response = "⭐ **Избранное:**\n\n"
    for fid in favs:
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == fid:
                response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
                break
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ТОП РЕЦЕПТОВ ==========
async def top_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes(user_id)
    
    if not recipes:
        await update.message.reply_text("📭 Нет рецептов")
        return
    
    stats = []
    for r in recipes:
        views = recipe_stats.get((user_id, r[0]), 0)
        stats.append((r[2], views, r[6], r[7]))
    stats.sort(key=lambda x: x[1], reverse=True)
    
    response = "🔥 **Топ рецептов:**\n\n"
    for i, (name, views, time, cal) in enumerate(stats[:5], 1):
        response += f"{i}. {name}\n   👁 {views} просмотров | ⏰ {time} мин | 🔥 {cal} ккал\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ПРАЗДНИЧНЫЕ ==========
async def holiday_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes_by_type(user_id, "праздничное")
    
    if not recipes:
        await update.message.reply_text("🎉 Праздничные рецепты:\n• Оливье\n• Сельдь под шубой\n• Мимоза\n• Наполеон\n• Тирамису")
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
        await update.message.reply_text("🏋️ Спортивное питание:\n• Куриное филе с гречкой\n• Омлет с овощами\n• Творог с ягодами\n• Протеиновый смузи")
        return
    
    response = "🏋️ **Спортивное питание:**\n\n"
    for r in recipes:
        response += f"🍽 {r[2]}\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал | 🥩 {r[8]}г белка\n   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ПО ТИПУ ПИТАНИЯ ==========
async def by_type_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("🥗 Диетическое")],
        [KeyboardButton("🌱 Постное")],
        [KeyboardButton("🍳 Обычное")],
        [KeyboardButton("🔙 Назад")]
    ], resize_keyboard=True)
    await update.message.reply_text("Выбери тип питания:", reply_markup=keyboard)

async def show_by_type(update: Update, context: ContextTypes.DEFAULT_TYPE, type_text):
    type_map = {"🥗 Диетическое": "диетическое", "🌱 Постное": "постное", "🍳 Обычное": "обычное"}
    recipe_type = type_map.get(type_text)
    if not recipe_type:
        return
    
    user_id = update.effective_user.id
    recipes = get_recipes_by_type(user_id, recipe_type)
    
    if not recipes:
        await update.message.reply_text(f"❌ Нет рецептов в категории {type_text}")
        return
    
    response = f"🥗 **{type_text}:**\n\n"
    for r in recipes[:15]:
        response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=main_keyboard())

# ========== ЧТО ИЗ ОСТАТКОВ ==========
async def from_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🥗 Напиши продукты через запятую:\nПример: яйца, помидоры, сыр")
    context.user_data['fridge_mode'] = True

async def process_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    products = [p.strip().lower() for p in update.message.text.split(',')]
    
    recipes = get_recipes(user_id)
    matches = []
    for r in recipes:
        ingredients = r[4].lower()
        match_count = sum(1 for p in products if p in ingredients)
        if match_count > 0:
            matches.append((r, match_count))
    matches.sort(key=lambda x: x[1], reverse=True)
    
    if not matches:
        await update.message.reply_text("🥗 Ничего не найдено")
    else:
        response = "🥗 **Из остатков:**\n\n"
        for r, cnt in matches[:5]:
            response += f"🍽 {r[2]} (совпадений: {cnt})\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал\n\n"
        await update.message.reply_text(response, parse_mode="Markdown")
    
    context.user_data['fridge_mode'] = False

# ========== ДОБАВЛЕНИЕ РЕЦЕПТА ==========
async def add_recipe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"step": "name"}
    await update.message.reply_text("📝 **Добавление рецепта**\n\nШаг 1/11: Напиши название блюда")

async def add_recipe_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states[user_id]
    text = update.message.text
    step = state["step"]
    
    if step == "name":
        state["name"] = text
        state["step"] = "category"
        await update.message.reply_text("Шаг 2/11: Категория (завтрак, обед, ужин, салат, десерт, спорт)")
    elif step == "category":
        state["category"] = text.lower()
        state["step"] = "ingredients"
        await update.message.reply_text("Шаг 3/11: Ингредиенты через запятую")
    elif step == "ingredients":
        state["ingredients"] = text
        state["step"] = "instructions"
        await update.message.reply_text("Шаг 4/11: Инструкция приготовления")
    elif step == "instructions":
        state["instructions"] = text
        state["step"] = "time"
        await update.message.reply_text("Шаг 5/11: Время в минутах")
    elif step == "time":
        try:
            state["cook_time"] = int(text)
            state["step"] = "calories"
            await update.message.reply_text("Шаг 6/11: Калории для порции 1x")
        except:
            await update.message.reply_text("❌ Введи число")
    elif step == "calories":
        try:
            state["calories"] = int(text)
            state["step"] = "protein"
            await update.message.reply_text("Шаг 7/11: Белки (г)")
        except:
            await update.message.reply_text("❌ Введи число")
    elif step == "protein":
        try:
            state["protein"] = float(text)
            state["step"] = "fat"
            await update.message.reply_text("Шаг 8/11: Жиры (г)")
        except:
            await update.message.reply_text("❌ Введи число")
    elif step == "fat":
        try:
            state["fat"] = float(text)
            state["step"] = "carbs"
            await update.message.reply_text("Шаг 9/11: Углеводы (г)")
        except:
            await update.message.reply_text("❌ Введи число")
    elif step == "carbs":
        try:
            state["carbs"] = float(text)
            state["step"] = "type"
            await update.message.reply_text("Шаг 10/11: Тип (диетическое, постное, обычное, праздничное, спортивное)")
        except:
            await update.message.reply_text("❌ Введи число")
    elif step == "type":
        valid = ["диетическое", "постное", "обычное", "праздничное", "спортивное"]
        if text.lower() in valid:
            state["recipe_type"] = text.lower()
            state["step"] = "tags"
            await update.message.reply_text("Шаг 11/11: Теги через запятую (или «нет»)")
        else:
            await update.message.reply_text(f"❌ Неверный тип. Выбери из: {', '.join(valid)}")
    elif step == "tags":
        tags = "" if text.lower() == "нет" else text
        add_recipe(
            user_id, state["name"], state["category"], state["ingredients"],
            state["instructions"], state["cook_time"], state["calories"],
            state["protein"], state["fat"], state["carbs"],
            state["recipe_type"], tags
        )
        await update.message.reply_text(
            f"✅ **Рецепт «{state['name']}» сохранён!**\n\n"
            f"🔥 {state['calories']} ккал | 🥩 {state['protein']}г б | 🧈 {state['fat']}г ж | 🍚 {state['carbs']}г у",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        del user_states[user_id]

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Состояния
    if user_id in user_states:
        await add_recipe_process(update, context)
        return
    
    if context.user_data.get('fridge_mode'):
        await process_fridge(update, context)
        return
    
    if context.user_data.get('search_mode'):
        await process_search(update, context)
        return
    
    if context.user_data.get('profile_setup'):
        await process_profile_setup(update, context)
        return
    
    # Кнопки
    if text == "📝 Добавить рецепт":
        await add_recipe_start(update, context)
    elif text == "📖 Мои рецепты":
        await my_recipes(update, context)
    elif text == "📚 Базовые рецепты":
        await base_recipes(update, context)
    elif text == "🔍 Найти рецепт":
        await find_recipe_start(update, context)
    elif text == "🍽 Меню на сегодня":
        await menu_today(update, context)
    elif text == "🧠 Умное меню":
        await smart_menu(update, context)
    elif text == "📊 Статус питания":
        await status_command(update, context)
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
    elif text == "👤 Мой профиль":
        await profile_command(update, context)
    elif text == "🔙 Назад":
        await update.message.reply_text("Главное меню", reply_markup=main_keyboard())
    elif text == "❓ Помощь":
        await help_command(update, context)
    else:
        await update.message.reply_text("Используй кнопки внизу 👇", reply_markup=main_keyboard())

# ========== INLINE КНОПКИ ==========
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
        else:
            user_favorites[user_id].add(recipe_id)
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == recipe_id:
                is_fav = recipe_id in user_favorites[user_id]
                await query.edit_message_reply_markup(reply_markup=favorite_keyboard(recipe_id, is_fav))
                break
    
    elif data.startswith("cart_"):
        recipe_id = int(data.split("_")[1])
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == recipe_id:
                if user_id not in user_cart:
                    user_cart[user_id] = []
                if (r, 1.0) not in user_cart[user_id]:
                    user_cart[user_id].append((r, 1.0))
                    await query.answer(f"✅ {r[2]} добавлен в список покупок!")
                else:
                    await query.answer("⚠️ Уже в списке")
                break
    
    elif data.startswith("eat_"):
        recipe_id = int(data.split("_")[1])
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == recipe_id:
                await query.edit_message_reply_markup(reply_markup=portion_keyboard(recipe_id, r[2]))
                break
    
    elif data.startswith("portion_"):
        parts = data.split("_")
        recipe_id = int(parts[1])
        portion = float(parts[2])
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == recipe_id:
                adj = adjust_by_portion(r, portion)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("☀️ Завтрак", callback_data=f"meal_{recipe_id}_{portion}_breakfast")],
                    [InlineKeyboardButton("🌤️ Обед", callback_data=f"meal_{recipe_id}_{portion}_lunch")],
                    [InlineKeyboardButton("🌙 Ужин", callback_data=f"meal_{recipe_id}_{portion}_dinner")],
                    [InlineKeyboardButton("🍎 Перекус", callback_data=f"meal_{recipe_id}_{portion}_snack")],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"eat_{recipe_id}")]
                ])
                await query.edit_message_text(
                    f"🍽 **{r[2]}**\n\n🔥 {adj['calories']} ккал\n🥩 {adj['protein']}г б | 🧈 {adj['fat']}г ж | 🍚 {adj['carbs']}г у\n\nВыбери приём пищи:",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                break
    
    elif data.startswith("meal_"):
        parts = data.split("_")
        recipe_id = int(parts[1])
        portion = float(parts[2])
        meal_type = parts[3]
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == recipe_id:
                adj = adjust_by_portion(r, portion)
                add_meal(user_id, meal_type, r[0], portion, adj['calories'], adj['protein'], adj['fat'], adj['carbs'])
                await query.answer(f"✅ {r[2]} ({portion}x) добавлен в дневник!")
                await query.delete_message()
                break
    
    elif data.startswith("del_"):
        recipe_id = int(data.split("_")[1])
        if delete_recipe(recipe_id, user_id):
            await query.message.delete()
            await query.message.reply_text("🗑 Рецепт удалён!")
    
    elif data.startswith("back_"):
        recipe_id = int(data.split("_")[1])
        recipes = get_recipes(user_id)
        for r in recipes:
            if r[0] == recipe_id:
                is_fav = r[0] in user_favorites.get(user_id, set())
                await query.edit_message_reply_markup(reply_markup=favorite_keyboard(recipe_id, is_fav))
                break

# ========== ЗАПУСК WEBHOOK ==========
async def start_webhook():
    app = Application.builder().token(TOKEN).build()
    await app.initialize()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("setup", setup_profile))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("smart_menu", smart_menu))
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