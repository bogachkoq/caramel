from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
import base64

app = Flask(__name__)
DB_NAME = "canteen_full.db"

# ===== КЛЮЧ ШИФРОВАНИЯ =====
# В продакшене храните этот ключ в переменных окружения!
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY') or Fernet.generate_key()
cipher = Fernet(ENCRYPTION_KEY)


def encrypt_data(data):
    """Шифрует строку"""
    if not data:
        return ''
    return cipher.encrypt(data.encode()).decode()


def decrypt_data(data):
    """Дешифрует строку"""
    if not data:
        return ''
    try:
        return cipher.decrypt(data.encode()).decode()
    except:
        return data  # Возвращаем как есть если не получилось расшифровать (для старых данных)


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        # Пользователи
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password TEXT, fullName TEXT, role TEXT, 
            school TEXT, grade TEXT, phone TEXT, email TEXT, balance REAL DEFAULT 0, 
            allergies TEXT DEFAULT '', isApproved INTEGER DEFAULT 1,
            cardNumber TEXT DEFAULT '', cardHolder TEXT DEFAULT '', cardExpiry TEXT DEFAULT '')''')

        # Меню (добавлено поле ingredients для состава блюда)
        db.execute('''CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT, 
            price REAL, 
            portions INTEGER, 
            type TEXT, 
            ingredients TEXT DEFAULT '',
            addedDate TEXT)''')

        # Заказы
        db.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user TEXT, 
            name TEXT, 
            price REAL, 
            status TEXT, 
            allergies TEXT, 
            issuedAt TEXT, 
            createdAt TEXT)''')

        # Ингредиенты
        db.execute('''CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT, 
            amount REAL, 
            unit TEXT)''')

        # Прочее
        db.execute('''CREATE TABLE IF NOT EXISTS reviews (
            dish TEXT, 
            text TEXT, 
            author TEXT)''')

        db.execute('''CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            item TEXT, 
            qty TEXT, 
            price REAL DEFAULT 0,
            status TEXT)''')

        db.execute('''CREATE TABLE IF NOT EXISTS notifications (
            title TEXT, 
            text TEXT, 
            type TEXT, 
            toUser TEXT, 
            toRole TEXT, 
            time TEXT)''')

        db.execute('''CREATE TABLE IF NOT EXISTS sub_transactions (
            user TEXT, 
            type TEXT, 
            amount REAL, 
            time TEXT)''')

        db.execute('''CREATE TABLE IF NOT EXISTS subscription_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            subType TEXT,
            date TEXT,
            dishesUsed TEXT,
            createdAt TEXT)''')

        # Проверяем существование столбца ingredients и добавляем если его нет
        cursor = db.execute("PRAGMA table_info(menu)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'ingredients' not in columns:
            print("[MIGRATION] Добавляем поле 'ingredients' в таблицу menu...")
            db.execute("ALTER TABLE menu ADD COLUMN ingredients TEXT DEFAULT ''")
            db.commit()
            print("[MIGRATION] ✅ Поле 'ingredients' успешно добавлено!")

        if 'category' not in columns:
            print("[MIGRATION] Добавляем поле 'category' в таблицу menu...")
            db.execute("ALTER TABLE menu ADD COLUMN category TEXT DEFAULT 'Обед'")
            db.commit()
            print("[MIGRATION] ✅ Поле 'category' успешно добавлено!")

        # Проверяем существование столбца price в таблице purchases
        cursor = db.execute("PRAGMA table_info(purchases)")
        purchase_columns = [column[1] for column in cursor.fetchall()]

        if 'price' not in purchase_columns:
            print("[MIGRATION] Добавляем поле 'price' в таблицу purchases...")
            db.execute("ALTER TABLE purchases ADD COLUMN price REAL DEFAULT 0")
            db.commit()
            print("[MIGRATION] ✅ Поле 'price' успешно добавлено!")

        # Проверяем существование полей карты в таблице users
        cursor = db.execute("PRAGMA table_info(users)")
        user_columns = [column[1] for column in cursor.fetchall()]

        if 'cardNumber' not in user_columns:
            print("[MIGRATION] Добавляем поля карты в таблицу users...")
            db.execute("ALTER TABLE users ADD COLUMN cardNumber TEXT DEFAULT ''")
            db.execute("ALTER TABLE users ADD COLUMN cardHolder TEXT DEFAULT ''")
            db.execute("ALTER TABLE users ADD COLUMN cardExpiry TEXT DEFAULT ''")
            db.commit()
            print("[MIGRATION] ✅ Поля карты успешно добавлены!")

        # Дефолтный админ
        db.execute(
            "INSERT OR IGNORE INTO users (username, password, fullName, role, school, isApproved) VALUES (?,?,?,?,?,?)",
            ('admin', generate_password_hash('123'), 'Главный Админ', 'admin', 'Система', 1))

        # Тестовые аккаунты (хэшированные пароли, зашифрованные данные)
        db.execute(
            "INSERT OR IGNORE INTO users (username, password, fullName, role, school, grade, balance, isApproved) VALUES (?,?,?,?,?,?,?,?)",
            ('a', generate_password_hash('1'), 'Иван Иванов', 'student', 'ГБОУ Школа №656', '9А', 1000, 1))

        db.execute(
            "INSERT OR IGNORE INTO users (username, password, fullName, role, school, phone, email, isApproved) VALUES (?,?,?,?,?,?,?,?)",
            ('aa', generate_password_hash('1'), 'Мария Петрова', 'chef', 'ГБОУ Школа №656',
             encrypt_data('+7 999 123-45-67'), encrypt_data('chef@school.ru'), 1))

        db.execute(
            "INSERT OR IGNORE INTO users (username, password, fullName, role, school, isApproved) VALUES (?,?,?,?,?,?)",
            ('aaa', generate_password_hash('1'), 'Администратор Тестовый', 'admin', 'ГБОУ Школа №656', 1))

        db.commit()
        print("[INIT] ✅ База данных инициализирована с зашифрованными данными")


init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/sync')
def sync():
    """Синхронизация всех данных - используется всеми пользователями"""
    with get_db() as db:
        menu_items = [dict(r) for r in db.execute("SELECT * FROM menu ORDER BY id DESC").fetchall()]
        orders_list = [dict(r) for r in db.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()]

        print(f"[SYNC] ✅ Отправляем {len(menu_items)} блюд в меню")
        print(f"[SYNC] ✅ Отправляем {len(orders_list)} заказов")

        # Выводим первые 3 блюда для проверки
        if menu_items:
            print("[SYNC] Первые блюда в меню:")
            for item in menu_items[:3]:
                ingredients_info = f", состав: {item.get('ingredients', 'не указан')}" if item.get(
                    'ingredients') else ""
                print(f"  - {item['name']} ({item['price']}₽, {item['portions']} порций{ingredients_info})")

        # Расшифровываем персональные данные пользователей
        users_raw = [dict(r) for r in db.execute("SELECT * FROM users").fetchall()]
        users_decrypted = []
        for u in users_raw:
            if u.get('phone'):
                u['phone'] = decrypt_data(u['phone'])
            if u.get('email'):
                u['email'] = decrypt_data(u['email'])
            if u.get('cardNumber'):
                u['cardNumber'] = decrypt_data(u['cardNumber'])
            if u.get('cardHolder'):
                u['cardHolder'] = decrypt_data(u['cardHolder'])
            users_decrypted.append(u)

        return jsonify({
            "menu": menu_items,
            "orders": orders_list,
            "ingredients": [dict(r) for r in db.execute("SELECT * FROM ingredients").fetchall()],
            "users": users_decrypted,
            "reviews": [dict(r) for r in db.execute("SELECT * FROM reviews").fetchall()],
            "purchases": [dict(r) for r in db.execute("SELECT * FROM purchases").fetchall()],
            "notifications": [dict(r) for r in db.execute("SELECT * FROM notifications").fetchall()],
            "subTransactions": [dict(r) for r in db.execute("SELECT * FROM sub_transactions").fetchall()],
            "subscriptionUsage": [dict(r) for r in db.execute("SELECT * FROM subscription_usage").fetchall()]
        })


@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    print(f"[LOGIN] Попытка входа: {d['username']}")

    with get_db() as db:
        u = db.execute("SELECT * FROM users WHERE username = ?", (d['username'],)).fetchone()
        if u and check_password_hash(u['password'], d['password']):
            if u['role'] == 'chef' and not u['isApproved']:
                print(f"[LOGIN] ❌ Повар {d['username']} не одобрен")
                return jsonify({"error": "Аккаунт повара ожидает одобрения админом"}), 403

            print(f"[LOGIN] ✅ Успешный вход: {d['username']} ({u['role']})")

            # Расшифровываем чувствительные данные перед отправкой
            user_data = dict(u)
            if user_data.get('phone'):
                user_data['phone'] = decrypt_data(user_data['phone'])
            if user_data.get('email'):
                user_data['email'] = decrypt_data(user_data['email'])
            if user_data.get('cardNumber'):
                user_data['cardNumber'] = decrypt_data(user_data['cardNumber'])
            if user_data.get('cardHolder'):
                user_data['cardHolder'] = decrypt_data(user_data['cardHolder'])

            return jsonify(user_data)

    print(f"[LOGIN] ❌ Неверные данные для {d['username']}")
    return jsonify({"error": "Неверный логин или пароль"}), 401


@app.route('/api/register', methods=['POST'])
def register():
    d = request.json
    print(f"[REGISTER] Регистрация нового пользователя: {d['username']} ({d['role']})")

    with get_db() as db:
        try:
            is_app = 0 if d['role'] == 'chef' else 1

            # Хэшируем пароль
            hashed_password = generate_password_hash(d['password'])

            # Шифруем персональные данные
            encrypted_phone = encrypt_data(d.get('phone', ''))
            encrypted_email = encrypt_data(d.get('email', ''))

            db.execute(
                "INSERT INTO users (username, password, fullName, role, school, grade, phone, email, isApproved) VALUES (?,?,?,?,?,?,?,?,?)",
                (d['username'], hashed_password, d['fullName'], d['role'], d['school'], d.get('grade', ''),
                 encrypted_phone, encrypted_email, is_app))
            db.commit()
            print(f"[REGISTER] ✅ Пользователь {d['username']} зарегистрирован (пароль захэширован)")
            return jsonify({"ok": True})
        except Exception as e:
            print(f"[REGISTER] ❌ Ошибка: {e}")
            return jsonify({"error": "Логин уже занят или ошибка данных"}), 400


@app.route('/api/action', methods=['POST'])
def action():
    d = request.json
    act = d.get('type')
    now_time = datetime.now().strftime("%H:%M")
    now_full = datetime.now().isoformat()

    print(f"\n{'=' * 60}")
    print(f"[ACTION] Получен запрос: {act}")
    print(f"[ACTION] Данные: {d}")
    print(f"{'=' * 60}")

    with get_db() as db:
        if act == 'buy':
            u = db.execute("SELECT balance FROM users WHERE username = ?", (d['user'],)).fetchone()
            m = db.execute("SELECT * FROM menu WHERE id = ?", (d['menuId'],)).fetchone()
            if u and m and u['balance'] >= m['price'] and m['portions'] > 0:
                db.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (m['price'], d['user']))
                db.execute("UPDATE menu SET portions = portions - 1 WHERE id = ?", (d['menuId'],))
                db.execute("INSERT INTO orders (user, name, price, status, allergies, createdAt) VALUES (?,?,?,?,?,?)",
                           (d['user'], m['name'], m['price'], 'Оплачено', d.get('allergies', ''), now_full))
                db.execute("INSERT INTO notifications (title, text, toUser, time) VALUES (?,?,?,?)",
                           ('Оплата', f'Заказ {m["name"]} принят', d['user'], now_time))
                print(f"[BUY] ✅ Покупка: {d['user']} купил {m['name']}")
            else:
                print(f"[BUY] ❌ Невозможно купить: баланс или порции")
                db.commit()
                return jsonify({"error": "Невозможно купить"}), 400

        elif act == 'add_menu_item':
            print(f"\n[ADD_DISH] 🍽️ ДОБАВЛЕНИЕ НОВОГО БЛЮДА")
            print(f"[ADD_DISH] Название: {d['name']}")
            print(f"[ADD_DISH] Цена: {d['price']}₽")
            print(f"[ADD_DISH] Порции: {d['portions']}")
            print(f"[ADD_DISH] Тип: {d.get('dishType', 'Второе')}")
            print(f"[ADD_DISH] Категория: {d.get('category', 'Обед')}")
            print(f"[ADD_DISH] Состав: {d.get('ingredients', 'не указан')}")
            print(f"[ADD_DISH] Дата: {now_full}")

            dish_type = d.get('dishType', 'Второе')
            ingredients = d.get('ingredients', '')
            category = d.get('category', 'Обед')

            cursor = db.execute(
                "INSERT INTO menu (name, price, portions, type, ingredients, category, addedDate) VALUES (?,?,?,?,?,?,?)",
                (d['name'], float(d['price']), int(d['portions']), dish_type, ingredients, category, now_full))

            dish_id = cursor.lastrowid

            # Уведомление для всех учеников о новом блюде
            db.execute("INSERT INTO notifications (title, text, toRole, time) VALUES (?,?,?,?)",
                       ('Новое блюдо!', f'В меню добавлено: {d["name"]} ({dish_type})', 'student', now_time))

            print(f"[ADD_DISH] ✅ Блюдо добавлено с ID: {dish_id}")

        elif act == 'buy_sub':
            db.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (d['price'], d['user']))
            db.execute("INSERT INTO sub_transactions (user, type, amount, time) VALUES (?,?,?,?)",
                       (d['user'], d['subType'], d['price'], now_full))
            # Уведомление ученику о покупке абонемента
            db.execute("INSERT INTO notifications (title, text, toUser, time) VALUES (?,?,?,?)",
                       ('Абонемент куплен', f'Абонемент «{d["subType"]}» успешно оплачен — {d["price"]}₽', d['user'],
                        now_time))
            print(f"[SUB] ✅ Абонемент: {d['user']} купил {d['subType']}")

        elif act == 'refill':
            db.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (d['amount'], d['user']))
            # Уведомление ученику о пополнении
            db.execute("INSERT INTO notifications (title, text, toUser, time) VALUES (?,?,?,?)",
                       ('Баланс пополнен', f'На счёт зачислено {d["amount"]}₽', d['user'], now_time))
            print(f"[REFILL] ✅ Пополнение: {d['user']} +{d['amount']}₽")

        elif act == 'confirm_order':
            order = db.execute("SELECT * FROM orders WHERE id = ?", (d['id'],)).fetchone()
            db.execute("UPDATE orders SET status = 'Выдано', issuedAt = ? WHERE id = ?", (now_time, d['id']))
            if order:
                # Уведомление ученику о выдаче
                db.execute("INSERT INTO notifications (title, text, toUser, time) VALUES (?,?,?,?)",
                           ('Заказ выдан', f'{order["name"]} — ваш заказ готов к получению', order['user'], now_time))
            print(f"[CONFIRM] ✅ Заказ #{d['id']} выдан")

        elif act == 'save_profile':
            db.execute("UPDATE users SET allergies = ? WHERE username = ?", (d['allergies'], d['user']))
            print(f"[PROFILE] ✅ Профиль обновлен: {d['user']}")

        elif act == 'approve_chef':
            db.execute("UPDATE users SET isApproved = 1 WHERE username = ?", (d['target'],))
            # Уведомление повару о том что его одобрили
            db.execute("INSERT INTO notifications (title, text, toUser, time) VALUES (?,?,?,?)",
                       ('Аккаунт одобрен', 'Ваш аккаунт повара успешно одобрен. Теперь вы можете войти.', d['target'],
                        now_time))
            print(f"[APPROVE] ✅ Повар одобрен: {d['target']}")

        elif act == 'reject_chef':
            db.execute("DELETE FROM users WHERE username = ?", (d['target'],))
            print(f"[REJECT] ✅ Повар удален: {d['target']}")

        elif act == 'update_stock':
            db.execute("UPDATE menu SET portions = ? WHERE id = ?", (int(d['val']), d['id']))
            print(f"[STOCK] ✅ Обновление порций: ID {d['id']} → {d['val']}")

        elif act == 'add_ing':
            db.execute("INSERT INTO ingredients (name, amount, unit) VALUES (?,?,?)", (d['name'], 0, d['unit']))
            print(f"[INGREDIENT] ✅ Ингредиент добавлен: {d['name']}")

        elif act == 'set_ing':
            db.execute("UPDATE ingredients SET amount = ? WHERE id = ?", (float(d['val']), d['id']))
            print(f"[INGREDIENT] ✅ Количество обновлено: ID {d['id']} → {d['val']}")

        elif act == 'add_review':
            db.execute("INSERT INTO reviews (dish, text, author) VALUES (?,?,?)", (d['dish'], d['text'], d['author']))
            print(f"[REVIEW] ✅ Отзыв от {d['author']}")

        elif act == 'add_purchase':
            price = d.get('price', 0)
            db.execute("INSERT INTO purchases (item, qty, price, status) VALUES (?,?,?,?)",
                       (d['item'], d['qty'], float(price), 'Ожидает'))
            # Уведомление админу о новой заявке на закупку
            db.execute("INSERT INTO notifications (title, text, toRole, time) VALUES (?,?,?,?)",
                       ('Новая закупка', f'Заявка: {d["item"]} ({d["qty"]}) — {price}₽. Ожидает одобрения.', 'admin',
                        now_time))
            print(f"[PURCHASE] ✅ Заявка на закупку: {d['item']} ({d['qty']}) на сумму {price}₽")

        elif act == 'approve_purchase':
            purchase = db.execute("SELECT * FROM purchases WHERE id = ?", (d['id'],)).fetchone()
            db.execute("UPDATE purchases SET status = 'Одобрено' WHERE id = ?", (d['id'],))
            if purchase:
                print(
                    f"[PURCHASE] ✅ Закупка одобрена: ID {d['id']} - {purchase['item']} на {(purchase['price'] or 0)}₽")
                # Уведомление повару (ИСПРАВЛЕНО: двойные кавычки снаружи, одинарные внутри)
                db.execute("INSERT INTO notifications (title, text, toRole, time) VALUES (?,?,?,?)",
                           ('Закупка одобрена',
                            f"{purchase['item']} ({purchase['qty']}) — {purchase.get('price', 0)}₽ одобрена", 'chef',
                            now_time))
            else:
                print(f"[PURCHASE] ✅ Закупка одобрена: ID {d['id']}")

        elif act == 'reject_purchase':
            purchase = db.execute("SELECT * FROM purchases WHERE id = ?", (d['id'],)).fetchone()
            db.execute("UPDATE purchases SET status = 'Запрещено' WHERE id = ?", (d['id'],))
            if purchase:
                print(f"[PURCHASE] ❌ Закупка запрещена: ID {d['id']} - {purchase['item']}")
                # Уведомление повару о запрете (ИСПРАВЛЕНО: двойные кавычки снаружи, одинарные внутри)
                db.execute("INSERT INTO notifications (title, text, toRole, time) VALUES (?,?,?,?)",
                           ('Закупка отклонена',
                            f"{purchase['item']} ({purchase['qty']}) — заявка запрещена администратором", 'chef',
                            now_time))
            else:
                print(f"[PURCHASE] ❌ Закупка запрещена: ID {d['id']}")

        elif act == 'save_card':
            # Шифруем данные карты перед сохранением
            encrypted_card = encrypt_data(d['cardNumber'])
            encrypted_holder = encrypt_data(d['cardHolder'])

            db.execute("UPDATE users SET cardNumber = ?, cardHolder = ?, cardExpiry = ? WHERE username = ?",
                       (encrypted_card, encrypted_holder, d['cardExpiry'], d['user']))
            print(f"[CARD] ✅ Карта сохранена (зашифрована) для {d['user']}: **** {d['cardNumber'][-4:]}")

        elif act == 'remove_card':
            db.execute("UPDATE users SET cardNumber = '', cardHolder = '', cardExpiry = '' WHERE username = ?",
                       (d['user'],))
            print(f"[CARD] ✅ Карта удалена для {d['user']}")

        elif act == 'use_subscription':
            # Проверяем что у пользователя есть абонемент
            today = datetime.now().strftime("%Y-%m-%d")
            sub_type = d['subType']  # 'Завтраки' или 'Обеды'

            # Проверяем что пользователь купил этот абонемент
            has_sub = db.execute("SELECT * FROM sub_transactions WHERE user = ? AND type = ?",
                                 (d['user'], sub_type)).fetchone()
            if not has_sub:
                print(f"[SUB_USE] ❌ У {d['user']} нет абонемента {sub_type}")
                return jsonify({"error": "У вас нет этого абонемента"}), 400

            # Проверяем что сегодня ещё не брал по этому абонементу
            already_used = db.execute("SELECT * FROM subscription_usage WHERE user = ? AND subType = ? AND date = ?",
                                      (d['user'], sub_type, today)).fetchone()
            if already_used:
                print(f"[SUB_USE] ❌ {d['user']} уже использовал абонемент {sub_type} сегодня")
                return jsonify({"error": "Вы уже использовали абонемент сегодня"}), 400

            # Получаем выбранные блюда
            selected_dishes = d.get('dishes', [])  # список ID блюд
            if not selected_dishes:
                return jsonify({"error": "Выберите блюда"}), 400

            # Создаём заказы для каждого выбранного блюда
            dishes_info = []
            for dish_id in selected_dishes:
                dish = db.execute("SELECT * FROM menu WHERE id = ?", (dish_id,)).fetchone()
                if dish and dish['portions'] > 0:
                    db.execute("UPDATE menu SET portions = portions - 1 WHERE id = ?", (dish_id,))
                    db.execute(
                        "INSERT INTO orders (user, name, price, status, allergies, createdAt) VALUES (?,?,?,?,?,?)",
                        (d['user'], dish['name'], 0, 'Оплачено', d.get('allergies', ''), now_full))
                    dishes_info.append(dish['name'])
                    print(f"[SUB_USE] ✅ {d['user']} взял по абонементу: {dish['name']}")

            # Записываем использование абонемента
            db.execute("INSERT INTO subscription_usage (user, subType, date, dishesUsed, createdAt) VALUES (?,?,?,?,?)",
                       (d['user'], sub_type, today, ', '.join(dishes_info), now_full))

            # Уведомление
            db.execute("INSERT INTO notifications (title, text, toUser, time) VALUES (?,?,?,?)",
                       ('Абонемент использован', f'{sub_type}: {", ".join(dishes_info)}', d['user'], now_time))

            print(f"[SUB_USE] ✅ Абонемент {sub_type} использован: {d['user']} — {', '.join(dishes_info)}")

        else:
            print(f"[ACTION] ⚠️ Неизвестное действие: {act}")

        db.commit()

    print(f"[ACTION] ✅ Действие {act} успешно выполнено и закоммичено\n")
    return jsonify({"ok": True})


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)

    print("\n" + "=" * 60)
    print("🚀 СЕРВЕР ЗАПУСКАЕТСЯ")
    print("=" * 60)
    print("📍 URL: http://127.0.0.1:8080")
    print("📂 База данных: canteen_full.db")
    print("=" * 60 + "\n")

    app.run(debug=True, port=8080)