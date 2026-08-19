import feedparser
import requests
import json
import os
import html
import re

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_URL = os.getenv("RSS_URL", "https://theartnewspaper.ru/feed")
STATE_FILE = "posted_ids.json"

print(f"🔍 Загружаю: {RSS_URL}")
feed = feedparser.parse(RSS_URL)
print(f"📊 Найдено записей в RSS: {len(feed.entries)}")

# Если записей 0, выводим статус парсера
if len(feed.entries) == 0:
    print("⚠️ RSS пуст или не распарсен. Проверь:")
    print("   - Открывается ли ссылка в браузере как XML?")
    print("   - Нет ли капчи/блокировки на сайте?")
    exit()

# Выводим первую запись для проверки
first = feed.entries[0]
print(f"✅ Первая запись найдена: {first.get('title', 'Без заголовка')}")
print(f"🔗 Ссылка: {first.get('link', 'Нет')}")
