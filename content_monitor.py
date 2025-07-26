import asyncio
import logging
import feedparser
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import re
from bs4 import BeautifulSoup

try:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logging.warning("Telethon не установлен. Мониторинг Telegram каналов недоступен.")

from config import config, ADMIN_USERS
from database import db

logger = logging.getLogger(__name__)

# Устанавливаем дату, до которой игнорируем старые посты
CUTOFF_DATE = datetime(2025, 7, 25, tzinfo=timezone.utc)

class ContentMonitor:
    def __init__(self):
        self.session = None
        self.tg_client = None
        self.keywords = config.KEYWORDS
        self.last_check = {}
        self.bot_instance = None
        
    async def safe_send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        """Безопасная отправка сообщения"""
        message_params = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        await self.bot_instance.send_message(**message_params)
        
    def set_bot_instance(self, bot_instance):
        """Устанавливает экземпляр бота для отправки уведомлений"""
        self.bot_instance = bot_instance
        
    async def init_telethon(self):
        """Инициализация Telethon клиента"""
        if not TELETHON_AVAILABLE:
            logger.warning("Telethon недоступен")
            return False
            
        try:
            config.validate_telethon()
            self.tg_client = TelegramClient(
                'content_monitor_session', 
                config.API_ID, 
                config.API_HASH
            )
            
            await self.tg_client.start(phone=config.PHONE_NUMBER)
            logger.info("Telethon клиент инициализирован")
            return True
            
        except ValueError as e:
            logger.error(f"Telethon не настроен: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка инициализации Telethon: {e}")
            return False
    
    async def init_session(self):
        """Инициализация HTTP сессии"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
    
    async def close(self):
        """Закрытие соединений"""
        if self.session:
            await self.session.close()
        if self.tg_client:
            await self.tg_client.disconnect()
    
    def check_keywords(self, text: str) -> List[str]:
        """
        Проверяет наличие ключевых слов в тексте с умным поиском похожих слов
        
        Логика поиска:
        - Фразы из нескольких слов: точное вхождение фразы
        - Длинные слова (5+ символов): поиск как подстроки (запуск → запуски, запуска)
        - Короткие слова (3-4 символа): поиск по границам слов (забегаем ложных срабатываний)
        """
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in self.keywords:
            keyword_lower = keyword.lower()
            
            # Проверяем вхождение ключевого слова
            if self._keyword_matches(text_lower, keyword_lower):
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _keyword_matches(self, text: str, keyword: str) -> bool:
        """
        Проверяет соответствие ключевого слова тексту
        
        Args:
            text: текст в нижнем регистре
            keyword: ключевое слово в нижнем регистре
        """
        # Если ключевое слово содержит пробелы - это фраза
        if ' ' in keyword:
            return keyword in text
        
        # Для длинных слов (5+ символов) используем поиск подстроки
        if len(keyword) >= 5:
            return keyword in text
        
        # Для коротких слов (3-4 символа) ищем по границам слов
        # Это предотвращает ложные срабатывания типа "бот" в "работа"
        import re
        
        # Создаем паттерн для поиска слова с границами
        # \b - граница слова, но учитываем кириллицу и латиницу
        pattern = r'(?:^|[^\w]|[^\u0400-\u04FF\w])' + re.escape(keyword) + r'(?:[^\w]|[^\u0400-\u04FF\w]|$)'
        
        # Упрощенная проверка для коротких слов
        # Ищем точное совпадение с границами
        words = re.findall(r'\b\w+\b', text, re.UNICODE)
        return keyword in words
    
    def clean_text(self, text: str) -> str:
        """
        Очищает текст, преобразуя Markdown-форматирование Telegram в HTML
        и сохраняя существующее HTML-форматирование
        """
        if not text:
            return ""
        
        try:
            # Сначала обрабатываем Markdown
            
            # Сохраняем URL из [text](url) временно
            urls = {}
            def save_url(match):
                url_id = f"__URL_{len(urls)}__"
                urls[url_id] = match.group(2)
                return f"[{match.group(1)}]({url_id})"
            
            # Временно сохраняем URL
            text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', save_url, text)
            
            # Экранируем HTML-теги, которые могут быть в тексте
            text = text.replace('<', '&lt;').replace('>', '&gt;')
            
            # Конвертируем Markdown в HTML
            # Важно: порядок имеет значение! Сначала более специфичные паттерны
            
            # Моноширинный текст (код)
            text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
            
            # Спойлер
            text = re.sub(r'\|\|([^|]+)\|\|', r'<span class="tg-spoiler">\1</span>', text)
            
            # Жирный текст
            text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
            
            # Курсив (два варианта)
            text = re.sub(r'__([^_]+)__', r'<i>\1</i>', text)
            text = re.sub(r'_([^_]+)_', r'<i>\1</i>', text)
            
            # Зачеркнутый текст
            text = re.sub(r'~~([^~]+)~~', r'<s>\1</s>', text)
            
            # Цитаты (могут быть многострочными)
            text = re.sub(r'(?m)^>\s*(.+)$', r'<blockquote>\1</blockquote>', text)
            
            # Восстанавливаем URL с правильным HTML-форматированием
            for url_id, url in urls.items():
                text = text.replace(f']({url_id})', f'</a>')
                text = text.replace(f'[', f'<a href="{url}">')
            
            # Теперь обрабатываем существующие HTML-теги
            soup = BeautifulSoup(text, 'html.parser')
            
            # Функция для рекурсивной обработки текста с сохранением форматирования
            def process_node(node):
                if node.name == 'b' or node.name == 'strong':
                    return f"<b>{node.get_text()}</b>"
                elif node.name == 'i' or node.name == 'em':
                    return f"<i>{node.get_text()}</i>"
                elif node.name == 'u':
                    return f"<u>{node.get_text()}</u>"
                elif node.name == 's' or node.name == 'strike' or node.name == 'del':
                    return f"<s>{node.get_text()}</s>"
                elif node.name == 'code':
                    return f"<code>{node.get_text()}</code>"
                elif node.name == 'pre':
                    return f"<pre>{node.get_text()}</pre>"
                elif node.name == 'blockquote':
                    return f"<blockquote>{node.get_text()}</blockquote>"
                elif node.name == 'span' and 'tg-spoiler' in node.get('class', []):
                    return f'<span class="tg-spoiler">{node.get_text()}</span>'
                elif node.name == 'a' and node.get('href'):
                    return f"<a href=\"{node['href']}\">{node.get_text()}</a>"
                elif node.name == 'br':
                    return '\n'
                elif node.name is None:  # Текстовый узел
                    return node.string or ''
                else:
                    # Рекурсивно обрабатываем дочерние элементы
                    return ''.join(process_node(child) for child in node.children)
            
            # Обрабатываем весь текст
            formatted_text = ''.join(process_node(child) for child in soup.children)
            
            # Удаляем множественные переносы строк
            formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
            
            # Удаляем лишние пробелы, сохраняя переносы строк
            formatted_text = re.sub(r' +', ' ', formatted_text)
            formatted_text = re.sub(r' *\n *', '\n', formatted_text)
            
            return formatted_text.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при очистке текста: {e}")
            # В случае ошибки возвращаем просто очищенный текст
            return soup.get_text(' ', strip=True)
    
    async def monitor_rss_sources(self):
        """Мониторинг RSS источников"""
        logger.info("Начинаем мониторинг RSS источников")
        
        for rss_url in config.RSS_SOURCES:
            try:
                await self._process_rss_feed(rss_url)
            except Exception as e:
                logger.error(f"Ошибка обработки RSS {rss_url}: {e}")
    
    async def _process_rss_feed(self, rss_url: str):
        """Обрабатывает один RSS источник"""
        try:
            if not self.session:
                await self.init_session()
            
            async with self.session.get(rss_url) as response:
                if response.status != 200:
                    logger.warning(f"RSS {rss_url} вернул статус {response.status}")
                    return
                
                content = await response.text()
                
            # Парсим RSS
            feed = feedparser.parse(content)
            
            if not feed.entries:
                logger.warning(f"RSS {rss_url} не содержит записей")
                return
            
            source_name = feed.feed.get('title', rss_url)
            logger.info(f"Обрабатываем RSS: {source_name} ({len(feed.entries)} записей)")
            
            # Получаем время последней проверки
            last_check_time = self.last_check.get(f"rss_{rss_url}", 
                                                datetime.now() - timedelta(hours=24))
            
            new_entries = 0
            for entry in feed.entries:
                try:
                    # Парсим дату публикации
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    
                    # Пропускаем старые записи
                    if pub_date and pub_date <= last_check_time:
                        continue
                    
                    # Получаем текст
                    title = entry.get('title', '')
                    description = entry.get('description', '') or entry.get('summary', '')
                    full_text = f"{title}\n\n{description}"
                    clean_full_text = self.clean_text(full_text)
                    
                    # Проверяем ключевые слова
                    matched_keywords = self.check_keywords(clean_full_text)
                    
                    if matched_keywords:
                        # Проверяем, не добавлен ли уже этот контент
                        entry_url = entry.get('link', '')
                        if await db.check_content_exists('rss', entry_url):
                            continue
                        
                        # Добавляем в базу
                        draft_id = await db.add_content_draft(
                            source_type='rss',
                            source_name=source_name,
                            original_text=clean_full_text,
                            source_url=entry_url,
                            source_date=pub_date.isoformat() if pub_date else None,
                            keywords_matched=matched_keywords
                        )
                        
                        new_entries += 1
                        logger.info(f"Добавлен RSS контент #{draft_id}: {title[:50]}...")
                        
                        # Отправляем новый пост админу (если бот доступен)
                        await self._notify_admin_about_new_post(draft_id)
                
                except Exception as e:
                    logger.error(f"Ошибка обработки RSS записи: {e}")
                    continue
            
            # Обновляем время последней проверки
            self.last_check[f"rss_{rss_url}"] = datetime.now()
            logger.info(f"RSS {source_name}: добавлено {new_entries} новых записей")
            
        except Exception as e:
            logger.error(f"Ошибка обработки RSS {rss_url}: {e}")
    
    async def monitor_telegram_channels(self):
        """Мониторинг Telegram каналов"""
        if not self.tg_client:
            logger.warning("Telethon клиент не инициализирован")
            return
        
        logger.info("Начинаем мониторинг Telegram каналов")
        
        for channel in config.TG_CHANNELS:
            try:
                await self._process_telegram_channel(channel)
            except Exception as e:
                logger.error(f"Ошибка обработки канала {channel}: {e}")
    
    async def _process_telegram_channel(self, channel: str):
        """Обрабатывает один Telegram канал"""
        try:
            # Получаем информацию о канале
            entity = await self.tg_client.get_entity(channel)
            
            # Получаем время последней проверки
            last_check_time = self.last_check.get(f"tg_{channel}", 
                                                datetime.now() - timedelta(hours=24))
            
            # Получаем последние сообщения
            messages = await self.tg_client.get_messages(
                entity, 
                limit=50,
                offset_date=last_check_time
            )
            
            logger.info(f"Обрабатываем канал {channel}: {len(messages)} сообщений")
            
            new_entries = 0
            for message in reversed(messages):  # От старых к новым
                try:
                    if not message.text:
                        continue
                    
                    # Проверяем ключевые слова
                    matched_keywords = self.check_keywords(message.text)
                    
                    if matched_keywords:
                        # Формируем URL сообщения
                        message_url = f"https://t.me/{channel.replace('@', '')}/{message.id}"
                        
                        # Проверяем, не добавлен ли уже этот контент
                        if await db.check_content_exists('telegram', message_url):
                            continue
                        
                        # Добавляем в базу
                        draft_id = await db.add_content_draft(
                            source_type='telegram',
                            source_name=channel,
                            original_text=message.text,
                            source_url=message_url,
                            source_date=message.date.isoformat(),
                            keywords_matched=matched_keywords
                        )
                        
                        new_entries += 1
                        logger.info(f"Добавлен TG контент #{draft_id}: {message.text[:50]}...")
                        
                        # Отправляем новый пост админу (если бот доступен)
                        await self._notify_admin_about_new_post(draft_id)
                
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения: {e}")
                    continue
            
            # Обновляем время последней проверки
            self.last_check[f"tg_{channel}"] = datetime.now()
            logger.info(f"Канал {channel}: добавлено {new_entries} новых записей")
            
        except Exception as e:
            logger.error(f"Ошибка обработки канала {channel}: {e}")
    
    async def run_monitoring_cycle(self):
        """Запускает полный цикл мониторинга"""
        logger.info("=== Начинаем цикл мониторинга контента ===")
        
        try:
            # Инициализируем сессии
            await self.init_session()
            await self.init_telethon()
            
            # Мониторим RSS
            await self.monitor_rss_sources()
            
            # Мониторим Telegram каналы
            if self.tg_client:
                await self.monitor_telegram_channels()
            
            logger.info("=== Цикл мониторинга завершен ===")
            
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга: {e}")
        finally:
            await self.close()

    async def send_new_post_to_admin(self, bot, admin_id: int, post_data: Dict):
        """Отправляет новый найденный пост админу с возможностями перефразирования"""
        try:
            from emoji_config import get_emoji, safe_html_with_emoji
            from keyboards import get_new_post_keyboard
            
            # Текст уже содержит HTML-форматирование, просто экранируем спецсимволы
            safe_text = post_data['original_text']  # HTML-форматирование уже сохранено
            safe_source = safe_html_with_emoji(post_data.get('source_name', 'Неизвестно'))
            safe_url = safe_html_with_emoji(post_data.get('source_url', ''))
            safe_keywords = safe_html_with_emoji(', '.join(post_data.get('keywords_matched', [])))
            
            # Эмоджи для оформления
            source_emoji = "📡" if post_data.get('source_type') == 'rss' else "💬"
            new_emoji = get_emoji("sparkle")
            
            # Формируем сообщение
            message_text = f"{new_emoji} <b>Новый пост найден!</b>\n\n"
            message_text += f"{source_emoji} <b>Источник:</b> {safe_source}\n"
            message_text += f"📅 <b>Дата:</b> {post_data.get('source_date', 'Неизвестно')[:19]}\n"
            message_text += f"🔍 <b>Ключевые слова:</b> {safe_keywords}\n"
            
            if safe_url:
                message_text += f"🔗 <b>Ссылка:</b> {safe_url}\n"
            
            message_text += f"\n📝 <b>Исходный текст:</b>\n{safe_text}\n\n"  # Убрали <i> чтобы сохранить оригинальное форматирование
            
            # Добавляем анализ для советов
            from chatgpt_integration import chatgpt_rewriter
            suggestions = chatgpt_rewriter.get_rewrite_suggestions(post_data['original_text'])
            content_type = chatgpt_rewriter._detect_content_type(post_data['original_text'])
            
            type_names = {
                "news": "📰 Новость",
                "update": "🔄 Обновление", 
                "airdrop": "🎁 Airdrop",
                "analysis": "📊 Аналитика"
            }
            
            message_text += f"🎯 <b>Тип:</b> {type_names.get(content_type, '📝 Общий')}\n"
            
            if suggestions:
                message_text += f"💡 <b>Нужно улучшить:</b>\n"
                for suggestion in list(suggestions.values())[:3]:  # Показываем только первые 3
                    message_text += f"• {suggestion}\n"
            
            message_text += f"\n⚡ Выберите действие:"
            
            # Отправляем сообщение с клавиатурой
            await bot.send_message(
                chat_id=admin_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=get_new_post_keyboard(post_data['id'])
            )
            
            logger.info(f"Новый пост отправлен админу: {post_data['id']}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки поста админу: {e}")

    async def _notify_admin_about_new_post(self, draft_id: int):
        """Уведомляет всех админов о новом найденном посте"""
        try:
            draft = await db.get_draft_by_id(draft_id)
            if not draft:
                logger.error(f"Черновик #{draft_id} не найден")
                return
            # Рассылаем всем админам
            for user_id in ADMIN_USERS:
                await self.send_new_post_to_admin(self.bot_instance, user_id, draft)
                logger.info(f"Уведомление о посте #{draft_id} отправлено админу {user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о посте #{draft_id}: {e}")

    async def analyze_channel(self, source_type: str, source_url: str, messages: List[dict]) -> dict:
        """Анализирует канал и собирает статистику"""
        stats = {
            'total_posts': len(messages),
            'matched_posts': 0,
            'last_post_date': None,
            'avg_posts_per_day': 0,
            'most_used_keywords': {},
            'activity_hours': {str(h): 0 for h in range(24)}
        }

        if not messages:
            return stats

        # Анализ постов
        matched_keywords = {}
        for msg in messages:
            # Подсчет совпадений по ключевым словам
            text = msg.get('text', '')
            found_keywords = self._find_matching_keywords(text)
            if found_keywords:
                stats['matched_posts'] += 1
                for kw in found_keywords:
                    matched_keywords[kw] = matched_keywords.get(kw, 0) + 1

            # Анализ времени публикации
            if msg.get('date'):
                post_date = datetime.fromtimestamp(msg['date'])
                if not stats['last_post_date'] or post_date > datetime.fromisoformat(stats['last_post_date']):
                    stats['last_post_date'] = post_date.isoformat()
                stats['activity_hours'][str(post_date.hour)] += 1

        # Вычисляем среднее количество постов в день
        if stats['last_post_date']:
            days_diff = (datetime.now() - datetime.fromisoformat(stats['last_post_date'])).days or 1
            stats['avg_posts_per_day'] = round(stats['total_posts'] / days_diff, 2)

        # Топ используемых ключевых слов
        stats['most_used_keywords'] = dict(sorted(
            matched_keywords.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10])

        return stats

    def _find_matching_keywords(self, text: str) -> List[str]:
        """Находит все совпадающие ключевые слова в тексте"""
        matched = []
        text_lower = text.lower()
        for keyword in self.keywords:
            if self._keyword_matches(text_lower, keyword.lower()):
                matched.append(keyword)
        return matched

    async def process_telegram_messages(self, channel: str, messages: List[dict]) -> List[dict]:
        """Обрабатывает сообщения из Telegram канала"""
        new_drafts = []
        
        # Анализируем канал
        stats = await self.analyze_channel('tg', channel, messages)
        await db.update_channel_stats('tg', channel, stats)
        
        # Обрабатываем сообщения
        for message in messages:
            if not message.get('text'):
                continue
                
            # Проверяем дату поста
            post_date = datetime.fromtimestamp(message['date'], tz=timezone.utc)
            if post_date < CUTOFF_DATE:
                logger.debug(f"Пропускаем старый пост от {post_date.isoformat()}")
                continue
                
            # Проверяем наличие ключевых слов
            if not any(kw.lower() in message['text'].lower() for kw in self.keywords):
                continue
                
            # Проверяем дубликаты
            source_url = f"https://t.me/{channel}/{message.get('id', '')}"
            if await db.check_content_exists('tg', source_url):
                continue
                
            # Добавляем в черновики
            draft_id = await db.add_content_draft(
                source_type='tg',
                source_name=channel,
                original_text=message['text'],
                source_url=source_url,
                source_date=post_date.isoformat(),
                keywords_matched=self._find_matching_keywords(message['text'])
            )
            
            if draft_id:
                new_drafts.append({
                    'id': draft_id,
                    'text': message['text'][:100] + '...',
                    'source': channel,
                    'date': post_date.isoformat()
                })
                
        # Отправляем уведомление только если есть новые посты
        if new_drafts and self.bot_instance:
            summary = f"📊 <b>Новые посты из {channel}:</b>\n\n"
            for draft in new_drafts:
                date_str = datetime.fromisoformat(draft['date']).strftime('%d.%m.%Y %H:%M')
                summary += f"• [{date_str}] {draft['text']}\n"
            summary += f"\nВсего найдено: {len(new_drafts)}"
            
            # Use Bot instance carefully without any proxy settings
            for user_id in config.ADMIN_USERS:
                try:
                    # Make sure to use only the required parameters
                    message_params = {
                        'chat_id': user_id,
                        'text': summary,
                        'parse_mode': "HTML"
                    }
                    await self.bot_instance.send_message(**message_params)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        
        return new_drafts

    async def process_rss_feed(self, feed_url: str, entries: List[dict]) -> List[dict]:
        """Обрабатывает записи из RSS ленты"""
        new_drafts = []
        
        # Анализируем ленту
        stats = await self.analyze_channel('rss', feed_url, [
            {'text': entry.get('title', '') + ' ' + entry.get('description', ''),
             'date': datetime.strptime(entry.get('published', ''), '%a, %d %b %Y %H:%M:%S %z').timestamp()
             if entry.get('published') else datetime.now().timestamp()}
            for entry in entries
        ])
        await db.update_channel_stats('rss', feed_url, stats)
        
        # Обрабатываем записи
        for entry in entries:
            title = entry.get('title', '')
            description = entry.get('description', '')
            text = f"{title}\n\n{description}"
            
            # Парсим и проверяем дату
            try:
                if entry.get('published'):
                    post_date = datetime.strptime(entry['published'], '%a, %d %b %Y %H:%M:%S %z')
                else:
                    post_date = datetime.now(timezone.utc)
                
                if post_date < CUTOFF_DATE:
                    logger.debug(f"Пропускаем старую RSS запись от {post_date.isoformat()}")
                    continue
            except Exception as e:
                logger.error(f"Ошибка парсинга даты RSS: {e}")
                post_date = datetime.now(timezone.utc)
            
            # Проверяем наличие ключевых слов
            if not any(kw.lower() in text.lower() for kw in self.keywords):
                continue
                
            # Проверяем дубликаты
            if await db.check_content_exists('rss', entry.get('link', '')):
                continue
                
            # Добавляем в черновики
            draft_id = await db.add_content_draft(
                source_type='rss',
                source_name=feed_url,
                original_text=text,
                source_url=entry.get('link', ''),
                source_date=post_date.isoformat(),
                keywords_matched=self._find_matching_keywords(text)
            )
            
            if draft_id:
                new_drafts.append({
                    'id': draft_id,
                    'text': text[:100] + '...',
                    'source': feed_url,
                    'date': post_date.isoformat()
                })
        
            # Отправляем уведомление только если есть новые посты
        if new_drafts and self.bot_instance:
            summary = f"📊 <b>Новые записи из {feed_url}:</b>\n\n"
            for draft in new_drafts:
                date_str = datetime.fromisoformat(draft['date']).strftime('%d.%m.%Y %H:%M')
                summary += f"• [{date_str}] {draft['text']}\n"
            summary += f"\nВсего найдено: {len(new_drafts)}"
            
            # Use Bot instance carefully without any proxy settings
            for user_id in config.ADMIN_USERS:
                try:
                    # Make sure to use only the required parameters
                    message_params = {
                        'chat_id': user_id,
                        'text': summary,
                        'parse_mode': "HTML"
                    }
                    await self.bot_instance.send_message(**message_params)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        
        return new_drafts# Глобальный экземпляр мониторинга
content_monitor = ContentMonitor() 