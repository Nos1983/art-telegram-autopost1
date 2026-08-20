import requests
import json
import os
import re
import time
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "1"))

print("🎨 Tate Collection Auto-Poster")
print(f"🤖 AI: {'✅' if HF_TOKEN else '⚠️'}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except: posted_ids = []

def parse_tate_collection():
    """Парсит Tate Collection и возвращает список работ"""
    
    url = "https://www.tate.org.uk/collection?attributes=img"
    print(f"📥 Загружаю: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        artworks = []
        
        # Ищем карточки работ (селекторы могут меняться)
        art_cards = soup.find_all('div', class_='artwork-item') or soup.find_all('article')
        
        print(f"📊 Найдено карточек: {len(art_cards)}")
        
        for card in art_cards[:10]:  # Берём первые 10
            try:
                # 🖼️ Картинка
                img_tag = card.find('img')
                if not img_tag:
                    continue
                    
                image_url = img_tag.get('src') or img_tag.get('data-src')
                if image_url:
                    # Добавляем https: если нет
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif not image_url.startswith('http'):
                        image_url = 'https://www.tate.org.uk' + image_url
                
                # 🎨 Название
                title_tag = card.find('h3') or card.find('h2') or card.find('a', class_='artwork-title')
                title = title_tag.get_text(strip=True) if title_tag else "Без названия"
                
                # 👨🎨 Художник
                artist_tag = card.find('div', class_='artist') or card.find('span', class_='artist-name')
                artist = artist_tag.get_text(strip=True) if artist_tag else None
                
                # 📅 Год
                year_tag = card.find('span', class_='date') or card.find('time')
                year = year_tag.get_text(strip=True) if year_tag else None
                
                #  Описание (если есть)
                desc_tag = card.find('p', class_='description') or card.find('div', class_='caption')
                description = desc_tag.get_text(strip=True) if desc_tag else None
                
                #  Ссылка на работу
                link_tag = card.find('a', href=True)
                link = 'https://www.tate.org.uk' + link_tag.get('href') if link_tag else url
                
                # Уникальный ID
                item_id = link
                
                if item_id in posted_ids:
                    continue
                
                artworks.append({
                    'id': item_id,
                    'title': title,
                    'artist': artist,
                    'year': year,
                    'description': description,
                    'image': image_url,
                    'link': link
                })
                
            except Exception as e:
                print(f"⚠️ Ошибка парсинга карточки: {e}")
                continue
        
        return artworks
        
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
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
    
    # Заголовок
    lines.append(f"<b>{artwork['title']}</b>\n")
    
    # Художник
    if artwork.get('artist'):
        lines.append(f"‍🎨 <b>Художник:</b> {artwork['artist']}")
    
    # Год
    if artwork.get('year'):
        lines.append(f"📅 <b>Год:</b> {artwork['year']}")
    
    # AI описание
    if ai_desc:
        lines.append(f"🖼️ <b>На изображении:</b> {ai_desc}")
    
    # Описание из сайта
    if artwork.get('description'):
        lines.append(f"📖 {artwork['description']}")
    
    # Ссылка
    lines.append(f"\n🔗 <a href=\"{artwork['link']}\">Подробнее на Tate.org.uk</a>")
    
    # Хештеги
    lines.append("\n#Tate #современноеискусство #арт #коллекция")
    
    return "\n".join(lines)

# 🔥 Основной запуск
print("\n🎨 Начинаю парсинг Tate Collection...")
artworks = parse_tate_collection()

if not artworks:
    print("⚠️ Не найдено работ!")
    exit(0)

print(f"✅ Найдено {len(artworks)} новых работ")

# Берём нужное количество
artworks_to_post = artworks[:POSTS_PER_RUN]
print(f"\n📤 Буду отправлять: {len(artworks_to_post)}\n")

# Отправка
sent = 0
for i, artwork in enumerate(artworks_to_post):
    print(f"[{i+1}] {artwork['title'][:50]}...")
    
    # AI-анализ картинки
    if artwork['image']:
        print(f"    🤖 AI-анализ...")
        ai_desc = analyze_image(artwork['image'])
        if ai_desc:
            print(f"    ✅ {ai_desc}")
    else:
        ai_desc = None
    
    # Создаём описание
    description = create_description(artwork, ai_desc)
    
    # Отправка
    try:
        if artwork['image']:
            res = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                json={
                    "chat_id": CHAT_ID,
                    "photo": artwork['image'],
                    "caption": description,
                    "parse_mode": "HTML"
                },
                timeout=30
            )
        else:
            res = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "text": description,
                    "parse_mode": "HTML"
                },
                timeout=15
            )
        
        if res.status_code == 200:
            posted_ids.append(artwork['id'])
            sent += 1
            print(f"    ✅ Отправлено!")
        else:
            print(f"    ❌ {res.text[:80]}")
            
    except Exception as e:
        print(f"    ❌ Ошибка: {e}")
    
    time.sleep(2)

# Сохранение
with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"\n Отправлено: {sent}/{len(artworks_to_post)}")
print(f"💾 Сохранено {len(posted_ids)} ID")
