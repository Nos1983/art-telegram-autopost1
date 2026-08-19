import feedparser
import requests
import json
import os
import re

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_URL = os.getenv("RSS_URL", "https://theartnewspaper.ru/feed")
STATE_FILE = "posted_ids.json"

# Загрузка уже опубликованных ID
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        posted_ids = json.load(f)
else:
    posted_ids = []

feed = feedparser.parse(RSS_URL)

# Очистка HTML и обрезка описания
clean_html = lambda html: re.sub(r'<[^>]+>', '', html)[:250]

new_items = []
for entry in feed.entries:
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title = entry.get("title", "Без заголовка")
    desc = clean_html(entry.get("summary", entry.get("description", "")))
    link = entry.get("link", "")
    date = entry.get("published", "")

    # Твой шаблон поста
    text = f"""🎨 <b>{title}</b>

{desc}...

🔗 <a href="{link}">Читать полностью</a>
📅 {date}

#современноеискусство #арт #выставка"""

    new_items.append({"id": item_id, "text": text})

# Отправка в Telegram
if new_items:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for item in new_items:
        res = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": item["text"],
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        })
        if res.status_code == 200:
            posted_ids.append(item["id"])
        else:
            print(f"❌ Ошибка отправки: {res.text}")

# Сохранение состояния
with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"✅ Готово. Опубликовано: {len(new_items)}")
# Сохранение состояния (в конце файла)
try:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
    print(f"✅ Состояние сохранено ({len(posted_ids)} ID)")
except Exception as e:
    print(f"⚠️ Не удалось сохранить состояние: {e}")
    # Это не критично — посты всё равно ушли в Telegram
