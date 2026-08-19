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

RSS_SOURCES = [
    "https://www.artsy.net/articles.rss",
    "https://hyperallergic.com/feed/",
    "https://www.tate.org.uk/rss",
    "https://www.artnews.com/feed/",
    "https://www.moma.org/magazine/articles/feed",
]

print(f"📚 Источников: {len(RSS_SOURCES)}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except: posted_ids = []

def translate_to_russian(text):
    """Перевод на русский через Google Translate"""
    if not text:
        return ""
    
    try:
        # Кодируем текст для URL
        import urllib.parse
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={encoded_text}"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            result = response.json()
            translated = result[0][0][0]
            return translated
    except Exception as e:
        print(f"️ Ошибка перевода: {e}")
    
    # Словарь частых слов (fallback)
    fallback_words = {
        'exhibition': 'выставка',
        'artist': 'художник',
        'art': 'искусство',
        'painting': 'картина',
        'sculpture': 'скульптура',
        'modern': 'современный',
        'contemporary': 'современный',
        'museum': 'музей',
        'gallery': 'галерея',
        'installation': 'инсталляция',
        'photograph': 'фотография',
        'abstract': 'абстрактный',
        'collection': 'коллекция',
        'new': 'новый',
        'show': 'выставка',
        'work': 'работа',
        'works': 'работы',
    }
    
    words = text.split()
    translated_words = [fallback_words.get(w.lower(), w) for w in words]
    return ' '.join(translated_words)

def extract_detailed_info(content_text, title):
    """Детальный анализ статьи"""
    info = {
        'artist': None,
        'technique': None,
        'style': None,
        'meaning': None,
        'exhibition': None,
        'year': None,
        'location': None,
        'materials': None,
        'period': None,
        'description': None
    }
    
    if not content_text:
        return info
    
    text_lower = content_text.lower()
    
    #  ХУДОЖНИК (ищем в первых 1000 символов)
    artist_patterns = [
        r'([A-Z][a-z]{3,}\s[A-Z][a-z]{3,})\s+(?:is|was|creates|painted|sculpted|known for)',
        r'(?:artist|painter|sculptor|photographer)\s+([A-Z][a-z]+\s[A-Z][a-z]+)',
        r'by\s+([A-Z][a-z]{3,}\s[A-Z][a-z]{3,})',
        r'works? by\s+([A-Z][a-z]+\s[A-Z][a-z]+)',
    ]
    
    for pattern in artist_patterns:
        match = re.search(pattern, content_text[:1000])
        if match:
            artist = match.group(1)
            if artist.lower() not in ['the artist', 'this artist', 'new york', 'los angeles']:
                info['artist'] = artist
                break
    
    # 🎭 ТЕХНИКА И МАТЕРИАЛЫ
    techniques = {
        'oil on canvas': 'масло на холсте',
        'oil painting': 'масляная живопись',
        'acrylic on canvas': 'акрил на холсте',
        'watercolor on paper': 'акварель на бумаге',
        'watercolor': 'акварель',
        'bronze sculpture': 'бронзовая скульптура',
        'marble sculpture': 'мраморная скульптура',
        'sculpture': 'скульптура',
        'installation': 'инсталляция',
        'video installation': 'видеоинсталляция',
        'sound installation': 'звуковая инсталляция',
        'photograph': 'фотография',
        'digital photograph': 'цифровая фотография',
        'digital art': 'цифровое искусство',
        'mixed media': 'смешанная техника',
        'charcoal on paper': 'уголь на бумаге',
        'pastel on paper': 'пастель на бумаге',
        'ink on paper': 'тушь на бумаге',
        'collage': 'коллаж',
        'performance art': 'перформанс',
        'conceptual art': 'концептуальное искусство',
        'print': 'гравюра',
        'etching': 'офорт',
        'lithograph': 'литография',
        'screenprint': 'шелкография',
    }
    
    for eng, rus in techniques.items():
        if eng in text_lower:
            info['technique'] = rus
            info['materials'] = rus
            break
    
    #  СТИЛЬ/НАПРАВЛЕНИЕ
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
        'cubism': 'кубизм',
        'fauvism': 'фовизм',
        'dadaism': 'дадаизм',
        'realism': 'реализм',
        'figurative': 'фигуративизм',
    }
    
    for eng, rus in styles.items():
        if eng in text_lower:
            info['style'] = rus
            break
    
    # 📅 ГОД
    year_patterns = [
        r'\b(19|20)\d{2}\b',
        r'created in (\d{4})',
        r'made in (\d{4})',
        r'from (\d{4})',
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, content_text)
        if match:
            info['year'] = match.group(0)
            break
    
    # 🏛️ ВЫСТАВКА/МУЗЕЙ
    museum_patterns = [
        r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+(?:Museum|Gallery|Biennale|Center|Institute)',
        r'at (?:the\s+)?([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+(?:Museum|Gallery)',
        r'exhibition at ([A-Za-z\s]+)',
    ]
    
    for pattern in museum_patterns:
        match = re.search(pattern, content_text)
        if match:
            info['exhibition'] = match.group(0).title()
            info['location'] = match.group(0)
            break
    
    # 💭 СМЫСЛ И ТЕМЫ (ищем в первых абзацах)
    first_paragraphs = '\n'.join(content_text.split('\n\n')[:3]) if '\n\n' in content_text else content_text[:800]
    
    themes = {
        'identity': 'идентичность и самопознание',
        'memory': 'память и воспоминания',
        'trauma': 'травма и исцеление',
        'politics': 'политический комментарий',
        'social justice': 'социальная справедливость',
        'gender': 'гендерные вопросы',
        'race': 'расовая проблематика',
        'migration': 'миграция и перемещение',
        'environment': 'экология и природа',
        'climate': 'климатические изменения',
        'technology': 'технологии и будущее',
        'digital': 'цифровая культура',
        'history': 'историческая рефлексия',
        'culture': 'культурная идентичность',
        'power': 'власть и иерархия',
        'consumerism': 'потребительство',
        'capitalism': 'капитализм',
        'feminism': 'феминизм',
        'decolonization': 'деколонизация',
        'spirituality': 'духовность',
    }
    
    found_themes = []
    for eng, rus in themes.items():
        if eng in first_paragraphs.lower():
            found_themes.append(rus)
    
    if found_themes:
        info['meaning'] = f"Работа исследует темы: {', '.join(found_themes[:3])}"
    
    # 📖 ОПИСАНИЕ (ищем описательные фразы)
    desc_patterns = [
        r'(?:depicts?|shows?|features?|presents?)\s+([^\.]+)',
        r'(?:a|an)\s+(?:stunning|powerful|striking|bold|vibrant)\s+([^\.]+)',
    ]
    
    for pattern in desc_patterns:
        match = re.search(pattern, first_paragraphs, re.IGNORECASE)
        if match:
            info['description'] = match.group(1).strip()
            break
    
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
                caption = result[0].get('generated_text', '')
                # Переводим описание картинки
                return translate_to_russian(caption)
    except:
        pass
    
    return None

def extract_image_url(entry):
    """Поиск картинки"""
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            u = m.get('url', '')
            if u and (u.endswith(('.jpg','.png','.jpeg')) or 'artsy' in u):
                return u
    content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    m = re.search(r'<img[^>]+src="([^"]+)"', content)
    return m.group(1) if m else None

def create_rich_description(info, ai_desc, title_ru):
    """Создаёт БОГАТОЕ описание на русском"""
    lines = []
    
    # Заголовок уже переведён
    lines.append(f"<b>{title_ru}</b>\n")
    
    # Художник
    if info['artist']:
        lines.append(f"👨‍🎨 <b>Художник:</b> {info['artist']}")
    
    # AI описание картинки
    if ai_desc:
        lines.append(f"🖼️ <b>На изображении:</b> {ai_desc}")
    
    # Техника/материалы
    if info['technique'] or info['materials']:
        tech = info['technique'] or info['materials']
        lines.append(f"🎨 <b>Техника:</b> {tech}")
    
    # Стиль
    if info['style']:
        lines.append(f"🎭 <b>Направление:</b> {info['style']}")
    
    # Выставка/музей
    if info['exhibition']:
        lines.append(f"🏛️ <b>Выставка:</b> {info['exhibition']}")
    
    # Год
    if info['year']:
        lines.append(f"📅 <b>Год:</b> {info['year']}")
    
    # Смысл/темы
    if info['meaning']:
        lines.append(f" <b>Смысл:</b> {info['meaning']}")
    
    # Описание из статьи
    if info['description']:
        desc_ru = translate_to_russian(info['description'])
        lines.append(f"📖 <b>Описание:</b> {desc_ru}")
    
    # Если совсем пусто
    if len(lines) <= 2:
        lines.append("Произведение современного искусства")
    
    return "\n".join(lines)

# Загрузка RSS
all_entries = []
print("\n Загружаю источники...")

for i, rss_url in enumerate(RSS_SOURCES):
    try:
        print(f"  [{i+1}/{len(RSS_SOURCES)}] {rss_url[:40]}...")
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(rss_url, headers=headers, timeout=10)
        feed = feedparser.parse(r.text)
        
        with_images = 0
        for entry in feed.entries:
            img = extract_image_url(entry)
            if img:
                with_images += 1
                entry['_source'] = rss_url
                all_entries.append(entry)
        
        print(f"      ✅ {len(feed.entries)} записей, {with_images} с картинками")
        time.sleep(1)
        
    except Exception as e:
        print(f"      ❌ {e}")

print(f"\n📊 Найдено с картинками: {len(all_entries)}")

# Обработка
new_items = []
print("\n🎨 Обрабатываю...")

for i, entry in enumerate(all_entries[:4]):  # 4 поста
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    title_en = entry.get("title", "Без названия")
    content_text = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    image_url = extract_image_url(entry)
    
    if not image_url:
        continue
    
    print(f"\n  [{i+1}] Заголовок: {title_en[:50]}...")
    
    #  ПЕРЕВОД ЗАГОЛОВКА
    title_ru = translate_to_russian(title_en)
    print(f"      Перевод: {title_ru[:50]}...")
    
    # Детальный анализ
    print(f"      🔍 Анализирую статью...")
    art_info = extract_detailed_info(content_text, title_en)
    
    # AI картинки
    ai_desc = None
    if image_url:
        print(f"      🤖 AI-анализ изображения...")
        ai_desc = analyze_image(image_url)
    
    # Создаём описание
    description = create_rich_description(art_info, ai_desc, title_ru)
    
    # Хештеги
    hashtags = "\n\n#современноеискусство #арт #выставка #художник"
    
    post_text = description + hashtags
    
    new_items.append({
        "id": item_id,
        "text": post_text,
        "image": image_url
    })
    
    time.sleep(3)  # Пауза для API

# Отправка
sent = 0
if new_items:
    print(f"\n📤 Отправляю {len(new_items)} постов...")
    
    for i, item in enumerate(new_items):
        try:
            print(f"  [{i+1}] Отправка...")
            
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
                
        except Exception as e:
            print(f"      ❌ {e}")
        
        time.sleep(1)
    
    print(f"\n🎉 Отправлено: {sent}/{len(new_items)}")
else:
    print("\n⚠️ Нечего отправлять")

# Сохранение
with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"💾 Сохранено {len(posted_ids)} ID")
