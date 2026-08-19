import feedparser
import requests
import json
import os
import html
import re
import time
from PIL import Image
from io import BytesIO

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_URL = os.getenv("RSS_URL", "https://www.pinterest.com/artsy/contemporary-art.rss")
HF_TOKEN = os.getenv("HF_TOKEN")

print(f"🔍 Загружаю: {RSS_URL}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    with open("posted_ids.json", "r", encoding="utf-8") as f:
        try: posted_ids = json.load(f)
        except: posted_ids = []

def analyze_image(image_url):
    """AI-анализ изображения через HuggingFace"""
    if not HF_TOKEN or not image_url:
        return None
    
    try:
        # Загружаем изображение
        img_response = requests.get(image_url, timeout=10)
        if img_response.status_code != 200:
            return None
        
        # Отправляем в AI модель BLIP (описание изображений)
        api_url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        
        response = requests.post(
            api_url,
            headers=headers,
            data=img_response.content,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                caption = result[0].get('generated_text', '')
                return caption
    except Exception as e:
        print(f"⚠️ Ошибка AI: {e}")
    
    return None

def translate_to_russian(text):
    """Простой перевод на русский (можно заменить на DeepL или Google Translate API)"""
    if not text:
        return ""
    
    # Словарь частых слов для перевода
    translations = {
        'painting': 'картина',
        'artwork': 'произведение искусства',
        'sculpture': 'скульптура',
        'photograph': 'фотография',
        'abstract': 'абстрактное',
        'modern': 'современное',
        'contemporary': 'современное',
        'art': 'искусство',
        'colorful': 'красочное',
        'black and white': 'чёрно-белое',
        'portrait': 'портрет',
        'landscape': 'пейзаж',
    }
    
    text_lower = text.lower()
    for eng, rus in translations.items():
        text_lower = text_lower.replace(eng, rus)
    
    # Если текст на английском — просто добавляем префикс
    if any(c.isalpha() for c in text):
        return f"На изображении: {text}"
    
    return text

def extract_image_url(entry):
    """Извлекает URL изображения из RSS"""
    # media:content
    if hasattr(entry, 'media_content') and entry.media_content:
        return entry.media_content[0].get('url', '')
    
    # enclosure
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('href', '')
    
    # img в HTML
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
    if img_match:
        return img_match.group(1)
    
    return ''

feed = feedparser.parse(RSS_URL, request_headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
})

print(f"📊 Записей в RSS: {len(feed.entries)}")

if len(feed.entries) == 0:
    print("⚠️ RSS пуст")
    exit(0)

new_items = []
for entry in feed.entries:
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title = entry.get("title", "Без названия")
    image_url = extract_image_url(entry)
    
    print(f"🖼️ Обрабатываю: {title[:50]}...")
    
    # AI-анализ изображения
    ai_description = analyze_image(image_url)
    
    if ai_description:
        # Переводим на русский
        ru_description = translate_to_russian(ai_description)
    else:
        ru_description = "Современное искусство"
    
    # 🎨 Формируем пост
    text = f"""🎨 <b>{title}</b>

{ru_description}

#современноеискусство #арт #AI"""

    new_items.append({
        "id": item_id,
        "text": text,
        "image": image_url
    })
    
    # Небольшая пауза, чтобы не заблокировали
    time.sleep(2)

# Отправка в Telegram
if new_items:
    url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    for i, item in enumerate(new_items):
        if not item["image"]:
            print(f"❌ [{i+1}] Нет картинки, пропускаю")
            continue
        
        try:
            res = requests.post(url_photo, json={
                "chat_id": CHAT_ID,
                "photo": item["image"],
                "caption": item["text"],
                "parse_mode": "HTML"
            }, timeout=30)
            
            if res.status_code == 200:
                posted_ids.append(item["id"])
                print(f"✅ [{i+1}] Отправлено с AI-описанием")
            else:
                print(f"❌ [{i+1}] Ошибка: {res.text}")
        except Exception as e:
            print(f"❌ [{i+1}] Ошибка отправки: {e}")
        
        time.sleep(1)  # Пауза между постами
    
    print(f"🎉 Опубликовано: {len([x for x in new_items if x['image']])}")

# Сохранение
if posted_ids:
    with open("posted_ids.json", "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
    print(f"💾 Сохранено ID: {len(posted_ids)}")
