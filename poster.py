import feedparser
import requests
import json
import os
import re
import time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RSS_URL = os.getenv("RSS_URL", "https://hyperallergic.com/feed/")
HF_TOKEN = os.getenv("HF_TOKEN")

print(f"🔍 Загружаю: {RSS_URL}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except: posted_ids = []

# Загрузка RSS
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    r = requests.get(RSS_URL, headers=headers, timeout=15)
    feed = feedparser.parse(r.text)
except:
    feed = feedparser.parse(RSS_URL, request_headers=headers)

print(f"📊 Записей в RSS: {len(feed.entries)}")

def extract_art_info(content_text, title):
    """Извлекает информацию об искусстве из текста статьи"""
    info = {
        'artist': None,
        'technique': None,
        'style': None,
        'meaning': None,
        'exhibition': None,
        'year': None
    }
    
    if not content_text:
        return info
    
    text = content_text.lower()
    
    #  Ищем имя художника (обычно в начале статьи)
    # Паттерн: "Имя Фамилия" с заглавных букв
    name_matches = re.findall(r'\b([A-Z][a-z]{2,}\s[A-Z][a-z]{2,})\b', content_text[:500])
    if name_matches:
        # Фильтруем общие слова
        filtered = [n for n in name_matches if n.lower() not in ['the art', 'new york', 'los angeles']]
        if filtered:
            info['artist'] = filtered[0]
    
    # 🎨 Техника и материалы
    techniques = {
        'oil on canvas': 'масло на холсте',
        'oil painting': 'масляная живопись',
        'acrylic on canvas': 'акрил на холсте',
        'watercolor': 'акварель',
        'sculpture': 'скульптура',
        'bronze sculpture': 'бронзовая скульптура',
        'installation': 'инсталляция',
        'video installation': 'видеоинсталляция',
        'photograph': 'фотография',
        'digital art': 'цифровое искусство',
        'mixed media': 'смешанная техника',
        'charcoal on paper': 'уголь на бумаге',
        'pastel': 'пастель',
        'ink': 'тушь',
        'collage': 'коллаж',
        'performance art': 'перформанс',
        'conceptual art': 'концептуальное искусство'
    }
    
    for eng, rus in techniques.items():
        if eng in text:
            info['technique'] = rus
            break
    
    #  Стиль/направление
    styles = {
        'abstract expressionism': 'абстрактный экспрессионизм',
        'abstract': 'абстракционизм',
        'surrealism': 'сюрреализм',
        'impressionism': 'импрессионизм',
        'expressionism': 'экспрессионизм',
        'minimalism': 'минимализм',
        'pop art': 'поп-арт',
        'contemporary art': 'современное искусство',
        'conceptual art': 'концептуализм',
        'postmodernism': 'постмодернизм',
        'fauvism': 'фовизм',
        'cubism': 'кубизм'
    }
    
    for eng, rus in styles.items():
        if eng in text:
            info['style'] = rus
            break
    
    # 📅 Год создания
    year_match = re.search(r'\b(19|20)\d{2}\b', content_text)
    if year_match:
        info['year'] = year_match.group(0)
    
    # ️ Выставка/музей
    museums = ['museum', 'gallery', 'biennale', 'exhibition', 'center']
    for museum in museums:
        if museum in text:
            # Ищем название перед словом museum/gallery
            match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+' + museum, content_text)
            if match:
                info['exhibition'] = match.group(0).title()
            break
    
    # 💭 Смысл/тема (ищем в первом абзаце)
    first_paragraph = content_text.split('\n\n')[0] if '\n\n' in content_text else content_text[:300]
    
    # Ищем ключевые темы
    themes = {
        'identity': 'идентичность и самопознание',
        'memory': 'память и воспоминания',
        'politics': 'политический комментарий',
        'social': 'социальная проблематика',
        'gender': 'гендерные вопросы',
        'race': 'расовая проблематика',
        'environment': 'экология и природа',
        'technology': 'технологии и будущее',
        'history': 'историческая рефлексия',
        'culture': 'культурная идентичность',
        'trauma': 'травма и исцеление',
        'migration': 'миграция и перемещение'
    }
    
    found_themes = [theme for eng, theme in themes.items() if eng in first_paragraph.lower()]
    if found_themes:
        info['meaning'] = f"Работа исследует темы: {', '.join(found_themes[:2])}"
    
    return info

def analyze_image_details(image_url):
    """AI-анализ визуальных деталей"""
    if not HF_TOKEN or not image_url:
        return None
    
    try:
        img_data = requests.get(image_url, timeout=10).content
        
        # Запрашиваем детальное описание
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
            if u and (u.endswith(('.jpg','.png','.jpeg')) or 'i.redd.it' in u):
                return u
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    m = re.search(r'<img[^>]+src="([^"]+)"', content)
    return m.group(1) if m else None

def create_detailed_description(info, ai_description, title):
    """Создаёт развёрнутое описание на русском"""
    
    parts = []
    
    # 1. Художник
    if info['artist']:
        parts.append(f"Художник: **{info['artist']}**")
    
    # 2. Название/выставка
    if info['exhibition']:
        parts.append(f"Выставка: {info['exhibition']}")
    
    # 3. Что изображено (AI)
    if ai_description:
        parts.append(f"На изображении: {ai_description}")
    
    # 4. Техника
    if info['technique']:
        parts.append(f"Техника: {info['technique']}")
    
    # 5. Стиль
    if info['style']:
        parts.append(f"Направление: {info['style']}")
    
    # 6. Год
    if info['year']:
        parts.append(f"Год: {info['year']}")
    
    # 7. Смысл
    if info['meaning']:
        parts.append(info['meaning'])
    elif not parts:
        parts.append("Произведение современного искусства")
    
    # Собираем вместе
    description = "\n".join(parts)
    
    return description

# Обработка записей
new_items = []
print("\n🎨 Обрабатываю...")

for i, entry in enumerate(feed.entries[:3]):
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title = entry.get("title", "Без названия")
    
    # Получаем полный текст статьи
    content_text = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    
    # Извлекаем информацию из текста
    print(f"  [{i+1}] Анализирую: {title[:40]}...")
    art_info = extract_art_info(content_text, title)
    
    # Картинка
    image_url = extract_image_url(entry)
    
    # AI-анализ изображения
    ai_desc = None
    if image_url:
        print(f"       🖼️ AI-анализ картинки...")
        ai_desc = analyze_image_details(image_url)
        if ai_desc:
            print(f"      ✅ {ai_desc}")
    
    # Создаём описание
    description = create_detailed_description(art_info, ai_desc, title)
    
    # 🎨 Формируем пост
    post_text = f"""🎨 <b>{title}</b>

{description}

#современноеискусство #арт #выставка #художник"""

    new_items.append({
        "id": item_id,
        "text": post_text,
        "image": image_url
    })
    
    time.sleep(3)

# Отправка
sent = 0
if new_items:
    print(f"\n📤 Отправляю...")
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
                print(f"  ❌ [{i+1}] {res.text[:80]}")
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
