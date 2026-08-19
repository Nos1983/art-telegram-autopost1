import feedparser
import requests
import json
import os
import re
import time
import random

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")

# 📚 Список RSS источников (добавляй/удаляй по желанию)
RSS_SOURCES = [
    "https://hyperallergic.com/feed/",
    "https://www.artsy.net/articles.rss",
    "https://www.tate.org.uk/rss",
    "https://www.artforum.com/news/rss",
    "https://www.artnews.com/feed/",
    "https://www.moma.org/magazine/articles/feed",
    "https://whitney.org/feed",
    "https://www.e-flux.com/notes/rss"
]

print(f"📚 Источников: {len(RSS_SOURCES)}")
print(f"🤖 AI: {'✅' if HF_TOKEN else '⚠️ Без HF_TOKEN'}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except: posted_ids = []

def extract_art_info(content_text, title):
    """Извлекает информацию об искусстве"""
    info = {
        'artist': None, 'technique': None, 'style': None,
        'meaning': None, 'exhibition': None, 'year': None
    }
    
    if not content_text:
        return info
    
    text = content_text.lower()
    
    # Художник
    name_matches = re.findall(r'\b([A-Z][a-z]{2,}\s[A-Z][a-z]{2,})\b', content_text[:500])
    if name_matches:
        filtered = [n for n in name_matches if n.lower() not in ['the art', 'new york', 'los angeles', 'the whitney']]
        if filtered:
            info['artist'] = filtered[0]
    
    # Техника
    techniques = {
        'oil on canvas': 'масло на холсте',
        'oil painting': 'масляная живопись',
        'acrylic': 'акрил',
        'watercolor': 'акварель',
        'sculpture': 'скульптура',
        'bronze': 'бронза',
        'installation': 'инсталляция',
        'video installation': 'видеоинсталляция',
        'photograph': 'фотография',
        'digital art': 'цифровое искусство',
        'mixed media': 'смешанная техника',
        'charcoal': 'уголь',
        'pastel': 'пастель',
        'collage': 'коллаж',
        'performance': 'перформанс'
    }
    
    for eng, rus in techniques.items():
        if eng in text:
            info['technique'] = rus
            break
    
    # Стиль
    styles = {
        'abstract expressionism': 'абстрактный экспрессионизм',
        'abstract': 'абстракционизм',
        'surrealism': 'сюрреализм',
        'impressionism': 'импрессионизм',
        'minimalism': 'минимализм',
        'pop art': 'поп-арт',
        'contemporary art': 'современное искусство',
        'conceptual art': 'концептуализм',
        'expressionism': 'экспрессионизм'
    }
    
    for eng, rus in styles.items():
        if eng in text:
            info['style'] = rus
            break
    
    # Год
    year_match = re.search(r'\b(19|20)\d{2}\b', content_text)
    if year_match:
        info['year'] = year_match.group(0)
    
    # Выставка
    museum_match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+(?:Museum|Gallery|Biennale|Center)', content_text)
    if museum_match:
        info['exhibition'] = museum_match.group(0)
    
    # Темы
    themes = {
        'identity': 'идентичность',
        'memory': 'память',
        'politics': 'политика',
        'social': 'социальные вопросы',
        'gender': 'гендер',
        'environment': 'экология',
        'technology': 'технологии',
        'history': 'история',
        'culture': 'культура',
        'migration': 'миграция'
    }
    
    first_para = content_text.split('\n\n')[0] if '\n\n' in content_text else content_text[:300]
    found_themes = [theme for eng, theme in themes.items() if eng in first_para.lower()]
    
    if found_themes:
        info['meaning'] = f"Исследует темы: {', '.join(found_themes[:2])}"
    
    return info

def analyze_image(image_url):
    """AI-анализ изображения"""
    if not HF_TOKEN or not image_url:
        return None
    
    try:
        img_data = requests.get(image_url, timeout=10).content
        response = requests.post(
            "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            data=img_data,
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('generated_text', '')
    except:
        pass
    
    return None

def extract_image_url(entry):
    """Извлекает URL картинки"""
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            u = m.get('url', '')
            if u and (u.endswith(('.jpg','.png','.jpeg')) or 'i.redd.it' in u or 'artsy' in u):
                return u
    
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    m = re.search(r'<img[^>]+src="([^"]+)"', content)
    return m.group(1) if m else None

def create_description(info, ai_desc, title):
    """Создаёт описание"""
    parts = []
    
    if info['artist']:
        parts.append(f"👨‍ **{info['artist']}**")
    
    if ai_desc:
        parts.append(f"🖼️ {ai_desc}")
    
    if info['technique']:
        parts.append(f"🎨 {info['technique']}")
    
    if info['style']:
        parts.append(f"🎭 {info['style']}")
    
    if info['exhibition']:
        parts.append(f"🏛️ {info['exhibition']}")
    
    if info['year']:
        parts.append(f"📅 {info['year']}")
    
    if info['meaning']:
        parts.append(f"💭 {info['meaning']}")
    
    if not parts:
        return "Произведение современного искусства"
    
    return "\n".join(parts)

#  Перемешиваем источники для разнообразия
random.shuffle(RSS_SOURCES)

all_entries = []

print("\n📥 Загружаю источники...")

# Собираем все записи из всех RSS
for i, rss_url in enumerate(RSS_SOURCES):
    try:
        print(f"  [{i+1}/{len(RSS_SOURCES)}] {rss_url[:40]}...")
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(rss_url, headers=headers, timeout=10)
        feed = feedparser.parse(r.text)
        
        print(f"      ✅ {len(feed.entries)} записей")
        
        for entry in feed.entries:
            # Добавляем источник в entry для отладки
            entry['_source'] = rss_url
            all_entries.append(entry)
        
        time.sleep(1)  # Не спамим сервера
        
    except Exception as e:
        print(f"      ❌ Ошибка: {e}")

print(f"\n📊 Всего записей: {len(all_entries)}")

# Берём только 5 свежих (чтобы не долго)
entries_to_process = all_entries[:5]

# Обработка
new_items = []
print("\n🎨 Обрабатываю...")

for i, entry in enumerate(entries_to_process):
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title = entry.get("title", "Без названия")
    content_text = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    image_url = extract_image_url(entry)
    source = entry.get('_source', 'Unknown')
    
    print(f"\n  [{i+1}] {title[:40]}...")
    print(f"      📰 Источник: {source[:50]}")
    
    # Извлекаем информацию
    art_info = extract_art_info(content_text, title)
    
    # AI-анализ
    if image_url:
        print(f"      🤖 AI-анализ...")
        ai_desc = analyze_image(image_url)
        if ai_desc:
            print(f"      ✅ {ai_desc}")
    else:
        ai_desc = None
    
    # Описание
    description = create_description(art_info, ai_desc, title)
    
    # Пост
    post_text = f"""🎨 <b>{title}</b>

{description}

#современноеискусство #арт #выставка #художник"""

    new_items.append({
        "id": item_id,
        "text": post_text,
        "image": image_url,
        "source": source
    })
    
    time.sleep(2)

# Отправка
sent = 0
if new_items:
    print(f"\n📤 Отправляю {len(new_items)} постов...")
    
    for i, item in enumerate(new_items):
        try:
            if item["image"]:
                res = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    json={
                        "chat_id": CHAT_ID,
                        "photo": item["image"],
                        "caption": item["text"],
                        "parse_mode": "HTML"
                    },
                    timeout=30
                )
            else:
                res = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": CHAT_ID,
                        "text": item["text"],
                        "parse_mode": "HTML"
                    },
                    timeout=15
                )
            
            if res.status_code == 200:
                posted_ids.append(item["id"])
                sent += 1
                print(f"  ✅ [{i+1}] Отправлено")
            else:
                print(f"  ❌ [{i+1}] {res.text[:60]}")
        except Exception as e:
            print(f"  ❌ [{i+1}] {e}")
        
        time.sleep(1)
    
    print(f"\n🎉 Успешно: {sent}/{len(new_items)}")
else:
    print("\n⚠️ Нечего отправлять")

# Сохранение
with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"💾 Сохранено {len(posted_ids)} ID")
print(f"📚 Источников доступно: {len(RSS_SOURCES)}")
