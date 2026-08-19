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
print(f"🤖 AI: {'✅' if HF_TOKEN else '️ Без HF_TOKEN описания будут простыми'}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
        print(f"📚 Загружено {len(posted_ids)} ID")
    except: posted_ids = []

# Загрузка RSS
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    r = requests.get(RSS_URL, headers=headers, timeout=15)
    feed = feedparser.parse(r.text)
except:
    feed = feedparser.parse(RSS_URL, request_headers=headers)

print(f"📊 Записей в RSS: {len(feed.entries)}")

def translate_text(text):
    """Перевод на русский через Google Translate"""
    if not text:
        return ""
    
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={text}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            result = response.json()
            return result[0][0][0]
    except:
        pass
    
    return text

def analyze_artwork(image_url, title, content_text=""):
    """Детальный AI-анализ произведения искусства"""
    if not HF_TOKEN or not image_url:
        return None
    
    try:
        # Скачиваем изображение
        img_data = requests.get(image_url, timeout=10).content
        
        # Используем BLIP-2 для более детального описания
        response = requests.post(
            "https://api-inference.huggingface.co/models/Salesforce/blip2-opt-2.7b",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            data=img_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                ai_description = result[0].get('generated_text', '')
                
                # Формируем развёрнутое описание
                description = f"{ai_description}. "
                
                # Анализируем дополнительные детали из текста статьи
                if content_text:
                    # Ищем информацию о технике
                    techniques = {
                        'oil painting': 'масляная живопись',
                        'acrylic': 'акрил',
                        'watercolor': 'акварель',
                        'sculpture': 'скульптура',
                        'installation': 'инсталляция',
                        'photograph': 'фотография',
                        'digital art': 'цифровое искусство',
                        'mixed media': 'смешанная техника',
                        'canvas': 'холст',
                        'bronze': 'бронза',
                        'charcoal': 'уголь',
                        'pastel': 'пастель'
                    }
                    
                    content_lower = content_text.lower()
                    found_techniques = [tech for tech, rus in techniques.items() if tech in content_lower]
                    
                    if found_techniques:
                        tech_ru = [techniques[t] for t in found_techniques[:2]]
                        description += f"Техника: {', '.join(tech_ru)}. "
                    
                    # Ищем стиль/направление
                    styles = {
                        'abstract': 'абстракционизм',
                        'surrealism': 'сюрреализм',
                        'impressionism': 'импрессионизм',
                        'expressionism': 'экспрессионизм',
                        'minimalism': 'минимализм',
                        'pop art': 'поп-арт',
                        'contemporary': 'современное искусство',
                        'conceptual': 'концептуализм'
                    }
                    
                    found_styles = [style for style, rus in styles.items() if style in content_lower]
                    
                    if found_styles:
                        style_ru = [styles[s] for s in found_styles[:1]]
                        description += f"Стиль: {', '.join(style_ru)}. "
                
                return description.strip()
                
    except Exception as e:
        print(f"⚠️ AI ошибка: {e}")
    
    return None

def extract_author_from_title(title):
    """Пытается извлечь имя автора из заголовка"""
    # Паттерны для поиска имён
    patterns = [
        r'([A-Z][a-z]+ [A-Z][a-z]+)',  # Имя Фамилия
        r'at the (\w+)',  # "at the Museum"
        r'in (\w+)',  # "in Gallery"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(1)
    
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

# Обработка записей
new_items = []
print("\n🎨 Обрабатываю...")

for i, entry in enumerate(feed.entries[:3]):  # Только 3 (AI медленный)
    item_id = entry.get("id", entry.get("link", ""))
    if not item_id or item_id in posted_ids:
        continue

    # Заголовок на русском
    title_en = entry.get("title", "Без названия")
    title_ru = translate_text(title_en)
    
    # Извлекаем контент для анализа
    content_text = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
    
    # Извлекаем автора
    author = extract_author_from_title(title_en)
    
    # Картинка
    image_url = extract_image_url(entry)
    
    print(f"  [{i+1}] {title_ru[:40]}...")
    
    # AI-анализ
    if image_url:
        print(f"       🤖 Анализирую произведение...")
        art_description = analyze_artwork(image_url, title_en, content_text)
        
        if art_description:
            print(f"      ✅ {art_description[:60]}...")
        else:
            art_description = "Произведение современного искусства"
            print(f"      ⚠️ AI не смог проанализировать")
    else:
        art_description = "Произведение современного искусства"
        print(f"      ⚠️ Нет изображения")
    
    # 🎨 Формируем развёрнутый пост
    post_text = f"""🎨 <b>{title_ru}</b>

{art_description}

#современноеискусство #арт #выставка #художник"""

    new_items.append({
        "id": item_id,
        "text": post_text,
        "image": image_url
    })
    
    time.sleep(3)  # Пауза для AI

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
