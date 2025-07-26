"""
Модуль для перефразирования и улучшения постов
"""

import re
import random
from typing import Dict, List, Optional
from emoji_config import apply_template, get_emoji, get_thematic_emoji


class ContentRewriter:
    """Класс для перефразирования контента в стиле новостного канала"""
    
    def __init__(self):
        self.news_intro_patterns = [
            "🔥 Важные новости! {content}",
            "📰 Свежая информация: {content}",
            "⚡ Горячие новости! {content}",
            "🎯 Актуально сейчас: {content}",
            "📢 Последние события: {content}",
            "🚀 Новое развитие событий! {content}",
            "💥 Сенсация! {content}",
            "🔔 Важное обновление: {content}"
        ]
        
        self.update_patterns = [
            "🔄 Обновление! {content}",
            "⚡ Новая версия: {content}",
            "🎉 Релиз! {content}",
            "🔧 Улучшения: {content}",
            "📱 Обновлено: {content}",
            "🆕 Новые функции: {content}",
            "🎯 Важные изменения: {content}"
        ]
        
        self.airdrop_patterns = [
            "🎁 Раздача! {content}",
            "💰 Новый аirdrop: {content}",
            "🪙 Бесплатные токены! {content}",
            "🎉 Подарки для пользователей: {content}",
            "💎 Не пропустите! {content}",
            "🔥 Горячая раздача: {content}",
            "⭐ Эксклюзивное предложение: {content}"
        ]
        
        self.call_to_action = [
            "Подписывайтесь на канал для самых свежих новостей!",
            "Не пропускайте важные обновления!",
            "Следите за развитием событий в нашем канале!",
            "Оставайтесь в курсе последних новостей!",
            "Будьте первыми узнавать важную информацию!",
            "Подписывайтесь, чтобы не пропустить ничего важного!",
            "Следите за нашими обновлениями!"
        ]
    
    def detect_content_type(self, text: str) -> str:
        """Определяет тип контента по ключевым словам"""
        text_lower = text.lower()
        
        # Airdrop / раздачи
        airdrop_keywords = ['airdrop', 'раздача', 'подарок', 'gifts', 'бесплатно', 'токен', 'drop']
        if any(keyword in text_lower for keyword in airdrop_keywords):
            return "airdrop"
        
        # Обновления
        update_keywords = ['обновление', 'update', 'релиз', 'версия', 'upgrade', 'улучшение']
        if any(keyword in text_lower for keyword in update_keywords):
            return "update"
        
        # Аналитика
        analysis_keywords = ['анализ', 'статистика', 'chart', 'график', 'данные', 'исследование']
        if any(keyword in text_lower for keyword in analysis_keywords):
            return "analysis"
        
        return "news"
    
    def clean_and_structure_text(self, text: str) -> str:
        """Тщательно очищает и структурирует исходный текст"""
        
        # Убираем Markdown форматирование
        text = re.sub(r'\*{1,3}([^*]*)\*{1,3}', r'\1', text)  # *text*, **text**, ***text***
        text = re.sub(r'_{1,3}([^_]*)_{1,3}', r'\1', text)    # _text_, __text__, ___text___
        text = re.sub(r'`{1,3}([^`]*)`{1,3}', r'\1', text)     # `code`
        
        # Убираем все ссылки и упоминания  
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)   # [text](link)
        text = re.sub(r'http[s]?://[^\s]+', '', text)         # обычные ссылки
        text = re.sub(r't\.me/[^\s]+', '', text)              # t.me ссылки
        text = re.sub(r'@\w+', '', text)                      # @упоминания
        text = re.sub(r'#\w+', '', text)                      # #хештеги
        
        # Убираем спецсимволы и мусор
        text = re.sub(r'[▪▫◾◽▸▹◂◃▴▵▾▿►◄▲▼♦♧♠♣♥♤♡♢]', '', text)
        text = re.sub(r'[➖➕➗✖️✔️❌❗❓⚠️]', '', text)
        text = re.sub(r'[┌┐└┘├┤┬┴┼─│]', '', text)
        text = re.sub(r'[|]', '', text)
        
        # Нормализуем знаки препинания
        text = re.sub(r'[.]{2,}', '...', text)
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        
        # Убираем лишние пробелы и переносы
        text = re.sub(r'\s{2,}', ' ', text)
        text = re.sub(r'\n{2,}', '\n', text)
        
        # Убираем пустые строки и лишние символы
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def extract_key_points(self, text: str) -> List[str]:
        """Извлекает ключевые моменты из текста"""
        # Разбиваем на предложения
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        # Берем самые информативные предложения (не слишком короткие)
        key_points = []
        for sentence in sentences:
            if len(sentence) > 20 and len(sentence) < 200:
                key_points.append(sentence)
        
        return key_points[:3]  # Максимум 3 ключевых момента
    
    def enhance_text(self, text: str, content_type: str) -> str:
        """Улучшает и дополняет текст"""
        # Выбираем подходящий паттерн в зависимости от типа контента
        if content_type == "airdrop":
            patterns = self.airdrop_patterns
        elif content_type == "update":
            patterns = self.update_patterns
        else:
            patterns = self.news_intro_patterns
        
        # Выбираем случайный паттерн
        pattern = random.choice(patterns)
        
        return pattern.format(content=text)
    
    def add_engaging_elements(self, text: str) -> str:
        """Добавляет элементы для повышения вовлеченности"""
        # Добавляем восклицательные знаки для важности
        if not text.endswith(('!', '?', '.')):
            text += '!'
        
        # Заменяем некоторые точки на восклицательные знаки
        text = re.sub(r'\.( [А-ЯA-Z])', r'!\1', text, count=1)
        
        return text
    
    def create_compelling_post(self, original_text: str, min_length: int = 200, max_length: int = 800) -> str:
        """
        Создает привлекательный пост из исходного текста
        
        Args:
            original_text: Исходный текст
            min_length: Минимальная длина поста
            max_length: Максимальная длина поста
        
        Returns:
            Переписанный качественный пост
        """
        # Определяем тип контента
        content_type = self.detect_content_type(original_text)
        
        # Очищаем исходный текст
        cleaned_text = self.clean_and_structure_text(original_text)
        
        # Если текст слишком короткий, расширяем его
        if len(cleaned_text) < min_length:
            # Извлекаем ключевые моменты
            key_points = self.extract_key_points(cleaned_text)
            
            if key_points:
                # Создаем расширенную версию
                main_point = key_points[0]
                
                # Добавляем контекст в зависимости от типа
                if content_type == "airdrop":
                    context = self._add_airdrop_context(main_point)
                elif content_type == "update":
                    context = self._add_update_context(main_point)
                else:
                    context = self._add_news_context(main_point)
                
                enhanced_text = f"{main_point} {context}"
            else:
                # Если ключевые моменты не найдены, улучшаем весь текст
                enhanced_text = self._expand_short_text(cleaned_text, content_type)
        else:
            # Если текст достаточно длинный, просто улучшаем его
            enhanced_text = cleaned_text
        
        # Обрезаем если слишком длинный
        if len(enhanced_text) > max_length:
            enhanced_text = enhanced_text[:max_length].rsplit(' ', 1)[0] + '...'
        
        # Добавляем элементы вовлеченности
        enhanced_text = self.add_engaging_elements(enhanced_text)
        
        # Добавляем эмоциональный заголовок
        final_text = self.enhance_text(enhanced_text, content_type)
        
        # Добавляем call to action
        cta = random.choice(self.call_to_action)
        if len(final_text) + len(cta) + 10 < max_length:
            final_text += f"\n\n💫 {cta}"
        
        return final_text
    
    def _add_airdrop_context(self, main_point: str) -> str:
        """Добавляет контекст для airdrop постов"""
        contexts = [
            "Это отличная возможность получить бесплатные токены!",
            "Не упустите шанс участвовать в раздаче.",
            "Количество участников ограничено.",
            "Раздача проходит в рамках развития экосистемы.",
            "Участие бесплатное и займет всего несколько минут."
        ]
        return random.choice(contexts)
    
    def _add_update_context(self, main_point: str) -> str:
        """Добавляет контекст для обновлений"""
        contexts = [
            "Обновление направлено на улучшение пользовательского опыта.",
            "Новые функции уже доступны всем пользователям.",
            "Это важный шаг в развитии платформы.",
            "Разработчики продолжают активно развивать проект.",
            "Обновление включает множество полезных улучшений."
        ]
        return random.choice(contexts)
    
    def _add_news_context(self, main_point: str) -> str:
        """Добавляет контекст для новостей"""
        contexts = [
            "Это событие может значительно повлиять на развитие индустрии.",
            "Эксперты считают это важным шагом вперед.",
            "Новость уже активно обсуждается в криптосообществе.",
            "Это подтверждает растущую популярность технологии.",
            "Следите за развитием событий в ближайшее время."
        ]
        return random.choice(contexts)
    
    def _expand_short_text(self, text: str, content_type: str) -> str:
        """Расширяет короткий текст"""
        if content_type == "airdrop":
            expansion = "Участники смогут получить токены абсолютно бесплатно. Это отличная возможность стать частью растущей экосистемы."
        elif content_type == "update":
            expansion = "Новая версия включает улучшения производительности и новые возможности для пользователей."
        else:
            expansion = "Это событие привлекло внимание всего криптосообщества и может стать поворотным моментом в развитии индустрии."
        
        return f"{text} {expansion}"


# Глобальный экземпляр для использования в других модулях
content_rewriter = ContentRewriter()


def rewrite_post(original_text: str, style: str = "auto") -> str:
    """
    Основная функция для переписывания постов
    
    Args:
        original_text: Исходный текст
        style: Стиль переписывания ("news", "update", "airdrop", "auto")
    
    Returns:
        Переписанный пост
    """
    rewritten = content_rewriter.create_compelling_post(original_text)
    
    # Применяем emoji шаблон
    if style == "auto":
        style = content_rewriter.detect_content_type(original_text)
    
    return apply_template(rewritten, style) 