import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import db
from handlers import router
from scheduler import scheduler

# Глобальная переменная для доступа к боту из планировщика
bot_instance = None

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Основная функция запуска бота"""
    try:
        # Проверяем конфигурацию
        config.validate()
        logger.info("Конфигурация проверена успешно")
        
        # Инициализируем базу данных
        await db.init_db()
        logger.info("База данных инициализирована")
        
        # Создаем бот и диспетчер
        global bot_instance
        bot = Bot(token=config.BOT_TOKEN, proxy=None)  # явно отключаем прокси
        bot_instance = bot
        dp = Dispatcher(storage=MemoryStorage())
        
        # Подключаем роутер
        dp.include_router(router)
        
        logger.info("Бот запускается...")
        
        # Уведомляем админа о запуске
        try:
            await bot.send_message(
                config.ADMIN_ID,
                "🚀 <b>Бот запущен!</b>\n\n"
                "Все системы работают нормально.\n"
                "Готов к обработке контента!",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление админу: {e}")
        
        # Запускаем планировщик с передачей экземпляра бота
        await scheduler.start(bot_instance)
        
        # Запускаем поллинг
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}") 