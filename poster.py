import requests
import json
import os
import time
import random
import html
import urllib.parse

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "1"))

print("🎨 Постер современного искусства")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except Exception:
        posted_ids = []

def translate(text):
    """Перевод en→ru (Google + запасной MyMemory)"""
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
    try:
        r = requests.get("https://api.mymemory.translated.net/get",
                         params={"q": text[:450], "langpair": "en|ru"}, timeout=8)
        if r.status_code == 200:
            out = r.json().get("responseData", {}).get("translatedText", "")
            if out:
                return out
    except Exception:
        pass
    return text

def fetch_modern_art_ids():
    """Отдел Modern and Contemporary Art (id=21), только с картинками"""
    url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
    r = requests.get(url, params={"departmentId": 21, "hasImages": "true"}, timeout=20)
    r.raise_for_status()
    return r.json().get("objectIDs", [])

def get_artwork(oid):
    url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        return r.json()
    return None

def download_image(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception:
        return None

# 🔥 Основной запуск
print("📥 Ищу работы современного искусства...")
try:
    all_ids = fetch_modern_art_ids()
except Exception as e:
    print(f"❌ Ошибка API: {e}")
    all_ids = []

print(f"📊 Найдено работ: {len(all_ids)}")

new_ids = [i for i in all_ids if i not in posted_ids]
if not new_ids:
    print("⚠️ Новых работ нет")
    with open("posted_ids.json", "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
    exit(0)

selected = random.sample(new_ids, min(10, len(new_ids)))

sent = 0
for oid in selected:
    if sent >= POSTS_PER_RUN:
        break

    art = get_artwork(oid)
    if not art or not art.get("primaryImage"):
        continue

    title = art.get("title", "")
    artist = art.get("artistDisplayName", "")
    date = art.get("objectDate", "")
    medium = art.get("medium", "")

    print(f"🎨 {title[:40]}...")

    # Переводим на русский
    title_ru = translate(title)
    artist_ru = translate(artist) if artist and artist != "Unknown" else ""
    medium_ru = translate(medium) if medium else ""

    # Скачиваем картинку САМИ (обход ошибки Telegram)
    image_data = download_image(art["primaryImage"])
    if not image_data:
        image_data = download_image(art.get("primaryImageSmall", ""))
    if not image_data:
        print("   ⚠️ Не скачалась картинка, пропускаю")
        continue

    # Подпись на русском, БЕЗ ссылки на источник
    esc = html.escape
    caption = f"🎨 <b>{esc(title_ru)}</b>\n\n"
    if artist_ru:
        caption += f"👨‍🎨 Художник: {esc(artist_ru)}\n"
    if date:
        caption += f"📅 Дата: {esc(date)}\n"
    if medium_ru:
        caption += f"🖌️ Техника: {esc(medium_ru)}\n"
    caption += "\n#современноеискусство #арт"

    # Отправка как файл
    res = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
        files={"photo": ("art.jpg", image_data, "image/jpeg")},
        timeout=60
    )

    if res.status_code == 200:
        posted_ids.append(oid)
        sent += 1
        print("   ✅ Отправлено!")
    else:
        print(f"   ❌ {res.text[:80]}")

    time.sleep(1)

with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"\n🎉 Отправлено: {sent}")
