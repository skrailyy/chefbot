import os
import sqlite3
import datetime

# ПРИНУДИТЕЛЬНОЕ УДАЛЕНИЕ СТАРОЙ БД (ВРЕМЕННО)
if os.path.exists('recipes.db'):
    os.remove('recipes.db')
    print("✅ Старая БД удалена")

conn = sqlite3.connect('recipes.db')
cursor = conn.cursor()

# ========== ТАБЛИЦА РЕЦЕПТОВ ==========
cursor.execute('''
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    ingredients TEXT NOT NULL,
    instructions TEXT NOT NULL,
    cook_time INTEGER NOT NULL,
    calories_1x INTEGER DEFAULT 0,
    protein_1x REAL DEFAULT 0,
    fat_1x REAL DEFAULT 0,
    carbs_1x REAL DEFAULT 0,
    recipe_type TEXT DEFAULT 'обычное',
    tags TEXT DEFAULT ''
)
''')

# ========== ТАБЛИЦА ПРОФИЛЕЙ ==========
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY,
    current_weight REAL DEFAULT 70,
    target_weight REAL DEFAULT 70,
    height REAL DEFAULT 170,
    age INTEGER DEFAULT 30,
    gender TEXT DEFAULT 'male',
    activity_level TEXT DEFAULT 'moderate',
    daily_calorie_limit INTEGER DEFAULT 2000,
    disliked_foods TEXT DEFAULT '',
    allergies TEXT DEFAULT ''
)
''')

# ========== ТАБЛИЦА ДНЕВНОГО ПИТАНИЯ ==========
cursor.execute('''
CREATE TABLE IF NOT EXISTS daily_meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    recipe_id INTEGER NOT NULL,
    portion REAL DEFAULT 1.0,
    calories INTEGER DEFAULT 0,
    protein REAL DEFAULT 0,
    fat REAL DEFAULT 0,
    carbs REAL DEFAULT 0
)
''')

# ========== ТАБЛИЦА МЕНЮ НА НЕДЕЛЮ ==========
cursor.execute('''
CREATE TABLE IF NOT EXISTS weekly_menu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    week_start TEXT NOT NULL,
    day TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    recipe_id INTEGER NOT NULL,
    portion REAL DEFAULT 1.0
)
''')

conn.commit()

# ========== ПРЕДУСТАНОВЛЕННЫЕ РЕЦЕПТЫ ==========
DEFAULT_RECIPES = [
    (0, "Овсянка с ягодами", "завтрак", 
     "овсяные хлопья 50г, молоко 150мл, ягоды 50г, мёд 1ч.л",
     "Залейте овсянку молоком, варите 5 минут. Добавьте ягоды и мёд.",
     10, 250, 8, 6, 40, "диетическое", "завтрак,быстро,полезно"),
    
    (0, "Сырники", "завтрак",
     "творог 200г, яйцо 1шт, мука 2ст.л, сахар 1ст.л, соль",
     "Смешайте творог с яйцом, мукой и сахаром. Сформируйте сырники. Жарьте до золотистой корочки.",
     20, 320, 18, 12, 30, "обычное", "завтрак,сытно"),
    
    (0, "Омлет с сыром", "завтрак",
     "яйца 3шт, молоко 50мл, сыр 50г, масло, соль, перец",
     "Взбейте яйца с молоком. Вылейте на сковороду, посыпьте сыром. Жарьте под крышкой 5 минут.",
     15, 350, 22, 25, 5, "обычное", "завтрак,быстро,белок"),
    
    (0, "Куриный суп", "обед",
     "куриное филе 300г, картофель 3шт, морковь 1шт, лук 1шт, вермишель 50г, соль, перец",
     "Сварите бульон из курицы. Добавьте нарезанный картофель, морковь, лук. За 5 минут до готовности добавьте вермишель.",
     40, 280, 25, 8, 30, "обычное", "суп,обед,сытно"),
    
    (0, "Борщ", "обед",
     "свёкла 2шт, капуста 300г, картофель 3шт, морковь 1шт, лук 1шт, томатная паста 2ст.л, мясо 400г",
     "Сварите мясной бульон. Добавьте нарезанные овощи. Свёклу обжарьте с томатной пастой. Варите 40 минут.",
     90, 350, 20, 12, 40, "обычное", "суп,обед,традиционное"),
    
    (0, "Грибной крем-суп", "обед",
     "шампиньоны 400г, сливки 200мл, лук 1шт, картофель 2шт, соль, перец",
     "Обжарьте лук и грибы. Добавьте нарезанный картофель, залейте водой. Варите 20 минут. Измельчите блендером, добавьте сливки.",
     35, 220, 8, 14, 18, "диетическое", "суп,диетическое,грибы"),
    
    (0, "Курица с гречкой", "ужин",
     "куриное филе 300г, гречка 150г, лук 1шт, морковь 1шт, соль, перец",
     "Обжарьте курицу с луком и морковью. Добавьте промытую гречку, залейте водой, тушите 25 минут.",
     35, 380, 35, 10, 42, "обычное", "ужин,сытно,полезно"),
    
    (0, "Рыба на пару с овощами", "ужин",
     "филе белой рыбы 300г, брокколи 200г, морковь 1шт, лимон, соль, перец",
     "Нарежьте овощи. Выложите рыбу и овощи в пароварку. Готовьте 20 минут. Сбрызните лимоном.",
     25, 240, 30, 8, 12, "диетическое", "ужин,диетическое,полезно"),
    
    (0, "Паста с овощами", "ужин",
     "паста 200г, цукини 1шт, помидоры черри 150г, чеснок 2зуб, оливковое масло, базилик",
     "Отварите пасту. Обжарьте цукини и помидоры с чесноком. Смешайте с пастой, добавьте базилик.",
     25, 410, 12, 14, 58, "постное", "ужин,постное,быстро"),
    
    (0, "Оливье", "салат",
     "колбаса 300г, картофель 4шт, морковь 2шт, яйца 4шт, огурцы солёные 3шт, горошек 1б, майонез",
     "Отварите картофель, морковь, яйца. Нарежьте все кубиками. Смешайте с горошком и майонезом.",
     40, 380, 12, 25, 30, "праздничное", "салат,праздник,новый год"),
    
    (0, "Сельдь под шубой", "салат",
     "сельдь 1шт, свёкла 2шт, картофель 3шт, морковь 2шт, яйца 3шт, лук 1шт, майонез",
     "Отварите овощи. Выкладывайте слоями: картофель, сельдь, лук, морковь, свёкла. Каждый слой смазывайте майонезом.",
     60, 420, 15, 30, 28, "праздничное", "салат,праздник,рыбный"),
    
    (0, "Греческий салат", "салат",
     "огурцы 2шт, помидоры 3шт, перец 1шт, сыр фета 200г, маслины 100г, оливковое масло, орегано",
     "Нарежьте овощи кубиками. Добавьте маслины и сыр фета. Заправьте маслом и орегано.",
     15, 280, 10, 20, 12, "диетическое", "салат,греческий,лёгкий"),
    
    (0, "Творожная запеканка", "десерт",
     "творог 400г, яйца 2шт, манка 3ст.л, сахар 3ст.л, изюм 50г",
     "Смешайте все ингредиенты. Выложите в форму. Запекайте 35 минут при 180°C.",
     45, 290, 18, 12, 28, "обычное", "десерт,сладкое"),
    
    (0, "Тирамису", "десерт",
     "печенье савоярди 200г, сыр маскарпоне 500г, яйца 3шт, сахар 100г, кофе 200мл, какао",
     "Разделите яйца. Желтки взбейте с сахаром, добавьте маскарпоне. Белки взбейте отдельно. Смешайте. Обмакните печенье в кофе. Выложите слоями. Посыпьте какао.",
     40, 480, 10, 30, 45, "праздничное", "десерт,итальянский,кофейный"),
    
    (0, "Куриное филе с гречкой", "спорт",
     "куриное филе 200г, гречка 80г, брокколи 100г, оливковое масло 1ч.л, соль",
     "Отварите гречку. Курицу запеките. Брокколи приготовьте на пару. Смешайте всё.",
     25, 420, 45, 10, 35, "спортивное", "спорт,белок,ПП"),
    
    (0, "Протеиновый смузи", "спорт",
     "протеин 1 ложка, банан 1шт, молоко 200мл, овсянка 30г, арахисовая паста 1ст.л",
     "Смешайте все ингредиенты в блендере. Взбивайте 30 секунд.",
     5, 450, 35, 18, 40, "спортивное", "спорт,протеин,напиток"),
]

def init_default_recipes():
    for recipe in DEFAULT_RECIPES:
        cursor.execute('SELECT COUNT(*) FROM recipes WHERE name = ? AND user_id = 0', (recipe[1],))
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
            INSERT INTO recipes (user_id, name, category, ingredients, instructions, cook_time, calories_1x, protein_1x, fat_1x, carbs_1x, recipe_type, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', recipe)
    conn.commit()

init_default_recipes()

# ========== ФУНКЦИИ ДЛЯ РЕЦЕПТОВ ==========
def add_recipe(user_id, name, category, ingredients, instructions, cook_time, calories=0, protein=0, fat=0, carbs=0, recipe_type="обычное", tags=""):
    cursor.execute('''
    INSERT INTO recipes (user_id, name, category, ingredients, instructions, cook_time, calories_1x, protein_1x, fat_1x, carbs_1x, recipe_type, tags)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, name, category, ingredients, instructions, cook_time, calories, protein, fat, carbs, recipe_type, tags))
    conn.commit()
    return cursor.lastrowid

def get_recipes(user_id):
    cursor.execute('SELECT * FROM recipes WHERE user_id = ? OR user_id = 0 ORDER BY user_id DESC, id', (user_id,))
    return cursor.fetchall()

def find_recipe_by_name(user_id, name):
    cursor.execute('SELECT * FROM recipes WHERE (user_id = ? OR user_id = 0) AND name LIKE ?', (user_id, f'%{name}%'))
    return cursor.fetchall()

def get_recipes_by_category(user_id, category):
    cursor.execute('SELECT * FROM recipes WHERE (user_id = ? OR user_id = 0) AND category = ?', (user_id, category))
    return cursor.fetchall()

def get_recipes_by_type(user_id, recipe_type):
    cursor.execute('SELECT * FROM recipes WHERE (user_id = ? OR user_id = 0) AND recipe_type = ?', (user_id, recipe_type))
    return cursor.fetchall()

def delete_recipe(recipe_id, user_id):
    cursor.execute('DELETE FROM recipes WHERE id = ? AND user_id = ?', (recipe_id, user_id))
    conn.commit()
    return cursor.rowcount > 0

def adjust_by_portion(recipe, portion):
    calories = int(recipe[7] * portion)
    protein = round(recipe[8] * portion, 1)
    fat = round(recipe[9] * portion, 1)
    carbs = round(recipe[10] * portion, 1)
    return {'calories': calories, 'protein': protein, 'fat': fat, 'carbs': carbs}

def get_recipe_with_portion(recipe, portion=1.0):
    adj = adjust_by_portion(recipe, portion)
    return {
        'id': recipe[0],
        'user_id': recipe[1],
        'name': recipe[2],
        'category': recipe[3],
        'ingredients': recipe[4],
        'instructions': recipe[5],
        'cook_time': recipe[6],
        'calories': adj['calories'],
        'protein': adj['protein'],
        'fat': adj['fat'],
        'carbs': adj['carbs'],
        'recipe_type': recipe[11],
        'tags': recipe[12],
        'portion': portion
    }

# ========== ФУНКЦИИ ДЛЯ ПРОФИЛЯ ==========
def get_user_profile(user_id):
    cursor.execute('SELECT * FROM user_profiles WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        current = row[1]
        target = row[2]
        if target > current:
            goal = 'gain'
        elif target < current:
            goal = 'lose'
        else:
            goal = 'maintain'
        return {
            'goal': goal,
            'current_weight': current,
            'target_weight': target,
            'height': row[3],
            'age': row[4],
            'gender': row[5],
            'activity_level': row[6],
            'daily_calorie_limit': row[7],
            'disliked_foods': [x for x in row[8].split(',') if x] if row[8] else [],
            'allergies': [x for x in row[9].split(',') if x] if row[9] else []
        }
    return None

def save_user_profile(user_id, profile):
    cursor.execute('''
    INSERT OR REPLACE INTO user_profiles 
    (user_id, current_weight, target_weight, height, age, gender, activity_level, daily_calorie_limit, disliked_foods, allergies)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, profile['current_weight'], profile['target_weight'], profile['height'],
        profile['age'], profile['gender'], profile['activity_level'],
        profile['daily_calorie_limit'], ','.join(profile['disliked_foods']),
        ','.join(profile['allergies'])
    ))
    conn.commit()

def calculate_daily_calories(weight, height, age, gender, activity_level, goal):
    if gender == 'male':
        bmr = 88.36 + (13.4 * weight) + (4.8 * height) - (5.7 * age)
    else:
        bmr = 447.6 + (9.2 * weight) + (3.1 * height) - (4.3 * age)
    
    activity_factors = {
        'sedentary': 1.2,
        'light': 1.375,
        'moderate': 1.55,
        'active': 1.725,
        'very_active': 1.9
    }
    tdee = bmr * activity_factors.get(activity_level, 1.55)
    
    if goal == 'lose':
        return max(1500, int(tdee - 500))
    elif goal == 'gain':
        return int(tdee + 500)
    else:
        return int(tdee)

# ========== ФУНКЦИИ ДЛЯ ДНЕВНИКА ПИТАНИЯ ==========
def get_today_calories(user_id):
    today = datetime.date.today().isoformat()
    cursor.execute('SELECT SUM(calories) FROM daily_meals WHERE user_id = ? AND date = ?', (user_id, today))
    result = cursor.fetchone()[0]
    return result or 0

def get_today_macros(user_id):
    today = datetime.date.today().isoformat()
    cursor.execute('SELECT SUM(protein), SUM(fat), SUM(carbs) FROM daily_meals WHERE user_id = ? AND date = ?', (user_id, today))
    result = cursor.fetchone()
    return {'protein': result[0] or 0, 'fat': result[1] or 0, 'carbs': result[2] or 0}

def add_meal(user_id, meal_type, recipe_id, portion, calories, protein, fat, carbs):
    today = datetime.date.today().isoformat()
    cursor.execute('''
    INSERT INTO daily_meals (user_id, date, meal_type, recipe_id, portion, calories, protein, fat, carbs)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, today, meal_type, recipe_id, portion, calories, protein, fat, carbs))
    conn.commit()

def clear_today_meals(user_id):
    today = datetime.date.today().isoformat()
    cursor.execute('DELETE FROM daily_meals WHERE user_id = ? AND date = ?', (user_id, today))
    conn.commit()

# ========== ФУНКЦИИ ДЛЯ МЕНЮ НА НЕДЕЛЮ ==========
def save_weekly_menu(user_id, week_start, menu):
    cursor.execute('DELETE FROM weekly_menu WHERE user_id = ? AND week_start = ?', (user_id, week_start))
    for day, meals in menu.items():
        for meal_type, info in meals.items():
            cursor.execute('''
            INSERT INTO weekly_menu (user_id, week_start, day, meal_type, recipe_id, portion)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, week_start, day, meal_type, info['id'], info.get('portion', 1.0)))
    conn.commit()

def get_weekly_menu(user_id, week_start):
    cursor.execute('SELECT day, meal_type, recipe_id, portion FROM weekly_menu WHERE user_id = ? AND week_start = ?', (user_id, week_start))
    rows = cursor.fetchall()
    menu = {}
    for row in rows:
        day = row[0]
        meal_type = row[1]
        if day not in menu:
            menu[day] = {}
        menu[day][meal_type] = {'id': row[2], 'portion': row[3]}
    return menu