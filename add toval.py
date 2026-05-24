# add_all_products.py
import sqlite3

DB_NAME = "shop_bot.db"

# Список товаров
products = [
    ("Modernité Impériale", "приветики", 3499, "812 Heritage",
     "AgACAgIAAxkBAAIXwmoSAdTybozQ-N4uj0E-3oiZmoaMAAIIImsbbaWRSH6vekVe2eysAQADAgADdwADOwQ"),
    ("L’Âme de la Neva light", "описание второго", 3499, "812 Heritage",
     "AgACAgIAAxkBAAIXyWoSAnBceflrlGhZRVr0dsRUhmJPAAJ8GGsbAY6QSPs7yY67SQfDAQADAgADdwADOwQ"),
    ("L’Âme de la Neva dark", "описание третьего", 3499, "812 Heritage",
     "AgACAgIAAxkBAAIXy2oSAnmOliEjMx9k1eVj7BL3gTuXAAJ9GGsbAY6QSOtfxtfGvIIuAQADAgADdwADOwQ"),
    ("Élégance 812 light", "описание второго", 3499, "812 Heritage",
     "AgACAgIAAxkBAAIXzWoSAp95Yk5N5IyAETqWeyYlOwlsAAKCGGsbAY6QSPwIbllqV8ddAQADAgADdwADOwQ"),
    ("Élégance 812 dark", "описание второго", 3499, "812 Heritage",
     "AgACAgIAAxkBAAIXz2oSAqTeaL-ZeW97bhNuWaYRz34HAAKDGGsbAY6QSOaAAYTjU7_KAQADAgADdwADOwQ"),
    ("Cathédrales de Brume light", "описание второго", 3499, "812 Heritage",
     "AgACAgIAAxkBAAIX0WoSArlv_KgysewWXjuP1nmr8o1kAAKEGGsbAY6QSNAyNUmITdWuAQADAgADdwADOwQ"),
    ("Cathédrales de Brume dark", "описание второго", 3499, "812 Heritage",
     "AgACAgIAAxkBAAIX02oSAsSkv1fLuVL8h3ueJLOJkLkzAAKFGGsbAY6QSNbAFKTEXfY8AQADAgADdwADOwQ"),
    ("L’Art d’Êtret", "бомба", 3499, "Le Jardin du Palais",
     "AgACAgIAAxkBAAIX1WoSAwtoo8d0rEmLk2MqzqvdiWm2AAKHGGsbAY6QSMRijwdRiyNeAQADAgADdwADOwQ"),
    ("L’Art d’Être dark", "бумлащддаф", 3499, "Le Jardin du Palais",
     "AgACAgIAAxkBAAIX12oSAxdXEDFfMA7hSZjkFRqjGEVhAAKIGGsbAY6QSA1sQ5YrPqpAAQADAgADdwADOwQ"),
    ("La Poésie du Nord light", "описание второго", 3499, "Le Jardin du Palais",
     "AgACAgIAAxkBAAIX2WoSAythr6Sj8iCl5AztlCtplfDmAAKJGGsbAY6QSM27_-QVLrCZAQADAgADdwADOwQ"),
    ("La Poésie du Nord dark", "описание второго", 3499, "Le Jardin du Palais",
     "AgACAgIAAxkBAAIX22oSAznW1PZOYrpbuHvKGKv3IVGbAAKKGGsbAY6QSErGm6nwsFopAQADAgADdwADOwQ"),
    ("Minuit à Saint-Pétersbourg light", "описание второго", 3499, "Le Jardin du Palais",
     "AgACAgIAAxkBAAIX3WoSA0Qi4o4tr1BxflcWxiuUB83ZAAKLGGsbAY6QSAsIs3orHCTpAQADAgADdwADOwQ"),
    ("Minuit à Saint-Pétersbourg dark", "описание второго", 3499, "Le Jardin du Palais",
     "AgACAgIAAxkBAAIX32oSA0x8Rl32sZbNYHqf_aFav_SIAAKQGGsbAY6QSOR6vuRlD3mXAQADAgADdwADOwQ"),
    ("Lumière de Neva light", "описание второго", 3499, "Le Jardin du Palais",
     "AgACAgIAAxkBAAIX4WoSA1jnO7ltw-h2HUoQidXZTawIAAKUGGsbAY6QSOn1KTm8DV1IAQADAgADdwADOwQ"),
    ("Lumière de Neva dark", "описание второго", 3499, "Le Jardin du Palais",
     "AgACAgIAAxkBAAIX42oSA2CTvscz-M6-HpU2J1DlOx7cAAKVGGsbAY6QSK-ZMfyi_J_2AQADAgADdwADOwQ"),
    ("Messager de Minuit", "описание второго", 3499, "White Night Guardians",
     "AgACAgIAAxkBAAIX7moSA8eQJfjIkUEM-fPa_A4ncO6lAAKZGGsbAY6QSGdXAUESLvFLAQADAgADdwADOwQ"),
    ("Mélancolie Impériale", "описание второго", 3499, "White Night Guardians",
     "AgACAgIAAxkBAAIX8WoSA84I0WaFN9393cOGbHsjQEVFAAKaGGsbAY6QSLQiwtsFWO2_AQADAgADdwADOwQ"),
    ("Bleu de la Neva", "описание второго", 3499, "White Night Guardians",
     "AgACAgIAAxkBAAIX82oSA9c-iviT689tly6KGQeFOiknAAKbGGsbAY6QSOMtZcArmf_cAQADAgADdwADOwQ"),
    ("Bordeaux de la Neva", "описание второго", 3499, "White Night Guardians",
     "AgACAgIAAxkBAAIX9WoSA97aYljUIQ7bXFWPZZKfz2sNAAKeGGsbAY6QSCAuNe7R0TiRAQADAgADdwADOwQ"),
    ("Les Veilleurs du Nord light", "описание второго", 3499, "White Night Guardians",
     "AgACAgIAAxkBAAIX92oSA_QdPDyPtJj6Bgn9mH6t3wLeAAKfGGsbAY6QSJX0CFsJyXPIAQADAgADdwADOwQ"),
    ("Les Veilleurs du Nord dark", "описание второго", 3499, "White Night Guardians",
     "AgACAgIAAxkBAAIX-WoSA_xbR2nm2pDW3Wga06XEY804AAKgGGsbAY6QSO27c79Cu8QVAQADAgADdwADOwQ"),
    # добавьте остальные товары сюда
]
conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

# Получаем список существующих товаров
cur.execute("SELECT name FROM products")
existing_products = set(row[0] for row in cur.fetchall())
print(f"📋 Существующих товаров в базе: {len(existing_products)}")

added = 0
skipped = 0
created_collections = []

for name, desc, price, collection_name, photo_id in products:
    # Проверяем, нет ли уже такого товара
    if name in existing_products:
        print(f"⏩ Товар '{name}' уже существует, пропускаем")
        skipped += 1
        continue

    # 1. Находим или создаём коллекцию ДЛЯ КАЖДОГО ТОВАРА
    cur.execute("SELECT id FROM collections WHERE name = ?", (collection_name,))
    collection = cur.fetchone()

    if collection:
        collection_id = collection[0]
        print(f"🔵 Коллекция '{collection_name}' найдена (ID={collection_id})")
    else:
        cur.execute("INSERT INTO collections (name, description) VALUES (?, ?)",
                    (collection_name, f"Коллекция {collection_name}"))
        collection_id = cur.lastrowid
        created_collections.append(collection_name)
        print(f"🆕 Создана коллекция: {collection_name} (ID={collection_id})")

    # 2. Добавляем товар
    cur.execute("""
        INSERT INTO products (collection_id, name, description, price, photo_file_id, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (collection_id, name, desc, price, photo_id))
    added += 1
    print(f"✅ Добавлен: {name} - {price}₽ в коллекцию '{collection_name}'")
    existing_products.add(name)

conn.commit()
conn.close()

print(f"\n📊 ИТОГИ:")
print(f"✅ Добавлено новых товаров: {added}")
print(f"⏩ Пропущено (уже были): {skipped}")
if created_collections:
    print(f"🆕 Создано новых коллекций: {', '.join(created_collections)}")
