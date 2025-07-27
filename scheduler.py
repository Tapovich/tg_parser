import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any

from content_monitor import content_monitor
from config import config
from database import db

logger = logging.getLogger(__name__)

# Очищаем переменные окружения от прокси на уровне модуля
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]
        logger.info(f"Scheduler: удалена переменная окружения: {var}")

class TaskScheduler:
    def __init__(self):
        self.running = False
        self.tasks = {}
        self.bot_instance = None
        
    async def start(self, bot_instance=None):
        """Запуск планировщика"""
        if self.running:
            logger.warning("Планировщик уже запущен")
            return
            
        # Очищаем переменные окружения перед запуском
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']
        for var in proxy_vars:
            if var in os.environ:
                del os.environ[var]
            
        self.bot_instance = bot_instance
        self.running = True
        logger.info("Запуск планировщика задач")
        
        # Передаем экземпляр бота в content_monitor
        if bot_instance:
            content_monitor.set_bot_instance(bot_instance)
            logger.info("Экземпляр бота передан в content_monitor")
        
        # Запускаем основной цикл планировщика
        asyncio.create_task(self._scheduler_loop())
        
        # Запускаем мониторинг контента с настраиваемым интервалом
        asyncio.create_task(self._monitor_content_loop())
    
    async def stop(self):
        """Остановка планировщика"""
        self.running = False
        logger.info("Планировщик остановлен")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        while self.running:
            try:
                current_time = datetime.now()
                current_time_str = current_time.strftime('%H:%M')
                
                # Проверяем, нужно ли отправить дайджест
                await self._check_digest_time(current_time_str)
                
                # Здесь можно добавить другие периодические задачи
                # Например, очистка старых записей, статистика и т.д.
                
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_content_loop(self):
        """Цикл мониторинга контента"""
        logger.info("Запуск цикла мониторинга контента")
        
        while self.running:
            try:
                # Запускаем мониторинг
                await content_monitor.run_monitoring_cycle()
                
                # Ждем до следующего цикла
                interval_minutes = config.MONITORING_INTERVAL_MINUTES
                logger.info(f"Следующий цикл мониторинга через {interval_minutes} минут")
                await asyncio.sleep(interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                # При ошибке ждем 5 минут и пробуем снова
                await asyncio.sleep(5 * 60)
    
    async def run_manual_monitoring(self):
        """Запуск мониторинга вручную"""
        logger.info("Запуск ручного мониторинга")
        try:
            await content_monitor.run_monitoring_cycle()
            return True
        except Exception as e:
            logger.error(f"Ошибка ручного мониторинга: {e}")
            return False
    
    async def _check_digest_time(self, current_time_str: str):
        """Проверяет, нужно ли отправить дайджест"""
        try:
            # Получаем настройки дайджеста для админа
            settings = await db.get_digest_settings(config.ADMIN_ID)
            
            if not settings:
                return
            
            # Проверяем время
            if settings['digest_time'] != current_time_str:
                return
            
            # Проверяем, не отправляли ли уже сегодня
            if settings['last_sent']:
                last_sent = datetime.fromisoformat(settings['last_sent'])
                if last_sent.date() == datetime.now().date():
                    return  # Уже отправляли сегодня
            
            # Отправляем дайджест
            from handlers import send_daily_digest
            
            if self.bot_instance:
                await send_daily_digest(self.bot_instance, config.ADMIN_ID)
                logger.info(f"Автоматический дайджест отправлен в {current_time_str}")
            
        except Exception as e:
            logger.error(f"Ошибка проверки времени дайджеста: {e}")
    
    async def send_manual_digest(self, bot):
        """Отправка дайджеста вручную"""
        try:
            from handlers import send_daily_digest
            await send_daily_digest(bot, config.ADMIN_ID)
            return True
        except Exception as e:
            logger.error(f"Ошибка ручной отправки дайджеста: {e}")
            return False

# Глобальный экземпляр планировщика
scheduler = TaskScheduler() 