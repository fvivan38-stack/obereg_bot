# bot.py - ЧАСТЬ 1
import asyncio
import sqlite3
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, LinkPreviewOptions
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InputMediaPhoto
from aiogram.client.session.aiohttp import AiohttpSession
import config
from database import *

# ========== НАСТРОЙКА ПРОКСИ ==========
# ========== СОЗДАНИЕ БОТА С ПРОКСИ ==========
async def create_bot_with_proxy():
    """Создание бота с прокси"""
    if config.USE_PROXY:
        # Создаём сессию с прокси
        session = AiohttpSession(proxy=config.PROXY_URL)
        print(f"🔵 Используется прокси: {config.PROXY_URL}")
        # Убираем DefaultBotProperties, используем простой способ
        return Bot(token=config.BOT_TOKEN, session=session)
    else:
        print("🔵 Прокси не используется")
        return Bot(token=config.BOT_TOKEN)

# Создаём бота (будет создан в main)
bot = None
dp = Dispatcher()
init_db()



# ========== СЛОВАРИ ==========
last_bot_messages = {}
user_pages = {}
admin_orders_pages = {}
pending_payments = {}
product_pages = {}


# ========== СОСТОЯНИЯ ==========
class OrderState(StatesGroup):
    waiting_for_city = State()
    waiting_for_size = State()
    waiting_for_date = State()
    waiting_for_custom_date = State()
    waiting_for_time = State()
    waiting_for_address = State()
    waiting_for_address_temp = State()
    waiting_for_phone = State()
    waiting_for_phone_temp = State()
    waiting_for_quantity = State()


class EditOrderState(StatesGroup):
    waiting_for_new_address = State()
    waiting_for_new_phone = State()


class AdminState(StatesGroup):
    waiting_for_menu_photo = State()
    waiting_for_menu_text = State()
    waiting_for_menu_links = State()
    waiting_for_collection_name = State()
    waiting_for_collection_desc = State()
    waiting_for_collection_photo = State()
    waiting_for_edit_collection_id = State()
    waiting_for_edit_collection_name = State()
    waiting_for_edit_collection_desc = State()
    waiting_for_edit_collection_photo = State()
    waiting_for_product_collection = State()
    waiting_for_product_name = State()
    waiting_for_product_desc = State()
    waiting_for_product_price = State()
    waiting_for_product_photo = State()
    waiting_for_edit_product_id = State()
    waiting_for_edit_product_name = State()
    waiting_for_edit_product_desc = State()
    waiting_for_edit_product_price = State()
    waiting_for_edit_product_photo = State()
    waiting_for_message_to_user = State()
    waiting_for_import_file = State()


class ProfileState(StatesGroup):
    waiting_for_new_phone = State()
    waiting_for_new_address = State()


class ReviewState(StatesGroup):
    waiting_for_review = State()
    waiting_for_rating = State()


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def is_admin(user_id):
    return user_id in config.ADMIN_IDS

# bot.py - добавьте в начало (после импортов)

async def show_admin_orders_with_pagination(callback, orders, page, order_type, title):
    """Показать заказы в админ-панели с пагинацией и фото"""
    if not orders:
        await callback.answer(f"Нет {title}", show_alert=True)
        return None

    total_orders = len(orders)
    orders_per_page = 1

    if page < 0:
        page = 0
    if page >= total_orders:
        page = total_orders - 1

    order = orders[page]
    order_id, user_id, username, order_number, total_price, city, addr, phone, created_at, delivery_date, delivery_time = order

    # Получаем товары и фото
    _, items = get_group_order(order_id)
    photos = []
    items_text = ""
    for item in items:
        product_id, product_name, qty, size, price, photo = item
        items_text += f"📦 {product_name} x{qty} (размер {size}) = {price * qty}₽\n"
        if photo:
            photos.append(photo)

    delivery = f"📍 {addr[:50]}" if city == "spb" else "🌍 Другой город"
    date_info = f"📅 Заказ: {created_at[:10]}"
    if delivery_date:
        date_info += f" | Доставка: {delivery_date} {delivery_time or ''}"

    text = (f"🧾 ЗАКАЗ №{order_number} ({page + 1}/{total_orders})\n"
            f"👤 @{username or str(user_id)}\n"
            f"📦 ТОВАРЫ:\n{items_text}\n"
            f"💰 Сумма: {total_price}₽\n"
            f"📱 Телефон: {phone}\n"
            f"🚚 {delivery}\n"
            f"{date_info}\n\n"
            f"📊 СТАТУС: {title}")

    # Кнопки навигации
    builder = InlineKeyboardBuilder()

    if page > 0:
        builder.button(text="◀️ НАЗАД", callback_data=f"admin_order_page_{order_type}_{page - 1}")
    if page + 1 < total_orders:
        builder.button(text="ВПЕРЕД ▶️", callback_data=f"admin_order_page_{order_type}_{page + 1}")

    # Кнопки действий в зависимости от типа
    if order_type == "pending":
        builder.button(text="✅ ПОДТВЕРДИТЬ ОПЛАТУ", callback_data=f"confirm_payment_group_{order_id}")
        builder.button(text="💬 НАПИСАТЬ", callback_data=f"msg_user_{user_id}")
    elif order_type == "shipping":
        builder.button(text="✈️ ПОДТВЕРДИТЬ ОТПРАВКУ", callback_data=f"ship_group_{order_id}")
        builder.button(text="💬 НАПИСАТЬ", callback_data=f"msg_user_{user_id}")
    elif order_type == "shipped":
        builder.button(text="📦 ОТМЕТИТЬ ДОСТАВЛЕНО", callback_data=f"deliver_group_{order_id}")
        builder.button(text="💬 НАПИСАТЬ", callback_data=f"msg_user_{user_id}")

    builder.button(text="« НАЗАД В МЕНЮ", callback_data="admin_panel")
    builder.adjust(1)

    # Сохраняем данные для пагинации
    admin_orders_pages[f"{callback.from_user.id}_{order_type}"] = {
        'orders': orders,
        'page': page,
        'title': title
    }

    await callback.answer()

    # Отправляем с фото
    if photos:
        try:
            from aiogram.types import InputMediaPhoto
            media_group = []
            for i, photo in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo, caption=text))
                else:
                    media_group.append(InputMediaPhoto(media=photo))
            await callback.message.delete()
            await callback.message.answer_media_group(media=media_group)
            await callback.message.answer("👇", reply_markup=builder.as_markup())
        except:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())

async def send_to_group(text, photo_id=None):
    """Отправляет сообщение в группу"""
    print(f"🔵 ПОПЫТКА ОТПРАВКИ В ГРУППУ: {text[:50]}...")
    print(f"🔵 GROUP_ID = {config.GROUP_ID}")

    try:
        if photo_id:
            await bot.send_photo(config.GROUP_ID, photo=photo_id, caption=text)
            print("✅ Фото отправлено в группу")
        else:
            await bot.send_message(config.GROUP_ID, text)
            print("✅ Сообщение отправлено в группу")
    except Exception as e:
        print(f"❌ Ошибка отправки в группу: {e}")

async def log_user_action(user, action, details=""):
    user_name = user.first_name or "Unknown"
    user_tag = f"@{user.username}" if user.username else f"ID:{user.id}"
    print(f"👤 {user_name} ({user_tag}) - {action} {details}")


async def delete_user_message(message):
    try:
        await message.delete()
    except:
        pass


async def delete_bot_message(user_id, message_id):
    if message_id:
        try:
            await bot.delete_message(user_id, message_id)
        except:
            pass


async def delete_previous_bot_message(user_id):
    if user_id in last_bot_messages and last_bot_messages[user_id]:
        try:
            await bot.delete_message(user_id, last_bot_messages[user_id])
        except:
            pass
        last_bot_messages[user_id] = None


async def safe_delete_message(message):
    try:
        await message.delete()
    except:
        pass


async def check_maintenance(message: types.Message):
    if config.MAINTENANCE_MODE:
        if not is_admin(message.from_user.id):
            await message.answer("🛠️ ВЕДУТСЯ ТЕХНИЧЕСКИЕ РАБОТЫ\n\nБот временно недоступен.\nПожалуйста, зайдите позже.\n\nПриносим извинения за неудобства! 🙏")
            return False
    return True
# bot.py - ЧАСТЬ 2

# ========== КЛАВИАТУРЫ ==========
def main_keyboard(user_id=None):
    keyboard = [
        [KeyboardButton(text="🛍️ КАТАЛОГ")],
        [KeyboardButton(text="🛒 КОРЗИНА"), KeyboardButton(text="⭐ ОТЗЫВЫ")],
        [KeyboardButton(text="👤 ПРОФИЛЬ"), KeyboardButton(text="🆘 ПОДДЕРЖКА")],
        [KeyboardButton(text="ℹ️ О МАГАЗИНЕ")]
    ]
    if user_id and is_admin(user_id):
        keyboard.append([KeyboardButton(text="👑 АДМИН-ПАНЕЛЬ")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def admin_panel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🖼️ Оформление главного меню", callback_data="admin_menu_settings")
    builder.button(text="➕ Добавить коллекцию", callback_data="admin_add_collection")
    builder.button(text="📁 Управление коллекциями", callback_data="admin_manage_collections")
    builder.button(text="🛍️ Добавить товар", callback_data="admin_add_product")
    builder.button(text="✏️ Редактировать товары", callback_data="admin_manage_products")
    builder.button(text="💰 Заказы на подтверждение", callback_data="admin_pending_orders")
    builder.button(text="📦 Заказы на отправку", callback_data="admin_orders")
    builder.button(text="🚚 Отправленные заказы", callback_data="admin_shipped_orders")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="🔗 Статистика переходов", callback_data="admin_link_stats")
    builder.button(text="📥 Импорт/Экспорт товаров", callback_data="admin_import_export")
    builder.button(text="💾 Резервное копирование", callback_data="admin_backup_menu")
    builder.button(text="🛠️ Технические работы", callback_data="admin_maintenance")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def collections_keyboard():
    collections = get_collections()
    builder = InlineKeyboardBuilder()
    for col in collections:
        builder.button(text=f"📁 {col[1]}", callback_data=f"collection_{col[0]}")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def size_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="S", callback_data="size_S"),
         InlineKeyboardButton(text="M", callback_data="size_M"),
         InlineKeyboardButton(text="L", callback_data="size_L")],
        [InlineKeyboardButton(text="XL", callback_data="size_XL"),
         InlineKeyboardButton(text="XXL", callback_data="size_XXL")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])


def city_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Санкт-Петербург", callback_data="city_spb")],
        [InlineKeyboardButton(text="🌍 Другой город", callback_data="city_other")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])


# ========== ГЛАВНОЕ МЕНЮ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user

    # Проверяем, новый ли пользователь
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user.id,))
    is_new = cur.fetchone() is None
    conn.close()

    add_user(user.id, user.username, user.first_name, user.last_name)

    await delete_user_message(message)
    await delete_previous_bot_message(user.id)


    # Отправляем уведомление только для новых пользователей (не админов)
    if is_new and not is_admin(user.id):
        user_tag = f"@{user.username}" if user.username else f"ID:{user.id}"
        await send_to_group(
            f"🆕 НОВЫЙ ПОЛЬЗОВАТЕЛЬ!\n\n"
            f"👤 {user.first_name}\n"
            f"🔖 {user_tag}\n"
            f"🆔 {user.id}",

        )

    await cmd_start_from_user(user.id, message)

async def cmd_start_from_user(user_id, message):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT username, first_name FROM users WHERE user_id = ?", (user_id,))
    user_data = cur.fetchone()
    conn.close()

    if user_data:
        username, first_name = user_data
    else:
        username = None
        first_name = "Пользователь"

    settings = get_menu_settings()
    welcome_text = settings[1] if settings and settings[1] else "Добро пожаловать в магазин одежды!"

    text = f"""✨ {welcome_text} ✨

[📢 Наш канал]({config.CHANNEL_LINK})
[🆘 Служба поддержки](https://t.me/{config.SUPPORT_USERNAME})

👋 Привет, {first_name}!

Используйте кнопки ниже для навигации:
"""

    link_preview = LinkPreviewOptions(is_disabled=True)

    if user_id in last_bot_messages:
        try:
            await bot.delete_message(user_id, last_bot_messages[user_id])
        except:
            pass

    if settings and settings[0]:
        try:
            sent_msg = await message.answer_photo(
                photo=settings[0],
                caption=text,
                parse_mode="Markdown",
                reply_markup=main_keyboard(user_id),
                link_preview_options=link_preview
            )
            last_bot_messages[user_id] = sent_msg.message_id
            return
        except:
            pass

    sent_msg = await message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard(user_id), link_preview_options=link_preview)
    last_bot_messages[user_id] = sent_msg.message_id


@dp.message(lambda message: message.text == "🏠 Главное меню")
async def home_menu(message: types.Message):
    user_id = message.from_user.id
    await delete_user_message(message)
    await delete_previous_bot_message(user_id)
    await cmd_start_from_user(user_id, message)


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)
    await cmd_start_from_user(callback.from_user.id, callback.message)


@dp.message(Command("showid"))
async def show_user_id(message: types.Message):
    await message.answer(f"Ваш ID: {message.from_user.id}")

# bot.py - ЧАСТЬ 3 (добавьте эту функцию)

# ========== КАТАЛОГ ==========
@dp.message(lambda message: message.text == "🛍️ КАТАЛОГ")
async def show_catalog(message: types.Message):
    user = message.from_user
    user_id = user.id
    await delete_user_message(message)
    await delete_previous_bot_message(user_id)

    # Отправляем уведомление в группу (только если не админ)
    if not is_admin(user.id):
        user_tag = f"@{user.username}" if user.username else f"ID:{user.id}"
        await send_to_group(
            f"📂 ПОЛЬЗОВАТЕЛЬ ЗАШЁЛ В КАТАЛОГ\n\n"
            f"👤 {user.first_name}\n"
            f"🔖 {user_tag}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )

    collections = get_collections()
    if not collections:
        await message.answer("😕 Пока нет коллекций")
        return

    settings = get_menu_settings()
    menu_photo = settings[0] if settings else None

    text = "📂 *НАШИ КОЛЛЕКЦИИ*"

    builder = InlineKeyboardBuilder()
    for col in collections:
        builder.button(text=f"📁 {col[1]}", callback_data=f"collection_{col[0]}")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    if menu_photo:
        try:
            await message.answer_photo(
                photo=menu_photo,
                caption=text,
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            return
        except:
            pass

    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("collection_"))
async def show_products(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)

    col_id = int(callback.data.split("_")[1])

    # Сохраняем ID коллекции для возврата
    user_id = callback.from_user.id
    if user_id not in product_pages:
        product_pages[user_id] = {}
    product_pages[user_id]['collection_id'] = col_id

    collection = get_collection(col_id)
    products = get_products_by_collection(col_id)

    if not products:
        await callback.message.answer("В этой коллекции пока нет товаров", reply_markup=collections_keyboard())
        return

    builder = InlineKeyboardBuilder()
    for product in products:
        prod_id, name, desc, price, photo = product
        builder.button(text=f"👕 {name} - {price}₽", callback_data=f"product_{prod_id}")

    builder.button(text="« Назад к коллекциям", callback_data="back_to_collections")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    text = f"📁 *{collection[1]}*\n\n{collection[2]}\n\n🛍️ *Товары в коллекции:*"

    if collection[3]:
        await callback.message.answer_photo(photo=collection[3], caption=text, parse_mode="Markdown",
                                            reply_markup=builder.as_markup())
    else:
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("product_"))
async def view_product(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)

    prod_id = int(callback.data.split("_")[1])

    # Сохраняем ID товара и коллекции для возврата
    user_id = callback.from_user.id
    product = get_product(prod_id)

    if not product:
        await callback.message.answer("Товар не найден", reply_markup=collections_keyboard())
        return

    # Сохраняем ID коллекции
    collection_name = product[5]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id FROM collections WHERE name = ?", (collection_name,))
    col = cur.fetchone()
    conn.close()

    if col:
        if user_id not in product_pages:
            product_pages[user_id] = {}
        product_pages[user_id]['collection_id'] = col[0]

    prod_id, name, full_desc, price, photo, collection_name = product

    text = f"<b>{name}</b>\n\n"
    text += f"💰 <b>Цена:</b> {price} руб.\n"
    text += f"📁 <b>Коллекция:</b> {collection_name}\n\n"
    text += f'<blockquote expandable>📝 <b>Описание:</b> {full_desc}</blockquote>'

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ В КОРЗИНУ", callback_data=f"buy_{prod_id}")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_products")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

    if photo:
        await callback.message.answer_photo(photo=photo, caption=text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@dp.callback_query(F.data == "back_to_products")
async def back_to_products(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)

    user_id = callback.from_user.id

    # Проверяем, есть ли сохранённая коллекция для этого пользователя
    if user_id in product_pages and product_pages[user_id].get('collection_id'):
        collection_id = product_pages[user_id]['collection_id']

        # Показываем товары в этой коллекции
        collection = get_collection(collection_id)
        products = get_products_by_collection(collection_id)

        if not products:
            await callback.message.answer("В этой коллекции пока нет товаров", reply_markup=collections_keyboard())
            return

        builder = InlineKeyboardBuilder()
        for product in products:
            prod_id, name, desc, price, photo = product
            builder.button(text=f"👕 {name} - {price}₽", callback_data=f"product_{prod_id}")

        builder.button(text="« Назад к коллекциям", callback_data="back_to_collections")
        builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
        builder.adjust(1)

        text = f"📁 *{collection[1]}*\n\n{collection[2]}\n\n🛍️ *Товары в коллекции:*"

        if collection[3]:
            await callback.message.answer_photo(photo=collection[3], caption=text, parse_mode="Markdown",
                                                reply_markup=builder.as_markup())
        else:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        # Если нет сохранённой коллекции - показываем список всех коллекций
        await show_catalog(callback.message)

@dp.callback_query(F.data == "back_to_collections")
async def back_to_collections(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)
    await show_catalog(callback.message)
# bot.py - ЧАСТЬ 4 (Корзина)

# ========== КОРЗИНА ==========
@dp.message(lambda message: message.text == "🛒 КОРЗИНА")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    print(f"🔵 show_cart вызван для user_id={user_id}")

    await delete_user_message(message)
    await delete_previous_bot_message(user_id)

    cart_items = get_cart(user_id)
    print(f"🔵 Найдено товаров в корзине: {len(cart_items)}")

    for item in cart_items:
        print(f"   - {item}")

    if not cart_items:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ ПЕРЕЙТИ В КАТАЛОГ", callback_data="go_to_catalog")],
            [InlineKeyboardButton(text="🏠 ГЛАВНОЕ МЕНЮ", callback_data="back_to_menu")]
        ])
        await message.answer("🛒 ВАША КОРЗИНА ПУСТА\n\nДобавьте товары через каталог!", reply_markup=keyboard)
        return


    total_price = 0
    text = "🛒 ВАША КОРЗИНА:\n\n"

    for item in cart_items:
        cart_id, product_id, name, price, quantity, size, photo = item
        item_total = price * quantity
        total_price += item_total
        text += f"📦 {name}\n📏 Размер: {size}\n🔢 {quantity} шт = {item_total}₽\n━━━━━━━━━━━━━━━\n"

    text += f"\n💰 ИТОГО: {total_price} руб."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ОФОРМИТЬ ЗАКАЗ", callback_data="checkout")],
        [InlineKeyboardButton(text="🗑️ ОЧИСТИТЬ КОРЗИНУ", callback_data="clear_cart")],
        [InlineKeyboardButton(text="🏠 ГЛАВНОЕ МЕНЮ", callback_data="back_to_menu")]
    ])

    sent_msg = await message.answer(text, reply_markup=keyboard)
    last_bot_messages[user_id] = sent_msg.message_id


@dp.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    clear_cart(user_id)
    await callback.answer("🗑️ Корзина очищена!", show_alert=True)
    await safe_delete_message(callback.message)
    await show_cart(callback.message)


# ========== ДОБАВЛЕНИЕ В КОРЗИНУ ==========
@dp.callback_query(F.data.startswith("buy_"))
async def add_to_cart_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete_message(callback.message)

    prod_id = int(callback.data.split("_")[1])
    product = get_product(prod_id)

    if not product:
        await callback.message.answer("Товар не найден")
        return

    await state.update_data(product_id=prod_id, price=product[3])

    sent_msg = await callback.message.answer(
        f"🛒 {product[1]}\n💰 Цена: {product[3]} руб.\n\n📏 ВЫБЕРИТЕ РАЗМЕР:",
        reply_markup=size_keyboard()
    )
    await state.update_data(last_bot_message=sent_msg.message_id)
    await state.set_state(OrderState.waiting_for_size)


@dp.callback_query(OrderState.waiting_for_size, F.data.startswith("size_"))
async def add_to_cart_size(callback: types.CallbackQuery, state: FSMContext):
    size = callback.data.split("_")[1]
    await state.update_data(size=size)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="qty_1"),
         InlineKeyboardButton(text="2", callback_data="qty_2"),
         InlineKeyboardButton(text="3", callback_data="qty_3")],
        [InlineKeyboardButton(text="4", callback_data="qty_4"),
         InlineKeyboardButton(text="5", callback_data="qty_5")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

    await safe_delete_message(callback.message)
    sent_msg = await callback.message.answer(f"📏 Размер: {size}\n\n🔢 ВЫБЕРИТЕ КОЛИЧЕСТВО:", reply_markup=keyboard)
    await state.update_data(last_bot_message=sent_msg.message_id)
    await state.set_state(OrderState.waiting_for_quantity)


@dp.callback_query(OrderState.waiting_for_quantity, F.data.startswith("qty_"))
async def add_to_cart_final(callback: types.CallbackQuery, state: FSMContext):
    quantity = int(callback.data.split("_")[1])
    data = await state.get_data()

    product_id = data["product_id"]
    size = data["size"]
    user_id = callback.from_user.id

    print(f"🔵 ДОБАВЛЕНИЕ В КОРЗИНУ: user={user_id}, product={product_id}, qty={quantity}, size={size}")

    add_to_cart(user_id, product_id, quantity, size)

    # ПРОВЕРЯЕМ СРАЗУ
    cart_check = get_cart(user_id)
    print(f"🔵 ПОСЛЕ ДОБАВЛЕНИЯ: в корзине {len(cart_check)} товаров")

    await safe_delete_message(callback.message)
    await callback.answer("✅ Товар добавлен в корзину!", show_alert=True)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ ПРОДОЛЖИТЬ ПОКУПКИ", callback_data="continue_shopping")],
        [InlineKeyboardButton(text="🛒 ПЕРЕЙТИ В КОРЗИНУ", callback_data="go_to_cart")],
        [InlineKeyboardButton(text="🏠 ГЛАВНОЕ МЕНЮ", callback_data="back_to_menu")]
    ])

    await callback.message.answer(f"✅ {quantity} шт добавлено в корзину!\nРазмер: {size}", reply_markup=keyboard)
    await state.clear()


@dp.callback_query(F.data == "continue_shopping")
async def continue_shopping(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    print(f"🔵 continue_shopping: user_id={user_id}")

    await callback.answer()
    await safe_delete_message(callback.message)

    # Показываем каталог
    collections = get_collections()
    if not collections:
        await callback.message.answer("😕 Пока нет коллекций")
        return

    settings = get_menu_settings()
    menu_photo = settings[0] if settings else None

    text = "📂 *НАШИ КОЛЛЕКЦИИ*"

    builder = InlineKeyboardBuilder()
    for col in collections:
        builder.button(text=f"📁 {col[1]}", callback_data=f"collection_{col[0]}")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    if menu_photo:
        try:
            await callback.message.answer_photo(
                photo=menu_photo,
                caption=text,
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            return
        except:
            pass

    await callback.message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())
@dp.callback_query(F.data == "go_to_cart")
async def go_to_cart_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    print(f"🔵 go_to_cart_handler: user_id={user_id}")

    await callback.answer()
    await safe_delete_message(callback.message)

    # Получаем корзину напрямую, без создания fake_message
    cart_items = get_cart(user_id)

    if not cart_items:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ ПЕРЕЙТИ В КАТАЛОГ", callback_data="go_to_catalog")],
            [InlineKeyboardButton(text="🏠 ГЛАВНОЕ МЕНЮ", callback_data="back_to_menu")]
        ])
        await callback.message.answer("🛒 ВАША КОРЗИНА ПУСТА\n\nДобавьте товары через каталог!", reply_markup=keyboard)
        return

    total_price = 0
    text = "🛒 ВАША КОРЗИНА:\n\n"

    for item in cart_items:
        cart_id, product_id, name, price, quantity, size, photo = item
        item_total = price * quantity
        total_price += item_total
        text += f"📦 {name}\n📏 Размер: {size}\n🔢 {quantity} шт = {item_total}₽\n━━━━━━━━━━━━━━━\n"

    text += f"\n💰 ИТОГО: {total_price} руб."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ОФОРМИТЬ ЗАКАЗ", callback_data="checkout")],
        [InlineKeyboardButton(text="🗑️ ОЧИСТИТЬ КОРЗИНУ", callback_data="clear_cart")],
        [InlineKeyboardButton(text="🏠 ГЛАВНОЕ МЕНЮ", callback_data="back_to_menu")]
    ])

    sent_msg = await callback.message.answer(text, reply_markup=keyboard)
    last_bot_messages[user_id] = sent_msg.message_id


@dp.callback_query(F.data == "go_to_catalog")
async def go_to_catalog(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    print(f"🔵 go_to_catalog: user_id={user_id}")

    await callback.answer()
    await safe_delete_message(callback.message)

    # Показываем каталог
    collections = get_collections()
    if not collections:
        await callback.message.answer("😕 Пока нет коллекций")
        return

    settings = get_menu_settings()
    menu_photo = settings[0] if settings else None

    text = "📂 *НАШИ КОЛЛЕКЦИИ*"

    builder = InlineKeyboardBuilder()
    for col in collections:
        builder.button(text=f"📁 {col[1]}", callback_data=f"collection_{col[0]}")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    if menu_photo:
        try:
            await callback.message.answer_photo(
                photo=menu_photo,
                caption=text,
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            return
        except:
            pass

    await callback.message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())
# bot.py - ЧАСТЬ 5 (Оформление заказа)

# ========== ОФОРМЛЕНИЕ ЗАКАЗА ИЗ КОРЗИНЫ ==========
@dp.callback_query(F.data == "checkout")
async def checkout_cart(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cart_items = get_cart(user_id)

    if not cart_items:
        await callback.answer("Корзина пуста!", show_alert=True)
        return

    total_price = sum(item[3] * item[4] for item in cart_items)
    await state.update_data(cart_items=cart_items, total_price=total_price, checkout=True)

    await safe_delete_message(callback.message)
    sent_msg = await callback.message.answer("📦 ВЫБЕРИТЕ ГОРОД ДОСТАВКИ:", reply_markup=city_keyboard())
    await state.update_data(last_bot_message=sent_msg.message_id)
    await state.set_state(OrderState.waiting_for_city)


# ========== ВЫБОР ГОРОДА ==========
@dp.callback_query(F.data == "city_spb", OrderState.waiting_for_city)
async def city_spb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete_message(callback.message)
    await state.update_data(delivery_city="spb")

    today = datetime.now()

    day1 = today + timedelta(days=2)
    day2 = today + timedelta(days=3)
    day3 = today + timedelta(days=4)

    # Форматируем даты с ведущими нулями
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{day1.day:02d}.{day1.month:02d}.{day1.year}",
                              callback_data=f"date_{day1.strftime('%Y-%m-%d')}")],
        [InlineKeyboardButton(text=f"{day2.day:02d}.{day2.month:02d}.{day2.year}",
                              callback_data=f"date_{day2.strftime('%Y-%m-%d')}")],
        [InlineKeyboardButton(text=f"{day3.day:02d}.{day3.month:02d}.{day3.year}",
                              callback_data=f"date_{day3.strftime('%Y-%m-%d')}")],
        [InlineKeyboardButton(text="✏️ Своя дата", callback_data="custom_date")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

    sent_msg = await callback.message.answer(
        "📅 ВЫБЕРИТЕ ДАТУ ДОСТАВКИ:\n\n⚠️ Доставка возможна не ранее чем через 2 дня!", reply_markup=keyboard)
    await state.update_data(last_bot_message=sent_msg.message_id)
    await state.set_state(OrderState.waiting_for_date)


@dp.callback_query(F.data == "city_other", OrderState.waiting_for_city)
async def city_other(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete_message(callback.message)
    await state.update_data(delivery_city="other", delivery_address=None)

    add_click_record(callback.from_user.id, callback.from_user.username or callback.from_user.first_name)
    tracking_url = f"{config.DELIVERY_LINK}?ref={callback.from_user.id}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Перейти по ссылке", url=tracking_url)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

    await callback.message.answer(
        f"🌍 ДОСТАВКА В ДРУГИЕ ГОРОДА\n\n"
        f"Для оформления заказа перейдите по ссылке ниже:\n\n"
        f"🔗 {tracking_url}\n\n"
        f"📊 Мы заботимся о качестве обслуживания!",
        reply_markup=keyboard
    )
    await state.clear()


# ========== ВЫБОР ДАТЫ ==========
@dp.callback_query(OrderState.waiting_for_date, F.data.startswith("date_"))
async def get_date(callback: types.CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_")[1]
    selected_date = datetime.strptime(date_str, '%Y-%m-%d')
    today = datetime.now()
    min_date = today + timedelta(days=2)

    if selected_date.date() < min_date.date():
        await callback.answer(f"❌ Доставка возможна не ранее {min_date.day}.{min_date.month}.{min_date.year}", show_alert=True)
        return

    await state.update_data(delivery_date=date_str)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="12:00-14:00", callback_data="time_12:00-14:00"),
         InlineKeyboardButton(text="14:00-16:00", callback_data="time_14:00-16:00")],
        [InlineKeyboardButton(text="16:00-18:00", callback_data="time_16:00-18:00"),
         InlineKeyboardButton(text="18:00-20:00", callback_data="time_18:00-20:00")],
        [InlineKeyboardButton(text="20:00-22:00", callback_data="time_20:00-22:00")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

    await safe_delete_message(callback.message)
    sent_msg = await callback.message.answer(
        f"📅 Дата: {selected_date.day}.{selected_date.month}.{selected_date.year}\n\n🕐 ВЫБЕРИТЕ ВРЕМЯ ДОСТАВКИ:",
        reply_markup=keyboard)
    await state.update_data(last_bot_message=sent_msg.message_id)
    await state.set_state(OrderState.waiting_for_time)


@dp.callback_query(F.data == "custom_date", OrderState.waiting_for_date)
async def custom_date_request(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete_message(callback.message)
    sent_msg = await callback.message.answer(
        "✏️ Введите ДАТУ ДОСТАВКИ в формате:\n\nДД.ММ.ГГГГ\n\nПример: 25.12.2024"
    )
    await state.update_data(last_bot_message=sent_msg.message_id)
    await state.set_state(OrderState.waiting_for_custom_date)


@dp.message(OrderState.waiting_for_custom_date)
async def get_custom_date(message: types.Message, state: FSMContext):
    date_text = message.text.strip()
    pattern = r'^\d{2}\.\d{2}\.\d{4}$'

    if not re.match(pattern, date_text):
        await message.answer("❌ Неверный формат! Используйте ДД.ММ.ГГГГ\nПример: 25.12.2024")
        return

    try:
        day, month, year = map(int, date_text.split('.'))
        selected_date = datetime(year, month, day)
        today = datetime.now()
        min_date = today + timedelta(days=2)

        if selected_date < min_date:
            await message.answer(f"❌ Доставка возможна не ранее {min_date.day}.{min_date.month}.{min_date.year}")
            return

        delivery_date = selected_date.strftime('%Y-%m-%d')
    except ValueError:
        await message.answer("❌ Неверная дата! Пример: 25.12.2024")
        return

    await delete_user_message(message)
    await state.update_data(delivery_date=delivery_date)

    data = await state.get_data()
    last_bot_msg_id = data.get('last_bot_message')
    if last_bot_msg_id:
        await delete_bot_message(message.from_user.id, last_bot_msg_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="12:00-14:00", callback_data="time_12:00-14:00"),
         InlineKeyboardButton(text="14:00-16:00", callback_data="time_14:00-16:00")],
        [InlineKeyboardButton(text="16:00-18:00", callback_data="time_16:00-18:00"),
         InlineKeyboardButton(text="18:00-20:00", callback_data="time_18:00-20:00")],
        [InlineKeyboardButton(text="20:00-22:00", callback_data="time_20:00-22:00")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

    sent_msg = await message.answer(f"📅 Дата: {date_text}\n\n🕐 ВЫБЕРИТЕ ВРЕМЯ ДОСТАВКИ:", reply_markup=keyboard)
    await state.update_data(last_bot_message=sent_msg.message_id)
    await state.set_state(OrderState.waiting_for_time)


# ========== ВЫБОР ВРЕМЕНИ И АДРЕСА ==========
@dp.callback_query(OrderState.waiting_for_time, F.data.startswith("time_"))
async def get_time(callback: types.CallbackQuery, state: FSMContext):
    time_slot = callback.data.split("_")[1]
    await state.update_data(delivery_time=time_slot)

    await safe_delete_message(callback.message)
    data = await state.get_data()
    delivery_date = data.get('delivery_date')

    profile = get_user_profile(callback.from_user.id)

    if profile and profile[5] and profile[4]:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Использовать данные профиля", callback_data="use_profile_data")],
            [InlineKeyboardButton(text="✏️ Ввести новые данные", callback_data="enter_new_data")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy"),
             InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
        await callback.message.answer(
            f"📅 Дата: {delivery_date}\n🕐 Время: {time_slot}\n\n"
            f"📋 Данные из профиля:\n📍 Адрес: {profile[5]}\n📱 Телефон: {profile[4]}\n\n"
            f"Использовать эти данные?",
            reply_markup=keyboard
        )
    elif data.get('checkout'):
        await callback.message.answer("🏠 Введите АДРЕС ДОСТАВКИ:")
        await state.set_state(OrderState.waiting_for_address)
    else:
        await callback.message.answer("🏠 Введите АДРЕС ДОСТАВКИ:")
        await state.set_state(OrderState.waiting_for_address)


@dp.callback_query(F.data == "use_profile_data")
async def use_profile_data(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete_message(callback.message)

    profile = get_user_profile(callback.from_user.id)
    print(f"🔵 use_profile_data - профиль: {profile}")

    if profile and profile[5] and profile[4]:
        await state.update_data(delivery_address=profile[5], phone=profile[4])
        data = await state.get_data()
        print(f"🔵 Данные после обновления: address={data.get('delivery_address')}, phone={data.get('phone')}")

        if data.get('checkout'):
            # Оформляем корзину АВТОМАТИЧЕСКИ (без запроса количества)
            cart_items = data.get('cart_items')
            delivery_city = data.get("delivery_city", "spb")
            delivery_address = data.get("delivery_address")
            phone = data.get("phone")
            delivery_date = data.get("delivery_date")
            delivery_time = data.get("delivery_time")

            # Подсчитываем общую сумму
            total_price_all = sum(item[3] * item[4] for item in cart_items)

            # Создаём групповой заказ (ОДИН раз)
            group_order_id, order_number = create_group_order(
                callback.from_user.id, total_price_all, delivery_city, delivery_address, phone, delivery_date, delivery_time
            )

            items_text = ""
            photos = []

            for item in cart_items:
                cart_id, product_id, name, price, qty, size, photo = item
                item_total = price * qty
                items_text += f"📦 {name} x{qty} (размер {size}) = {item_total}₽\n"
                if photo:
                    photos.append(photo)
                # Добавляем товар в групповой заказ
                add_group_order_item(group_order_id, product_id, name, qty, size, price, photo)

            clear_cart(callback.from_user.id)

            delivery_text = f"\n📍 Адрес: {delivery_address}\n📱 Телефон: {phone}"
            if delivery_date:
                delivery_text += f"\n📅 Дата: {delivery_date}\n🕐 Время: {delivery_time}"

            payment_text = config.PAYMENT_DETAILS.format(price=total_price_all)
            payment_text += f"\n\n🧾 ЗАКАЗ №{order_number}\n"
            payment_text += f"📦 Товары:\n{items_text}\n"
            payment_text += f"💰 ИТОГО: {total_price_all} руб.{delivery_text}"

            # Отправляем ВСЕ ФОТО В ОДНОМ СООБЩЕНИИ (галерея)
            if photos:
                try:
                    from aiogram.types import InputMediaPhoto
                    media_group = []
                    for i, photo in enumerate(photos):
                        if i == 0:
                            media_group.append(InputMediaPhoto(media=photo, caption=payment_text))
                        else:
                            media_group.append(InputMediaPhoto(media=photo))
                    await callback.message.answer_media_group(media=media_group)
                    # Отправляем кнопки отдельным сообщением
                    await callback.message.answer("👇", reply_markup=payment_keyboard(group_order_id))
                except Exception as e:
                    print(f"Ошибка отправки галереи: {e}")
                    await callback.message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))
            else:
                await callback.message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))

            await state.clear()
        else:
            # Обычный заказ - один товар
            await callback.message.answer(f"💰 Цена: {data['price']} руб.\n\nВведите КОЛИЧЕСТВО (1-5):")
            await state.set_state(OrderState.waiting_for_quantity)
    else:
        await callback.message.answer("❌ Данные профиля не заполнены. Введите адрес:")
        await state.set_state(OrderState.waiting_for_address)

@dp.callback_query(F.data == "enter_new_data")
async def enter_new_data(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_delete_message(callback.message)
    await callback.message.answer("🏠 Введите АДРЕС ДОСТАВКИ (не сохранится в профиль):")
    await state.set_state(OrderState.waiting_for_address_temp)


@dp.message(OrderState.waiting_for_address_temp)
async def get_address_temp(message: types.Message, state: FSMContext):
    if len(message.text) < 5:
        await message.answer("❌ Введите корректный адрес (минимум 5 символов)")
        return

    await delete_user_message(message)
    await state.update_data(delivery_address=message.text)

    data = await state.get_data()
    last_bot_msg_id = data.get('last_bot_message')
    if last_bot_msg_id:
        await delete_bot_message(message.from_user.id, last_bot_msg_id)

    await message.answer("📱 Введите НОМЕР ТЕЛЕФОНА (не сохранится в профиль):\n\nПример: +7 999 123-45-67")
    await state.set_state(OrderState.waiting_for_phone_temp)


@dp.message(OrderState.waiting_for_phone_temp)
async def get_phone_temp(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if len(phone) < 10:
        await message.answer("❌ Введите корректный номер телефона")
        return

    await delete_user_message(message)
    await state.update_data(phone=phone)

    data = await state.get_data()
    last_bot_msg_id = data.get('last_bot_message')
    if last_bot_msg_id:
        await delete_bot_message(message.from_user.id, last_bot_msg_id)

    if data.get('checkout'):
        # Оформляем корзину автоматически
        cart_items = data.get('cart_items')
        delivery_city = data.get("delivery_city", "spb")
        delivery_address = data.get("delivery_address")
        phone = data.get("phone")
        delivery_date = data.get("delivery_date")
        delivery_time = data.get("delivery_time")

        # Подсчитываем общую сумму
        total_price_all = sum(item[3] * item[4] for item in cart_items)

        # Создаём групповой заказ (ОДИН раз)
        group_order_id, order_number = create_group_order(
            message.from_user.id, total_price_all, delivery_city, delivery_address, phone, delivery_date, delivery_time
        )

        items_text = ""
        photos = []

        for item in cart_items:
            cart_id, product_id, name, price, qty, size, photo = item
            item_total = price * qty
            items_text += f"📦 {name} x{qty} (размер {size}) = {item_total}₽\n"
            if photo:
                photos.append(photo)
            # Добавляем товар в групповой заказ
            add_group_order_item(group_order_id, product_id, name, qty, size, price, photo)

        clear_cart(message.from_user.id)

        delivery_text = f"\n📍 Адрес: {delivery_address}\n📱 Телефон: {phone}"
        if delivery_date:
            delivery_text += f"\n📅 Дата: {delivery_date}\n🕐 Время: {delivery_time}"

        payment_text = config.PAYMENT_DETAILS.format(price=total_price_all)
        payment_text += f"\n\n🧾 ЗАКАЗ №{order_number}\n"
        payment_text += f"📦 Товары:\n{items_text}\n"
        payment_text += f"💰 ИТОГО: {total_price_all} руб.{delivery_text}"

        # Отправляем ВСЕ ФОТО В ОДНОМ СООБЩЕНИИ (галерея)
        if photos:
            try:
                from aiogram.types import InputMediaPhoto
                media_group = []
                for i, photo in enumerate(photos):
                    if i == 0:
                        media_group.append(InputMediaPhoto(media=photo, caption=payment_text))
                    else:
                        media_group.append(InputMediaPhoto(media=photo))
                await message.answer_media_group(media=media_group)
                # Отправляем кнопки отдельным сообщением
                await message.answer("👇", reply_markup=payment_keyboard(group_order_id))
            except Exception as e:
                print(f"Ошибка отправки галереи: {e}")
                await message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))
        else:
            await message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))

        await state.clear()
    else:
        await message.answer(f"💰 Цена: {data['price']} руб.\n\nВведите КОЛИЧЕСТВО (1-5):")
        await state.set_state(OrderState.waiting_for_quantity)

@dp.message(OrderState.waiting_for_address)
async def get_address(message: types.Message, state: FSMContext):
    if len(message.text) < 5:
        await message.answer("❌ Введите корректный адрес (минимум 5 символов)")
        return

    await delete_user_message(message)
    address = message.text
    await state.update_data(delivery_address=address)

    profile = get_user_profile(message.from_user.id)
    if not profile or not profile[4]:
        update_user_profile(message.from_user.id, address=address)
        await message.answer("✅ Адрес сохранён в профиль!")

    data = await state.get_data()
    last_bot_msg_id = data.get('last_bot_message')
    if last_bot_msg_id:
        await delete_bot_message(message.from_user.id, last_bot_msg_id)

    await message.answer("📱 Введите НОМЕР ТЕЛЕФОНА:\n\nПример: +7 999 123-45-67")
    await state.set_state(OrderState.waiting_for_phone)


@dp.message(OrderState.waiting_for_phone)
async def get_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if len(phone) < 10:
        await message.answer("❌ Введите корректный номер телефона")
        return

    await delete_user_message(message)
    await state.update_data(phone=phone)

    profile = get_user_profile(message.from_user.id)
    if not profile or not profile[3]:
        update_user_profile(message.from_user.id, phone=phone)
        await message.answer("✅ Телефон сохранён в профиль!")

    data = await state.get_data()
    last_bot_msg_id = data.get('last_bot_message')
    if last_bot_msg_id:
        await delete_bot_message(message.from_user.id, last_bot_msg_id)

    if data.get('checkout'):
        # Оформляем корзину автоматически
        cart_items = data.get('cart_items')
        delivery_city = data.get("delivery_city", "spb")
        delivery_address = data.get("delivery_address")
        phone = data.get("phone")
        delivery_date = data.get("delivery_date")
        delivery_time = data.get("delivery_time")

        # Подсчитываем общую сумму
        total_price_all = sum(item[3] * item[4] for item in cart_items)

        # Создаём групповой заказ (ОДИН раз)
        group_order_id, order_number = create_group_order(
            message.from_user.id, total_price_all, delivery_city, delivery_address, phone, delivery_date, delivery_time
        )

        items_text = ""
        photos = []

        for item in cart_items:
            cart_id, product_id, name, price, qty, size, photo = item
            item_total = price * qty
            items_text += f"📦 {name} x{qty} (размер {size}) = {item_total}₽\n"
            if photo:
                photos.append(photo)
            # Добавляем товар в групповой заказ
            add_group_order_item(group_order_id, product_id, name, qty, size, price, photo)

        clear_cart(message.from_user.id)

        delivery_text = f"\n📍 Адрес: {delivery_address}\n📱 Телефон: {phone}"
        if delivery_date:
            delivery_text += f"\n📅 Дата: {delivery_date}\n🕐 Время: {delivery_time}"

        payment_text = config.PAYMENT_DETAILS.format(price=total_price_all)
        payment_text += f"\n\n🧾 ЗАКАЗ №{order_number}\n"
        payment_text += f"📦 Товары:\n{items_text}\n"
        payment_text += f"💰 ИТОГО: {total_price_all} руб.{delivery_text}"

        if photos:
            try:
                await message.answer_photo(photo=photos[0], caption=payment_text, reply_markup=payment_keyboard(group_order_id))
                for photo in photos[1:]:
                    await message.answer_photo(photo=photo)
            except:
                await message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))
        else:
            await message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))

        await state.clear()
    else:
        await message.answer(f"💰 Цена: {data['price']} руб.\n\nВведите КОЛИЧЕСТВО (1-5):")
        await state.set_state(OrderState.waiting_for_quantity)

# bot.py - ЧАСТЬ 6 (process_quantity и оплата)

# ========== ОФОРМЛЕНИЕ ЗАКАЗА ==========
@dp.message(OrderState.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text.strip())
        if quantity < 1:
            raise ValueError
    except:
        await message.answer("❌ Введите число больше 0")
        return

    await delete_user_message(message)

    data = await state.get_data()
    last_bot_msg_id = data.get('last_bot_message')
    if last_bot_msg_id:
        await delete_bot_message(message.from_user.id, last_bot_msg_id)

    if data.get('order_created'):
        await message.answer("❌ Заказ уже создан!")
        await state.clear()
        return

    await state.update_data(order_created=True)
    user_id = message.from_user.id

    # ========== ОФОРМЛЕНИЕ КОРЗИНЫ (НЕСКОЛЬКО ТОВАРОВ) ==========
    if data.get('checkout'):
        cart_items = data.get('cart_items')
        delivery_city = data.get("delivery_city", "spb")
        delivery_address = data.get("delivery_address")
        phone = data.get("phone")
        delivery_date = data.get("delivery_date")
        delivery_time = data.get("delivery_time")

        # Подсчитываем общую сумму
        total_price_all = sum(item[3] * item[4] for item in cart_items)

        # Создаём групповой заказ
        group_order_id, order_number = create_group_order(
            user_id, total_price_all, delivery_city, delivery_address, phone, delivery_date, delivery_time
        )

        items_text = ""
        photos = []

        for item in cart_items:
            cart_id, product_id, name, price, qty, size, photo = item
            item_total = price * qty
            items_text += f"📦 {name} x{qty} (размер {size}) = {item_total}₽\n"
            if photo:
                photos.append(photo)
            # Добавляем товар в групповой заказ
            add_group_order_item(group_order_id, product_id, name, qty, size, price, photo)

        clear_cart(user_id)

        delivery_text = f"\n📍 Адрес: {delivery_address}\n📱 Телефон: {phone}"
        if delivery_date:
            delivery_text += f"\n📅 Дата: {delivery_date}\n🕐 Время: {delivery_time}"

        payment_text = config.PAYMENT_DETAILS.format(price=total_price_all)
        payment_text += f"\n\n🧾 ЗАКАЗ №{order_number}\n"
        payment_text += f"📦 Товары:\n{items_text}\n"
        payment_text += f"💰 ИТОГО: {total_price_all} руб.{delivery_text}"

        # Отправляем ВСЕ ФОТО В ОДНОМ СООБЩЕНИИ (галерея)
        if photos:
            try:
                from aiogram.types import InputMediaPhoto
                media_group = []
                for i, photo in enumerate(photos):
                    if i == 0:
                        media_group.append(InputMediaPhoto(media=photo, caption=payment_text))
                    else:
                        media_group.append(InputMediaPhoto(media=photo))
                await message.answer_media_group(media=media_group)
                # Отправляем кнопки отдельным сообщением
                await message.answer("👇", reply_markup=payment_keyboard(group_order_id))
            except Exception as e:
                print(f"Ошибка отправки галереи: {e}")
                await message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))
        else:
            await message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))

        await state.clear()
        return

    # ========== ОФОРМЛЕНИЕ ОДНОГО ТОВАРА (НЕ ИЗ КОРЗИНЫ) ==========
    product_id = data["product_id"]
    price_per_unit = data["price"]
    total_price = price_per_unit * quantity
    delivery_city = data.get("delivery_city", "spb")
    delivery_address = data.get("delivery_address")
    phone = data.get("phone")
    size = data.get("size", "не указан")
    delivery_date = data.get("delivery_date")
    delivery_time = data.get("delivery_time")

    product = get_product(product_id)

    # Создаём групповой заказ (для одного товара)
    group_order_id, order_number = create_group_order(
        user_id, total_price, delivery_city, delivery_address, phone, delivery_date, delivery_time
    )

    # Добавляем товар в групповой заказ
    add_group_order_item(group_order_id, product_id, product[1], quantity, size, total_price, product[4])

    delivery_text = f"\n📍 Адрес: {delivery_address}\n📱 Телефон: {phone}"
    if delivery_date:
        delivery_text += f"\n📅 Дата: {delivery_date}\n🕐 Время: {delivery_time}"

    payment_text = config.PAYMENT_DETAILS.format(price=total_price)
    payment_text += f"\n\n🧾 ЗАКАЗ №{order_number}\n"
    payment_text += f"📦 {product[1]}\n"
    payment_text += f"📏 Размер: {size}\n"
    payment_text += f"🔢 {quantity} шт\n"
    payment_text += f"💰 {total_price} руб.{delivery_text}"

    # Для одного товара - отправляем одно фото с текстом
    if product[4]:
        try:
            await message.answer_photo(photo=product[4], caption=payment_text, reply_markup=payment_keyboard(group_order_id))
        except:
            await message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))
    else:
        await message.answer(payment_text, reply_markup=payment_keyboard(group_order_id))

    await state.clear()
# ========== ОПЛАТА ==========
@dp.callback_query(F.data.startswith("paid_"))
async def confirm_payment(callback: types.CallbackQuery):
    group_order_id = int(callback.data.split("_")[1])

    # Получаем групповой заказ
    order, items = get_group_order(group_order_id)

    if not order:
        await callback.answer("❌ Заказ не найден!", show_alert=True)
        return

    if order[9] != "pending":
        await callback.answer(f"❌ Заказ уже {order[9]}!", show_alert=True)
        return

    # Обновляем статус
    update_group_order_status(group_order_id, "paid")
    await callback.answer("✅ Спасибо! Заказ оплачен.")

    await safe_delete_message(callback.message)

    # Формируем сообщение для админа
    items_text = ""
    photos = []
    for item in items:
        product_id, product_name, qty, size, price, photo = item
        items_text += f"📦 {product_name} x{qty} (размер {size}) = {price * qty}₽\n"
        if photo:
            photos.append(photo)

    delivery_text = f"📍 Адрес: {order[5]}\n📱 Телефон: {order[6]}"
    if order[7]:
        delivery_text += f"\n📅 Дата: {order[7]}\n🕐 Время: {order[8]}"

    admin_text = (f"🔔 НОВЫЙ ОПЛАЧЕННЫЙ ЗАКАЗ!\n\n"
                  f"🧾 №{order[2]}\n"
                  f"👤 @{callback.from_user.username or callback.from_user.id}\n"
                  f"📦 Товары:\n{items_text}\n"
                  f"💰 ИТОГО: {order[3]} руб.\n"
                  f"{delivery_text}")

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ ОПЛАТУ", callback_data=f"confirm_group_payment_{group_order_id}")],
        [InlineKeyboardButton(text="💬 НАПИСАТЬ ПОКУПАТЕЛЮ", callback_data=f"msg_user_{order[1]}")]
    ])

    # Отправляем админу - ВСЕ ФОТО В ОДНОМ СООБЩЕНИИ
    for admin_id in config.ADMIN_IDS:
        try:
            if photos:
                # Отправляем одно сообщение со всеми фото
                media_group = []
                for i, photo in enumerate(photos):
                    if i == 0:
                        # Первое фото с подписью
                        media_group.append(types.InputMediaPhoto(media=photo, caption=admin_text))
                    else:
                        # Остальные фото без подписи
                        media_group.append(types.InputMediaPhoto(media=photo))

                # Отправляем группу фото (все в одном сообщении)
                await bot.send_media_group(admin_id, media=media_group)
                # Отправляем кнопки отдельным сообщением
                await bot.send_message(admin_id, "👇 Действия с заказом:", reply_markup=admin_keyboard)
            else:
                await bot.send_message(admin_id, admin_text, reply_markup=admin_keyboard)
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")

    await callback.message.answer(f"✅ ЗАКАЗ №{order[2]} ОПЛАЧЕН!\n\nСтатус: ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ")

@dp.callback_query(F.data == "cancel_buy")
async def cancel_buy(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Покупка отменена")
    await safe_delete_message(callback.message)
    await cmd_start(callback.message)
# bot.py - ЧАСТЬ 7 (Профиль и другие)
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)

    user_id = callback.from_user.id

    # Создаём новое сообщение
    await callback.message.answer(
        "🏠 Возвращаемся в главное меню..."
    )

    # Запускаем команду start для пользователя
    fake_message = types.Message(
        message_id=callback.message.message_id,
        chat=callback.message.chat,
        from_user=callback.from_user,
        date=callback.message.date,
        text="/start"
    )
    await cmd_start(fake_message)
# ========== ПРОФИЛЬ ==========
async def show_profile(message, user_id):
    if user_id in last_bot_messages:
        try:
            await bot.delete_message(user_id, last_bot_messages[user_id])
        except:
            pass

    profile = get_user_profile(user_id)
    messages = get_user_messages(user_id)
    orders = get_user_orders(user_id)

    if profile:
        uid, username, first_name, last_name, phone, address = profile
        first_name = first_name if first_name else (username if username else str(uid))
        display_name = f"@{username}" if username else str(uid)
    else:
        first_name = "Пользователь"
        display_name = str(user_id)
        phone = "не указан"
        address = "не указан"

    text = f"""👤 ПРОФИЛЬ

👤 Имя: {first_name}
🔖 Тег: {display_name}
📱 Телефон: {phone or 'не указан'}
📍 Адрес: {address or 'не указан'}

━━━━━━━━━━━━━━━━━━━━━━━
📦 ЗАКАЗОВ: {len(orders)}
💬 СООБЩЕНИЙ: {len(messages)}
━━━━━━━━━━━━━━━━━━━━━━━"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать профиль", callback_data="edit_profile")],
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders_from_profile")],
        [InlineKeyboardButton(text="💬 Сообщения от администратора", callback_data="admin_messages")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

    sent_msg = await message.answer(text, reply_markup=keyboard)
    last_bot_messages[user_id] = sent_msg.message_id


@dp.message(lambda message: message.text == "👤 ПРОФИЛЬ")
async def profile_menu(message: types.Message):
    if not await check_maintenance(message):
        return
    await log_user_action(message.from_user, "👤 ОТКРЫЛ ПРОФИЛЬ")
    user_id = message.from_user.id
    await delete_user_message(message)
    await show_profile(message, user_id)


# ========== РЕДАКТИРОВАНИЕ ПРОФИЛЯ ==========
@dp.callback_query(F.data == "edit_profile")
async def edit_profile_menu(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    await safe_delete_message(callback.message)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Изменить телефон", callback_data="profile_edit_phone")],
        [InlineKeyboardButton(text="📍 Изменить адрес", callback_data="profile_edit_address")],
        [InlineKeyboardButton(text="« Назад в профиль", callback_data="back_to_profile")]
    ])

    sent_msg = await callback.message.answer("✏️ ЧТО ХОТИТЕ ИЗМЕНИТЬ?", reply_markup=keyboard)
    last_bot_messages[user_id] = sent_msg.message_id


@dp.callback_query(F.data == "profile_edit_phone")
async def edit_phone_permanent(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    await safe_delete_message(callback.message)
    sent_msg = await callback.message.answer("📱 Введите НОВЫЙ НОМЕР ТЕЛЕФОНА:\n\nПример: +7 999 123-45-67")
    last_bot_messages[user_id] = sent_msg.message_id
    await state.set_state(ProfileState.waiting_for_new_phone)


@dp.message(ProfileState.waiting_for_new_phone)
async def save_new_phone_permanent(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if len(phone) < 10:
        await message.answer("❌ Введите корректный номер телефона")
        return

    try:
        await message.delete()
    except:
        pass

    update_user_profile(message.from_user.id, phone=phone)
    await message.answer(f"✅ Телефон обновлен в профиле: {phone}")
    await state.clear()
    await show_profile(message, message.from_user.id)


@dp.callback_query(F.data == "profile_edit_address")
async def edit_address_permanent(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    await safe_delete_message(callback.message)
    sent_msg = await callback.message.answer("📍 Введите НОВЫЙ АДРЕС ДОСТАВКИ:")
    last_bot_messages[user_id] = sent_msg.message_id
    await state.set_state(ProfileState.waiting_for_new_address)


@dp.message(ProfileState.waiting_for_new_address)
async def save_new_address_permanent(message: types.Message, state: FSMContext):
    address = message.text.strip()
    if len(address) < 5:
        await message.answer("❌ Введите корректный адрес")
        return

    try:
        await message.delete()
    except:
        pass

    update_user_profile(message.from_user.id, address=address)
    await message.answer(f"✅ Адрес обновлен в профиле: {address}")
    await state.clear()
    await show_profile(message, message.from_user.id)


@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer()
    await safe_delete_message(callback.message)
    await show_profile(callback.message, user_id)


# ========== МОИ ЗАКАЗЫ ==========
@dp.callback_query(F.data == "my_orders_from_profile")
async def my_orders_from_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer()

    try:
        await callback.message.delete()
    except:
        pass

    orders = get_user_orders(user_id)

    if not orders:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ Перейти в каталог", callback_data="back_to_menu")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
        await callback.message.answer("📭 У вас пока нет заказов\n\nПерейдите в Каталог, чтобы сделать первый заказ!", reply_markup=keyboard)
        return

    user_pages[user_id] = {'orders': orders, 'page': 0}
    await show_order_page_with_return(callback.message, user_id, 0)


@dp.message(lambda message: message.text == "📦 Мои заказы")
async def my_orders(message: types.Message):
    if not await check_maintenance(message):
        return
    await log_user_action(message.from_user, "📦 ПРОСМОТР ЗАКАЗОВ")
    user_id = message.from_user.id

    await delete_user_message(message)
    await delete_previous_bot_message(user_id)

    orders = get_user_orders(user_id)

    if not orders:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ Перейти в каталог", callback_data="back_to_menu")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
        sent_msg = await message.answer("📭 У вас пока нет заказов\n\nПерейдите в Каталог, чтобы сделать первый заказ!", reply_markup=keyboard)
        last_bot_messages[user_id] = sent_msg.message_id
        return

    user_pages[user_id] = {'orders': orders, 'page': 0}
    sent_msg = await show_order_page_with_return(message, user_id, 0)
    if sent_msg:
        last_bot_messages[user_id] = sent_msg.message_id


async def show_order_page_with_return(message, user_id, page):
    data = user_pages.get(user_id)
    if not data:
        return None

    orders = data['orders']
    total_orders = len(orders)
    orders_per_page = 1

    start_idx = page * orders_per_page
    end_idx = min(start_idx + orders_per_page, total_orders)

    if start_idx >= total_orders and total_orders > 0:
        page = total_orders - 1
        start_idx = page * orders_per_page
        end_idx = min(start_idx + orders_per_page, total_orders)
        user_pages[user_id]['page'] = page

    status_display = {
        "pending": ("⏳ НЕ ОПЛАЧЕНО", "Заказ создан, ожидает оплаты."),
        "paid": ("✅ ОПЛАЧЕНО, ЖДЁТ ПОДТВЕРЖДЕНИЯ", "Заказ оплачен! Администратор проверит оплату."),
        "shipped": ("🚚 В ПУТИ", "Заказ отправлен! Ожидайте доставку."),
        "delivered": ("📦 ДОСТАВЛЕНО", "Заказ доставлен! Спасибо за покупку!"),
        "cancelled": ("❌ ОТМЕНЕН", "Заказ отменен.")
    }

    text = f"📋 ВАШИ ЗАКАЗЫ (страница {page + 1} из {(total_orders + orders_per_page - 1) // orders_per_page})\n\n"
    current_photo = None

    for i in range(start_idx, end_idx):
        order = orders[i]
        order_id, name, quantity, price, status, date, size, address, phone, photo, delivery_date, delivery_time = order
        current_photo = photo
        status_text, status_desc = status_display.get(status, ("НЕИЗВЕСТНО", ""))

        text += f"🧾 ЗАКАЗ #{order_id}\n📦 {name}\n📏 Размер: {size}\n🔢 {quantity} шт = {price}₽\n📍 Адрес: {address}\n📱 Телефон: {phone}\n"
        if delivery_date:
            text += f"📅 Доставка: {delivery_date} {delivery_time or ''}\n"
        text += f"📅 Дата заказа: {date[:10]}\n━━━━━━━━━━━━━━━\n📊 СТАТУС: {status_text}\n💬 {status_desc}\n"

    builder = InlineKeyboardBuilder()

    if page > 0:
        builder.button(text="◀️ Назад", callback_data=f"orders_page_{page - 1}")
    if end_idx < total_orders:
        builder.button(text="Вперед ▶️", callback_data=f"orders_page_{page + 1}")

    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(2)

    if current_photo:
        try:
            return await message.answer_photo(photo=current_photo, caption=text, reply_markup=builder.as_markup())
        except:
            return await message.answer(text, reply_markup=builder.as_markup())
    else:
        return await message.answer(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("orders_page_"))
async def orders_page_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    page = int(callback.data.split("_")[2])
    await callback.answer()
    await safe_delete_message(callback.message)

    if user_id in user_pages:
        user_pages[user_id]['page'] = page
    else:
        orders = get_user_orders(user_id)
        if orders:
            user_pages[user_id] = {'orders': orders, 'page': page}

    await show_order_page_with_return(callback.message, user_id, page)


# ========== СООБЩЕНИЯ ОТ АДМИНА ==========
@dp.callback_query(F.data == "admin_messages")
async def admin_messages_list(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    messages = get_user_messages(user_id)

    await callback.answer()
    await safe_delete_message(callback.message)

    if not messages:
        text = "💬 СООБЩЕНИЯ ОТ АДМИНИСТРАТОРА\n\n📭 У вас пока нет сообщений."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="« Назад в профиль", callback_data="back_to_profile_clean")]
        ])
        await callback.message.answer(text, reply_markup=keyboard)
        return

    text = "💬 СООБЩЕНИЯ ОТ АДМИНИСТРАТОРА:\n\n"
    for msg in messages[:10]:
        msg_id, msg_text, created_at, is_read = msg
        status = "✅" if is_read else "🆕"
        text += f"{status} {created_at[:19]}\n{msg_text}\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад в профиль", callback_data="back_to_profile_clean")]
    ])
    await callback.message.answer(text, reply_markup=keyboard)


# ========== ОТЗЫВЫ ==========
@dp.message(lambda message: message.text == "⭐ ОТЗЫВЫ")
async def show_reviews_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 СМОТРЕТЬ ОТЗЫВЫ", url=config.REVIEWS_LINK)],
        [InlineKeyboardButton(text="🏠 ГЛАВНОЕ МЕНЮ", callback_data="back_to_menu")]
    ])
    await message.answer("⭐ ОТЗЫВЫ О МАГАЗИНЕ\n\nНажмите на кнопку ниже, чтобы посмотреть отзывы:", reply_markup=keyboard)


# ========== ПОДДЕРЖКА ==========
@dp.message(lambda message: message.text == "🆘 ПОДДЕРЖКА")
async def support(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 НАПИСАТЬ В ПОДДЕРЖКУ", url=f"https://t.me/{config.SUPPORT_USERNAME}")],
        [InlineKeyboardButton(text="🏠 ГЛАВНОЕ МЕНЮ", callback_data="back_to_menu")]
    ])
    text = "🆘 СЛУЖБА ПОДДЕРЖКИ\n\nНажмите на кнопку ниже, чтобы связаться с нами.\n\n📌 Ответ в течение 5-10 минут!"
    await message.answer(text, reply_markup=keyboard)


# ========== О МАГАЗИНЕ ==========
@dp.message(lambda message: message.text == "ℹ️ О МАГАЗИНЕ")
async def about_shop(message: types.Message):
    text = """👕 О МАГАЗИНЕ

✅ Качественная одежда от проверенных поставщиков
✅ Быстрая доставка по России
✅ Примерка перед покупкой
✅ Возврат в течение 14 дней

Мы работаем для вас! ❤️"""
    await message.answer(text)
# bot.py - ЧАСТЬ 8 (Админ-панель и остальное)
# Добавьте эти функции перед "# ========== АДМИН-ПАНЕЛЬ =========="

# ========== КЛАВИАТУРЫ (недостающие) ==========
def admin_panel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🖼️ Оформление главного меню", callback_data="admin_menu_settings")
    builder.button(text="➕ Добавить коллекцию", callback_data="admin_add_collection")
    builder.button(text="📁 Управление коллекциями", callback_data="admin_manage_collections")
    builder.button(text="🛍️ Добавить товар", callback_data="admin_add_product")
    builder.button(text="✏️ Редактировать товары", callback_data="admin_manage_products")
    builder.button(text="💰 Заказы на подтверждение", callback_data="admin_pending_orders")
    builder.button(text="📦 Заказы на отправку", callback_data="admin_orders")
    builder.button(text="🚚 Отправленные заказы", callback_data="admin_shipped_orders")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="🔗 Статистика переходов", callback_data="admin_link_stats")
    builder.button(text="📥 Импорт/Экспорт товаров", callback_data="admin_import_export")
    builder.button(text="💾 Резервное копирование", callback_data="admin_backup_menu")
    builder.button(text="🛠️ Технические работы", callback_data="admin_maintenance")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def collections_keyboard():
    collections = get_collections()
    builder = InlineKeyboardBuilder()
    for col in collections:
        builder.button(text=f"📁 {col[1]}", callback_data=f"collection_{col[0]}")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def size_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="S", callback_data="size_S"),
         InlineKeyboardButton(text="M", callback_data="size_M"),
         InlineKeyboardButton(text="L", callback_data="size_L")],
        [InlineKeyboardButton(text="XL", callback_data="size_XL"),
         InlineKeyboardButton(text="XXL", callback_data="size_XXL")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])


def city_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Санкт-Петербург", callback_data="city_spb")],
        [InlineKeyboardButton(text="🌍 Другой город", callback_data="city_other")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])


def payment_keyboard(group_order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{group_order_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_group_order_{group_order_id}"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])
# ========== АДМИН-ПАНЕЛЬ ==========
@dp.message(lambda message: message.text == "👑 АДМИН-ПАНЕЛЬ")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    user_id = message.from_user.id
    await delete_user_message(message)
    await delete_previous_bot_message(user_id)

    sent_msg = await message.answer("👑 АДМИН-ПАНЕЛЬ\n\nВыберите действие:", reply_markup=admin_panel_keyboard())
    last_bot_messages[user_id] = sent_msg.message_id


@dp.callback_query(F.data == "admin_panel")
async def back_to_admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    await callback.answer()
    try:
        await callback.message.edit_text("👑 АДМИН-ПАНЕЛЬ\n\nВыберите действие:", reply_markup=admin_panel_keyboard())
    except:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer("👑 АДМИН-ПАНЕЛЬ\n\nВыберите действие:", reply_markup=admin_panel_keyboard())


# ========== СТАТИСТИКА ==========
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM group_orders")
    orders = cur.fetchone()[0]

    cur.execute("SELECT SUM(total_price) FROM group_orders WHERE status IN ('paid', 'shipped', 'delivered')")
    revenue = cur.fetchone()[0] or 0

    cur.execute("SELECT status, COUNT(*) FROM group_orders GROUP BY status")
    status_counts = cur.fetchall()
    conn.close()

    status_names = {
        "pending": "⏳ Ожидают оплаты",
        "paid": "✅ Оплачены (ждут отправки)",
        "shipped": "🚚 Отправлены",
        "delivered": "📦 Доставлены",
        "cancelled": "❌ Отменены"
    }

    text = f"📊 СТАТИСТИКА БОТА\n\n👥 Пользователей: {users}\n📦 Заказов: {orders}\n💰 Выручка: {revenue} руб.\n\n📋 ПО СТАТУСАМ:\n"
    for status, count in status_counts:
        name = status_names.get(status, status)
        text += f"  {name}: {count}\n"

    await callback.answer()
    await callback.message.answer(text)


# ========== СТАТИСТИКА ПЕРЕХОДОВ ==========
@dp.callback_query(F.data == "admin_link_stats")
async def admin_link_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    stats = get_link_stats()

    text = f"🔗 СТАТИСТИКА ПЕРЕХОДОВ\n\n📌 Всего переходов: {stats['total']}\n👥 Уникальных: {stats['unique']}\n📅 Сегодня: {stats['today']}\n📆 За неделю: {stats['week']}\n\n🕐 ПОСЛЕДНИЕ 10 ПЕРЕХОДОВ:\n"

    for i, (username, date) in enumerate(stats['recent'], 1):
        text += f"{i}. @{username or 'anon'} - {date[:19]}\n"

    if not stats['recent']:
        text += "Нет переходов"

    await callback.answer()
    await callback.message.answer(text)


# ========== ЗАКАЗЫ НА ПОДТВЕРЖДЕНИЕ ==========
@dp.callback_query(F.data == "admin_pending_orders")
async def admin_pending_orders(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT go.id, go.user_id, u.username, go.order_number, go.total_price, 
               go.delivery_city, go.delivery_address, go.phone, go.created_at, 
               go.delivery_date, go.delivery_time
        FROM group_orders go
        JOIN users u ON go.user_id = u.user_id
        WHERE go.status = 'paid'
        ORDER BY go.created_at ASC
    """)
    orders = cur.fetchall()
    conn.close()

    if not orders:
        await callback.answer("Нет заказов, ожидающих подтверждения", show_alert=True)
        return

    await show_admin_orders_with_pagination(callback, orders, 0, "pending", "ОПЛАЧЕН, ЖДЁТ ПОДТВЕРЖДЕНИЯ")

@dp.callback_query(F.data.startswith("confirm_payment_group_"))
async def confirm_payment_group(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    order_id = int(callback.data.split("_")[-1])
    order, items = get_group_order(order_id)

    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if order[9] != "paid":
        await callback.answer("Заказ не в статусе 'оплачен'", show_alert=True)
        return

    await callback.answer("✅ Оплата подтверждена!")

    # Получаем фото
    photos = []
    items_text = ""
    for item in items:
        product_id, product_name, qty, size, price, photo = item
        items_text += f"📦 {product_name} x{qty} (размер {size}) = {price * qty}₽\n"
        if photo:
            photos.append(photo)

    text = (f"✅ ЗАКАЗ №{order[2]} - ОПЛАТА ПОДТВЕРЖДЕНА!\n\n"
            f"📦 ТОВАРЫ:\n{items_text}\n"
            f"📍 Адрес: {order[5]}\n"
            f"📱 Телефон: {order[6]}\n\n"
            f"Заказ передан в обработку.")

    try:
        await callback.message.delete()
    except:
        pass

    if photos:
        try:
            from aiogram.types import InputMediaPhoto
            media_group = []
            for i, photo in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo, caption=text))
                else:
                    media_group.append(InputMediaPhoto(media=photo))
            await callback.message.answer_media_group(media=media_group)
        except:
            await callback.message.answer(text)
    else:
        await callback.message.answer(text)

    # Уведомляем покупателя
    buyer_text = (f"✅ ВАШ ЗАКАЗ №{order[2]} ПОДТВЕРЖДЁН!\n\n"
                  f"Скоро заказ будет передан в службу доставки.\n"
                  f"Вы можете отслеживать статус в разделе «Мои заказы».")

    await bot.send_message(
        order[1],
        buyer_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders_from_profile")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
    )
# ========== ЗАКАЗЫ НА ОТПРАВКУ ==========
@dp.callback_query(F.data == "admin_orders")
async def admin_orders(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT go.id, go.user_id, u.username, go.order_number, go.total_price, 
               go.delivery_city, go.delivery_address, go.phone, go.created_at, 
               go.delivery_date, go.delivery_time
        FROM group_orders go
        JOIN users u ON go.user_id = u.user_id
        WHERE go.status = 'paid'
        ORDER BY go.created_at ASC
    """)
    orders = cur.fetchall()
    conn.close()

    if not orders:
        await callback.answer("Нет заказов, ожидающих отправки", show_alert=True)
        return

    await show_admin_orders_with_pagination(callback, orders, 0, "shipping", "ОПЛАЧЕН, ЖДЁТ ОТПРАВКИ")
# ========== ОТПРАВЛЕННЫЕ ЗАКАЗЫ ==========
@dp.callback_query(F.data == "admin_shipped_orders")
async def admin_shipped_orders(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT go.id, go.user_id, u.username, go.order_number, go.total_price, 
               go.delivery_city, go.delivery_address, go.phone, go.created_at, 
               go.delivery_date, go.delivery_time
        FROM group_orders go
        JOIN users u ON go.user_id = u.user_id
        WHERE go.status = 'shipped'
        ORDER BY go.created_at ASC
    """)
    orders = cur.fetchall()
    conn.close()

    if not orders:
        await callback.answer("Нет отправленных заказов", show_alert=True)
        return

    await show_admin_orders_with_pagination(callback, orders, 0, "shipped", "В ПУТИ")


@dp.callback_query(F.data.startswith("admin_order_page_"))
async def admin_order_page_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    parts = callback.data.split("_")
    order_type = parts[3]
    page = int(parts[4])

    # Получаем заказы из соответствующей таблицы
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if order_type == "pending" or order_type == "shipping":
        cur.execute("""
            SELECT go.id, go.user_id, u.username, go.order_number, go.total_price, 
                   go.delivery_city, go.delivery_address, go.phone, go.created_at, 
                   go.delivery_date, go.delivery_time
            FROM group_orders go
            JOIN users u ON go.user_id = u.user_id
            WHERE go.status = 'paid'
            ORDER BY go.created_at ASC
        """)
    elif order_type == "shipped":
        cur.execute("""
            SELECT go.id, go.user_id, u.username, go.order_number, go.total_price, 
                   go.delivery_city, go.delivery_address, go.phone, go.created_at, 
                   go.delivery_date, go.delivery_time
            FROM group_orders go
            JOIN users u ON go.user_id = u.user_id
            WHERE go.status = 'shipped'
            ORDER BY go.created_at ASC
        """)
    else:
        return

    orders = cur.fetchall()
    conn.close()

    if not orders:
        await callback.answer("Заказы не найдены", show_alert=True)
        return

    title = "ОПЛАЧЕН, ЖДЁТ ПОДТВЕРЖДЕНИЯ" if order_type == "pending" else "ОПЛАЧЕН, ЖДЁТ ОТПРАВКИ" if order_type == "shipping" else "В ПУТИ"

    await show_admin_orders_with_pagination(callback, orders, page, order_type, title)

# ========== ПОДТВЕРЖДЕНИЕ ОТПРАВКИ ==========
@dp.callback_query(F.data.startswith("ship_group_"))
async def admin_confirm_shipment_group(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    order_id = int(callback.data.split("_")[-1])
    order, items = get_group_order(order_id)

    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if order[9] != "paid":
        await callback.answer("Невозможно отправить - заказ не оплачен", show_alert=True)
        return

    update_group_order_status(order_id, "shipped")
    await callback.answer("✅ Отправка подтверждена!")

    # Формируем сообщение с фото для админа
    items_text = ""
    photos = []
    for item in items:
        product_id, product_name, qty, size, price, photo = item
        items_text += f"📦 {product_name}\n📏 Размер: {size}\n🔢 {qty} шт = {price * qty}₽\n"
        if photo:
            photos.append(photo)

    delivery_text = f"📍 Адрес: {order[5]}\n📱 Телефон: {order[6]}"
    if order[7]:
        delivery_text += f"\n📅 Доставка: {order[7]} {order[8] or ''}"

    admin_text = (f"✅ ЗАКАЗ №{order[2]} ОТПРАВЛЕН!\n\n"
                  f"📦 ТОВАРЫ:\n{items_text}\n"
                  f"{delivery_text}\n\n"
                  f"👤 Покупатель: @{callback.from_user.username or callback.from_user.id}")

    # Отправляем админу галерею с фото
    try:
        await callback.message.delete()
    except:
        pass

    if photos:
        try:
            from aiogram.types import InputMediaPhoto
            media_group = []
            for i, photo in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo, caption=admin_text))
                else:
                    media_group.append(InputMediaPhoto(media=photo))
            await callback.message.answer_media_group(media=media_group)
        except Exception as e:
            print(f"Ошибка отправки галереи: {e}")
            await callback.message.answer(admin_text)
    else:
        await callback.message.answer(admin_text)

    # Уведомляем покупателя
    buyer_id = order[1]
    buyer_text = (f"🚚 ВАШ ЗАКАЗ №{order[2]} ОТПРАВЛЕН!\n\n"
                  f"📦 ТОВАРЫ:\n{items_text}\n"
                  f"{delivery_text}\n\n"
                  f"Ожидайте доставку!")

    buyer_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders_from_profile")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

    try:
        if photos:
            from aiogram.types import InputMediaPhoto
            media_group = []
            for i, photo in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo, caption=buyer_text))
                else:
                    media_group.append(InputMediaPhoto(media=photo))
            await bot.send_media_group(buyer_id, media=media_group)
            await bot.send_message(buyer_id, "👇", reply_markup=buyer_keyboard)
        else:
            await bot.send_message(buyer_id, buyer_text, reply_markup=buyer_keyboard)
    except Exception as e:
        print(f"Ошибка отправки покупателю: {e}")
        await bot.send_message(buyer_id, buyer_text, reply_markup=buyer_keyboard)
# ========== ОТМЕТКА ДОСТАВКИ ==========
@dp.callback_query(F.data.startswith("deliver_group_"))
async def mark_as_delivered_group(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    order_id = int(callback.data.split("_")[-1])
    order, items = get_group_order(order_id)

    if not order or order[9] != "shipped":
        await callback.answer("Невозможно отметить доставку", show_alert=True)
        return

    update_group_order_status(order_id, "delivered")
    await callback.answer("✅ Заказ отмечен как доставленный!")

    # Формируем сообщение с фото для админа
    items_text = ""
    photos = []
    for item in items:
        product_id, product_name, qty, size, price, photo = item
        items_text += f"📦 {product_name}\n📏 Размер: {size}\n🔢 {qty} шт = {price * qty}₽\n"
        if photo:
            photos.append(photo)

    delivery_text = f"📍 Адрес: {order[5]}\n📱 Телефон: {order[6]}"
    if order[7]:
        delivery_text += f"\n📅 Доставка: {order[7]} {order[8] or ''}"

    admin_text = (f"📦 ЗАКАЗ №{order[2]} ДОСТАВЛЕН!\n\n"
                  f"📦 ТОВАРЫ:\n{items_text}\n"
                  f"{delivery_text}\n\n"
                  f"👤 Покупатель: @{callback.from_user.username or callback.from_user.id}")

    try:
        await callback.message.delete()
    except:
        pass

    if photos:
        try:
            from aiogram.types import InputMediaPhoto
            media_group = []
            for i, photo in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo, caption=admin_text))
                else:
                    media_group.append(InputMediaPhoto(media=photo))
            await callback.message.answer_media_group(media=media_group)
        except Exception as e:
            print(f"Ошибка отправки галереи: {e}")
            await callback.message.answer(admin_text)
    else:
        await callback.message.answer(admin_text)

    # Уведомляем покупателя с кнопкой отзыва
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ ОСТАВИТЬ ОТЗЫВ", url=config.REVIEWS_LINK)],
        [InlineKeyboardButton(text="🏠 ГЛАВНОЕ МЕНЮ", callback_data="back_to_menu")]
    ])

    buyer_text = (f"📦 ЗАКАЗ №{order[2]} ДОСТАВЛЕН!\n\n"
                  f"📦 ТОВАРЫ:\n{items_text}\n"
                  f"{delivery_text}\n\n"
                  f"Спасибо за покупку! ❤️")

    try:
        if photos:
            from aiogram.types import InputMediaPhoto
            media_group = []
            for i, photo in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo, caption=buyer_text))
                else:
                    media_group.append(InputMediaPhoto(media=photo))
            await bot.send_media_group(order[1], media=media_group)
            await bot.send_message(order[1], "👇", reply_markup=keyboard)
        else:
            await bot.send_message(order[1], buyer_text, reply_markup=keyboard)
    except Exception as e:
        print(f"Ошибка отправки покупателю: {e}")
        await bot.send_message(order[1], buyer_text, reply_markup=keyboard)
# ========== НАПИСАТЬ ПОКУПАТЕЛЮ ==========
@dp.callback_query(F.data.startswith("msg_user_"))
async def message_to_user_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])
    user = get_user(user_id)

    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await state.update_data(target_user_id=user_id, target_username=user[1])
    await callback.answer()
    await safe_delete_message(callback.message)

    await callback.message.answer(f"💬 НАПИСАТЬ ПОКУПАТЕЛЮ @{user[1]}\n\nВведите сообщение:")
    await state.set_state(AdminState.waiting_for_message_to_user)


@dp.message(AdminState.waiting_for_message_to_user)
async def send_message_to_user(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("target_user_id")
    username = data.get("target_username")

    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    await bot.send_message(user_id, f"📩 СООБЩЕНИЕ ОТ АДМИНИСТРАТОРА:\n\n{message.text}")
    add_admin_message(user_id, message.text)
    await message.answer(f"✅ Сообщение отправлено @{username} и сохранено в историю!")
    await state.clear()


# ========== ОФОРМЛЕНИЕ ГЛАВНОГО МЕНЮ ==========
@dp.callback_query(F.data == "admin_menu_settings")
async def admin_menu_settings(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    settings = get_menu_settings()

    builder = InlineKeyboardBuilder()
    builder.button(text="🖼️ Изменить фото", callback_data="menu_set_photo")
    builder.button(text="📝 Изменить текст", callback_data="menu_set_text")
    builder.button(text="🔗 Изменить ссылки", callback_data="menu_set_links")
    builder.button(text="« Назад", callback_data="admin_panel")
    builder.adjust(1)

    text = "🖼️ ОФОРМЛЕНИЕ ГЛАВНОГО МЕНЮ\n\n"
    if settings:
        photo_id, welcome_text, channel_link, chat_link, support_links = settings
        text += f"📝 Приветствие: {welcome_text[:50]}\n📢 Канал: {channel_link}\n💬 Чат: {chat_link}\n🆘 Поддержка: {support_links}\n📸 Фото: {'есть' if photo_id else 'нет'}"

    await callback.answer()
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data == "menu_set_photo")
async def menu_set_photo(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("📸 Отправьте ФОТО для главного меню\n(или /delete чтобы удалить)")
    await state.set_state(AdminState.waiting_for_menu_photo)


@dp.message(AdminState.waiting_for_menu_photo)
async def save_menu_photo(message: types.Message, state: FSMContext):
    if message.text and message.text.lower() == "/delete":
        update_menu_settings(photo_file_id=None)
        await message.answer("✅ Фото главного меню удалено!")
    elif message.photo:
        photo_id = message.photo[-1].file_id
        update_menu_settings(photo_file_id=photo_id)
        await message.answer("✅ Фото главного меню обновлено!")
    else:
        await message.answer("❌ Отправьте фото или /delete")
        return
    await state.clear()
    await cmd_start(message)


@dp.callback_query(F.data == "menu_set_text")
async def menu_set_text(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("📝 Введите новый ТЕКСТ ПРИВЕТСТВИЯ:")
    await state.set_state(AdminState.waiting_for_menu_text)


@dp.message(AdminState.waiting_for_menu_text)
async def save_menu_text(message: types.Message, state: FSMContext):
    update_menu_settings(welcome_text=message.text)
    await message.answer(f"✅ Текст обновлен: {message.text}")
    await state.clear()
    await cmd_start(message)


@dp.callback_query(F.data == "menu_set_links")
async def menu_set_links(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("🔗 Введите ссылки в формате:\n\nКанал: @channel\nЧат: @chat\nПоддержка: @support")
    await state.set_state(AdminState.waiting_for_menu_links)


@dp.message(AdminState.waiting_for_menu_links)
async def save_menu_links(message: types.Message, state: FSMContext):
    lines = message.text.split('\n')
    channel = '@канал'
    chat = '@чат'
    support = '@поддержка'

    for line in lines:
        if line.lower().startswith('канал:'):
            channel = line.split(':', 1)[1].strip()
        elif line.lower().startswith('чат:'):
            chat = line.split(':', 1)[1].strip()
        elif line.lower().startswith('поддержка:'):
            support = line.split(':', 1)[1].strip()

    update_menu_settings(channel_link=channel, chat_link=chat, support_links=support)
    await message.answer(f"✅ Ссылки обновлены!\n📢 {channel}\n💬 {chat}\n🆘 {support}")
    await state.clear()
    await cmd_start(message)

# bot.py - ЧАСТЬ 9 (Управление коллекциями и товарами)

# ========== ДОБАВЛЕНИЕ КОЛЛЕКЦИИ ==========
@dp.callback_query(F.data == "admin_add_collection")
async def admin_add_collection(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer("📝 Введите НАЗВАНИЕ коллекции:")
    await state.set_state(AdminState.waiting_for_collection_name)


@dp.message(AdminState.waiting_for_collection_name)
async def add_collection_name(message: types.Message, state: FSMContext):
    await state.update_data(col_name=message.text)
    await message.answer("📝 Введите ОПИСАНИЕ коллекции:")
    await state.set_state(AdminState.waiting_for_collection_desc)


@dp.message(AdminState.waiting_for_collection_desc)
async def add_collection_desc(message: types.Message, state: FSMContext):
    await state.update_data(col_desc=message.text)
    await message.answer("📸 Отправьте ФОТО для коллекции (или /skip):")
    await state.set_state(AdminState.waiting_for_collection_photo)


@dp.message(AdminState.waiting_for_collection_photo)
async def add_collection_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id if message.photo else None
    add_collection(data['col_name'], data['col_desc'], photo_id)
    await message.answer(f"✅ Коллекция «{data['col_name']}» добавлена!")
    await state.clear()
    await admin_panel(message)


# ========== УПРАВЛЕНИЕ КОЛЛЕКЦИЯМИ ==========
@dp.callback_query(F.data == "admin_manage_collections")
async def admin_manage_collections(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    collections = get_collections()
    if not collections:
        await callback.answer("Нет коллекций", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for col in collections:
        builder.button(text=f"✏️ {col[1]}", callback_data=f"edit_col_{col[0]}")
    builder.button(text="« Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.answer()
    await callback.message.edit_text("📁 УПРАВЛЕНИЕ КОЛЛЕКЦИЯМИ\n\nВыберите коллекцию:", reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("edit_col_"))
async def edit_collection_menu(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    col_id = int(callback.data.split("_")[-1])
    collection = get_collection(col_id)
    await state.update_data(edit_collection_id=col_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить название", callback_data=f"edit_col_name_{col_id}")
    builder.button(text="📝 Изменить описание", callback_data=f"edit_col_desc_{col_id}")
    builder.button(text="📸 Изменить фото", callback_data=f"edit_col_photo_{col_id}")
    builder.button(text="🗑️ Удалить коллекцию", callback_data=f"delete_col_{col_id}")
    builder.button(text="« Назад", callback_data="admin_manage_collections")
    builder.adjust(1)

    text = f"📁 {collection[1]}\n\n📝 {collection[2]}\n📸 Фото: {'есть' if collection[3] else 'нет'}"

    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except:
        pass


@dp.callback_query(F.data.startswith("edit_col_name_"))
async def edit_collection_name_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    col_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_collection_id=col_id)

    await callback.answer()
    await callback.message.answer("✏️ Введите НОВОЕ НАЗВАНИЕ коллекции:")
    await state.set_state(AdminState.waiting_for_edit_collection_name)


@dp.message(AdminState.waiting_for_edit_collection_name)
async def edit_collection_name_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    col_id = data.get('edit_collection_id')
    update_collection(col_id, name=message.text)
    await message.answer(f"✅ Название изменено на: {message.text}")
    await state.clear()
    await admin_panel(message)


@dp.callback_query(F.data.startswith("edit_col_desc_"))
async def edit_collection_desc_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    col_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_collection_id=col_id)

    await callback.answer()
    await callback.message.answer("📝 Введите НОВОЕ ОПИСАНИЕ коллекции:")
    await state.set_state(AdminState.waiting_for_edit_collection_desc)


@dp.message(AdminState.waiting_for_edit_collection_desc)
async def edit_collection_desc_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    col_id = data.get('edit_collection_id')
    update_collection(col_id, description=message.text)
    await message.answer("✅ Описание коллекции обновлено!")
    await state.clear()
    await admin_panel(message)


@dp.callback_query(F.data.startswith("edit_col_photo_"))
async def edit_collection_photo_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    col_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_collection_id=col_id)
    await callback.answer()
    await callback.message.answer("📸 Отправьте НОВОЕ ФОТО для коллекции\n(или /delete чтобы удалить)")
    await state.set_state(AdminState.waiting_for_edit_collection_photo)


@dp.message(AdminState.waiting_for_edit_collection_photo)
async def edit_collection_photo_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    col_id = data.get('edit_collection_id')

    if message.text and message.text.lower() == "/delete":
        update_collection(col_id, photo_file_id=None)
        await message.answer("✅ Фото коллекции удалено!")
    elif message.photo:
        photo_id = message.photo[-1].file_id
        update_collection(col_id, photo_file_id=photo_id)
        await message.answer("✅ Фото коллекции обновлено!")
    else:
        await message.answer("❌ Отправьте фото или /delete")
        return
    await state.clear()
    await admin_panel(message)


@dp.callback_query(F.data.startswith("delete_col_"))
async def delete_collection_confirm(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    col_id = int(callback.data.split("_")[-1])
    collection = get_collection(col_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"confirm_del_col_{col_id}")
    builder.button(text="❌ Нет", callback_data=f"edit_col_{col_id}")
    builder.adjust(1)

    await callback.answer()
    await callback.message.edit_text(f"⚠️ УДАЛИТЬ КОЛЛЕКЦИЮ «{collection[1]}»?\n\nВсе товары в ней тоже будут удалены!", reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("confirm_del_col_"))
async def delete_collection_execute(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    col_id = int(callback.data.split("_")[-1])
    delete_collection(col_id)
    await callback.answer("✅ Коллекция удалена!")
    await admin_manage_collections(callback)


# ========== ДОБАВЛЕНИЕ ТОВАРА ==========
@dp.callback_query(F.data == "admin_add_product")
async def admin_add_product(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    collections = get_collections()
    if not collections:
        await callback.answer("Сначала создайте коллекцию!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for col in collections:
        builder.button(text=col[1], callback_data=f"select_col_{col[0]}")
    builder.button(text="« Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.answer()
    await callback.message.edit_text("📁 ВЫБЕРИТЕ КОЛЛЕКЦИЮ для нового товара:", reply_markup=builder.as_markup())
    await state.set_state(AdminState.waiting_for_product_collection)


@dp.callback_query(AdminState.waiting_for_product_collection, F.data.startswith("select_col_"))
async def select_collection_for_product(callback: types.CallbackQuery, state: FSMContext):
    col_id = int(callback.data.split("_")[-1])
    await state.update_data(col_id=col_id)
    await callback.answer()
    await callback.message.answer("📝 Введите НАЗВАНИЕ товара:")
    await state.set_state(AdminState.waiting_for_product_name)


@dp.message(AdminState.waiting_for_product_name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(prod_name=message.text)
    await message.answer("📝 Введите ОПИСАНИЕ товара:")
    await state.set_state(AdminState.waiting_for_product_desc)


@dp.message(AdminState.waiting_for_product_desc)
async def add_product_desc(message: types.Message, state: FSMContext):
    await state.update_data(prod_desc=message.text)
    await message.answer("💰 Введите ЦЕНУ товара (в рублях):")
    await state.set_state(AdminState.waiting_for_product_price)


@dp.message(AdminState.waiting_for_product_price)
async def add_product_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(prod_price=price)
        await message.answer("📸 Отправьте ФОТО товара (или /skip):")
        await state.set_state(AdminState.waiting_for_product_photo)
    except:
        await message.answer("❌ Введите число!")


@dp.message(AdminState.waiting_for_product_photo)
async def add_product_photo_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id if message.photo else None
    add_product(data['col_id'], data['prod_name'], data['prod_desc'], data['prod_price'], photo_id)
    await message.answer(f"✅ Товар «{data['prod_name']}» добавлен!")
    await state.clear()
    await admin_panel(message)


# ========== РЕДАКТИРОВАНИЕ ТОВАРОВ ==========
@dp.callback_query(F.data == "admin_manage_products")
async def admin_manage_products(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    products = get_all_products()
    if not products:
        await callback.answer("Нет товаров", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for prod in products:
        short_name = prod[1][:25] + "..." if len(prod[1]) > 25 else prod[1]
        builder.button(text=f"✏️ {short_name} ({prod[5]})", callback_data=f"admin_edit_prod_{prod[0]}")
    builder.button(text="« Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.answer()
    await callback.message.edit_text("✏️ РЕДАКТИРОВАНИЕ ТОВАРОВ\n\nВыберите товар:", reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("admin_edit_prod_"))
async def edit_product_menu(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    prod_id = int(callback.data.split("_")[-1])
    product = get_product(prod_id)
    await state.update_data(edit_product_id=prod_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить название", callback_data=f"edit_prod_name_{prod_id}")
    builder.button(text="📝 Изменить описание", callback_data=f"edit_prod_desc_{prod_id}")
    builder.button(text="💰 Изменить цену", callback_data=f"edit_prod_price_{prod_id}")
    builder.button(text="📸 Изменить фото", callback_data=f"edit_prod_photo_{prod_id}")
    builder.button(text="🗑️ Удалить товар", callback_data=f"delete_prod_{prod_id}")
    builder.button(text="« Назад", callback_data="admin_manage_products")
    builder.adjust(1)

    text = f"✏️ {product[1]}\n\n💰 Цена: {product[3]} руб.\n📁 Коллекция: {product[5]}"

    await callback.answer()
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("edit_prod_name_"))
async def edit_product_name_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    prod_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_product_id=prod_id)
    await callback.message.answer("✏️ Введите НОВОЕ НАЗВАНИЕ товара:")
    await state.set_state(AdminState.waiting_for_edit_product_name)


@dp.message(AdminState.waiting_for_edit_product_name)
async def edit_product_name_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    prod_id = data.get('edit_product_id')
    update_product(prod_id, name=message.text)
    await message.answer(f"✅ Название изменено на: {message.text}")
    await state.clear()
    await admin_panel(message)


@dp.callback_query(F.data.startswith("edit_prod_desc_"))
async def edit_product_desc_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    prod_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_product_id=prod_id)
    await callback.message.answer("📝 Введите НОВОЕ ОПИСАНИЕ товара:")
    await state.set_state(AdminState.waiting_for_edit_product_desc)


@dp.message(AdminState.waiting_for_edit_product_desc)
async def edit_product_desc_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    prod_id = data.get('edit_product_id')
    update_product(prod_id, description=message.text)
    await message.answer("✅ Описание товара обновлено!")
    await state.clear()
    await admin_panel(message)


@dp.callback_query(F.data.startswith("edit_prod_price_"))
async def edit_product_price_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    prod_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_product_id=prod_id)
    await callback.message.answer("💰 Введите НОВУЮ ЦЕНУ товара (в рублях):")
    await state.set_state(AdminState.waiting_for_edit_product_price)


@dp.message(AdminState.waiting_for_edit_product_price)
async def edit_product_price_save(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        data = await state.get_data()
        prod_id = data.get('edit_product_id')
        update_product(prod_id, price=price)
        await message.answer(f"✅ Цена изменена на: {price} руб.")
        await state.clear()
        await admin_panel(message)
    except:
        await message.answer("❌ Введите число!")


@dp.callback_query(F.data.startswith("edit_prod_photo_"))
async def edit_product_photo_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    prod_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_product_id=prod_id)
    await callback.message.answer("📸 Отправьте НОВОЕ ФОТО для товара\n(или /delete чтобы удалить)")
    await state.set_state(AdminState.waiting_for_edit_product_photo)


@dp.message(AdminState.waiting_for_edit_product_photo)
async def edit_product_photo_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    prod_id = data.get('edit_product_id')

    if message.text and message.text.lower() == "/delete":
        update_product(prod_id, photo_file_id=None)
        await message.answer("✅ Фото товара удалено!")
    elif message.photo:
        photo_id = message.photo[-1].file_id
        update_product(prod_id, photo_file_id=photo_id)
        await message.answer("✅ Фото товара обновлено!")
    else:
        await message.answer("❌ Отправьте фото или /delete")
        return
    await state.clear()
    await admin_panel(message)


@dp.callback_query(F.data.startswith("delete_prod_"))
async def delete_product_confirm(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    prod_id = int(callback.data.split("_")[-1])
    product = get_product(prod_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"confirm_del_prod_{prod_id}")
    builder.button(text="❌ Нет", callback_data=f"admin_edit_prod_{prod_id}")
    builder.adjust(1)

    await callback.answer()
    await callback.message.edit_text(f"⚠️ УДАЛИТЬ ТОВАР «{product[1]}»?", reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("confirm_del_prod_"))
async def delete_product_execute(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    prod_id = int(callback.data.split("_")[-1])
    delete_product(prod_id)
    await callback.answer("✅ Товар удалён!")
    await admin_manage_products(callback)
# bot.py - ЧАСТЬ 10 (Импорт/Экспорт, Технические работы, Запуск)

# ========== ИМПОРТ/ЭКСПОРТ ==========
@dp.callback_query(F.data == "admin_import_export")
async def admin_import_export(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Экспорт товаров (CSV)", callback_data="admin_export_products")],
        [InlineKeyboardButton(text="📥 Импорт товаров (CSV)", callback_data="admin_import_products")],
        [InlineKeyboardButton(text="📋 Показать шаблон CSV", callback_data="admin_show_template")],
        [InlineKeyboardButton(text="« Назад", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(
        "📦 ИМПОРТ/ЭКСПОРТ ТОВАРОВ\n\n"
        "• Экспорт - скачать текущие товары в CSV файл\n"
        "• Импорт - загрузить товары из CSV файла\n"
        "• Шаблон - посмотреть пример формата\n\n"
        "⚠️ При импорте товары будут ДОБАВЛЕНЫ к существующим!",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_export_products")
async def admin_export_products(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    csv_data = export_products_to_csv()

    from aiogram.types import BufferedInputFile
    input_file = BufferedInputFile(csv_data, filename="products_backup.csv")

    await callback.message.answer_document(
        document=input_file,
        caption="📦 АРХИВ ТОВАРОВ\n\nСкачано: " + datetime.now().strftime("%d.%m.%Y %H:%M")
    )
    await callback.answer("✅ Экспорт завершён!")


@dp.callback_query(F.data == "admin_import_products")
async def admin_import_products(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "📥 ЗАГРУЗИТЕ CSV ФАЙЛ\n\n"
        "Отправьте CSV файл с товарами.\n"
        "Формат должен соответствовать экспортированному.\n\n"
        "Чтобы получить шаблон - нажмите «Показать шаблон»"
    )
    await state.set_state(AdminState.waiting_for_import_file)


@dp.message(AdminState.waiting_for_import_file, F.document)
async def admin_import_file(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if not (message.document.file_name.endswith('.csv') or message.document.file_name.endswith('.txt')):
        await message.answer("❌ Пожалуйста, отправьте CSV или TXT файл!")
        return

    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_bytes = await bot.download_file(file.file_path)

    imported, errors = import_products_from_csv(file_bytes.read())

    result_text = f"📥 ИМПОРТ ЗАВЕРШЁН!\n\n✅ Добавлено товаров: {imported}"

    if errors:
        result_text += f"\n\n⚠️ ОШИБОК: {len(errors)}"
        for err in errors[:5]:
            result_text += f"\n• {err}"

    await message.answer(result_text)
    await state.clear()


@dp.callback_query(F.data == "admin_show_template")
async def admin_show_template(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    template = """Название,Описание,Цена,Коллекция,Photo File ID
Футболка OBEREG,Премиальная футболка из хлопка,1500,Новинки,
Джинсы классические,Синие джинсы прямого кроя,3500,Хиты продаж,
Свитер уютный,Теплый шерстяной свитер,2500,Зима 2024,AgACAgIAAxkBAAI...

📝 ПРАВИЛА ЗАПОЛНЕНИЯ:
• Первая строка - заголовки (не изменять)
• Название - текст
• Описание - текст
• Цена - только число
• Коллекция - название существующей или новой коллекции
• Photo File ID - опционально (можно оставить пустым)
• Разделитель - запятая (,)"""

    await callback.message.answer(f"```\n{template}\n```", parse_mode="Markdown")
    await callback.answer()


# ========== ТЕХНИЧЕСКИЕ РАБОТЫ ==========
@dp.callback_query(F.data == "admin_maintenance")
async def admin_maintenance(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return

    config.MAINTENANCE_MODE = not config.MAINTENANCE_MODE

    status = "ВКЛЮЧЕН" if config.MAINTENANCE_MODE else "ВЫКЛЮЧЕН"
    await callback.answer(f"🛠️ Режим технических работ {status}!", show_alert=True)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

    if config.MAINTENANCE_MODE:
        await callback.message.answer(
            "🛠️ РЕЖИМ ТЕХНИЧЕСКИХ РАБОТ ВКЛЮЧЕН\n\n"
            "Все пользователи будут видеть сообщение о ведущихся работах.\n"
            "Только администратор имеет доступ.\n\n"
            "Чтобы выключить - нажмите кнопку снова.",
            reply_markup=admin_panel_keyboard()
        )
    else:
        await callback.message.answer(
            "✅ РЕЖИМ ТЕХНИЧЕСКИХ РАБОТ ВЫКЛЮЧЕН\n\n"
            "Бот снова доступен для всех пользователей.",
            reply_markup=admin_panel_keyboard()
        )


# ========== ПРОПУСК ФОТО ==========
@dp.message(Command("skip"))
async def skip_photo(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current == AdminState.waiting_for_collection_photo:
        data = await state.get_data()
        add_collection(data['col_name'], data['col_desc'], None)
        await message.answer(f"✅ Коллекция «{data['col_name']}» добавлена без фото!")
        await state.clear()
        await admin_panel(message)
    elif current == AdminState.waiting_for_product_photo:
        data = await state.get_data()
        add_product(data['col_id'], data['prod_name'], data['prod_desc'], data['prod_price'], None)
        await message.answer(f"✅ Товар «{data['prod_name']}» добавлен без фото!")
        await state.clear()
        await admin_panel(message)


# ========== ПОЛУЧЕНИЕ PHOTO ID ==========
@dp.message(F.photo)
async def get_photo_id(message: types.Message):
    file_id = message.photo[-1].file_id
    await message.answer(f"📸 Photo ID:\n`{file_id}`", parse_mode="Markdown")
    print(f"Photo ID: {file_id}")


# ========== ЗАПУСК ==========
async def main():
    global bot
    bot = await create_bot_with_proxy()
    print("✅ Бот запущен!")
    print(f"Администраторы: {config.ADMIN_IDS}")

    # Проверяем, что бот может подключиться к Telegram
    try:
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())