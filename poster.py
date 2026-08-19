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

# 📚 Источники С КАРТИНКАМИ (проверено)
RSS_SOURCES = [
    "https://www.artsy.net/articles.rss",           # ✅ Отличные картинки
    "https://hyperallergic.com/feed/",              # ✅ Хорошие картинки
    "https://www.tate.org.uk/rss",                  # ✅ Музейные работы
    "https://www.artnews.com/feed/",                # ✅ Картинки есть
    "https://www.moma.org/magazine/articles/feed",  # ✅ MoMA коллекции
    "https://artasiapacific.com/rss",               # ✅ Азиатское искусство
]

print(f"📚 Источников: {len(RSS_SOURCES)}")
print(f" AI: {'✅' if HF_TOKEN else '⚠️'}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except: posted_ids = []

def extract_image_url(entry):
    """Усиленный поиск картинки в RSS"""
    image_url = None
    
    # 1. media:thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        image_url = entry.media_thumbnail[0].get('url', '')
        if image_url:
            return image_url
    
    # 2. media:content (приоритет на изображения)
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            url = m.get('url', '')
            media_type = m.get('type', '')
            
            # Приоритет на изображения
            if media_type.startswith('image/') or url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return url
    
    # 3. enclosure
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            url = enc.get('href', '')
            if enc.get('type', '').startswith('image/') or url.endswith(('.jpg', '.jpeg', '.png')):
                return url
    
    # 4. Ищем в content/summary HTML
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    
    # Ищем <img> теги
    img_patterns = [
        r'<img[^>]+src="([^"]+)"',
        r'<img[^>]+src=\'([^\']+)\'',
    ]
    
    for pattern in img_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            # Возвращаем первую подходящую картинку
            for img_url in matches:
                # Пропускаем маленькие иконки
                if not any(x in img_url.lower() for x in ['icon', 'logo', 'pixel', 'spacer']):
                    return img_url
    
    # 5. Ищем в description
    if hasattr(entry, 'description'):
        desc_matches = re.findall(r'<img[^>]+src="([^"]+)"', entry.description, re.IGNORECASE)
        if desc_matches:
            return desc_matches[0]
    
    # 6. Проверяем image поле
    if hasattr(entry, 'image'):
        img = entry.image
        if isinstance(img, dict):
            return img.get('href', '') or img.get('url', '')
        elif isinstance(img, str):
            return img
    
    return None

def extract_art_info(content_text, title):
    """Извлекает информацию"""
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
        filtered = [n for n in name_matches if n.lower() not in ['the art', 'new york', 'los angeles']]
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
    museum_match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+(?:Museum|Gallery|Biennale)', content_text)
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
        'culture': 'культура'
    }
    
    first_para = content_text.split('\n\n')[0] if '\n\n' in content_text else content_text[:300]
    found_themes = [theme for eng, theme in themes.items() if eng in first_para.lower()]
    
    if found_themes:
        info['meaning'] = f"Исследует: {', '.join(found_themes[:2])}"
    
    return info

def analyze_image(image_url):
    """AI-анализ"""
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

def create_description(info, ai_desc):
    """Создаёт описание"""
    parts = []
    
    if info['artist']:
        parts.append(f"👨‍🎨 **{info['artist']}**")
    
    if ai_desc:
        parts.append(f"🖼️ {ai_desc}")
    
    if info['technique']:
        parts.append(f"🎨 {info['technique']}")
    
    if info['style']:
        parts.append(f"🎭 {info['style']}")
    
    if info['exhibition']:
        parts.append(f"🏛️ {info['exhibition']}")
    
    if info['year']:
        parts.append(f" {info['year']}")
    
    if info['meaning']:
        parts.append(f" {info['meaning']}")
    
    return "\n".join(parts) if parts else "Произведение современного искусства"

# Собираем все записи
all_entries = []
print("\n📥 Загружаю источники...")

for i, rss_url in enumerate(RSS_SOURCES):
    try:
        print(f"  [{i+1}/{len(RSS_SOURCES)}] {rss_url[:45]}...")
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(rss_url, headers=headers, timeout=10)
        feed = feedparser.parse(r.text)
        
        entries_with_images = 0
        for entry in feed.entries:
            img = extract_image_url(entry)
            if img:
                entries_with_images += 1
                entry['_source'] = rss_url
                all_entries.append(entry)
        
        print(f"      ✅ {len(feed.entries)} записей, {entries_with_images} с картинками")
        time.sleep(1)
        
    except Exception as e:
        print(f"      ❌ Ошибка: {e}")

print(f"\n📊 Найдено записей С КАРТИНКАМИ: {len(all_entries)}")

if len(all_entries) == 0:
    print("⚠️ Не найдено постов с картинками!")
    print("💡 Попробую загрузить без фильтра...")
    
    # Пробуем без фильтра
    for rss_url in RSS_SOURCES[:2]:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(rss_url, headers=headers, timeout=10)
            feed = feedparser.parse(r.text)
            for entry in feed.entries[:3]:
                entry['_source'] = rss_url
                all_entries.append(entry)
        except:
            pass

# Берём 3-5 свежих
entries_to_process = all_entries[:5]

# Обработка
new_items = []
print("\n Обрабатываю...")

for i, entry in enumerate(entries_to_process):
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title = entry.get("title", "Без названия")
    content_text = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    image_url = extract_image_url(entry)
    source = entry.get('_source', 'Unknown')
    
    #  ВАЖНО: Пропускаем без картинок!
    if not image_url:
        print(f"\n  [{i+1}] ⏭️ Пропущено (нет картинки): {title[:30]}...")
        continue
    
    print(f"\n  [{i+1}] {title[:40]}...")
    print(f"      ️ {image_url[:60]}...")
    print(f"      📰 {source[:50]}")
    
    # Информация
    art_info = extract_art_info(content_text, title)
    
    # AI
    print(f"      🤖 AI-анализ...")
    ai_desc = analyze_image(image_url)
    if ai_desc:
        print(f"      ✅ {ai_desc}")
    
    # Описание
    description = create_description(art_info, ai_desc)
    
    # Пост
    post_text = f"""🎨 <b>{title}</b>

{description}

#современноеискусство #арт #выставка"""

    new_items.append({
        "id": item_id,
        "text": post_text,
        "image": image_url
    })
    
    time.sleep(2)

# Отправка (ТОЛЬКО с картинками!)
sent = 0
if new_items:
    print(f"\n📤 Отправляю {len(new_items)} постов С КАРТИНКАМИ...")
    
    for i, item in enumerate(new_items):
        try:
            print(f"  [{i+1}] Отправка картинки...")
            
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
            
            if res.status_code == 200:
                posted_ids.append(item["id"])
                sent += 1
                print(f"      ✅ Успешно!")
            else:
                print(f"      ❌ {res.text[:80]}")
                
                # Пробуем скачать и отправить как файл
                try:
                    img_data = requests.get(item["image"], timeout=10).content
                    res = requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        data={"chat_id": CHAT_ID, "caption": item["text"]},
                        files={"photo": ("art.jpg", img_data, "image/jpeg")},
                        timeout=30
                    )
                    if res.status_code == 200:
                        posted_ids.append(item["id"])
                        sent += 1
                        print(f"      ✅ Отправлено как файл!")
                except:
                    pass
                    
        except Exception as e:
            print(f"      ❌ Ошибка: {e}")
        
        time.sleep(1)
    
    print(f"\n🎉 Отправлено: {sent}/{len(new_items)}")
else:
    print("\n⚠️ Нечего отправлять (нет постов с картинками)")

# Сохранение
with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"💾 Сохранено {len(posted_ids)} ID")
