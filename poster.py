import requests
import json
import os
import time
import random

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "1"))

print("🏛️ The Met Collection Auto-Poster")
print(f"🤖 AI: {'✅' if HF_TOKEN else '⚠️'}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except: posted_ids = []

def fetch_met_artworks(has_image=True, limit=50):
    """Загружает работы через API The Met"""
    
    # 1. Получаем список ID объектов
    ids_url = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
    
    print(f"📥 Запрашиваю список объектов...")
    
    try:
        # The Met API не требует ключа
        response = requests.get(ids_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        object_ids = data.get('objectIDs', [])
        print(f"📊 Всего объектов в API: {len(object_ids)}")
        
        # Берём случайные ID (чтобы разнообразие)
        # Фильтруем уже отправленные
        available_ids = [oid for oid in object_ids if oid not in posted_ids]
        
        if not available_ids:
            print("⚠️ Все ID уже отправлены!")
            return []
        
        # Берём нужное количество + запас
        selected_ids = random.sample(available_ids, min(limit, len(available_ids)))
        print(f"✅ Выбрано {len(selected_ids)} новых ID")
        
        # 2. Загружаем детали для каждого объекта
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
                print(f"⚠️ Ошибка загрузки объекта {oid}: {e}")
                continue
            
            time.sleep(0.2)  # Не спамим API
        
        return artworks
        
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        return []

def analyze_image(image_url):
    """AI-анализ изображения"""
    if not HF_TOKEN or not image_url:
        return None
    
    try:
        img_data = requests.get(image_url, timeout=10).content
        response = requests.post(
            "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            data=img_data,
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('generated_text', '')
    except:
        pass
    
    return None

def create_description(artwork, ai_desc):
    """Создаёт описание на русском"""
    lines = []
    
    title = artwork.get('title', 'Без названия')
    artist = artwork.get('artistDisplayName')
    year = artwork.get('objectDate')
    medium = artwork.get('medium')
    department = artwork.get('department')
    image_url = artwork.get('primaryImage')
    link = artwork.get('objectURL', 'https://www.metmuseum.org')
    
    # Заголовок
    lines.append(f"<b>{title}</b>\n")
    
    # Художник
    if artist and artist != 'Unknown':
        lines.append(f"👨‍🎨 <b>Художник:</b> {artist}")
    
    # Год/период
    if year:
        lines.append(f"📅 <b>Дата:</b> {year}")
    
    # Отдел музея
    if department:
        lines.append(f"🏛️ <b>Отдел:</b> {department}")
    
    # Техника/материалы
    if medium:
        # Обрезаем если слишком длинно
        medium_short = medium[:100] + "..." if len(medium) > 100 else medium
        lines.append(f"🎨 <b>Материалы:</b> {medium_short}")
    
    # AI описание картинки
    if ai_desc:
        lines.append(f"🖼️ <b>На изображении:</b> {ai_desc}")
    
    # Ссылка
    lines.append(f"\n🔗 <a href=\"{link}\">Подробнее на Met Museum</a>")
    
    # Хештеги
    lines.append("\n#TheMet #искусство #арт #музей #коллекция")
    
    return "\n".join(lines)

# 🔥 Основной запуск
print("\n🏛️ Загружаю работы из The Met API...")
artworks = fetch_met_artworks(has_image=True, limit=30)

if not artworks:
    print("⚠️ Не найдено новых работ с картинками")
    # Создаём файл чтобы Git не упал
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
        print(f"    ⚠️ Нет картинки, пропускаю")
        continue
    
    print(f"    🖼️ {image_url[:70]}...")
    
    # AI-анализ
    ai_desc = None
    if HF_TOKEN:
        print(f"    🤖 AI-анализ...")
        ai_desc = analyze_image(image_url)
        if ai_desc:
            print(f"    ✅ {ai_desc}")
    
    # Создаём описание
    description = create_description(artwork, ai_desc)
    
    # Отправка
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json={
                "chat_id": CHAT_ID,
                "photo": image_url,
                "caption": description,
                "parse_mode": "HTML"
            },
            timeout=30
        )
        
        if res.status_code == 200:
            posted_ids.append(object_id)
            sent += 1
            print(f"    ✅ Отправлено!")
        else:
            print(f"    ❌ {res.text[:80]}")
            
    except Exception as e:
        print(f"    ❌ Ошибка: {e}")
    
    time.sleep(2)

# 🔒 ВСЕГДА сохраняем файл
with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"\n🎉 Отправлено: {sent}/{len(artworks_to_post)}")
print(f"💾 Сохранено {len(posted_ids)} ID")
