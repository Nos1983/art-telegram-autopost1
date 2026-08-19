import feedparser
import requests
import json
import os
import html
import re
import time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_URL = os.getenv("RSS_URL")
HF_TOKEN = os.getenv("HF_TOKEN")

print(f"🔍 Загружаю: {RSS_URL}")

if not RSS_URL:
    print("❌ RSS_URL не задан!")
    exit(1)

posted_ids = []
if os.path.exists("posted_ids.json"):
    with open("posted_ids.json", "r", encoding="utf-8") as f:
        try: posted_ids = json.load(f)
        except: posted_ids = []

# Парсинг с правильными заголовками
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
}

try:
    response = requests.get(RSS_URL, headers=headers, timeout=10)
    print(f"📡 Статус ответа: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Сайт вернул ошибку {response.status_code}")
        print(" Попробуй другой RSS_URL из списка")
        exit(1)
    
    feed = feedparser.parse(response.content)
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
    exit(1)

print(f"📊 Записей в RSS: {len(feed.entries)}")

if len(feed.entries) == 0:
    print("⚠️ RSS пуст или не распарсен")
    print("🔍 Проверь ссылку в браузере:")
    print(f"   {RSS_URL}")
    print("💡 Если в браузере тоже пусто — смени источник")
    exit(0)

def extract_image_url(entry):
    """Ищет картинку в RSS"""
    # media:content
    if hasattr(entry, 'media_content') and entry.media_content:
        return entry.media_content[0].get('url', '')
    
    # enclosure
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('href', '')
    
    # Ищем в HTML
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
    if img_match:
        return img_match.group(1)
    
    return ''

def analyze_image_simple(image_url, title):
    """Простое описание без AI (если HF_TOKEN не задан)"""
    if not image_url:
        return "Произведение современного искусства"
    
    # Если есть HF_TOKEN — используем AI
    if HF_TOKEN:
        try:
            img_data = requests.get(image_url, timeout=10).content
            response = requests.post(
                "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large",
                headers={"Authorization": f"Bearer {HF_TOKEN}"},
                data=img_data,
                timeout=15
            )
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get('generated_text', 'Современное искусство')
        except:
            pass
    
    # Fallback — просто название
    return f"Работа: {title}"

new_items = []
print("\n🎨 Обрабатываю записи...")

for i, entry in enumerate(feed.entries[:5]):  # Берём только первые 5
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title = entry.get("title", "Без названия")
    image_url = extract_image_url(entry)
    link = entry.get("link", "")
    
    print(f"  [{i+1}] {title[:40]}... {'✓' if image_url else '✗ нет картинки'}")
    
    # AI-описание или простое
    description = analyze_image_simple(image_url, title)
    
    # Формируем пост
    text = f"""🎨 <b>{title}</b>

{description}

<a href="{link}">Подробнее</a>

#современноеискусство #арт"""

    new_items.append({
        "id": item_id,
        "text": text,
        "image": image_url
    })
    
    time.sleep(1)

# Отправка
if new_items:
    print(f"\n📤 Отправляю {len(new_items)} постов...")
    
    url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    for i, item in enumerate(new_items):
        if not item["image"]:
            print(f"  [{i+1}] Пропуск (нет картинки)")
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
                print(f"  [{i+1}] ✅ Отправлено")
            else:
                print(f"  [{i+1}] ❌ {res.text}")
        except Exception as e:
            print(f"  [{i+1}] ❌ Ошибка: {e}")
        
        time.sleep(1)
    
    print(f"\n🎉 Готово! Отправлено: {len([x for x in new_items if x['image']])}")
else:
    print("\n⚠️ Нечего отправлять")

# Сохранение
if posted_ids:
    with open("posted_ids.json", "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
