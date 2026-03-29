import sqlite3

# Подключение к базе данных
conn = sqlite3.connect('recipes.db')
cursor = conn.cursor()

# Создание таблицы рецептов
cursor.execute('''
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    ingredients TEXT NOT NULL,
    instructions TEXT NOT NULL,
    cook_time INTEGER NOT NULL
)
''')
conn.commit()

# Функция для добавления рецепта
def add_recipe(user_id, name, category, ingredients, instructions, cook_time):
    cursor.execute('''
    INSERT INTO recipes (user_id, name, category, ingredients, instructions, cook_time)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, name, category, ingredients, instructions, cook_time))
    conn.commit()
    return cursor.lastrowid

# Функция для получения всех рецептов пользователя
def get_recipes(user_id):
    cursor.execute('SELECT * FROM recipes WHERE user_id = ?', (user_id,))
    return cursor.fetchall()

# Функция для поиска рецепта по названию
def find_recipe_by_name(user_id, name):
    cursor.execute('SELECT * FROM recipes WHERE user_id = ? AND name LIKE ?', (user_id, f'%{name}%'))
    return cursor.fetchall()

# Функция для получения рецептов по категории
def get_recipes_by_category(user_id, category):
    cursor.execute('SELECT * FROM recipes WHERE user_id = ? AND category = ?', (user_id, category))
    return cursor.fetchall()

# Функция для удаления рецепта
def delete_recipe(recipe_id, user_id):
    cursor.execute('DELETE FROM recipes WHERE id = ? AND user_id = ?', (recipe_id, user_id))
    conn.commit()
    return cursor.rowcount > 0