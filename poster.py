import requests
import json
import os
import time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "1"))

print("🎨 Tate Collection Auto-Poster (API)")
print(f"🤖 AI: {'✅' if HF_TOKEN else '⚠️'}")

posted_ids = []
if os.path.exists("posted_ids.json"):
    try:
        with open("posted_ids.json", "r", encoding="utf-8") as f:
            posted_ids = json.load(f)
    except: posted_ids = []

def fetch_tate_artworks(has_image=True, limit=20):
    """Загружает работы через официальный API Tate"""
    
    # Tate API: https://www.tate.org.uk/art/artworks.json
    url = "https://www.tate.org.uk/art/artworks.json"
    params = {
        'q': '',
        'hasImage': 'true' if has_image else 'false',
        'size': limit,
        'sort': '-dated',  # Сначала новые
    }
    
    print(f"📥 Запрашиваю API: {url}")
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        artworks = data.get('results', [])
        print(f"📊 Найдено работ в API: {len(artworks)}")
        
        return artworks
        
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        return []

def get_high_res_image(thumbnail_url):
    """Получает ссылку на изображение в высоком разрешении"""
    if not thumbnail_url:
        return None
    
    # Tate хранит картинки в разных форматах
    # Пробуем получить полное разрешение
    if '/800-' in thumbnail_url:
        return thumbnail_url.replace('/800-', '/1200-')
    elif 'image.tate.org.uk' in thumbnail_url:
        # Заменяем превью на оригинал
        return thumbnail_url.replace('/images/', '/images/large/')
    
    return thumbnail_url

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

def create_description(artwork, ai_desc):
    """Создаёт описание на русском"""
    lines = []
    
    title = artwork.get('title', 'Без названия')
    artist = artwork.get('artist', [{}])[0].get('name') if artwork.get('artist') else None
    year = artwork.get('dateText')
    medium = artwork.get('medium')
    description = artwork.get('thumbnailCopyright') or artwork.get('inscription')
    link = f"https://www.tate.org.uk{artwork.get('url', '')}"
    
    # Заголовок
    lines.append(f"<b>{title}</b>\n")
    
    # Художник
    if artist:
        lines.append(f"👨‍🎨 <b>Художник:</b> {artist}")
    
    # Год
    if year:
        lines.append(f"📅 <b>Год:</b> {year}")
    
    # Техника
    if medium:
        lines.append(f"🎨 <b>Техника:</b> {medium}")
    
    # AI описание картинки
    if ai_desc:
        lines.append(f"🖼️ <b>На изображении:</b> {ai_desc}")
    
    # Описание/права
    if description and len(description) < 200:
        lines.append(f"📖 {description}")
    
    # Ссылка
    lines.append(f"\n🔗 <a href=\"{link}\">Подробнее на Tate.org.uk</a>")
    
    # Хештеги
    lines.append("\n#Tate #искусство #арт #коллекция #музей")
    
    return "\n".join(lines)

# 🔥 Основной запуск
print("\n🎨 Загружаю работы из Tate API...")
artworks = fetch_tate_artworks(has_image=True, limit=20)

# Фильтруем уже отправленные
new_artworks = [a for a in artworks if a.get('id') not in posted_ids]

if not new_artworks:
    print("⚠️ Все работы уже отправлены или API вернул пустой результат")
    # Создаём пустой файл, чтобы Git не упал
    with open("posted_ids.json", "w", encoding="utf-8") as f:
        json.dump(posted_ids, f, ensure_ascii=False, indent=2)
    print("💾 Сохранено (0 новых)")
    exit(0)

print(f"✅ Найдено {len(new_artworks)} новых работ")

# Берём нужное количество
artworks_to_post = new_artworks[:POSTS_PER_RUN]
print(f"\n📤 Буду отправлять: {len(artworks_to_post)}\n")

# Отправка
sent = 0
for i, artwork in enumerate(artworks_to_post):
    title = artwork.get('title', 'Без названия')
    print(f"[{i+1}] {title[:50]}...")
    
    # Картинка
    thumb = artwork.get('thumbnailUrl')
    image_url = get_high_res_image(thumb) if thumb else None
    
    if not image_url:
        print(f"    ⚠️ Нет картинки, пропускаю")
        continue
    
    print(f"    🖼️ {image_url[:60]}...")
    
    # AI-анализ
    if HF_TOKEN:
        print(f"    🤖 AI-анализ...")
        ai_desc = analyze_image(image_url)
        if ai_desc:
            print(f"    ✅ {ai_desc}")
    else:
        ai_desc = None
    
    # Создаём описание
    description = create_description(artwork, ai_desc)
    
    # Отправка
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json={
                "chat_id": CHAT_ID,
                "photo": image_url,
                "caption": description,
                "parse_mode": "HTML"
            },
            timeout=30
        )
        
        if res.status_code == 200:
            posted_ids.append(artwork.get('id'))
            sent += 1
            print(f"    ✅ Отправлено!")
        else:
            print(f"    ❌ {res.text[:80]}")
            
    except Exception as e:
        print(f"    ❌ Ошибка: {e}")
    
    time.sleep(2)

# 🔒 ВСЕГДА сохраняем файл (даже если 0 отправлено)
with open("posted_ids.json", "w", encoding="utf-8") as f:
    json.dump(posted_ids, f, ensure_ascii=False, indent=2)

print(f"\n🎉 Отправлено: {sent}/{len(artworks_to_post)}")
print(f"💾 Сохранено {len(posted_ids)} ID")
