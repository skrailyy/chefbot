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
    get_today_macros, add_meal, clear_today_meals, adjust_by_portion,
    get_weekly_menu, save_weekly_menu
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
        [KeyboardButton("📅 Меню на неделю"), KeyboardButton("🛒 Список покупок")],
        [KeyboardButton("🥗 Что из остатков?"), KeyboardButton("⭐ Избранное")],
        [KeyboardButton("🔥 Топ рецептов"), KeyboardButton("🎉 Праздничные")],
        [KeyboardButton("🏋️ Спортивное питание"), KeyboardButton("🥗 По типу питания")],
        [KeyboardButton("👤 Мой профиль"), KeyboardButton("❓ Помощь")]
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

def weekly_menu_keyboard():
    days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
    keyboard = []
    for i in range(0, 7, 2):
        row = []
        if i < 7:
            row.append(InlineKeyboardButton(days[i], callback_data=f"weekday_{i}"))
        if i + 1 < 7:
            row.append(InlineKeyboardButton(days[i + 1], callback_data=f"weekday_{i + 1}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("✅ Сохранить меню", callback_data="save_weekly")])
    return InlineKeyboardMarkup(keyboard)

# ========== ПРОФИЛЬ ==========

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    

    user_id = update.effective_user.id
    profile = get_user_profile(user_id)

    if not profile:
        context.user_data['profile_setup'] = {'step': 'current_weight'}
        await update.message.reply_text(
            "**Давай настроим твой профиль!**\n\n"
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
        f"❌ Нелюбимые продукты: {', '.join(profile['disliked_foods']) if profile['disliked_foods'] else 'Нет'}\n"
        f"⚠️ Аллергии: {', '.join(profile['allergies']) if profile['allergies'] else 'Нет'}\n\n"
        f"🔄 Чтобы изменить профиль, используй /setup",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def setup_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['profile_setup'] = {'step': 'current_weight'}
    await update.message.reply_text(
        "🔄 **Настройка профиля**\n\n"
        "Шаг 1/7: Какой у тебя текущий вес? (в кг)"
    )

async def process_profile_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    setup = context.user_data.get('profile_setup', {})
    step = setup.get('step')

    

    # Загружаем текущий профиль или создаём новый
    profile = get_user_profile(user_id)
    if not profile:
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
    
    # ШАГ 1: Текущий вес
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
    
    # ШАГ 2: Целевой вес
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
    
    # ШАГ 3: Пол
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
    
    # ШАГ 4: Возраст
    elif step == 'age':
        try:
            profile['age'] = int(text)
            setup['step'] = 'height'
            await update.message.reply_text("Шаг 5/7: Какой у тебя рост? (в см)")
        except:
            await update.message.reply_text("❌ Введи число, например: 30")
        return
    
    # ШАГ 5: Рост
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
    
    # ШАГ 6: Активность и расчёт калорий
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
    
    # ШАГ 7: Нелюбимые продукты
    elif step == 'disliked':
        if text.lower() != 'нет':
            profile['disliked_foods'] = [x.strip() for x in text.split(',')]
        setup['step'] = 'allergies'
        await update.message.reply_text(
            f"⚠️ Есть ли у тебя аллергии?\n"
            f"Напиши через запятую (например: орехи, молоко)\n"
            f"Или напиши «нет»:"
        )
        return
    
    # ШАГ 8: Аллергии и сохранение
    elif step == 'allergies':
        if text.lower() != 'нет':
            profile['allergies'] = [x.strip() for x in text.split(',')]
        
        # СОХРАНЯЕМ ПРОФИЛЬ
        save_user_profile(user_id, profile)
        del context.user_data['profile_setup']
        
        # Определяем текст цели для красивого вывода
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
    
    elif step == 'age':
        try:
            profile['age'] = int(text)
            setup['step'] = 'height'
            await update.message.reply_text("Шаг 5/7: Какой у тебя рост? (в см)")
        except:
            await update.message.reply_text("❌ Введи число, например: 30")
        return
    
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
            
            # Определяем цель для расчёта калорий
            if profile['target_weight'] > profile['current_weight']:
                goal = 'gain'
            elif profile['target_weight'] < profile['current_weight']:
                goal = 'lose'
            else:
                goal = 'maintain'
            
            # Рассчитываем дневную норму калорий
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
    
    elif step == 'disliked':
        if text.lower() != 'нет':
            profile['disliked_foods'] = [x.strip() for x in text.split(',')]
        setup['step'] = 'allergies'
        await update.message.reply_text(
            f"⚠️ Есть ли у тебя аллергии?\n"
            f"Напиши через запятую (например: орехи, молоко)\n"
            f"Или напиши «нет»:"
        )
        return
    
    elif step == 'allergies':
        if text.lower() != 'нет':
            profile['allergies'] = [x.strip() for x in text.split(',')]
        
        # Сохраняем профиль
        save_user_profile(user_id, profile)
        del context.user_data['profile_setup']
        
        # Определяем текст цели для показа
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
        await update.message.reply_text(
            "🎉 Ты уже выполнил дневную норму калорий!\n"
            "💪 Отдохни или займись спортом!\n\n"
            "🍽 Завтра бот снова подберёт для тебя меню."
        )
        return

    recipes = get_recipes(user_id)

    # Фильтруем по аллергиям и нелюбимым продуктам
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

        filtered.append(r)

    if not filtered:
        await update.message.reply_text(
            f"❌ Нет рецептов, подходящих под твои ограничения.\n\n"
            f"💡 Попробуй добавить новые рецепты через «Добавить рецепт»"
        )
        return

    # Группируем по категориям
    breakfasts = [r for r in filtered if r[3].lower() == "завтрак"]
    lunches = [r for r in filtered if r[3].lower() == "обед"]
    dinners = [r for r in filtered if r[3].lower() == "ужин"]

    if not breakfasts or not lunches or not dinners:
        missing = []
        if not breakfasts:
            missing.append("завтрак")
        if not lunches:
            missing.append("обед")
        if not dinners:
            missing.append("ужин")
        await update.message.reply_text(
            f"❌ Нет рецептов в категориях: {', '.join(missing)}\n\n"
            f"📝 Добавь рецепты через «Добавить рецепт»"
        )
        return

    # Выбираем случайные рецепты
    selected = {
        "завтрак": random.choice(breakfasts),
        "обед": random.choice(lunches),
        "ужин": random.choice(dinners)
    }

    # Считаем общую калорийность
    total_calories = sum(r[7] for r in selected.values())

    # Умное масштабирование порций
    if total_calories < remaining:
        target = min(remaining, profile['daily_calorie_limit'])
        scale = target / total_calories
        scale = max(0.7, min(2.5, scale))
        scale = round(scale, 1)

        response = "🧠 **Умное меню с автоматической корректировкой порций:**\n\n"
        total = 0
        for meal_type, recipe in selected.items():
            adj = adjust_by_portion(recipe, scale)
            response += f"🍽 **{meal_type.capitalize()}:** {recipe[2]}\n"
            response += f"   ⏰ {recipe[6]} мин | 🔥 {adj['calories']} ккал\n"
            response += f"   🥩 {adj['protein']}г б | 🧈 {adj['fat']}г ж | 🍚 {adj['carbs']}г у\n"
            response += f"   🍽 Порция увеличена: {scale}x (было 1x)\n\n"
            total += adj['calories']

        response += f"📊 **Итого:** {total} ккал"
        response += f"\n🎯 **Цель:** {profile['daily_calorie_limit']} ккал"
        response += f"\n💪 **Осталось:** {remaining - total} ккал"

        if scale > 1.5:
            response += f"\n\n⚠️ Порции увеличены значительно ({scale}x). Для более точного попадания в норму добавь больше рецептов с разной калорийностью."

        await update.message.reply_text(response, parse_mode="Markdown")
        user_cart[user_id] = [(recipe, scale) for recipe in selected.values()]

    else:
        response = "🧠 **Умное меню с учётом твоего профиля:**\n\n"
        total = 0
        for meal_type, recipe in selected.items():
            response += f"🍽 **{meal_type.capitalize()}:** {recipe[2]}\n"
            response += f"   ⏰ {recipe[6]} мин | 🔥 {recipe[7]} ккал\n"
            response += f"   🥩 {recipe[8]}г б | 🧈 {recipe[9]}г ж | 🍚 {recipe[10]}г у\n\n"
            total += recipe[7]

        response += f"📊 **Итого:** {total} ккал"
        response += f"\n🎯 **Цель:** {profile['daily_calorie_limit']} ккал"
        response += f"\n💪 **Осталось:** {remaining - total} ккал"

        await update.message.reply_text(response, parse_mode="Markdown")
        user_cart[user_id] = [(recipe, 1.0) for recipe in selected.values()]

# ========== МЕНЮ НА СЕГОДНЯ ==========
async def menu_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes(user_id)

    breakfasts = [r for r in recipes if r[3].lower() == "завтрак"]
    lunches = [r for r in recipes if r[3].lower() == "обед"]
    dinners = [r for r in recipes if r[3].lower() == "ужин"]

    missing = []
    if not breakfasts:
        missing.append("завтрак")
    if not lunches:
        missing.append("обед")
    if not dinners:
        missing.append("ужин")

    if missing:
        await update.message.reply_text(
            f"❌ Нет рецептов в категориях: {', '.join(missing)}\n\n"
            f"📝 Добавь рецепты через «Добавить рецепт»"
        )
        return

    selected = {
        "завтрак": random.choice(breakfasts),
        "обед": random.choice(lunches),
        "ужин": random.choice(dinners)
    }

    response = "🍽 **Меню на сегодня:**\n\n"
    for meal_type, recipe in selected.items():
        response += f"☀️ {meal_type.capitalize()}: {recipe[2]}\n"
        response += f"   ⏰ {recipe[6]} мин | 🔥 {recipe[7]} ккал\n\n"

    await update.message.reply_text(response, parse_mode="Markdown")
    user_cart[user_id] = [(recipe, 1.0) for recipe in selected.values()]

# ========== МЕНЮ НА НЕДЕЛЮ ==========
async def weekly_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 **Создание меню на неделю**\n\n"
        "Выбери день недели:",
        reply_markup=weekly_menu_keyboard()
    )

# ========== СПИСОК ПОКУПОК ==========
async def shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = user_cart.get(user_id, [])

    if not cart:
        await update.message.reply_text(
            "🛒 Сначала сгенерируй меню («Меню на сегодня» или «Умное меню»)\n"
            "Или добавь рецепты в корзину кнопкой «Добавить в список покупок»"
        )
        return

    ingredients = {}
    for recipe, portion in cart:
        adj = adjust_by_portion(recipe, portion)
        items = adj['ingredients'].split(',')
        for item in items:
            item = item.strip().lower()
            if item and len(item) > 2:
                ingredients[item] = ingredients.get(item, 0) + 1

    response = "🛒 **Список покупок:**\n\n"
    for ing, count in sorted(ingredients.items()):
        response += f"• {ing}\n"

    response += f"\n📊 **Всего позиций:** {len(ingredients)}"
    response += f"\n🍽 **Выбрано блюд:** {len(cart)}"

    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ПОИСК РЕЦЕПТА ==========
async def find_recipe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Напиши название блюда:")

async def process_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.message.text
    recipes = find_recipe_by_name(user_id, query)

    for r in recipes:
        recipe_stats[(user_id, r[0])] = recipe_stats.get((user_id, r[0]), 0) + 1

    if not recipes:
        await update.message.reply_text(f"❌ Рецепт «{query}» не найден")
    else:
        for r in recipes:
            is_fav = r[0] in user_favorites.get(user_id, set())
            response = f"🍽 **{r[2]}**\n\n"
            response += f"📂 Категория: {r[3]}\n"
            response += f"🛒 Ингредиенты (1x): {r[4]}\n"
            response += f"👨‍🍳 Приготовление: {r[5]}\n"
            response += f"⏰ Время: {r[6]} мин\n"
            response += f"🔥 Калории (1x): {r[7]} ккал\n"
            response += f"🥩 {r[8]}г б | 🧈 {r[9]}г ж | 🍚 {r[10]}г у"
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=favorite_keyboard(r[0], is_fav))

# ========== МОИ РЕЦЕПТЫ ==========
async def my_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes(user_id)
    user_recipes = [r for r in recipes if r[1] != 0]

    if not user_recipes:
        await update.message.reply_text("📭 У тебя пока нет своих рецептов.")
        return

    response = "📖 **Мои рецепты:**\n\n"
    for r in user_recipes[:20]:
        response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал (1x)\n   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== БАЗОВЫЕ РЕЦЕПТЫ ==========
async def base_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import cursor
    cursor.execute('SELECT * FROM recipes WHERE user_id = 0 ORDER BY id')
    recipes = cursor.fetchall()

    response = "📚 **Базовые рецепты (50+):**\n\n"
    for r in recipes[:25]:
        emoji = ""
        if r[11] == "праздничное":
            emoji = "🎉 "
        elif r[11] == "диетическое":
            emoji = "🥗 "
        elif r[11] == "спортивное":
            emoji = "🏋️ "
        response += f"{emoji}🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал (1x)\n   ─────────────\n"
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
                response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал (1x)\n   ─────────────\n"
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
        response += f"{i}. {name}\n   👁 {views} просмотров | ⏰ {time} мин | 🔥 {cal} ккал (1x)\n"

    if not any(s[1] > 0 for s in stats):
        response += "\n📊 Нет просмотров. Ищи рецепты!"

    await update.message.reply_text(response, parse_mode="Markdown")

# ========== ПРАЗДНИЧНЫЕ ==========
async def holiday_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes_by_type(user_id, "праздничное")

    if not recipes:
        await update.message.reply_text("🎉 Оливье, Сельдь под шубой, Мимоза, Наполеон, Тирамису")
        return

    response = "🎉 **Праздничные рецепты:**\n\n"
    for r in recipes:
        response += f"🍽 {r[2]}\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал (1x)\n   ─────────────\n"
    await update.message.reply_text(response, parse_mode="Markdown")

# ========== СПОРТИВНОЕ ПИТАНИЕ ==========
async def sport_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    recipes = get_recipes_by_type(user_id, "спортивное")

    if not recipes:
        await update.message.reply_text("🏋️ Куриное филе с гречкой, Омлет с овощами, Творог с ягодами, Протеиновый смузи")
        return

    response = "🏋️ **Спортивное питание:**\n\n"
    for r in recipes:
        response += f"🍽 {r[2]}\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал (1x) | 🥩 {r[8]}г белка\n   ─────────────\n"
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
        response += f"🍽 {r[2]}\n   📂 {r[3]} | ⏰ {r[6]} мин | 🔥 {r[7]} ккал (1x)\n   ─────────────\n"
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
            response += f"🍽 {r[2]} (совпадений: {cnt})\n   ⏰ {r[6]} мин | 🔥 {r[7]} ккал (1x)\n\n"
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
        await update.message.reply_text("Шаг 3/11: Ингредиенты через запятую (для стандартной порции 1x)")
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
            await update.message.reply_text("Шаг 6/11: Калории для порции 1x (или 0)")
        except:
            await update.message.reply_text("❌ Введи число")
    elif step == "calories":
        try:
            state["calories"] = int(text)
            state["step"] = "protein"
            await update.message.reply_text("Шаг 7/11: Белки (г) для порции 1x")
        except:
            await update.message.reply_text("❌ Введи число")
    elif step == "protein":
        try:
            state["protein"] = float(text)
            state["step"] = "fat"
            await update.message.reply_text("Шаг 8/11: Жиры (г) для порции 1x")
        except:
            await update.message.reply_text("❌ Введи число")
    elif step == "fat":
        try:
            state["fat"] = float(text)
            state["step"] = "carbs"
            await update.message.reply_text("Шаг 9/11: Углеводы (г) для порции 1x")
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
            f"🔥 {state['calories']} ккал | 🥩 {state['protein']}г б | 🧈 {state['fat']}г ж | 🍚 {state['carbs']}г у (порция 1x)\n\n"
            f"💡 Теперь можно выбирать порции: 0.5x, 1x, 1.5x, 2x!",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        del user_states[user_id]

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in user_states:
        await add_recipe_process(update, context)
        return

    if context.user_data.get('fridge_mode'):
        await process_fridge(update, context)
        return

    if context.user_data.get('search_mode'):
        await process_search(update, context)
        context.user_data['search_mode'] = False
        return

    if context.user_data.get('profile_setup'):
        await process_profile_setup(update, context)
        return

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
    elif text == "🧠 Умное меню":
        await smart_menu(update, context)
    elif text == "📊 Статус питания":
        await status_command(update, context)
    elif text == "📅 Меню на неделю":
        await weekly_menu_command(update, context)
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Помощь:**\n\n"
        "🧠 **Умное меню** — подбирает блюда под твой профиль\n"
        "📊 **Статус питания** — показывает прогресс за день\n"
        "👤 **Мой профиль** — настройка цели, веса, аллергий\n"
        "📅 **Меню на неделю** — создай план на 7 дней\n"
        "🛒 **Список покупок** — из выбранных рецептов\n\n"
        "🍽 **Порции:** при добавлении в дневник можно выбрать 0.5x, 1x, 1.5x или 2x\n\n"
        "💡 **Совет:** Настрой профиль, чтобы бот подбирал идеальное меню!",
        reply_markup=main_keyboard()
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍🍳 **Привет! Я ChefMind — твой умный нутрициолог-помощник!**\n\n"
        "🎯 **Что я умею:**\n"
        "• 🧠 Подбираю меню под твои калории и аллергии\n"
        "• 📊 Отслеживаю БЖУ и остаток калорий\n"
        "• 📅 Составляю меню на неделю\n"
        "• 🛒 Формирую список покупок\n"
        "• 🍽 Регулирую порции (0.5x, 1x, 1.5x, 2x)\n\n"
        "👇 **Начни с настройки профиля:** нажми «👤 Мой профиль»\n\n"
        "Или сразу попробуй «🧠 Умное меню»!",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

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
                    f"🍽 **{r[2]}**\n\n"
                    f"🔥 {adj['calories']} ккал\n"
                    f"🥩 {adj['protein']}г б | 🧈 {adj['fat']}г ж | 🍚 {adj['carbs']}г у\n\n"
                    f"Выбери приём пищи:",
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
                await query.answer(f"✅ {r[2]} ({portion}x) добавлен в дневник как {meal_type}!")
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

    elif data.startswith("weekday_"):
        day_idx = int(data.split("_")[1])
        days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("☀️ Завтрак", callback_data=f"weekly_meal_{day_idx}_breakfast")],
            [InlineKeyboardButton("🌤️ Обед", callback_data=f"weekly_meal_{day_idx}_lunch")],
            [InlineKeyboardButton("🌙 Ужин", callback_data=f"weekly_meal_{day_idx}_dinner")],
            [InlineKeyboardButton("🔙 К дням", callback_data="weekly_back")]
        ])
        await query.edit_message_text(
            f"📅 **{days[day_idx]}**\n\nВыбери приём пищи:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    elif data.startswith("weekly_meal_"):
        parts = data.split("_")
        day_idx = int(parts[2])
        meal_type = parts[3]
        user_id = update.effective_user.id
        category_map = {'breakfast': 'завтрак', 'lunch': 'обед', 'dinner': 'ужин'}
        recipes = get_recipes_by_category(user_id, category_map[meal_type])
        if not recipes:
            await query.answer("❌ Нет рецептов в этой категории!")
            return
        keyboard = []
        for r in recipes[:10]:
            keyboard.append([InlineKeyboardButton(f"{r[2]} ({r[7]} ккал)", callback_data=f"weekly_choose_{day_idx}_{meal_type}_{r[0]}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"weekday_{day_idx}")])
        await query.edit_message_text(
            f"📅 Выбери рецепт для {meal_type}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("weekly_choose_"):
        parts = data.split("_")
        day_idx = int(parts[2])
        meal_type = parts[3]
        recipe_id = int(parts[4])
        user_id = update.effective_user.id
        if 'weekly_menu' not in context.user_data:
            context.user_data['weekly_menu'] = {}
        if day_idx not in context.user_data['weekly_menu']:
            context.user_data['weekly_menu'][day_idx] = {}
        context.user_data['weekly_menu'][day_idx][meal_type] = recipe_id
        await query.answer("✅ Рецепт добавлен в меню!")
        days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("☀️ Завтрак", callback_data=f"weekly_meal_{day_idx}_breakfast")],
            [InlineKeyboardButton("🌤️ Обед", callback_data=f"weekly_meal_{day_idx}_lunch")],
            [InlineKeyboardButton("🌙 Ужин", callback_data=f"weekly_meal_{day_idx}_dinner")],
            [InlineKeyboardButton("🔙 К дням", callback_data="weekly_back")]
        ])
        await query.edit_message_text(
            f"📅 **{days[day_idx]}**\n\n✅ Рецепт добавлен!\n\nВыбери следующий приём пищи:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    elif data == "weekly_back":
        await query.edit_message_text(
            "📅 **Создание меню на неделю**\n\nВыбери день недели:",
            reply_markup=weekly_menu_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "save_weekly":
        if 'weekly_menu' not in context.user_data or not context.user_data['weekly_menu']:
            await query.answer("❌ Нет выбранных блюд!")
            return
        week_start = datetime.date.today().isoformat()
        days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
        menu = {}
        for day_idx, meals in context.user_data['weekly_menu'].items():
            day_name = days[day_idx]
            menu[day_name] = {}
            for meal_type, recipe_id in meals.items():
                menu[day_name][meal_type] = {'id': recipe_id, 'portion': 1.0}
        save_weekly_menu(user_id, week_start, menu)
        del context.user_data['weekly_menu']
        await query.answer("✅ Меню на неделю сохранено!")
        await query.edit_message_text(
            "✅ **Меню на неделю сохранено!**\n\n"
            "Теперь ты можешь:\n"
            "• Смотреть список покупок на неделю\n"
            "• Автоматически добавлять блюда в дневник",
            parse_mode="Markdown"
        )

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
    app.add_handler(CommandHandler("weekly_menu", weekly_menu_command))
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