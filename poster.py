import feedparser
import requests
import json
import os
import re
import time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_URL = os.getenv("RSS_URL")
HF_TOKEN = os.getenv("HF_TOKEN")

print(f"🔍 Загружаю: {RSS_URL}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    with open("posted_ids.json", "r", encoding="utf-8") as f:
        try: posted_ids = json.load(f)
        except: posted_ids = []

# Парсинг
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
feed = feedparser.parse(RSS_URL, request_headers=headers)

print(f"📊 Записей в RSS: {len(feed.entries)}")

if len(feed.entries) == 0:
    print("⚠️ RSS пуст")
    exit(0)

def extract_image_url(entry):
    """Извлекает ПРЯМУЮ ссылку на картинку из Reddit RSS"""
    
    # 1. media:thumbnail (Reddit часто кладёт сюда)
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        thumb_url = entry.media_thumbnail[0].get('url', '')
        # Заменяем превью на полную версию
        if 'preview.redd.it' in thumb_url:
            return thumb_url.replace('preview.redd.it', 'i.redd.it').split('?')[0]
        return thumb_url
    
    # 2. media:content
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            url = media.get('url', '')
            if url and ('i.redd.it' in url or '.jpg' in url or '.png' in url):
                return url
    
    # 3. Ищем в описании (content/summary)
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    
    # Ищем img с прямыми ссылками на Reddit
    img_patterns = [
        r'https://i\.redd\.it/[^\s"\'>]+',
        r'https://preview\.redd\.it/[^\s"\'>]+',
        r'<img[^>]+src="(https?://[^\"]+\.(?:jpg|jpeg|png|gif))"'
    ]
    
    for pattern in img_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            url = match.group(0) if 'i.redd.it' in match.group(0) else match.group(1)
            # Нормализуем URL
            url = url.replace('preview.redd.it', 'i.redd.it').split('?')[0]
            return url
    
    # 4. Ссылка на сам пост Reddit (можно скачать через API, но это сложнее)
    return None

def download_and_upload_image(image_url):
    """Скачивает картинку и возвращает как файл (для надёжности)"""
    try:
        response = requests.get(image_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if response.status_code == 200:
            return response.content
    except:
        pass
    return None

new_items = []
print("\n Обрабатываю...")

for i, entry in enumerate(feed.entries[:5]):  # Берём 5 постов
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title = entry.get("title", "Без названия")
    link = entry.get("link", "")
    image_url = extract_image_url(entry)
    
    print(f"  [{i+1}] {title[:30]}...")
    if image_url:
        print(f"      🖼️ {image_url[:60]}...")
    else:
        print(f"      ✗ нет картинки")
    
    # Формируем текст
    text = f"""🎨 <b>{title}</b>

<a href="{link}">Открыть пост на Reddit</a>

#современноеискусство #арт #reddit"""

    new_items.append({
        "id": item_id,
        "text": text,
        "image_url": image_url
    })
    
    time.sleep(1)

# Отправка
if new_items:
    print(f"\n📤 Отправляю...")
    
    url_text = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    sent_count = 0
    for i, item in enumerate(new_items):
        if item["image_url"]:
            # Пробуем отправить с картинкой
            try:
                # Метод 1: Отправляем URL напрямую
                res = requests.post(url_photo, json={
                    "chat_id": CHAT_ID,
                    "photo": item["image_url"],
                    "caption": item["text"],
                    "parse_mode": "HTML"
                }, timeout=30)
                
                if res.status_code == 200:
                    posted_ids.append(item["id"])
                    print(f"  [{i+1}] ✅ С картинкой (URL)")
                    sent_count += 1
                else:
                    err = res.text
                    print(f"  [{i+1}] ️ URL не сработал: {err[:50]}")
                    
                    # Метод 2: Скачиваем и отправляем как файл
                    img_data = download_and_upload_image(item["image_url"])
                    if img_data:
                        res = requests.post(url_photo, data={
                            "chat_id": CHAT_ID,
                            "caption": item["text"],
                            "parse_mode": "HTML"
                        }, files={"photo": ("image.jpg", img_data, "image/jpeg")}, timeout=30)
                        
                        if res.status_code == 200:
                            posted_ids.append(item["id"])
                            print(f"  [{i+1}] ✅ С картинкой (файл)")
                            sent_count += 1
                        else:
                            print(f"  [{i+1}] ❌ Файл не отправлен: {res.text[:50]}")
                    else:
                        print(f"  [{i+1}] ❌ Не удалось скачать картинку")
                        
            except Exception as e:
                print(f"  [{i+1}] ❌ Ошибка: {e}")
        else:
            # Отправляем только текст
            res = requests.post(url_text, json={
                "chat_id": CHAT_ID,
                "text": item["text"],
                "parse_mode": "HTML"
            }, timeout=10)
            
            if res.status_code == 200:
                posted_ids.append(item["id"])
                print(f"  [{i+1}] ✅ Текст")
                sent_count += 1
            else:
                print(f"  [{i+1}] ❌ Текст: {res.text[:50]}")
        
        time.sleep(1)
    
    print(f"\n🎉 Отправлено: {sent_count}/{len(new_items)}")

# Сохранение
if posted_ids:
    with open("posted_ids.json", "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
    print(f"💾 Сохранено ID: {len(posted_ids)}")
