import aiosqlite
import asyncio
from typing import List, Dict, Optional
import json
from datetime import datetime
import os

# Очищаем переменные окружения от прокси на уровне модуля
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        
    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица для хранения постов на модерации
            await db.execute('''
                CREATE TABLE IF NOT EXISTS pending_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_text TEXT NOT NULL,
                    rewritten_text TEXT NOT NULL,
                    source_url TEXT,
                    source_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            
            # Таблица для ключевых слов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Таблица для источников
            await db.execute('''
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_check TIMESTAMP
                )
            ''')
            
            # Таблица для настроек
            await db.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            
            # Таблица для черновиков постов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS content_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    original_text TEXT NOT NULL,
                    source_url TEXT,
                    source_date TIMESTAMP,
                    keywords_matched TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'new',
                    processed_at TIMESTAMP
                )
            ''')
            
            # Таблица для опубликованных постов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS published_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pending_post_id INTEGER,
                    draft_id INTEGER,
                    original_text TEXT NOT NULL,
                    published_text TEXT NOT NULL,
                    source_url TEXT,
                    source_type TEXT,
                    channel_id TEXT NOT NULL,
                    message_id INTEGER,
                    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (pending_post_id) REFERENCES pending_posts (id),
                    FOREIGN KEY (draft_id) REFERENCES content_drafts (id)
                )
            ''')
            
            # Таблица для логирования действий
            await db.execute('''
                CREATE TABLE IF NOT EXISTS action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id INTEGER NOT NULL,
                    details TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для дайджестов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS digest_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    digest_time TEXT NOT NULL,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    last_sent TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для статистики каналов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS channel_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    total_posts INTEGER DEFAULT 0,
                    matched_posts INTEGER DEFAULT 0,
                    last_post_date TIMESTAMP,
                    avg_posts_per_day REAL DEFAULT 0,
                    most_used_keywords TEXT,
                    activity_hours TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_type, source_url)
                )
            ''')
            
            await db.commit()
    
    async def add_pending_post(self, original_text: str, rewritten_text: str, 
                              source_url: str = None, source_type: str = None) -> int:
        """Добавляет пост на модерацию"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO pending_posts (original_text, rewritten_text, source_url, source_type)
                VALUES (?, ?, ?, ?)
            ''', (original_text, rewritten_text, source_url, source_type))
            await db.commit()
            return cursor.lastrowid
    
    async def get_pending_post(self, post_id: int) -> Optional[Dict]:
        """Получает пост на модерации по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM pending_posts WHERE id = ? AND status = 'pending'
            ''', (post_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_post_by_id(self, post_id: int) -> Optional[Dict]:
        """Получает пост по ID независимо от статуса"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM pending_posts WHERE id = ?
            ''', (post_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_post_status(self, post_id: int, status: str):
        """Обновляет статус поста"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE pending_posts SET status = ? WHERE id = ?
            ''', (status, post_id))
            await db.commit()
    
    async def update_post_text(self, post_id: int, new_text: str):
        """Обновляет текст поста"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE pending_posts SET rewritten_text = ? WHERE id = ?
            ''', (new_text, post_id))
            await db.commit()
    
    async def add_keyword(self, keyword: str):
        """Добавляет ключевое слово"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR IGNORE INTO keywords (keyword) VALUES (?)
            ''', (keyword.lower(),))
            await db.commit()
    
    async def get_keywords(self) -> List[str]:
        """Получает все активные ключевые слова"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT keyword FROM keywords WHERE is_active = TRUE
            ''')
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def add_content_draft(self, source_type: str, source_name: str, 
                               original_text: str, source_url: str = None, 
                               source_date: str = None, keywords_matched: List[str] = None) -> int:
        """Добавляет черновик контента"""
        keywords_str = ','.join(keywords_matched) if keywords_matched else ''
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO content_drafts 
                (source_type, source_name, original_text, source_url, source_date, keywords_matched)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (source_type, source_name, original_text, source_url, source_date, keywords_str))
            await db.commit()
            return cursor.lastrowid
    
    async def get_content_drafts(self, status: str = 'new', limit: int = 50) -> List[Dict]:
        """Получает черновики контента по статусу"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM content_drafts 
                WHERE status = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (status, limit))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_draft_status(self, draft_id: int, status: str):
        """Обновляет статус черновика"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE content_drafts 
                SET status = ?, processed_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (status, draft_id))
            await db.commit()
    
    async def get_draft_by_id(self, draft_id: int) -> Optional[Dict]:
        """Получает черновик по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM content_drafts WHERE id = ?
            ''', (draft_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def check_content_exists(self, source_type: str, source_url: str) -> bool:
        """Проверяет, существует ли уже контент с таким URL"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT id FROM content_drafts 
                WHERE source_type = ? AND source_url = ?
            ''', (source_type, source_url))
            row = await cursor.fetchone()
            return row is not None
    
    async def add_published_post(self, pending_post_id: int = None, draft_id: int = None,
                                original_text: str = None, published_text: str = None,
                                source_url: str = None, source_type: str = None,
                                channel_id: str = None, message_id: int = None) -> int:
        """Добавляет запись об опубликованном посте"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO published_posts 
                (pending_post_id, draft_id, original_text, published_text, 
                 source_url, source_type, channel_id, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (pending_post_id, draft_id, original_text, published_text,
                  source_url, source_type, channel_id, message_id))
            await db.commit()
            return cursor.lastrowid
    
    async def get_published_posts_stats(self) -> Dict:
        """Получает статистику опубликованных постов"""
        async with aiosqlite.connect(self.db_path) as db:
            # Общее количество
            cursor = await db.execute('SELECT COUNT(*) FROM published_posts')
            total = (await cursor.fetchone())[0]
            
            # За последние 24 часа
            cursor = await db.execute('''
                SELECT COUNT(*) FROM published_posts 
                WHERE published_at > datetime('now', '-24 hours')
            ''')
            last_24h = (await cursor.fetchone())[0]
            
            # За последние 7 дней
            cursor = await db.execute('''
                SELECT COUNT(*) FROM published_posts 
                WHERE published_at > datetime('now', '-7 days')
            ''')
            last_7d = (await cursor.fetchone())[0]
            
            return {
                'total': total,
                'last_24h': last_24h,
                'last_7d': last_7d
            }
    
    async def log_action(self, user_id: int, action_type: str, target_type: str, 
                        target_id: int, details: str = None, old_value: str = None, 
                        new_value: str = None) -> int:
        """Записывает действие в лог"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO action_logs 
                (user_id, action_type, target_type, target_id, details, old_value, new_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, action_type, target_type, target_id, details, old_value, new_value))
            await db.commit()
            return cursor.lastrowid
    
    async def get_action_logs(self, limit: int = 50, action_type: str = None) -> List[Dict]:
        """Получает логи действий"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if action_type:
                cursor = await db.execute('''
                    SELECT * FROM action_logs 
                    WHERE action_type = ?
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (action_type, limit))
            else:
                cursor = await db.execute('''
                    SELECT * FROM action_logs 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_comprehensive_stats(self) -> Dict:
        """Получает расширенную статистику"""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            
            # Статистика черновиков
            cursor = await db.execute('SELECT status, COUNT(*) FROM content_drafts GROUP BY status')
            drafts_stats = await cursor.fetchall()
            stats['drafts'] = {status: count for status, count in drafts_stats}
            
            # Статистика постов
            cursor = await db.execute('SELECT status, COUNT(*) FROM pending_posts GROUP BY status')
            posts_stats = await cursor.fetchall()
            stats['posts'] = {status: count for status, count in posts_stats}
            
            # Статистика публикаций
            cursor = await db.execute('SELECT COUNT(*) FROM published_posts')
            published_count = (await cursor.fetchone())[0]
            stats['published_total'] = published_count
            
            # Статистика по дням
            cursor = await db.execute('''
                SELECT DATE(published_at) as date, COUNT(*) as count 
                FROM published_posts 
                WHERE published_at > datetime('now', '-7 days')
                GROUP BY DATE(published_at)
                ORDER BY date DESC
            ''')
            daily_stats = await cursor.fetchall()
            stats['daily_published'] = {date: count for date, count in daily_stats}
            
            # Статистика источников
            cursor = await db.execute('''
                SELECT source_type, COUNT(*) as count 
                FROM content_drafts 
                GROUP BY source_type
            ''')
            source_stats = await cursor.fetchall()
            stats['sources'] = {source: count for source, count in source_stats}
            
            return stats
    
    async def get_last_published_posts(self, limit: int = 10) -> List[Dict]:
        """Получает последние опубликованные посты"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM published_posts 
                ORDER BY published_at DESC 
                LIMIT ?
            ''', (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def set_digest_time(self, user_id: int, digest_time: str) -> int:
        """Устанавливает время для ежедневного дайджеста"""
        async with aiosqlite.connect(self.db_path) as db:
            # Удаляем старые настройки
            await db.execute('DELETE FROM digest_settings WHERE user_id = ?', (user_id,))
            
            # Добавляем новые
            cursor = await db.execute('''
                INSERT INTO digest_settings (user_id, digest_time)
                VALUES (?, ?)
            ''', (user_id, digest_time))
            await db.commit()
            return cursor.lastrowid
    
    async def get_digest_settings(self, user_id: int) -> Optional[Dict]:
        """Получает настройки дайджеста для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM digest_settings WHERE user_id = ? AND is_enabled = TRUE
            ''', (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_digest_last_sent(self, user_id: int):
        """Обновляет время последней отправки дайджеста"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE digest_settings 
                SET last_sent = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            ''', (user_id,))
            await db.commit()
    
    async def get_digest_drafts(self, limit: int = 5) -> List[Dict]:
        """Получает черновики для дайджеста (новые за последние 24 часа)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM content_drafts 
                WHERE status = 'new' 
                AND created_at > datetime('now', '-24 hours')
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def disable_digest(self, user_id: int):
        """Отключает дайджест для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE digest_settings 
                SET is_enabled = FALSE 
                WHERE user_id = ?
            ''', (user_id,))
            await db.commit()

    async def add_source(self, source_type: str, source_url: str) -> int:
        """Добавляет источник (RSS или TG канал)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT OR IGNORE INTO sources (source_type, source_url, is_active)
                VALUES (?, ?, TRUE)
            ''', (source_type, source_url))
            await db.commit()
            return cursor.lastrowid

    async def remove_source(self, source_type: str, source_url: str) -> int:
        """Удаляет (деактивирует) источник"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                UPDATE sources SET is_active = FALSE WHERE source_type = ? AND source_url = ?
            ''', (source_type, source_url))
            await db.commit()
            return cursor.rowcount

    async def get_sources(self, source_type: str = None, only_active: bool = True) -> list:
        """Получает список источников (RSS или TG)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = 'SELECT * FROM sources WHERE 1=1'
            params = []
            if source_type:
                query += ' AND source_type = ?'
                params.append(source_type)
            if only_active:
                query += ' AND is_active = TRUE'
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_channel_stats(self, source_type: str, source_url: str, stats_data: dict):
        """Обновляет статистику канала"""
        async with aiosqlite.connect(self.db_path) as db:
            # Конвертируем словари в JSON для хранения
            if 'most_used_keywords' in stats_data and isinstance(stats_data['most_used_keywords'], dict):
                stats_data['most_used_keywords'] = json.dumps(stats_data['most_used_keywords'])
            if 'activity_hours' in stats_data and isinstance(stats_data['activity_hours'], dict):
                stats_data['activity_hours'] = json.dumps(stats_data['activity_hours'])

            # Формируем SQL запрос динамически
            fields = ', '.join(stats_data.keys())
            placeholders = ', '.join(['?' for _ in stats_data])
            values = list(stats_data.values())

            await db.execute(f'''
                INSERT INTO channel_stats (source_type, source_url, {fields}, updated_at)
                VALUES (?, ?, {placeholders}, CURRENT_TIMESTAMP)
                ON CONFLICT(source_type, source_url) DO UPDATE SET
                {', '.join(f'{k}=excluded.{k}' for k in stats_data.keys())},
                updated_at=CURRENT_TIMESTAMP
            ''', [source_type, source_url] + values)
            
            await db.commit()

    async def get_channel_stats(self, source_type: str = None, source_url: str = None) -> List[Dict]:
        """Получает статистику каналов"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            query = 'SELECT * FROM channel_stats WHERE 1=1'
            params = []
            
            if source_type:
                query += ' AND source_type = ?'
                params.append(source_type)
            if source_url:
                query += ' AND source_url = ?'
                params.append(source_url)
                
            query += ' ORDER BY updated_at DESC'
            
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            
            # Преобразуем JSON обратно в словари
            result = []
            for row in rows:
                row_dict = dict(row)
                if row_dict.get('most_used_keywords'):
                    try:
                        row_dict['most_used_keywords'] = json.loads(row_dict['most_used_keywords'])
                    except:
                        row_dict['most_used_keywords'] = {}
                if row_dict.get('activity_hours'):
                    try:
                        row_dict['activity_hours'] = json.loads(row_dict['activity_hours'])
                    except:
                        row_dict['activity_hours'] = {}
                result.append(row_dict)
            
            return result

# Глобальный экземпляр базы данных
db = Database() 