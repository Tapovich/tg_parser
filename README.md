# 🤖 TG Content Manager Bot

Telegram бот для автоматизации управления контентом в Telegram-каналах с фокусом на TON/Telegram/крипто тематику.

## 🌟 Возможности

- 📡 **Мониторинг источников**:
  - Telegram каналы
  - RSS ленты
  - X (через RSSHub/Nitter)

- 🔍 **Умный поиск контента**:
  - Гибкий поиск по ключевым словам
  - Учет вариаций слов
  - Анализ релевантности

- 📝 **Работа с контентом**:
  - Сохранение оригинального форматирования
  - Генерация промптов для ChatGPT
  - Анализ и рекомендации по улучшению

- 👥 **Модерация**:
  - Система одобрения постов
  - Возможность редактирования
  - Предотвращение дубликатов

- 📊 **Статистика и аналитика**:
  - Анализ активности каналов
  - Статистика по ключевым словам
  - Отчеты об эффективности

## 🛠 Технологии

- Python 3.9+
- aiogram 3.2.0
- Telethon
- aiosqlite
- OpenAI API
- BeautifulSoup4

## 📋 Требования

- Python 3.9 или выше
- Telegram Bot Token
- OpenAI API ключ (опционально)
- Telegram API credentials (для Telethon)

## 🚀 Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/tg-content-manager.git
cd tg-content-manager
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate  # Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл .env на основе env_template.txt:
```bash
cp env_template.txt .env
# Заполните .env своими значениями
```

## ⚙️ Настройка

1. Получите Telegram Bot Token у @BotFather

2. Для мониторинга Telegram каналов:
   - Получите API_ID и API_HASH на https://my.telegram.org
   - Добавьте их в .env файл

3. Для использования ChatGPT:
   - Получите API ключ на https://platform.openai.com
   - Добавьте OPENAI_API_KEY в .env

## 🚀 Запуск

```bash
python main.py
```

## 📝 Использование

1. **Базовые команды**:
   - `/start` - Запуск бота
   - `/help` - Список команд
   - `/admin` - Панель администратора

2. **Управление источниками**:
   - `/add_tg` - Добавить Telegram канал
   - `/add_rss` - Добавить RSS ленту
   - `/list_sources` - Список источников

3. **Модерация**:
   - Используйте кнопки "Одобрить", "Редактировать", "Удалить"
   - Получайте промпты для ChatGPT
   - Анализируйте контент перед публикацией

## 🤝 Вклад в проект

Мы приветствуем ваш вклад в проект! Пожалуйста:

1. Форкните репозиторий
2. Создайте ветку для вашей фичи
3. Внесите изменения
4. Отправьте Pull Request

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE) файл

## 👥 Авторы

- [Ваше имя](https://github.com/yourusername)

## 📞 Контакты

- Telegram: [@yourusername](https://t.me/yourusername)
- Email: your.email@example.com 