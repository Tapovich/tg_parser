import asyncio
import logging
import feedparser
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import re
from bs4 import BeautifulSoup
import os
import time

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

# Очищаем переменные окружения от прокси на уровне модуля
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]
        logger.info(f"Удалена переменная окружения: {var}")

class ContentMonitor:
    def __init__(self):
        self.session = None
        self.tg_client = None
        self.keywords = config.KEYWORDS
        self.last_check = {}
        self.bot_instance = None
        self.last_notification_time = {}  # Для защиты от flood control
        self.min_notification_interval = 30  # Минимальный интервал между уведомлениями (секунды)
        
    async def safe_send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        """Безопасная отправка сообщения с защитой от flood control"""
        try:
            # Проверяем, не слишком ли часто отправляем сообщения
            current_time = time.time()
            last_time = self.last_notification_time.get(chat_id, 0)
            
            if current_time - last_time < self.min_notification_interval:
                wait_time = self.min_notification_interval - (current_time - last_time)
                logger.info(f"Ждем {wait_time:.1f} секунд перед отправкой сообщения пользователю {chat_id}")
                await asyncio.sleep(wait_time)
            
            message_params = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            await self.bot_instance.send_message(**message_params)
            
            # Обновляем время последней отправки
            self.last_notification_time[chat_id] = time.time()
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю {chat_id}: {e}")
            # При ошибке flood control ждем дольше
            if "Flood control" in str(e) or "Too Many Requests" in str(e):
                logger.warning(f"Flood control для пользователя {chat_id}, ждем 5 минут")
                self.last_notification_time[chat_id] = time.time() + 300  # 5 минут
        
    def set_bot_instance(self, bot_instance):
        """Устанавливает экземпляр бота для отправки уведомлений"""
        self.bot_instance = bot_instance
        logger.info(f"Экземпляр бота установлен в content_monitor: {bot_instance is not None}")
        if bot_instance:
            logger.info(f"Бот ID: {getattr(bot_instance, 'id', 'неизвестно')}")
        else:
            logger.warning("Экземпляр бота не передан!")
        
    async def init_telethon(self):
        """Инициализация Telethon клиента"""
        if not TELETHON_AVAILABLE:
            logger.warning("Telethon недоступен")
            return False
            
        try:
            config.validate_telethon()
            
            # Очищаем переменные окружения перед инициализацией Telethon
            proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']
            for var in proxy_vars:
                if var in os.environ:
                    del os.environ[var]
            
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
        # Очищаем переменные окружения перед созданием сессии
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']
        for var in proxy_vars:
            if var in os.environ:
                del os.environ[var]
        
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
        """
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in self.keywords:
            keyword_lower = keyword.lower()
            if self._keyword_matches(text_lower, keyword_lower):
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _keyword_matches(self, text: str, keyword: str) -> bool:
        """
        Проверяет соответствие ключевого слова тексту
        """
        if ' ' in keyword:
            return keyword in text
        if len(keyword) >= 5:
            return keyword in text
        import re
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
            urls = {}
            def save_url(match):
                url_id = f"__URL_{len(urls)}__"
                urls[url_id] = match.group(2)
                return f"[{match.group(1)}]({url_id})"
            text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', save_url, text)
            text = text.replace('<', '&lt;').replace('>', '&gt;')
            text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
            text = re.sub(r'\|\|([^|]+)\|\|', r'<span class="tg-spoiler">\1</span>', text)
            text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'__([^_]+)__', r'<i>\1</i>', text)
            text = re.sub(r'_([^_]+)_', r'<i>\1</i>', text)
            text = re.sub(r'~~([^~]+)~~', r'<s>\1</s>', text)
            text = re.sub(r'(?m)^>\s*(.+)$', r'<blockquote>\1</blockquote>', text)
            for url_id, url in urls.items():
                text = text.replace(f']({url_id})', f'</a>')
                text = text.replace(f'[', f'<a href="{url}">')
            soup = BeautifulSoup(text, 'html.parser')
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
                elif node.name is None:
                    return node.string or ''
                else:
                    return ''.join(process_node(child) for child in node.children)
            formatted_text = ''.join(process_node(child) for child in soup.children)
            formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
            formatted_text = re.sub(r' +', ' ', formatted_text)
            formatted_text = re.sub(r' *\n *', '\n', formatted_text)
            return formatted_text.strip()
        except Exception as e:
            logger.error(f"Ошибка при очистке текста: {e}")
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
            feed = feedparser.parse(content)
            if not feed.entries:
                logger.warning(f"RSS {rss_url} не содержит записей")
                return
            source_name = feed.feed.get('title', rss_url)
            logger.info(f"Обрабатываем RSS: {source_name} ({len(feed.entries)} записей)")
            
            # Получаем время последней проверки из базы данных
            last_check_time = await self._get_last_check_time(f"rss_{rss_url}")
            if not last_check_time:
                # Если нет записи в БД, берем время 24 часа назад с UTC
                last_check_time = datetime.now(timezone.utc) - timedelta(hours=24)
                logger.info(f"RSS {rss_url}: нет записи в БД, берем время {last_check_time}")
            else:
                # Убеждаемся, что last_check_time имеет часовой пояс
                if last_check_time.tzinfo is None:
                    last_check_time = last_check_time.replace(tzinfo=timezone.utc)
                
                # Добавляем буфер времени для компенсации разницы часовых поясов
                # Отнимаем 6 часов от времени последней проверки, чтобы захватить больше записей
                last_check_time = last_check_time - timedelta(hours=6)
                logger.info(f"RSS {rss_url}: время последней проверки {last_check_time} (с буфером -6ч)")
            
            new_entries = 0
            for entry in feed.entries:
                try:
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        # Создаем datetime с UTC
                        pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        # Создаем datetime с UTC
                        pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                    
                    # Пропускаем старые записи
                    if pub_date and pub_date <= last_check_time:
                        logger.debug(f"Пропускаем старую RSS запись: {pub_date} <= {last_check_time}")
                        continue
                    
                    title = entry.get('title', '')
                    description = entry.get('description', '') or entry.get('summary', '')
                    full_text = f"{title}\n\n{description}"
                    clean_full_text = self.clean_text(full_text)
                    matched_keywords = self.check_keywords(clean_full_text)
                    logger.debug(f"RSS запись '{title}': найдены ключевые слова {matched_keywords}")
                    
                    if matched_keywords:
                        entry_url = entry.get('link', '')
                        if await db.check_content_exists('rss', entry_url):
                            logger.debug(f"RSS пост уже существует: {entry_url}")
                            continue
                        
                        logger.info(f"Добавляем новый RSS пост: {title[:50]}...")
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
                        
                        # Проверяем, что бот доступен для уведомлений
                        if self.bot_instance:
                            logger.info(f"Отправляем уведомление о RSS посте #{draft_id}")
                            await self._notify_admin_about_new_post(draft_id)
                        else:
                            logger.warning(f"Бот не доступен для уведомления о RSS посте #{draft_id}")
                    else:
                        logger.debug(f"RSS запись '{title}' не содержит ключевых слов")
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки RSS записи: {e}")
                    continue
            
            # Обновляем время последней проверки в БД
            await self._update_last_check_time(f"rss_{rss_url}")
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
            entity = await self.tg_client.get_entity(channel)
            
            # Получаем время последней проверки из базы данных
            last_check_time = await self._get_last_check_time(f"tg_{channel}")
            if not last_check_time:
                # Если нет записи в БД, берем время 24 часа назад с UTC
                last_check_time = datetime.now(timezone.utc) - timedelta(hours=24)
                logger.info(f"Канал {channel}: нет записи в БД, берем время {last_check_time}")
            else:
                # Убеждаемся, что last_check_time имеет часовой пояс
                if last_check_time.tzinfo is None:
                    last_check_time = last_check_time.replace(tzinfo=timezone.utc)
                
                # Добавляем буфер времени для компенсации разницы часовых поясов
                # Отнимаем 6 часов от времени последней проверки, чтобы захватить больше сообщений
                last_check_time = last_check_time - timedelta(hours=6)
                logger.info(f"Канал {channel}: время последней проверки {last_check_time} (с буфером -6ч)")
            
            messages = await self.tg_client.get_messages(
                entity, 
                limit=50,
                offset_date=last_check_time
            )
            logger.info(f"Обрабатываем канал {channel}: {len(messages)} сообщений")
            new_entries = 0
            for message in reversed(messages):
                try:
                    if not message.text:
                        logger.debug(f"Пропускаем сообщение без текста: {message.id}")
                        continue
                    
                    # Проверяем, что сообщение действительно новое
                    # message.date уже имеет часовой пояс от Telethon
                    if message.date <= last_check_time:
                        logger.debug(f"Пропускаем старое сообщение {message.id}: {message.date} <= {last_check_time}")
                        continue
                    
                    logger.debug(f"Обрабатываем новое сообщение {message.id}: {message.date}")
                    matched_keywords = self.check_keywords(message.text)
                    logger.debug(f"Найдены ключевые слова: {matched_keywords}")
                    
                    if matched_keywords:
                        message_url = f"https://t.me/{channel.replace('@', '')}/{message.id}"
                        if await db.check_content_exists('telegram', message_url):
                            logger.debug(f"Пост уже существует: {message_url}")
                            continue
                        
                        logger.info(f"Добавляем новый TG пост: {message.text[:50]}...")
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
                        
                        # Проверяем, что бот доступен для уведомлений
                        if self.bot_instance:
                            logger.info(f"Отправляем уведомление о посте #{draft_id}")
                            await self._notify_admin_about_new_post(draft_id)
                        else:
                            logger.warning(f"Бот не доступен для уведомления о посте #{draft_id}")
                    else:
                        logger.debug(f"Сообщение {message.id} не содержит ключевых слов")
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения: {e}")
                    continue
            
            # Обновляем время последней проверки в БД
            await self._update_last_check_time(f"tg_{channel}")
            logger.info(f"Канал {channel}: добавлено {new_entries} новых записей")
        except Exception as e:
            logger.error(f"Ошибка обработки канала {channel}: {e}")
    
    async def _get_last_check_time(self, source_key: str) -> Optional[datetime]:
        """Получает время последней проверки из базы данных"""
        try:
            # Получаем из БД время последней проверки
            result = await db.get_setting(f"last_check_{source_key}")
            if result:
                dt = datetime.fromisoformat(result)
                # Убеждаемся, что datetime имеет часовой пояс
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        except Exception as e:
            logger.error(f"Ошибка получения времени последней проверки: {e}")
        return None
    
    async def _update_last_check_time(self, source_key: str):
        """Обновляет время последней проверки в базе данных"""
        try:
            # Сохраняем время с UTC
            current_time = datetime.now(timezone.utc)
            await db.set_setting(f"last_check_{source_key}", current_time.isoformat())
        except Exception as e:
            logger.error(f"Ошибка обновления времени последней проверки: {e}")
    
    async def run_monitoring_cycle(self):
        """Запускает полный цикл мониторинга"""
        logger.info("=== Начинаем цикл мониторинга контента ===")
        try:
            await self.init_session()
            await self.init_telethon()
            await self.monitor_rss_sources()
            if self.tg_client:
                await self.monitor_telegram_channels()
            logger.info("=== Цикл мониторинга завершен ===")
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга: {e}")
        finally:
            await self.close()

    async def send_new_post_to_admin(self, bot, admin_id: int, post_data: Dict):
        """Отправляет новый найденный пост админу с защитой от flood control"""
        try:
            from emoji_config import get_emoji, safe_html_with_emoji
            from keyboards import get_new_post_keyboard
            
            # Проверяем, что бот доступен
            if not bot:
                logger.error("Бот не доступен для отправки сообщения")
                return
                
            safe_text = post_data['original_text']
            safe_source = safe_html_with_emoji(post_data.get('source_name', 'Неизвестно'))
            safe_url = safe_html_with_emoji(post_data.get('source_url', ''))
            safe_keywords = safe_html_with_emoji(', '.join(post_data.get('keywords_matched', [])))
            source_emoji = "📡" if post_data.get('source_type') == 'rss' else "💬"
            new_emoji = get_emoji("sparkle")
            message_text = f"{new_emoji} <b>Новый пост найден!</b>\n\n"
            message_text += f"{source_emoji} <b>Источник:</b> {safe_source}\n"
            message_text += f"📅 <b>Дата:</b> {post_data.get('source_date', 'Неизвестно')[:19]}\n"
            message_text += f"🔍 <b>Ключевые слова:</b> {safe_keywords}\n"
            if safe_url:
                message_text += f"🔗 <b>Ссылка:</b> {safe_url}\n"
            message_text += f"\n📝 <b>Исходный текст:</b>\n{safe_text}\n\n"
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
                for suggestion in list(suggestions.values())[:3]:
                    message_text += f"• {suggestion}\n"
            message_text += f"\n⚡ Выберите действие:"
            
            # Создаем клавиатуру с кнопками
            keyboard = get_new_post_keyboard(post_data['id'])
            
            # Используем безопасную отправку с защитой от flood control
            await self.safe_send_message(
                chat_id=admin_id,
                text=message_text,
                parse_mode="HTML"
            )
            
            # Отправляем клавиатуру отдельным сообщением
            await bot.send_message(
                chat_id=admin_id,
                text="🎛 <b>Действия с постом:</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            logger.info(f"Новый пост отправлен админу: {post_data['id']}")
        except Exception as e:
            logger.error(f"Ошибка отправки поста админу: {e}")
            # Дополнительная отладочная информация
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def _notify_admin_about_new_post(self, draft_id: int):
        """Уведомляет всех админов о новом найденном посте с защитой от flood control"""
        try:
            logger.info(f"Начинаем уведомление о посте #{draft_id}")
            draft = await db.get_draft_by_id(draft_id)
            if not draft:
                logger.error(f"Черновик #{draft_id} не найден")
                return
            
            logger.info(f"Черновик #{draft_id} найден: {draft.get('original_text', '')[:50]}...")
            
            # Отправляем уведомления с задержкой между админами
            for i, user_id in enumerate(ADMIN_USERS):
                try:
                    logger.info(f"Отправляем уведомление админу {user_id} о посте #{draft_id}")
                    await self.send_new_post_to_admin(self.bot_instance, user_id, draft)
                    logger.info(f"Уведомление о посте #{draft_id} отправлено админу {user_id}")
                    
                    # Добавляем задержку между отправками для защиты от flood control
                    if i < len(ADMIN_USERS) - 1:  # Не ждем после последнего админа
                        await asyncio.sleep(2)  # 2 секунды между уведомлениями
                        
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {user_id}: {e}")
                    
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
        matched_keywords = {}
        for msg in messages:
            text = msg.get('text', '')
            found_keywords = self._find_matching_keywords(text)
            if found_keywords:
                stats['matched_posts'] += 1
                for kw in found_keywords:
                    matched_keywords[kw] = matched_keywords.get(kw, 0) + 1
            if msg.get('date'):
                post_date = datetime.fromtimestamp(msg['date'])
                if not stats['last_post_date'] or post_date > datetime.fromisoformat(stats['last_post_date']):
                    stats['last_post_date'] = post_date.isoformat()
                stats['activity_hours'][str(post_date.hour)] += 1
        if stats['last_post_date']:
            days_diff = (datetime.now() - datetime.fromisoformat(stats['last_post_date'])).days or 1
            stats['avg_posts_per_day'] = round(stats['total_posts'] / days_diff, 2)
        stats['most_used_keywords'] = dict(sorted(
            matched_keywords.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10])
        return stats

    def _find_matching_keywords(self, text: str) -> List[str]:
        matched = []
        text_lower = text.lower()
        for keyword in self.keywords:
            if self._keyword_matches(text_lower, keyword.lower()):
                matched.append(keyword)
        return matched

    async def process_telegram_messages(self, channel: str, messages: List[dict]) -> List[dict]:
        new_drafts = []
        stats = await self.analyze_channel('tg', channel, messages)
        await db.update_channel_stats('tg', channel, stats)
        for message in messages:
            if not message.get('text'):
                continue
            post_date = datetime.fromtimestamp(message['date'], tz=timezone.utc)
            if post_date < CUTOFF_DATE:
                logger.debug(f"Пропускаем старый пост от {post_date.isoformat()}")
                continue
            if not any(kw.lower() in message['text'].lower() for kw in self.keywords):
                continue
            source_url = f"https://t.me/{channel}/{message.get('id', '')}"
            if await db.check_content_exists('tg', source_url):
                continue
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
        if new_drafts and self.bot_instance:
            summary = f"📊 <b>Новые посты из {channel}:</b>\n\n"
            for draft in new_drafts:
                date_str = datetime.fromisoformat(draft['date']).strftime('%d.%m.%Y %H:%M')
                summary += f"• [{date_str}] {draft['text']}\n"
            summary += f"\nВсего найдено: {len(new_drafts)}"
            for user_id in config.ADMIN_USERS:
                try:
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
        new_drafts = []
        stats = await self.analyze_channel('rss', feed_url, [
            {'text': entry.get('title', '') + ' ' + entry.get('description', ''),
             'date': datetime.strptime(entry.get('published', ''), '%a, %d %b %Y %H:%M:%S %z').timestamp()
             if entry.get('published') else datetime.now().timestamp()}
            for entry in entries
        ])
        await db.update_channel_stats('rss', feed_url, stats)
        for entry in entries:
            title = entry.get('title', '')
            description = entry.get('description', '')
            text = f"{title}\n\n{description}"
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
            if not any(kw.lower() in text.lower() for kw in self.keywords):
                continue
            if await db.check_content_exists('rss', entry.get('link', '')):
                continue
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
        if new_drafts and self.bot_instance:
            summary = f"📊 <b>Новые записи из {feed_url}:</b>\n\n"
            for draft in new_drafts:
                date_str = datetime.fromisoformat(draft['date']).strftime('%d.%m.%Y %H:%M')
                summary += f"• [{date_str}] {draft['text']}\n"
            summary += f"\nВсего найдено: {len(new_drafts)}"
            for user_id in config.ADMIN_USERS:
                try:
                    message_params = {
                        'chat_id': user_id,
                        'text': summary,
                        'parse_mode': "HTML"
                    }
                    await self.bot_instance.send_message(**message_params)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        return new_drafts

content_monitor = ContentMonitor() 