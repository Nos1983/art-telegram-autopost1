import feedparser
import requests
import json
import os
import re
import time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_URL = os.getenv("RSS_URL")

print(f"🔍 Загружаю: {RSS_URL}")
print(f" BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
print(f"🔐 CHAT_ID: {CHAT_ID[:20] if CHAT_ID else '❌'}...")

# Загрузка ID
posted_ids = []
if os.path.exists("posted_ids.json"):
    with open("posted_ids.json", "r", encoding="utf-8") as f:
        try:
            posted_ids = json.load(f)
            print(f"📚 Загружено {len(posted_ids)} ID из памяти")
        except:
            posted_ids = []
else:
    print(" Файл posted_ids.json не найден (начинаю с нуля)")

# Парсинг
headers = {'User-Agent': 'Mozilla/5.0'}
feed = feedparser.parse(RSS_URL, request_headers=headers)

print(f"📊 Записей в RSS: {len(feed.entries)}")

if len(feed.entries) == 0:
    print("⚠️ RSS пуст")
    exit(0)

def extract_image_url(entry):
    """Ищет картинку"""
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get('url', '')
        return url.replace('preview.redd.it', 'i.redd.it').split('?')[0] if 'preview' in url else url
    
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            url = media.get('url', '')
            if url and ('i.redd.it' in url or '.jpg' in url):
                return url
    
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    match = re.search(r'https://i\.redd\.it/[^\s"\'>]+', content)
    if match:
        return match.group(0).split('?')[0]
    
    return None

new_items = []
skipped_ids = 0

print("\n🎨 Обрабатываю записи...")
for i, entry in enumerate(feed.entries[:10]):  # Берём 10 для теста
    item_id = entry.get("id", entry.get("link", ""))
    
    if not item_id:
        print(f"  [{i+1}] ✗ Нет ID, пропускаю")
        continue
    
    if item_id in posted_ids:
        skipped_ids += 1
        print(f"  [{i+1}] ⏭️ Уже отправлен")
        continue

    title = entry.get("title", "Без названия")
    image_url = extract_image_url(entry)
    link = entry.get("link", "")
    
    print(f"  [{i+1}] ✅ НОВЫЙ: {title[:30]}...")
    print(f"       {link[:50]}")
    print(f"      🖼️ {'Есть картинка' if image_url else 'Нет картинки'}")
    
    text = f""" <b>{title}</b>

<a href="{link}">Открыть на Reddit</a>

#арт #современноеискусство"""

    new_items.append({
        "id": item_id,
        "text": text,
        "image_url": image_url
    })
    
    time.sleep(0.5)

print(f"\n Итого:")
print(f"   Найдено новых: {len(new_items)}")
print(f"   Пропущено (уже есть): {skipped_ids}")

# Отправка
if new_items:
    print(f"\n Начинаю отправку...")
    
    url_text = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    sent = 0
    for i, item in enumerate(new_items):
        print(f"\n  [{i+1}] Отправляю...")
        
        try:
            if item["image_url"]:
                # С картинкой
                res = requests.post(url_photo, json={
                    "chat_id": CHAT_ID,
                    "photo": item["image_url"],
                    "caption": item["text"],
                    "parse_mode": "HTML"
                }, timeout=30)
                
                print(f"      Статус: {res.status_code}")
                if res.status_code == 200:
                    posted_ids.append(item["id"])
                    print(f"      ✅ УСПЕХ!")
                    sent += 1
                else:
                    print(f"       Ошибка: {res.text[:100]}")
            else:
                # Только текст
                res = requests.post(url_text, json={
                    "chat_id": CHAT_ID,
                    "text": item["text"],
                    "parse_mode": "HTML"
                }, timeout=10)
                
                print(f"      Статус: {res.status_code}")
                if res.status_code == 200:
                    posted_ids.append(item["id"])
                    print(f"      ✅ УСПЕХ (текст)!")
                    sent += 1
                else:
                    print(f"      ❌ Ошибка: {res.text[:100]}")
                    
        except Exception as e:
            print(f"      ❌ Исключение: {e}")
        
        time.sleep(1)
    
    print(f"\n Готово! Отправлено: {sent}/{len(new_items)}")
else:
    print("\n⚠️ Нечего отправлять (все посты уже были или RSS пуст)")

# Сохранение
if posted_ids:
    with open("posted_ids.json", "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
    print(f"💾 Сохранено {len(posted_ids)} ID")
