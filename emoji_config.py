import random

# Telegram Premium Emoji IDs
PREMIUM_EMOJIS = {
    "laptop": "5244683263494069880",
    "kiss": "5244946884291732268",
    "cigarette": "5244688456109530025",
    "brain": "5194904652662971938",
    "gift": "5456203011183371567",
    "heart": "5424912684078348533",
    "gold_star": "4974529275114816593",
    "peach": "5454327849936755071",
    "dance": "5458694341323136053",
    "angry": "5456509220876721655",
    "play_button": "5262865002519353097",
    "sparkle": "5262668688154187507",
    "blue_heart": "5265009986496386438",
    "fireball": "5264962561467502824",
    "wifi": "5262724084642372455",
    "tech": "5264768725298469219",
    "check": "5343715481238925891",
    "cross": "5343709640083400091",
    "reload": "5465368548702446780",
    "red_dot": "5328262446605951527",
    "diamond": "5370546279375982437",
    "airplane": "5397669646390282694",
    "city": "5371100325862200313",
    "yellow_star": "5370718451729978105",
    "warning": "5368454557288391017",
    "clock": "5262873450720025099",
    "bread": "5343975734782205808",
    "sleepy": "5956434386109862089",
    "hourglass": "5229006053043089024",
    "envelope": "5350291836378307462",
    "present": "5936238625250350064",
    "chart": "5368334006146322724",
    "tower": "5262948196035875637",
    "shine": "5262587135315170424",
    "square": "5264980093524005655",
    "red_heart": "5248973918642910563",
    "blob_love": "5956318202949537587",
    "smile": "6229021005310854941",
    "ok_hand": "5244673243335370634",
    "star_simple": "5321485469249198987"
}

# Fallback emoji для клиентов, которые не поддерживают Premium emoji
FALLBACK_EMOJIS = {
    "yellow_star": "⭐",
    "check": "✅",
    "heart": "❤️",
    "brain": "🧠",
    "gift": "🎁",
    "sparkle": "✨",
    "warning": "⚠️",
    "airplane": "✈️",
    "clock": "🕐",
    "diamond": "💎",
    "reload": "🔄",
    "tech": "💻",
    "tower": "🗼",
    "envelope": "📧",
    "shine": "🌟",
    "ok_hand": "👌",
    "smile": "😊",
    "laptop": "💻",
    "kiss": "😘",
    "angry": "😠",
    "play_button": "▶️",
    "blue_heart": "💙",
    "fireball": "🔥",
    "wifi": "📶",
    "cross": "❌",
    "red_dot": "🔴",
    "city": "🏙️",
    "bread": "🍞",
    "sleepy": "😴",
    "hourglass": "⏳",
    "present": "🎁",
    "chart": "📊",
    "square": "⬜",
    "red_heart": "❤️",
    "blob_love": "🥰",
    "star_simple": "⭐"
}

def get_random_emoji() -> str:
    """Возвращает случайный Premium emoji в HTML формате"""
    emoji_id = random.choice(list(PREMIUM_EMOJIS.values()))
    return f'<tg-emoji emoji-id="{emoji_id}"></tg-emoji>'

def get_emoji(name: str) -> str:
    """Возвращает конкретный Premium emoji по имени в HTML формате"""
    emoji_id = PREMIUM_EMOJIS.get(name)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}"></tg-emoji>'
    return ""

def get_emoji_with_fallback(name: str, use_premium: bool = True) -> str:
    """
    Получает emoji с возможностью fallback на обычные Unicode emoji
    """
    if use_premium and name in PREMIUM_EMOJIS:
        return f'<tg-emoji emoji-id="{PREMIUM_EMOJIS[name]}"></tg-emoji>'
    elif name in FALLBACK_EMOJIS:
        return FALLBACK_EMOJIS[name]
    else:
        return "😊"  # Дефолтный emoji

def get_mixed_emoji_text(text: str, emoji_name: str) -> str:
    """
    Создает текст с Premium emoji и fallback emoji для лучшей совместимости
    """
    premium_emoji = get_emoji(emoji_name)
    fallback_emoji = FALLBACK_EMOJIS.get(emoji_name, "😊")

    return f"{premium_emoji}{fallback_emoji} {text}"

def get_thematic_emoji(content: str) -> str:
    """Возвращает тематический emoji на основе содержания текста"""
    content_lower = content.lower()

    # Определяем тематику по ключевым словам
    if any(word in content_lower for word in ['ton', 'блокчейн', 'blockchain', 'криптовалюта', 'токен']):
        return get_emoji("diamond")
    elif any(word in content_lower for word in ['обновление', 'update', 'новость', 'релиз']):
        return get_emoji("yellow_star")
    elif any(word in content_lower for word in ['airdrop', 'подарок', 'раздача', 'gift']):
        return get_emoji("gift")
    elif any(word in content_lower for word in ['технология', 'tech', 'разработка', 'ai', 'бот']):
        return get_emoji("tech")
    elif any(word in content_lower for word in ['рост', 'успех', 'топ', 'лучший']):
        return get_emoji("check")
    elif any(word in content_lower for word in ['любовь', 'сердце', 'нравится']):
        return get_emoji("red_heart")
    elif any(word in content_lower for word in ['время', 'скоро', 'ожидание']):
        return get_emoji("clock")
    elif any(word in content_lower for word in ['важно', 'внимание', 'предупреждение']):
        return get_emoji("warning")
    else:
        return get_emoji("sparkle")  # По умолчанию

def add_emojis_to_post(text: str, style: str = "random") -> str:
    """
    Добавляет Premium emoji в пост

    Args:
        text: Исходный текст поста
        style: Стиль добавления emoji ('random', 'thematic', 'structured')
    """
    lines = text.split('\n')
    if not lines:
        return text

    if style == "random":
        # Случайные emoji в начале и конце
        start_emoji = get_random_emoji()
        end_emoji = get_random_emoji()

        lines[0] = f"{start_emoji} {lines[0]}"
        lines[-1] = f"{lines[-1]} {end_emoji}"

    elif style == "thematic":
        # Тематические emoji
        start_emoji = get_thematic_emoji(text)

        lines[0] = f"{start_emoji} {lines[0]}"

        # Добавляем emoji в середину, если пост длинный
        if len(lines) > 3:
            middle_idx = len(lines) // 2
            middle_emoji = get_thematic_emoji(lines[middle_idx])
            lines[middle_idx] = f"{lines[middle_idx]} {middle_emoji}"

    elif style == "structured":
        # Структурированное размещение emoji
        title_emoji = get_emoji("yellow_star")
        content_emoji = get_emoji("brain")
        cta_emoji = get_emoji("heart")

        lines[0] = f"{title_emoji} {lines[0]}"

        # Ищем абзац с основным контентом
        for i, line in enumerate(lines[1:], 1):
            if line.strip() and len(line) > 50:
                lines[i] = f"{lines[i]} {content_emoji}"
                break

        # Добавляем CTA emoji в конец
        if len(lines) > 1:
            lines[-1] = f"{lines[-1]} {cta_emoji}"

    return '\n'.join(lines)

# Предустановленные шаблоны для разных типов постов
POST_TEMPLATES = {
    "news": {
        "start_emoji": "yellow_star",
        "content_emoji": "brain",
        "end_emoji": "sparkle"
    },
    "update": {
        "start_emoji": "reload",
        "content_emoji": "tech",
        "end_emoji": "check"
    },
    "airdrop": {
        "start_emoji": "gift",
        "content_emoji": "diamond",
        "end_emoji": "heart"
    },
    "analysis": {
        "start_emoji": "chart",
        "content_emoji": "brain",
        "end_emoji": "ok_hand"
    }
}

def apply_template(text: str, template_name: str) -> str:
    """Применяет предустановленный шаблон emoji к посту"""
    if template_name not in POST_TEMPLATES:
        return add_emojis_to_post(text, "thematic")

    template = POST_TEMPLATES[template_name]
    lines = text.split('\n')

    if not lines:
        return text

    # Начальный emoji
    start_emoji = get_emoji(template["start_emoji"])
    lines[0] = f"{start_emoji} {lines[0]}"

    # Emoji в середине контента
    if len(lines) > 2:
        middle_idx = len(lines) // 2
        content_emoji = get_emoji(template["content_emoji"])
        lines[middle_idx] = f"{lines[middle_idx]} {content_emoji}"

    # Конечный emoji
    if len(lines) > 1:
        end_emoji = get_emoji(template["end_emoji"])
        lines[-1] = f"{lines[-1]} {end_emoji}"

    return '\n'.join(lines)

def safe_html_with_emoji(text: str) -> str:
    """
    Безопасно экранирует HTML теги, но сохраняет Premium emoji теги

    Args:
        text: Исходный текст с возможными emoji тегами

    Returns:
        Безопасный для HTML текст с работающими emoji
    """
    import html
    import re

    # Находим все tg-emoji теги
    emoji_pattern = r'<tg-emoji emoji-id="[^"]+"></tg-emoji>'
    emoji_tags = re.findall(emoji_pattern, text)

    # Заменяем emoji теги на плейсхолдеры
    temp_text = text
    placeholders = []
    for i, emoji_tag in enumerate(emoji_tags):
        placeholder = f"__EMOJI_PLACEHOLDER_{i}__"
        placeholders.append((placeholder, emoji_tag))
        temp_text = temp_text.replace(emoji_tag, placeholder, 1)

    # Экранируем весь текст
    escaped_text = html.escape(temp_text)

    # Возвращаем emoji теги обратно
    for placeholder, emoji_tag in placeholders:
        escaped_text = escaped_text.replace(placeholder, emoji_tag)

    return escaped_text

def validate_emoji_text(text: str) -> str:
    """
    Проверяет и исправляет emoji теги в тексте

    Args:
        text: Текст с потенциальными emoji тегами

    Returns:
        Текст с валидными emoji тегами
    """
    import re

    # Исправляем экранированные emoji теги
    text = re.sub(r'&lt;tg-emoji emoji-id=&quot;([^&]+)&quot;&gt;&lt;/tg-emoji&gt;',
                  r'<tg-emoji emoji-id="\1"></tg-emoji>', text)

    # Проверяем валидность emoji ID
    def check_emoji_id(match):
        emoji_id = match.group(1)
        if emoji_id in PREMIUM_EMOJIS.values():
            return match.group(0)
        else:
            # Если ID не найден, возвращаем случайный валидный emoji
            import random
            valid_id = random.choice(list(PREMIUM_EMOJIS.values()))
            return f'<tg-emoji emoji-id="{valid_id}"></tg-emoji>'

    # Заменяем невалидные emoji ID
    text = re.sub(r'<tg-emoji emoji-id="([^"]+)"></tg-emoji>', check_emoji_id, text)

    return text 