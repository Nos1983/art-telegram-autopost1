import feedparser
import requests
import json
import os
import re
import time
import sys

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_URL = os.getenv("RSS_URL", "https://www.reddit.com/r/ContemporaryArt/.rss")
HF_TOKEN = os.getenv("HF_TOKEN")

print(f"🔍 Загружаю: {RSS_URL}")
print(f"🔑 BOT: {'✅' if BOT_TOKEN else '❌'} | CHAT: {CHAT_ID[:20] if CHAT_ID else '❌'}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
        print(f"📚 Загружено {len(posted_ids)} ID из памяти")
    except: posted_ids = []

# 🔥 Надёжная загрузка RSS через requests
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*'
}

feed = feedparser.parse("")
try:
    r = requests.get(RSS_URL, headers=headers, timeout=15)
    r.raise_for_status()
    print(f"✅ RSS получен: {len(r.text)} байт")
    feed = feedparser.parse(r.text)
except Exception as e:
    print(f"⚠️ Ошибка прямой загрузки: {e}. Пробую fallback...")
    feed = feedparser.parse(RSS_URL, request_headers=headers)

print(f"📊 Записей в RSS: {len(feed.entries)}")

if len(feed.entries) == 0:
    print("💡 RSS пуст или заблокирован. Попробуй в секрете другую ссылку:")
    print("   https://hyperallergic.com/feed/  или  https://www.artsy.net/articles.rss")

def extract_image_url(entry):
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '').replace('preview.redd.it', 'i.redd.it').split('?')[0]
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            u = m.get('url', '')
            if u and ('i.redd.it' in u or u.endswith(('.jpg','.png','.jpeg'))): return u
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    m = re.search(r'https://i\.redd\.it/[^\s"\'>]+', content)
    return m.group(0).split('?')[0] if m else None

new_items = []
for i, entry in enumerate(feed.entries[:5]):
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids: continue

    title = entry.get("title", "Без названия")
    link = entry.get("link", "")
    img = extract_image_url(entry)
    print(f"  [{i+1}] {'🖼️' if img else '📝'} {title[:35]}...")

    text = f"""🎨 <b>{title}</b>\n\n<a href="{link}">Источник</a>\n\n#арт #современноеискусство"""
    new_items.append({"id": item_id, "text": text, "image": img})
    time.sleep(0.5)

# Отправка
sent = 0
if new_items:
    print(f"\n📤 Отправляю {len(new_items)} постов...")
    for i, item in enumerate(new_items):
        try:
            if item["image"]:
                res = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", json={
                    "chat_id": CHAT_ID, "photo": item["image"], "caption": item["text"], "parse_mode": "HTML"
                }, timeout=30)
            else:
                res = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    "chat_id": CHAT_ID, "text": item["text"], "parse_mode": "HTML"
                }, timeout=15)
                
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
    print("\n⚠️ Новых постов нет (или RSS пуст)")

# 🔒 ВСЕГДА сохраняем файл, чтобы Git не падал
with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)
print(f"💾 Сохранено {len(posted_ids)} ID")
