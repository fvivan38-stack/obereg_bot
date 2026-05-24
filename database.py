# database.py
import sqlite3
from datetime import datetime
import csv
import io
import random

DB_NAME = "shop_bot.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            address TEXT,
            registered_at TEXT
        )
    """)

    # Таблица коллекций
    cur.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            photo_file_id TEXT,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        )
    """)

    # Таблица товаров
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            photo_file_id TEXT,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        )
    """)

    # Таблица корзины
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            size TEXT,
            added_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Таблица групповых заказов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_number TEXT UNIQUE,
            total_price INTEGER NOT NULL,
            delivery_city TEXT,
            delivery_address TEXT,
            phone TEXT,
            delivery_date TEXT,
            delivery_time TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Таблица товаров в групповом заказе
    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT,
            quantity INTEGER DEFAULT 1,
            size TEXT,
            price INTEGER NOT NULL,
            photo_file_id TEXT,
            FOREIGN KEY (group_order_id) REFERENCES group_orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Таблица отзывов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT,
            review_text TEXT,
            rating INTEGER,
            created_at TEXT,
            is_approved INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Таблица настроек главного меню
    cur.execute("""
        CREATE TABLE IF NOT EXISTS menu_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_file_id TEXT,
            welcome_text TEXT,
            channel_link TEXT,
            chat_link TEXT,
            support_links TEXT
        )
    """)

    # Таблица статистики переходов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS link_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            click_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Таблица сообщений от администратора
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_text TEXT,
            created_at TEXT,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Добавляем настройки по умолчанию
    cur.execute("SELECT COUNT(*) FROM menu_settings")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO menu_settings (id, welcome_text, channel_link, chat_link, support_links)
            VALUES (1, 'Добро пожаловать в магазин одежды!', '@ваш_канал', '@ваш_чат', '@ваша_поддержка')
        """)

    # Добавляем тестовые коллекции
    cur.execute("SELECT COUNT(*) FROM collections")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO collections (name, description) VALUES ('Новинки', 'Свежие поступления')")
        cur.execute("INSERT INTO collections (name, description) VALUES ('Хиты продаж', 'Самые популярные товары')")

    # Создаём индексы
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON group_orders(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON group_orders(status)")

    conn.commit()
    conn.close()


# ========== НАСТРОЙКИ МЕНЮ ==========
def get_menu_settings():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT photo_file_id, welcome_text, channel_link, chat_link, support_links FROM menu_settings WHERE id = 1")
    result = cur.fetchone()
    conn.close()
    return result


def update_menu_settings(photo_file_id=None, welcome_text=None, channel_link=None, chat_link=None, support_links=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if photo_file_id is not None:
        cur.execute("UPDATE menu_settings SET photo_file_id = ? WHERE id = 1", (photo_file_id,))
    if welcome_text is not None:
        cur.execute("UPDATE menu_settings SET welcome_text = ? WHERE id = 1", (welcome_text,))
    if channel_link is not None:
        cur.execute("UPDATE menu_settings SET channel_link = ? WHERE id = 1", (channel_link,))
    if chat_link is not None:
        cur.execute("UPDATE menu_settings SET chat_link = ? WHERE id = 1", (chat_link,))
    if support_links is not None:
        cur.execute("UPDATE menu_settings SET support_links = ? WHERE id = 1", (support_links,))
    conn.commit()
    conn.close()


# ========== КОЛЛЕКЦИИ ==========
def add_collection(name, description, photo_file_id=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO collections (name, description, photo_file_id) VALUES (?, ?, ?)", (name, description, photo_file_id))
    conn.commit()
    conn.close()


def get_collections():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, photo_file_id FROM collections WHERE is_active = 1 ORDER BY sort_order")
    result = cur.fetchall()
    conn.close()
    return result


def get_collection(collection_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, photo_file_id FROM collections WHERE id = ?", (collection_id,))
    result = cur.fetchone()
    conn.close()
    return result


def update_collection(collection_id, name=None, description=None, photo_file_id=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if name:
        cur.execute("UPDATE collections SET name = ? WHERE id = ?", (name, collection_id))
    if description:
        cur.execute("UPDATE collections SET description = ? WHERE id = ?", (description, collection_id))
    if photo_file_id is not None:
        cur.execute("UPDATE collections SET photo_file_id = ? WHERE id = ?", (photo_file_id, collection_id))
    conn.commit()
    conn.close()


def delete_collection(collection_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE collection_id = ?", (collection_id,))
    cur.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    conn.commit()
    conn.close()


# ========== ТОВАРЫ ==========
def add_product(collection_id, name, description, price, photo_file_id=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO products (collection_id, name, description, price, photo_file_id) VALUES (?, ?, ?, ?, ?)",
                (collection_id, name, description, price, photo_file_id))
    conn.commit()
    conn.close()


def get_products_by_collection(collection_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, price, photo_file_id FROM products WHERE collection_id = ? AND is_active = 1 ORDER BY sort_order", (collection_id,))
    result = cur.fetchall()
    conn.close()
    return result


def get_product(product_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, p.description, p.price, p.photo_file_id, c.name 
        FROM products p
        JOIN collections c ON p.collection_id = c.id
        WHERE p.id = ? AND p.is_active = 1
    """, (product_id,))
    result = cur.fetchone()
    conn.close()
    return result


def update_product(product_id, name=None, description=None, price=None, photo_file_id=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if name:
        cur.execute("UPDATE products SET name = ? WHERE id = ?", (name, product_id))
    if description:
        cur.execute("UPDATE products SET description = ? WHERE id = ?", (description, product_id))
    if price:
        cur.execute("UPDATE products SET price = ? WHERE id = ?", (price, product_id))
    if photo_file_id is not None:
        cur.execute("UPDATE products SET photo_file_id = ? WHERE id = ?", (photo_file_id, product_id))
    conn.commit()
    conn.close()


def delete_product(product_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def get_all_products():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, p.description, p.price, p.photo_file_id, c.name 
        FROM products p
        JOIN collections c ON p.collection_id = c.id
        WHERE p.is_active = 1
    """)
    result = cur.fetchall()
    conn.close()
    return result


# ========== КОРЗИНА ==========
def add_to_cart(user_id, product_id, quantity, size):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cart (user_id, product_id, quantity, size, added_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, product_id, quantity, size, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_cart(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.product_id, p.name, p.price, c.quantity, c.size, p.photo_file_id
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, (user_id,))
    result = cur.fetchall()
    conn.close()
    print(f"🔵 get_cart({user_id}) вернул {len(result)} товаров")
    return result


def clear_cart(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ========== ПОЛЬЗОВАТЕЛИ ==========
def add_user(user_id, username, first_name, last_name, phone=None, address=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, phone, address, registered_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, first_name, last_name, phone, address, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def update_user_profile(user_id, phone=None, address=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if phone:
        cur.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
    if address:
        cur.execute("UPDATE users SET address = ? WHERE user_id = ?", (address, user_id))
    conn.commit()
    conn.close()


def get_user_profile(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, first_name, last_name, phone, address FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result


def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, first_name, phone FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result


# ========== ГРУППОВЫЕ ЗАКАЗЫ ==========
def create_group_order(user_id, total_price, delivery_city, delivery_address, phone, delivery_date, delivery_time):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    now = datetime.now().isoformat()
    order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

    cur.execute("""
        INSERT INTO group_orders (user_id, order_number, total_price, delivery_city, delivery_address, phone, delivery_date, delivery_time, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (user_id, order_number, total_price, delivery_city, delivery_address, phone, delivery_date, delivery_time, now, now))

    group_order_id = cur.lastrowid
    conn.commit()
    conn.close()
    print(f"✅ Создан групповой заказ #{group_order_id} с номером {order_number}")
    return group_order_id, order_number


def add_group_order_item(group_order_id, product_id, product_name, quantity, size, price, photo_file_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO group_order_items (group_order_id, product_id, product_name, quantity, size, price, photo_file_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (group_order_id, product_id, product_name, quantity, size, price, photo_file_id))
    conn.commit()
    conn.close()


def get_group_order(group_order_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM group_orders WHERE id = ?", (group_order_id,))
    order = cur.fetchone()
    items = []
    if order:
        cur.execute("""
            SELECT product_id, product_name, quantity, size, price, photo_file_id
            FROM group_order_items
            WHERE group_order_id = ?
        """, (group_order_id,))
        items = cur.fetchall()
    conn.close()
    return order, items


def update_group_order_status(group_order_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE group_orders SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), group_order_id))
    conn.commit()
    conn.close()


def get_pending_confirmation_orders():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT go.id, go.user_id, u.username, go.order_number, go.total_price, go.delivery_city, go.delivery_address, go.phone, go.created_at, go.delivery_date, go.delivery_time
        FROM group_orders go
        JOIN users u ON go.user_id = u.user_id
        WHERE go.status = 'paid'
        ORDER BY go.created_at ASC
    """)
    result = cur.fetchall()
    conn.close()
    return result


def get_paid_orders():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT go.id, go.user_id, u.username, go.order_number, go.total_price, go.delivery_city, go.delivery_address, go.phone, go.created_at, go.delivery_date, go.delivery_time
        FROM group_orders go
        JOIN users u ON go.user_id = u.user_id
        WHERE go.status = 'paid'
        ORDER BY go.created_at ASC
    """)
    result = cur.fetchall()
    conn.close()
    return result


def get_shipped_orders():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT go.id, go.user_id, u.username, go.order_number, go.total_price, go.delivery_city, go.delivery_address, go.phone, go.created_at, go.delivery_date, go.delivery_time
        FROM group_orders go
        JOIN users u ON go.user_id = u.user_id
        WHERE go.status = 'shipped'
        ORDER BY go.created_at ASC
    """)
    result = cur.fetchall()
    conn.close()
    return result


# ========== ОТЗЫВЫ ==========
def add_review(user_id, user_name, review_text, rating):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reviews (user_id, user_name, review_text, rating, created_at, is_approved)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (user_id, user_name, review_text, rating, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_approved_reviews():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_name, review_text, rating, created_at FROM reviews WHERE is_approved = 1 ORDER BY created_at DESC LIMIT 10")
    result = cur.fetchall()
    conn.close()
    return result


# ========== СООБЩЕНИЯ АДМИНА ==========
def add_admin_message(user_id, message_text):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO admin_messages (user_id, message_text, created_at)
        VALUES (?, ?, ?)
    """, (user_id, message_text, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_user_messages(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, message_text, created_at, is_read 
        FROM admin_messages 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    """, (user_id,))
    result = cur.fetchall()
    conn.close()
    return result


# ========== СТАТИСТИКА ПЕРЕХОДОВ ==========
def add_click_record(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO link_clicks (user_id, username, click_date)
        VALUES (?, ?, ?)
    """, (user_id, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_link_stats():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM link_clicks")
    total_clicks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM link_clicks")
    unique_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM link_clicks WHERE date(click_date) = date('now')")
    today_clicks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM link_clicks WHERE date(click_date) >= date('now', '-7 days')")
    week_clicks = cur.fetchone()[0]
    cur.execute("SELECT username, click_date FROM link_clicks ORDER BY click_date DESC LIMIT 10")
    recent = cur.fetchall()
    conn.close()
    return {
        'total': total_clicks,
        'unique': unique_users,
        'today': today_clicks,
        'week': week_clicks,
        'recent': recent
    }


# ========== ЭКСПОРТ/ИМПОРТ CSV ==========
def export_products_to_csv():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT p.name, p.description, p.price, c.name, p.photo_file_id
        FROM products p
        JOIN collections c ON p.collection_id = c.id
        WHERE p.is_active = 1
    """)
    products = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Название", "Описание", "Цена", "Коллекция", "Photo File ID"])

    for prod in products:
        writer.writerow([prod[0], prod[1], prod[2], prod[3], prod[4] or ""])

    return output.getvalue().encode('utf-8-sig')


def import_products_from_csv(csv_content):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    csv_file = io.StringIO(csv_content.decode('utf-8-sig'))
    reader = csv.reader(csv_file)
    all_rows = list(reader)

    if not all_rows:
        return 0, ["Файл пустой"]

    imported = 0
    errors = []

    for row_num, row in enumerate(all_rows[1:], start=2):
        if len(row) < 4:
            errors.append(f"Строка {row_num}: Недостаточно данных")
            continue

        name = row[0].strip()
        description = row[1].strip()
        price_str = row[2].strip()
        collection_name = row[3].strip()
        photo_file_id = row[4].strip() if len(row) > 4 and row[4] else None

        if not name:
            errors.append(f"Строка {row_num}: Пустое название товара")
            continue

        cur.execute("SELECT id FROM products WHERE name = ?", (name,))
        if cur.fetchone():
            continue

        try:
            price = int(float(price_str))
        except:
            errors.append(f"Строка {row_num}: Неверная цена '{price_str}'")
            continue

        cur.execute("SELECT id FROM collections WHERE name = ?", (collection_name,))
        collection = cur.fetchone()
        if collection:
            collection_id = collection[0]
        else:
            cur.execute("INSERT INTO collections (name, description) VALUES (?, ?)",
                       (collection_name, f"Коллекция {collection_name}"))
            collection_id = cur.lastrowid

        cur.execute("""
            INSERT INTO products (collection_id, name, description, price, photo_file_id, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (collection_id, name, description, price, photo_file_id))
        imported += 1

    conn.commit()
    conn.close()
    return imported, errors


# ========== ЗАКАЗЫ (СТАРЫЕ, ДЛЯ СОВМЕСТИМОСТИ) ==========
def get_user_orders(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT go.id, '' as product_name, 1 as quantity, go.total_price, go.status, go.created_at,
               '' as size, go.delivery_address, go.phone, '' as photo_file_id,
               go.delivery_date, go.delivery_time
        FROM group_orders go
        WHERE go.user_id = ?
        ORDER BY go.created_at DESC
    """, (user_id,))
    result = cur.fetchall()
    conn.close()
    return result
# database.py - добавьте в начало
import pytz
from datetime import datetime

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

def get_now_moscow():
    """Получить текущее время по Москве"""
    return datetime.now(MOSCOW_TZ).isoformat()
