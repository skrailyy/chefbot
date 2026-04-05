import os
import sqlite3
import datetime

# ПРИНУДИТЕЛЬНОЕ УДАЛЕНИЕ СТАРОЙ БД
if os.path.exists('recipes.db'):
    os.remove('recipes.db')
    print("✅ Старая БД удалена")

conn = sqlite3.connect('recipes.db')
cursor = conn.cursor()

# ТАБЛИЦА РЕЦЕПТОВ
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

# ТАБЛИЦА ПРОФИЛЕЙ
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

# ТАБЛИЦА ДНЕВНОГО ПИТАНИЯ
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

conn.commit()

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
        user_id, 
        profile['current_weight'], 
        profile['target_weight'], 
        profile['height'],
        profile['age'], 
        profile['gender'], 
        profile['activity_level'],
        profile['daily_calorie_limit'], 
        ','.join(profile['disliked_foods']),
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

# ОСТАЛЬНЫЕ ФУНКЦИИ (add_recipe, get_recipes и т.д.) ОСТАВЬ КАК БЫЛИ