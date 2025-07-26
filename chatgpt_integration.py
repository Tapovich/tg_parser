"""
Интеграция с ChatGPT API для качественного перефразирования постов
"""

import openai
import re
import logging
from typing import Dict, Optional, List
from config import config
import asyncio

logger = logging.getLogger(__name__)

# Инициализация OpenAI
client = None
if config.OPENAI_API_KEY:
    client = openai.OpenAI(api_key="sk-...")



class ChatGPTRewriter:
    """Класс для интеграции с ChatGPT API"""
    
    def __init__(self):
        self.channel_style = {
            "theme": "TON/Telegram/Крипта",
            "tone": "Дерзкий, провокационный, с иронией",
            "audience": "Крипто-энтузиасты, разработчики, инвесторы",
            "length": "200-400 символов, но если пост нужен более информативный и с деталями, то можно и больше",
            "emoji": "1-3 эмодзи для акцентов",
            "style": "Факты + мнение + сарказм"
        }
        
        self.base_prompt = """Ты — редактор дерзкого новостного Telegram-канала про TON, Telegram Gifts и крипту.
Пиши посты в стиле: факты + мнение + лёгкий сарказм + цепляющий заголовок.

Структура:
1. Заголовок с эмоцией или цепкой фразой (эмодзи приветствуются)
2. Суть новости в 2–4 коротких абзацах
3. Личный вывод, вопрос или провокация для вовлечения аудитории

Стиль:
• Короткие абзацы (1–3 строки)
• Дерзкая подача, ирония, иногда слегка грубоватые слова, но без перегиба
• 1–3 эмодзи для акцентов
• Уникальный текст: никаких шаблонов, канцелярита и сухих пересказов

Примеры постов:
• «🤨 OHUENKO Chat В С Е! Сообщения теперь только за 10 000 звёзд — почти $150 за сообщение. Затишье перед бурей или новый релиз?»
• «✈️ Telegram тестирует рейтинг профиля: чем больше звёзд купил — тем выше уровень. Социерархия внутри мессенджера? Не похоже ли это на старый ВК?»
• «❄️ Криптозима началась: Трамп подписал закон GENIUS — теперь стейблкоины под жёстким надзором. Свободы стало меньше.»
• «🎭 Что происходит со стикерами? Все ждут интеграцию, но пока это только слова. Telegram молчит — значит, не время.»
• «💎 TON ворвался в топ non-EVM-сетей: FDV $16,8 млрд. TON по $10 — всё ещё миф?»
• «🔥 Самый дорогой Telegram-подарок в истории! Plush Pepe Cozy Galaxy ушёл с аукциона за $96 000.»

ВАЖНО:
• НЕ используй ссылки и упоминания
• НЕ добавляй хештеги
• НЕ используй markdown-разметку
• Пиши живым языком
• Добавляй провокационные вопросы
• Используй иронию и сарказм

Перефразируй следующий пост в этом стиле:"""

    def clean_source_text(self, text: str) -> str:
        """Тщательно очищает исходный текст перед отправкой в ChatGPT"""
        
        # Убираем Markdown форматирование
        text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)  # *text*, **text**, ***text***
        text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)    # _text_, __text__, ___text___
        text = re.sub(r'`{1,3}([^`]+)`{1,3}', r'\1', text)     # `code`
        
        # Убираем все ссылки и упоминания
        text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)   # [text](link)
        text = re.sub(r'https?://[^\s]+', '', text)           # обычные ссылки
        text = re.sub(r't\.me/[^\s]+', '', text)              # t.me ссылки
        text = re.sub(r'@\w+', '', text)                      # @упоминания
        text = re.sub(r'#\w+', '', text)                      # #хештеги
        
        # Убираем спецсимволы и мусор
        text = re.sub(r'[▪▫◾◽▸▹◂◃▴▵▾▿►◄▲▼♦♧♠♣♥♤♡♢]', '', text)  # геометрические символы
        text = re.sub(r'[➖➕➗✖️✔️❌❗❓⚠️🔥]', '', text)         # служебные символы
        text = re.sub(r'[┌┐└┘├┤┬┴┼─│]', '', text)              # рамки
        text = re.sub(r'[•·‣⁃]', '', text)                     # списки
        
        # Убираем множественные пробелы и переносы
        text = re.sub(r'\s{2,}', ' ', text)
        text = re.sub(r'\n{2,}', '\n', text)
        
        # Убираем пустые строки и лишние символы в начале/конце
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        # Финальная очистка
        text = re.sub(r'^[^\w\d]+|[^\w\d.,!?]+$', '', text.strip())
        
        return text.strip()

    def get_copyable_prompt(self, original_text: str, content_type: str = "news") -> str:
        """Генерирует готовый промпт для copy-paste в ChatGPT"""
        
        # Сначала очищаем исходный текст
        cleaned_text = self.clean_source_text(original_text)
        
        # Определяем специфический стиль для типа контента
        type_specific = {
            "news": "🗞 НОВОСТЬ: Сделай заголовок с эмоцией + провокационный вывод",
            "update": "🔄 ОБНОВЛЕНИЕ: Подчеркни важность + добавь иронию о конкурентах", 
            "airdrop": "🎁 AIRDROP: Создай ощущение FOMO + намекни на подводные камни",
            "analysis": "📊 АНАЛИТИКА: Добавь экспертный сарказм + неожиданный вывод"
        }
        
        specific_instruction = type_specific.get(content_type, type_specific["news"])
        
        copyable_prompt = f"""Ты — редактор дерзкого новостного Telegram-канала про TON, Telegram Gifts и крипту.
Пиши посты в стиле: факты + мнение + лёгкий сарказм + цепляющий заголовок.

СТРУКТУРА:
1. Заголовок с эмоцией или цепкой фразой (эмодзи приветствуются)
2. Суть новости в 2–4 коротких абзацах
3. Личный вывод, вопрос или провокация для вовлечения аудитории

СТИЛЬ:
• Короткие абзацы (1–3 строки)
• Дерзкая подача, ирония, иногда слегка грубоватые слова
• 1–3 эмодзи для акцентов
• Уникальный текст без шаблонов и канцелярита

СПЕЦИАЛЬНАЯ ИНСТРУКЦИЯ: {specific_instruction}

ИСХОДНЫЙ ТЕКСТ:
{cleaned_text}

Напиши дерзкий пост для Telegram-канала в описанном стиле:"""

        return copyable_prompt
    
    def get_rewrite_suggestions(self, original_text: str) -> Dict[str, str]:
        """Генерирует советы что именно нужно перефразировать"""
        
        suggestions = {}
        
        # Анализируем исходный текст
        if len(original_text) < 100:
            suggestions["length"] = "📏 Текст слишком короткий - нужно добавить контекст и детали"
        
        if "http" in original_text or "t.me" in original_text:
            suggestions["links"] = "🔗 Убрать все ссылки из текста"
        
        if "@" in original_text:
            suggestions["mentions"] = "👤 Убрать упоминания пользователей (@username)"
        
        if "#" in original_text:
            suggestions["hashtags"] = "🏷️ Убрать хештеги"
        
        if original_text.count("(") > 2 or original_text.count("[") > 1:
            suggestions["brackets"] = "📝 Убрать лишние скобки и упростить структуру"
        
        # Проверяем эмоциональность
        boring_words = ["сообщает", "объявляет", "заявляет", "информирует"]
        if any(word in original_text.lower() for word in boring_words):
            suggestions["tone"] = "🎭 Сделать текст более энергичным и менее формальным"
        
        # Проверяем emoji
        if not any(char for char in original_text if ord(char) > 127):
            suggestions["emoji"] = "✨ Добавить 2-3 тематических emoji для привлечения внимания"
        
        # Проверяем структуру
        if "." not in original_text or original_text.count(".") < 2:
            suggestions["structure"] = "📋 Структурировать информацию на несколько предложений"
        
        return suggestions
    
    async def rewrite_with_chatgpt(self, original_text: str, content_type: str = "auto") -> Optional[str]:
        """Автоматически перефразирует текст через ChatGPT API"""
        
        if not client:
            logger.warning("OpenAI API ключ не настроен")
            return None
        
        try:
            # Сначала очищаем исходный текст
            cleaned_text = self.clean_source_text(original_text)
            logger.info(f"Очищенный текст: {cleaned_text[:100]}...")
            
            # Проверяем что после очистки что-то осталось
            if len(cleaned_text.strip()) < 10:
                logger.warning("После очистки текст стал слишком коротким")
                return None
            
            # Определяем тип контента если не указан
            if content_type == "auto":
                content_type = self._detect_content_type(cleaned_text)
            
            # Создаем промпты для системы и пользователя
            system_prompt = """Ты — редактор дерзкого новостного Telegram-канала про TON, Telegram Gifts и крипту.
Пиши посты в стиле: факты + мнение + лёгкий сарказм + цепляющий заголовок.

СТРУКТУРА:
1. Заголовок с эмоцией или цепкой фразой (эмодзи приветствуются)
2. Суть новости в 2–4 коротких абзацах
3. Личный вывод, вопрос или провокация для вовлечения аудитории

СТИЛЬ:
• Короткие абзацы (1–3 строки)
• Дерзкая подача, ирония, иногда слегка грубоватые слова
• 1–3 эмодзи для акцентов
• Уникальный текст без шаблонов и канцелярита
• Если новость важная - можно писать подробнее

ВАЖНО:
• НЕ используй ссылки и упоминания
• НЕ добавляй хештеги
• НЕ используй markdown-разметку
• Пиши живым языком
• Добавляй провокационные вопросы
• Используй иронию и сарказм"""

            # Определяем специальную инструкцию по типу контента
            type_instructions = {
                "news": "🗞 Сделай заголовок с эмоцией + провокационный вывод",
                "update": "🔄 Подчеркни важность + добавь иронию о конкурентах", 
                "airdrop": "🎁 Создай ощущение FOMO + намекни на подводные камни",
                "analysis": "📊 Добавь экспертный сарказм + неожиданный вывод"
            }
            
            instruction = type_instructions.get(content_type, type_instructions["news"])
            
            user_prompt = f"""СПЕЦИАЛЬНАЯ ИНСТРУКЦИЯ: {instruction}

ИСХОДНЫЙ ТЕКСТ:
{cleaned_text}

Напиши дерзкий пост для Telegram-канала в описанном стиле:"""
            
            # Оборачиваем синхронный вызов в asyncio.to_thread
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                max_tokens=800,  # Увеличили для более длинных постов
                temperature=0.7,  # Чуть больше креативности
                top_p=0.9,
                frequency_penalty=0.3,
                presence_penalty=0.2
            )
            
            if response.choices:
                rewritten_text = response.choices[0].message.content.strip()
                
                # Дополнительная очистка результата
                cleaned_text = self._clean_chatgpt_output(rewritten_text)
                
                logger.info(f"ChatGPT успешно перефразировал текст: {len(original_text)} -> {len(cleaned_text)} символов")
                return cleaned_text
            
        except Exception as e:
            logger.error(f"Ошибка ChatGPT API: {e}")
            return None
        
        return None
        
    def _detect_content_type(self, text: str) -> str:
        """Определяет тип контента"""
        text_lower = text.lower()
        
        airdrop_keywords = ['airdrop', 'раздача', 'подарок', 'gifts', 'бесплатно', 'токен', 'drop']
        if any(keyword in text_lower for keyword in airdrop_keywords):
            return "airdrop"
        
        update_keywords = ['обновление', 'update', 'релиз', 'версия', 'upgrade', 'улучшение']
        if any(keyword in text_lower for keyword in update_keywords):
            return "update"
        
        analysis_keywords = ['анализ', 'статистика', 'chart', 'график', 'данные', 'исследование']
        if any(keyword in text_lower for keyword in analysis_keywords):
            return "analysis"
        
        return "news"
    
    def _clean_chatgpt_output(self, text: str) -> str:
        """Тщательно очищает вывод ChatGPT от мусора и артефактов"""
        
        # Убираем возможные артефакты ChatGPT
        text = re.sub(r'^(Перефразированный пост:|Готовый пост:|Результат:|Вот переписанный пост:|Итоговый пост:)', '', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'^[\"\']|[\"\']$', '', text).strip()  # Убираем кавычки в начале/конце
        
        # КРИТИЧНО: Убираем все битые ссылки и Markdown
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)   # [text](link) -> text
        text = re.sub(r'\*{1,3}([^*]*)\*{1,3}', r'\1', text)  # **text** -> text
        text = re.sub(r'_{1,3}([^_]*)_{1,3}', r'\1', text)    # __text__ -> text
        text = re.sub(r'`([^`]*)`', r'\1', text)              # `code` -> code
        
        # Убираем любые URL и битые ссылки
        text = re.sub(r'https?://[^\s]*', '', text)
        text = re.sub(r't\.me/[^\s]*', '', text)
        text = re.sub(r'@\w+', '', text)
        
        # Убираем спецсимволы и мусор которые могли проскочить
        text = re.sub(r'[▪▫◾◽▸▹◂◃▴▵▾▿►◄▲▼♦♧♠♣♥♤♡♢]', '', text)
        text = re.sub(r'[➖➕➗✖️✔️❌❗❓⚠️]', '', text)
        text = re.sub(r'[┌┐└┘├┤┬┴┼─│]', '', text)
        text = re.sub(r'[|]', '', text)  # Убираем вертикальные черты
        
        # Убираем множественные пробелы и переносы
        text = re.sub(r' {2,}', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Убираем пустые строки и нормализуем
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        # Проверяем что текст не содержит мусора
        if len(text) < 50:
            raise ValueError("Полученный текст слишком короткий")
        
        # Проверяем на наличие битых элементов
        problematic_patterns = [r'\[\s*\]', r'\(\s*\)', r'\*{2,}', r'_{2,}', r'http', r't\.me']
        for pattern in problematic_patterns:
            if re.search(pattern, text):
                # Еще раз очищаем агрессивно
                text = re.sub(pattern, '', text)
        
        return text.strip()

# Готовые промпты для разных типов контента
READY_PROMPTS = {
    "news": """🗞️ ПРОМПТ ДЛЯ НОВОСТЕЙ (Copy → Paste в ChatGPT):

Ты редактор крипто-канала о TON/Telegram. Перефразируй новость:

✅ Сделай сенсационный заголовок с emoji
✅ Убери ссылки, упоминания, скобки  
✅ Добавь экспертный комментарий
✅ 200-500 символов
✅ Заверши: "Подписывайтесь на канал!"

ТЕКСТ: [ВСТАВЬ СЮДА ИСХОДНЫЙ ПОСТ]""",

    "update": """🔄 ПРОМПТ ДЛЯ ОБНОВЛЕНИЙ (Copy → Paste в ChatGPT):

Ты редактор Telegram-канала о TON. Перефразируй обновление:

✅ Подчеркни важность улучшений
✅ Убери техническую терминологию  
✅ Добавь энтузиазм с emoji
✅ 200-500 символов
✅ Заверши CTA для подписки

ТЕКСТ: [ВСТАВЬ СЮДА ИСХОДНЫЙ ПОСТ]""",

    "airdrop": """🎁 ПРОМПТ ДЛЯ AIRDROP (Copy → Paste в ChatGPT):

Ты редактор крипто-канала. Перефразируй информацию о раздаче:

✅ Создай ощущение срочности
✅ Подчеркни бесплатность и ценность
✅ Убери сложные условия участия
✅ 200-400 символов  
✅ Мотивируй к действию

ТЕКСТ: [ВСТАВЬ СЮДА ИСХОДНЫЙ ПОСТ]""",

    "analysis": """📊 ПРОМПТ ДЛЯ АНАЛИТИКИ (Copy → Paste в ChatGPT):

Ты аналитик крипто-рынка. Перефразируй данные:

✅ Сделай акцент на важности данных
✅ Упрости сложную статистику
✅ Добавь экспертное мнение
✅ 300-600 символов
✅ Призови следить за трендами

ТЕКСТ: [ВСТАВЬ СЮДА ИСХОДНЫЙ ПОСТ]"""
}

# Глобальный экземпляр
chatgpt_rewriter = ChatGPTRewriter()

async def rewrite_post_with_ai(original_text: str, use_chatgpt: bool = True) -> str:
    """
    Основная функция для перефразирования с AI
    
    Args:
        original_text: Исходный текст
        use_chatgpt: Использовать ChatGPT API (True) или локальную систему (False)
    
    Returns:
        Перефразированный пост
    """
    if use_chatgpt and config.OPENAI_API_KEY:
        # Пробуем ChatGPT
        result = await chatgpt_rewriter.rewrite_with_chatgpt(original_text)
        if result:
            return result
        else:
            logger.warning("ChatGPT не сработал, используем локальную систему")
    
    # Fallback на локальную систему
    from content_rewriter import rewrite_post
    return rewrite_post(original_text)

def get_manual_rewrite_prompt(original_text: str, content_type: str = "auto") -> str:
    """Генерирует готовый промпт для ручного использования в ChatGPT"""
    
    if content_type == "auto":
        content_type = chatgpt_rewriter._detect_content_type(original_text)
    
    return chatgpt_rewriter.get_copyable_prompt(original_text, content_type) 
