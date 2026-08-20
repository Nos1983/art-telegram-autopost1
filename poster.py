import feedparser
import requests
import json
import os
import time
import random
import re
import html
import urllib.parse

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "1"))

print("🎨 Постер современного искусства (Artsy)")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except Exception:
        posted_ids = []

def translate(text):
    """Перевод en→ru"""
    if not text:
        return ""
    text = text.strip()
    try:
        q = urllib.parse.quote(text)
        r = requests.get(
            f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={q}",
            timeout=8)
        if r.status_code == 200:
            out = r.json()[0][0][0]
            if out:
                return out
    except Exception:
        pass
    return text

def extract_image_url(entry):
    """Ищет картинку в RSS"""
    # media:thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    
    # media:content
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            u = m.get('url', '')
            if u and (u.endswith(('.jpg','.png','.jpeg','.webp')) or 'artsy' in u):
                return u
    
    # Ищем в HTML
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    m = re.search(r'<img[^>]+src="([^"]+)"', content)
    return m.group(1) if m else None

def download_image(url):
    """Скачивает картинку"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"   ⚠️ Не скачалась: {e}")
        return None

# 🔥 Загрузка RSS
rss_url = "https://www.artsy.net/articles.rss"
print(f"📥 Загружаю: {rss_url}")

try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(rss_url, headers=headers, timeout=15)
    feed = feedparser.parse(r.text)
except Exception as e:
    print(f"❌ Ошибка RSS: {e}")
    feed = feedparser.parse(rss_url, request_headers={'User-Agent': 'Mozilla/5.0'})

print(f"📊 Найдено записей: {len(feed.entries)}")

# Фильтруем новые
new_entries = []
for entry in feed.entries:
    item_id = entry.get("id", entry.get("link", ""))
    if item_id and item_id not in posted_ids:
        image_url = extract_image_url(entry)
        if image_url:
            new_entries.append(entry)

if not new_entries:
    print("⚠️ Новых записей с картинками нет")
    with open("posted_ids.json", "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
    exit(0)

print(f"✅ Новых с картинками: {len(new_entries)}")

# Берём нужное количество
entries_to_post = new_entries[:POSTS_PER_RUN]

sent = 0
for i, entry in enumerate(entries_to_post):
    title = entry.get("title", "Без названия")
    item_id = entry.get("id", entry.get("link", ""))
    
    print(f"\n[{i+1}] {title[:50]}...")
    
    # Картинка
    image_url = extract_image_url(entry)
    if not image_url:
        print("   ⚠️ Нет картинки")
        continue
    
    print(f"   🖼️ {image_url[:60]}...")
    
    # Скачиваем картинку
    print("   📥 Скачиваю...")
    image_data = download_image(image_url)
    if not image_data:
        continue
    
    print(f"   ✅ Скачано: {len(image_data)} байт")
    
    # Переводим заголовок
    title_ru = translate(title)
    
    # Подпись на русском, БЕЗ ссылки
    esc = html.escape
    caption = f"🎨 <b>{esc(title_ru)}</b>\n\n"
    caption += "#современноеискусство #арт #выставка"
    
    # Отправка
    print("   📤 Отправляю...")
    res = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
        files={"photo": ("art.jpg", image_data, "image/jpeg")},
        timeout=60
    )
    
    if res.status_code == 200:
        posted_ids.append(item_id)
        sent += 1
        print("   ✅ Отправлено!")
    else:
        print(f"   ❌ {res.text[:80]}")
    
    time.sleep(1)

with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"\n🎉 Отправлено: {sent}")
