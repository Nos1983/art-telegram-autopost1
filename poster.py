import requests
import json
import os
import time
import random

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "1"))

print("🏛️ The Met Collection Auto-Poster")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except: posted_ids = []

def fetch_met_artworks():
    """Загружает работы через API The Met"""
    
    ids_url = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
    
    print(f"📥 Запрашиваю список объектов...")
    
    try:
        response = requests.get(ids_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        object_ids = data.get('objectIDs', [])
        print(f"📊 Всего объектов: {len(object_ids)}")
        
        # Фильтруем уже отправленные
        available_ids = [oid for oid in object_ids if oid not in posted_ids]
        
        if not available_ids:
            print("⚠️ Все ID уже отправлены!")
            return []
        
        # Берём случайные ID
        selected_ids = random.sample(available_ids, min(50, len(available_ids)))
        print(f"✅ Выбрано {len(selected_ids)} новых ID")
        
        # Загружаем детали
        artworks = []
        for oid in selected_ids:
            try:
                detail_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}"
                detail_resp = requests.get(detail_url, timeout=10)
                
                if detail_resp.status_code == 200:
                    artwork = detail_resp.json()
                    
                    # Пропускаем без картинки
                    if not artwork.get('primaryImage'):
                        continue
                    
                    artworks.append(artwork)
                    
            except Exception as e:
                continue
            
            time.sleep(0.2)
        
        return artworks
        
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        return []

def create_description(artwork):
    """Создаёт описание из метаданных The Met"""
    
    title = artwork.get('title', 'Без названия')
    artist = artwork.get('artistDisplayName')
    year = artwork.get('objectDate')
    medium = artwork.get('medium')
    department = artwork.get('department')
    culture = artwork.get('culture')
    gallery_num = artwork.get('galleryNumber')
    link = artwork.get('objectURL', 'https://www.metmuseum.org')
    
    lines = []
    
    # Заголовок
    lines.append(f"<b>{title}</b>\n")
    
    # Художник
    if artist and artist != 'Unknown':
        lines.append(f"👨‍🎨 <b>Художник:</b> {artist}")
    
    # Год/период
    if year:
        lines.append(f"📅 <b>Дата:</b> {year}")
    
    # Культура/регион
    if culture and culture != 'Unknown':
        lines.append(f"🌍 <b>Культура:</b> {culture}")
    
    # Отдел музея
    if department:
        lines.append(f"🏛️ <b>Отдел:</b> {department}")
    
    # Техника/материалы (красиво форматируем)
    if medium:
        # Заменяем технические термины на понятные
        medium_map = {
            'Oil on canvas': 'Масло на холсте',
            'Watercolor': 'Акварель',
            'Bronze': 'Бронза',
            'Marble': 'Мрамор',
            'Ink on paper': 'Тушь на бумаге',
            'Photograph': 'Фотография',
            'Sculpture': 'Скульптура',
            'Painting': 'Живопись',
        }
        
        medium_ru = medium_map.get(medium, medium)
        lines.append(f"🎨 <b>Техника:</b> {medium_ru[:100]}")
    
    # Номер галереи (если есть)
    if gallery_num:
        lines.append(f"🖼️ <b>Галерея:</b> {gallery_num}")
    
    # Ссылка
    lines.append(f"\n🔗 <a href=\"{link}\">Подробнее на Met Museum</a>")
    
    # Хештеги
    lines.append("\n#TheMet #искусство #арт #музей #коллекция")
    
    return "\n".join(lines)

def download_image(image_url):
    """Скачивает изображение и возвращает байты"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(image_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"⚠️ Не удалось скачать картинку: {e}")
        return None

def send_photo_as_file(image_data, caption):
    """Отправляет картинку как файл (обходит проблему с URL)"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    files = {
        'photo': ('artwork.jpg', image_data, 'image/jpeg')
    }
    
    data = {
        'chat_id': CHAT_ID,
        'caption': caption,
        'parse_mode': 'HTML'
    }
    
    try:
        res = requests.post(url, data=data, files=files, timeout=60)
        return res
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return None

# 🔥 Основной запуск
print("\n🏛️ Загружаю работы из The Met API...")
artworks = fetch_met_artworks()

if not artworks:
    print("⚠️ Не найдено новых работ с картинками")
    with open("posted_ids.json", "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
    print("💾 Сохранено (0 новых)")
    exit(0)

print(f"✅ Найдено {len(artworks)} работ с картинками")

# Берём нужное количество
artworks_to_post = artworks[:POSTS_PER_RUN]
print(f"\n📤 Буду отправлять: {len(artworks_to_post)}\n")

# Отправка
sent = 0
for i, artwork in enumerate(artworks_to_post):
    title = artwork.get('title', 'Без названия')
    object_id = artwork.get('objectID')
    
    print(f"[{i+1}] {title[:50]}...")
    
    # Картинка
    image_url = artwork.get('primaryImage')
    if not image_url:
        print(f"    ⚠️ Нет картинки")
        continue
    
    print(f"    🖼️ Скачиваю картинку...")
    
    # Скачиваем картинку
    image_data = download_image(image_url)
    if not image_data:
        print(f"    ❌ Не удалось скачать картинку")
        continue
    
    print(f"    ✅ Скачано: {len(image_data)} байт")
    
    # Создаём описание из метаданных
    description = create_description(artwork)
    
    # Отправляем как файл
    print(f"    📤 Отправляю...")
    res = send_photo_as_file(image_data, description)
    
    if res and res.status_code == 200:
        posted_ids.append(object_id)
        sent += 1
        print(f"    ✅ Отправлено!")
    else:
        if res:
            print(f"    ❌ {res.text[:80]}")
        else:
            print(f"    ❌ Ошибка отправки")
    
    time.sleep(1)

# Сохранение
with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"\n🎉 Отправлено: {sent}/{len(artworks_to_post)}")
print(f"💾 Сохранено {len(posted_ids)} ID")
