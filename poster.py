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
STATE_FILE = "posted_ids.json"

if not RSS_URL:
    print("❌ Ошибка: RSS_URL не задан!")
    exit(1)

print(f"🔍 Загружаю: {RSS_URL}")

# Загрузка ID
posted_ids = []
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        try: posted_ids = json.load(f)
        except: posted_ids = []

# Парсинг с заголовками браузера
feed = feedparser.parse(RSS_URL, request_headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

print(f"📊 Записей в RSS: {len(feed.entries)}")

if len(feed.entries) == 0:
    print("⚠️ RSS пуст — проверь ссылку в браузере")
    exit(0)

# Очистка текста
def clean(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.escape(text)
    return text.strip()[:400]

new_items = []
for entry in feed.entries:
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title = clean(entry.get("title", ""))
    # Reddit часто кладёт контент в 'content' или 'summary'
    desc = clean(entry.get("content", [{}])[0].get("value", "") or entry.get("summary", ""))
    link = entry.get("link", "")
    date = clean(entry.get("published", ""))

    # 🎨 Шаблон поста
    text = f"""🎨 {title}

{desc}...

🔗 {link}
📅 {date}

#современноеискусство #арт #выставка"""

    new_items.append({"id": item_id, "text": text})

# Отправка в Telegram
if new_items:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for item in new_items:
        res = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": item["text"]
        })
        if res.status_code == 200:
            posted_ids.append(item["id"])
            print(f"✅ Отправлено: {item['id'][:40]}")
        else:
            print(f"❌ Telegram: {res.text}")
            time.sleep(1)
    print(f"🎉 Опубликовано: {len(new_items)}")
else:
    print("ℹ️ Новых постов нет")

# Сохранение состояния
if posted_ids:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
    print(f"💾 Сохранено ID: {len(posted_ids)}")
