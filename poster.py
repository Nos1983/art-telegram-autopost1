import feedparser
import requests
import json
import os
import re
import time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_URL = os.getenv("RSS_URL", "https://hyperallergic.com/feed/")
HF_TOKEN = os.getenv("HF_TOKEN")

print(f"🔍 Загружаю: {RSS_URL}")
print(f" AI: {'✅' if HF_TOKEN else '❌ (без HF_TOKEN описания будут простыми)'}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
        print(f"📚 Загружено {len(posted_ids)} ID")
    except: posted_ids = []

# Загрузка RSS
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    r = requests.get(RSS_URL, headers=headers, timeout=15)
    feed = feedparser.parse(r.text)
except:
    feed = feedparser.parse(RSS_URL, request_headers=headers)

print(f"📊 Записей в RSS: {len(feed.entries)}")

def analyze_image(image_url):
    """AI-анализ изображения через HuggingFace"""
    if not HF_TOKEN or not image_url:
        return None
    
    try:
        # Скачиваем изображение
        img_data = requests.get(image_url, timeout=10).content
        
        # Отправляем в BLIP (описание изображений)
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
    except Exception as e:
        print(f"⚠️ AI ошибка: {e}")
    
    return None

def translate_to_russian(text):
    """Перевод на русский через Google Translate (бесплатно)"""
    if not text:
        return "Произведение современного искусства"
    
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={text}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            result = response.json()
            return result[0][0][0]
    except:
        pass
    
    # Словарь частых слов (fallback)
    translations = {
        'painting': 'картина', 'artwork': 'произведение искусства',
        'sculpture': 'скульптура', 'photograph': 'фотография',
        'abstract': 'абстрактное', 'modern': 'современное',
        'contemporary': 'современное', 'art': 'искусство',
        'colorful': 'красочное', 'black and white': 'чёрно-белое',
        'portrait': 'портрет', 'landscape': 'пейзаж',
        'digital art': 'цифровое искусство', 'installation': 'инсталляция',
        'mixed media': 'смешанная техника', 'canvas': 'холст',
        'oil': 'масло', 'watercolor': 'акварель', 'acrylic': 'акрил'
    }
    
    text_lower = text.lower()
    for eng, rus in translations.items():
        text_lower = text_lower.replace(eng, rus)
    
    return text_lower.capitalize()

def create_detailed_description(ai_caption, title):
    """Создаёт развёрнутое описание на русском"""
    caption_ru = translate_to_russian(ai_caption) if ai_caption else "абстрактная композиция"
    
    # Добавляем детали
    descriptions = [
        f"{caption_ru}. Работа выполнена в стиле современного искусства.",
        f"На изображении: {caption_ru}. Характерно для актуальных художественных практик.",
        f"{caption_ru}. Пример современного визуального языка."
    ]
    
    # Выбираем случайное или первое
    return descriptions[0]

def extract_image_url(entry):
    """Извлекает URL картинки"""
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            u = m.get('url', '')
            if u and (u.endswith(('.jpg','.png','.jpeg')) or 'i.redd.it' in u):
                return u
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    m = re.search(r'<img[^>]+src="([^"]+)"', content)
    return m.group(1) if m else None

# Обработка записей
new_items = []
print("\n🎨 Обрабатываю...")

for i, entry in enumerate(feed.entries[:3]):  # Только 3 поста (AI медленный)
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title = entry.get("title", "Без названия")
    image_url = extract_image_url(entry)
    
    print(f"  [{i+1}] {title[:30]}...")
    
    # AI-анализ
    if image_url:
        print(f"       Анализирую изображение...")
        ai_caption = analyze_image(image_url)
        description = create_detailed_description(ai_caption, title)
        print(f"      ✅ {description[:60]}...")
    else:
        description = "Произведение современного искусства"
        print(f"      ⚠️ Нет изображения")
    
    # 🎨 Формируем пост (БЕЗ ссылки на источник!)
    text = f"""🎨 <b>{title}</b>

{description}

#современноеискусство #арт #выставка #художник"""

    new_items.append({
        "id": item_id,
        "text": text,
        "image": image_url
    })
    
    time.sleep(2)  # Пауза для AI

# Отправка
sent = 0
if new_items:
    print(f"\n📤 Отправляю...")
    for i, item in enumerate(new_items):
        try:
            if item["image"]:
                res = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    json={
                        "chat_id": CHAT_ID,
                        "photo": item["image"],
                        "caption": item["text"],
                        "parse_mode": "HTML"
                    },
                    timeout=30
                )
            else:
                res = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": CHAT_ID,
                        "text": item["text"],
                        "parse_mode": "HTML"
                    },
                    timeout=15
                )
            
            if res.status_code == 200:
                posted_ids.append(item["id"])
                sent += 1
                print(f"  ✅ [{i+1}] Отправлено")
            else:
                print(f"  ❌ [{i+1}] {res.text[:80]}")
        except Exception as e:
            print(f"  ❌ [{i+1}] {e}")
        time.sleep(1)
    
    print(f"\n🎉 Успешно: {sent}/{len(new_items)}")
else:
    print("\n⚠️ Нечего отправлять")

# Сохранение
with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)
print(f"💾 Сохранено {len(posted_ids)} ID")
