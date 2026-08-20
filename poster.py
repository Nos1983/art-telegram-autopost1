import requests
import json
import os
import re
import time
import random
import html
import hashlib
import urllib.parse

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "1"))
STATE_FILE = "posted_ids.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ================= СЛУЖЕБНОЕ =================

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_state(ids):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, indent=2)

def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()

def clean_filename(t):
    t = t.replace("File:", "")
    t = re.sub(r"\.[A-Za-z0-9]+$", "", t)
    return t.replace("_", " ").strip()

def extract_year(s):
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", s or "")
    return m.group(1) if m else ""

def translate(text):
    """en→ru. Возвращает None, если оба сервиса недоступны."""
    if not text or not text.strip():
        return None
    text = text.strip()
    try:
        q = urllib.parse.quote(text[:450])
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q=" + q,
            timeout=8)
        if r.status_code == 200:
            out = r.json()[0][0][0]
            if out:
                return out.strip()
    except Exception:
        pass
    try:
        r = requests.get("https://api.mymemory.translated.net/get",
                         params={"q": text[:450], "langpair": "en|ru"}, timeout=8)
        if r.status_code == 200:
            out = r.json().get("responseData", {}).get("translatedText", "")
            if out and "MYMEMORY" not in out.upper():
                return out.strip()
    except Exception:
        pass
    return None

def download(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        if len(r.content) < 2000:
            return None
        return r.content
    except Exception as e:
        print(f"   ⚠️ Не удалось скачать картинку: {e}")
        return None

# ================= ИСТОЧНИКИ =================

def source_commons(limit=20):
    """A) Wikimedia Commons — проверенные категории, без ключа."""
    items = []
    cats = ["Category:21st-century_paintings", "Category:20th-century_paintings"]
    for cat in cats:
        try:
            r = requests.get("https://commons.wikimedia.org/w/api.php", params={
                "action": "query", "format": "json",
                "generator": "categorymembers", "gcmtitle": cat,
                "gcmtype": "file", "gcmlimit": limit,
                "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1200,
            }, headers=HEADERS, timeout=20)
            pages = (r.json().get("query") or {}).get("pages") or {}
            for page in pages.values():
                info = (page.get("imageinfo") or [{}])[0]
                meta = info.get("extmetadata") or {}
                image_url = info.get("thumburl") or info.get("url")
                if not image_url:
                    continue
                title = strip_html((meta.get("ObjectName") or {}).get("value")) \
                        or clean_filename(page.get("title", ""))
                artist = strip_html((meta.get("Artist") or {}).get("value"))
                desc = strip_html((meta.get("ImageDescription") or {}).get("value"))
                year = extract_year(strip_html((meta.get("DateTimeOriginal") or {}).get("value")) or title)
                medium = ""
                low = (desc + " " + title).lower()
                for eng in ["oil on canvas", "watercolor", "bronze", "acrylic", "collage", "charcoal", "photograph"]:
                    if eng in low:
                        medium = eng
                        break
                items.append({"id": "commons:" + str(page.get("pageid")), "title": title,
                              "artist": artist, "year": year, "medium": medium,
                              "description": desc, "image_url": image_url})
            if items:
                break
        except Exception as e:
            print(f"⚠️ Commons ошибка: {e}")
    return items

def source_aic(limit=10):
    """B) Art Institute of Chicago — без ключа, отдел Modern and Contemporary Art."""
    items = []
    try:
        r = requests.get("https://api.artic.edu/api/v1/artworks", params={
            "limit": 100, "page": random.randint(1, 300),
            "fields": "id,title,artist_display,date_display,medium_display,image_id,department_title",
        }, headers=HEADERS, timeout=20)
        for a in r.json().get("data", []):
            if not a.get("image_id") or a.get("department_title") != "Modern and Contemporary Art":
                continue
            items.append({
                "id": "aic:" + str(a["id"]),
                "title": a.get("title") or "Untitled",
                "artist": (a.get("artist_display") or "").split("\n")[0],
                "year": a.get("date_display") or "",
                "medium": a.get("medium_display") or "",
                "description": "",
                "image_url": f"https://www.artic.edu/iiif/2/{a['image_id']}/full/1200,/0/default.jpg",
            })
            if len(items) >= limit:
                break
    except Exception as e:
        print(f"⚠️ AIC ошибка: {e}")
    return items

def source_met(limit=10):
    """C) The Met — только /objects и /objects/{id} (без /search)."""
    items = []
    try:
        r = requests.get("https://collectionapi.metmuseum.org/public/collection/v1/objects", timeout=20)
        ids = r.json().get("objectIDs", [])
        random.shuffle(ids)
        for oid in ids:
            if len(items) >= limit:
                break
            try:
                d = requests.get(
                    f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}",
                    timeout=10).json()
            except Exception:
                continue
            if d.get("departmentId") != 21 or not d.get("primaryImage"):
                continue
            items.append({
                "id": "met:" + str(oid),
                "title": d.get("title") or "Untitled",
                "artist": d.get("artistDisplayName") or "",
                "year": d.get("objectDate") or "",
                "medium": d.get("medium") or "",
                "description": "",
                "image_url": d["primaryImage"],
            })
            time.sleep(0.15)
    except Exception as e:
        print(f"⚠️ Met ошибка: {e}")
    return items

# ================= ПОДПИСЬ =================

def compose_description(art, title_ru):
    """Уникальное 📖-описание из данных работы (3 варианта по хешу ID)."""
    artist = art.get("artist") or "автор"
    year = art.get("year") or "XX век"
    medium = art.get("medium") or ""
    med = f"Материал: {medium}. " if medium else ""
    h = int(hashlib.md5(art["id"].encode()).hexdigest(), 16)
    variants = [
        f"Работа «{title_ru}» создана художником {artist}, {year}. {med}"
        f"Образный строй и колорит отражают поиски нового визуального языка, характерные для современного искусства.",
        f"В произведении «{title_ru}» ({year}) {artist} выстраивает диалог со зрителем о памяти, времени и месте человека в меняющемся мире. {med}",
        f"«{title_ru}» — пример того, как {artist} переосмысляет традиции жанра, обращаясь к темам идентичности, пространства и формы. {med}",
    ]
    return variants[h % len(variants)]

def build_caption(art):
    title_ru = translate(art["title"])
    if not title_ru:          # перевод недоступен — английский не постим
        return None
    lines = [f"🎨 <b>{html.escape(title_ru)}</b>", ""]
    if art.get("artist"):
        lines.append(f"👨‍🎨 Художник: {html.escape(translate(art['artist']) or art['artist'])}")
    if art.get("year"):
        lines.append(f"📅 Год: {html.escape(str(art['year']))}")
    if art.get("medium"):
        lines.append(f"🖌️ Техника: {html.escape(translate(art['medium']) or art['medium'])}")
    desc = art.get("description") or ""
    desc_ru = translate(desc[:400]) if len(desc) > 60 else None
    if not desc_ru:
        desc_ru = compose_description(art, title_ru)
    lines += ["", f"📖 {html.escape(desc_ru)}", "", "#современноеискусство #арт"]
    return "\n".join(lines)[:1000]

# ================= ОТПРАВКА =================

def send_photo(image_data, caption):
    return requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
        files={"photo": ("art.jpg", image_data, "image/jpeg")},
        timeout=60)

def main():
    print("🎨 Автопостер современного искусства")
    posted = load_state()
    print(f"📚 В памяти: {len(posted)} ID")

    candidates = []
    for name, fn in [("Commons", source_commons), ("AIC", source_aic), ("Met", source_met)]:
        print(f"🔎 Источник: {name}...")
        got = [c for c in fn() if c["id"] not in posted]
        print(f"   новых работ: {len(got)}")
        candidates += got
        if len(candidates) >= 3:
            break

    if not candidates:
        print("ℹ️ Новых работ нет. Завершаюсь без ошибки.")
        save_state(posted)
        return

    sent = 0
    for art in candidates:
        if sent >= POSTS_PER_RUN:
            break
        print(f"🎨 Готовлю: {art['title'][:50]}")
        caption = build_caption(art)
        if not caption:
            print("   ⚠️ Перевод недоступен — пропускаю работу")
            continue
        img = download(art["image_url"])
        if not img:
            continue
        res = send_photo(img, caption)
        if res.status_code == 200:
            posted.append(art["id"])
            sent += 1
            print("   ✅ Отправлено")
        else:
            print(f"   ❌ Telegram: {res.text[:100]}")
        time.sleep(1)

    print(f"🎉 Отправлено: {sent}")
    save_state(posted)          # создаётся ВСЕГДА
    print(f"💾 Сохранено ID: {len(posted)}")

main()
