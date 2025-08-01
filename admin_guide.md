# Руководство администратора

## 🎛 Основные команды

### `/start`
Запуск бота. Показывает приветственное сообщение с описанием функций.

### `/setup`
**Первоначальная настройка бота:**
- Добавляет ключевые слова в базу данных
- Создает демонстрационный черновик для тестирования
- Инициализирует все необходимые таблицы

### `/admin`
**Главная панель управления с кнопками:**
- 📋 Черновики контента
- 🔄 Запустить мониторинг
- 📝 Ключевые слова
- 📡 Источники
- 📊 Статистика

## 📊 Команды мониторинга

### `/queue`
**Показывает очередь черновиков:**
- Список новых черновиков (до 10 штук)
- Источник, дата, ключевые слова
- Превью текста (80 символов)

### `/last`
**Последние опубликованные посты:**
- 5 последних публикаций
- Дата и время публикации
- Превью текста (100 символов)
- Прямые ссылки на посты в канале

### `/stats`
**Детальная статистика:**
- Черновики: новые, обработанные, удаленные
- Посты: ожидают модерации, одобрены, опубликованы, отклонены
- Общее количество публикаций
- Статистика по источникам
- Публикации за неделю по дням

### `/settings`
**Текущие настройки:**
- Основные параметры (Admin ID, канал, БД)
- RSS источники (список всех)
- Telegram каналы для мониторинга
- Ключевые слова (первые 20)
- Статус Telethon

### `/logs`
**Журнал действий администратора:**
- Последние 20 выполненных действий
- Тип действия с эмодзи
- Время выполнения
- ID целевого объекта
- Описание действия

### `/setdigest`
**Настройка ежедневного дайджеста:**
- `/setdigest 09:00` - установить время рассылки
- `/setdigest off` - отключить дайджест
- Автоматическая отправка в указанное время
- 3-5 лучших новых черновиков за 24 часа

### `/digest`
**Ручная отправка дайджеста:**
- Формирует дайджест немедленно
- Показывает новые черновики с кнопками
- Полезно для тестирования

## 🧪 Тестовые команды

### `/demo`
Создает демонстрационный пост для тестирования модерации.

### `/test_post`
Создает готовый пост и отправляет на модерацию для тестирования публикации в канал.

## 📝 Рабочий процесс

### 1. Мониторинг источников
Бот автоматически сканирует источники каждые 30 минут:
- RSS: ton.org, blog.ton.org
- Telegram каналы: @tonstatus, @tonblockchain, @toncoin_news, @ton_announcements

### 2. Фильтрация
Найденный контент проверяется на наличие ключевых слов:
- TON, Telegram, gifts, airdrop, stars, update, bot, NFT
- токен, криптовалюта, блокчейн, DeFi, Web3, подарки

### 3. Создание черновиков
Подходящий контент сохраняется в базу как черновик со статусом "new".

### 4. Обработка черновиков
1. Просмотрите черновики: `/admin` → "📋 Черновики контента"
2. Выберите черновик для обработки
3. Нажмите "✍️ Переписать" для создания поста
4. Пост автоматически отправится вам в личные сообщения

### 5. Модерация постов
В личных сообщениях вы получите пост с кнопками:
- **✅ Одобрить** - публикует в канал, сохраняет факт публикации
- **✏️ Редактировать** - позволяет изменить текст
- **❌ Отклонить** - отклоняет пост, меняет статус

## 📊 Система логирования

Все действия администратора записываются в базу данных:

### Типы действий:
- `approve_post` - одобрение поста для публикации
- `reject_post` - отклонение поста
- `edit_post` - редактирование текста поста
- `create_post_from_draft` - создание поста из черновика
- `delete_draft` - удаление черновика

### Записываемая информация:
- User ID администратора
- Тип действия
- ID целевого объекта
- Детали операции
- Старое значение (до изменения)
- Новое значение (после изменения)
- Время действия

## 🔧 Настройка канала

### Требования:
1. Бот должен быть добавлен в канал как администратор
2. У бота должны быть права "Publish Messages"
3. В `.env` должен быть указан корректный `CHANNEL_ID`

### Формат CHANNEL_ID:
- `@username` для публичных каналов
- `-100123456789` для приватных каналов

### Получение числового ID:
1. Перешлите любое сообщение из канала боту [@userinfobot](https://t.me/userinfobot)
2. Скопируйте полученный ID в формате -100...

## 🚨 Устранение неполадок

### Бот не отвечает:
- Проверьте `BOT_TOKEN`
- Убедитесь, что `ADMIN_ID` правильный

### Не работает публикация:
- Проверьте права бота в канале
- Убедитесь в правильности `CHANNEL_ID`
- Проверите логи на ошибки

### Не находит новый контент:
- Проверьте доступность RSS источников
- Убедитесь в настройке Telethon (если нужен мониторинг TG каналов)
- Проверьте ключевые слова

### Telethon не работает:
- Заполните `API_ID`, `API_HASH`, `PHONE_NUMBER`
- При первом запуске введите код из SMS
- Если не нужен мониторинг TG, можно пропустить настройку

## 📈 Оптимизация работы

### Рекомендации:
1. Регулярно проверяйте `/queue` для обработки новых черновиков
2. Используйте `/stats` для анализа эффективности
3. Настройте дополнительные ключевые слова при необходимости
4. Мониторьте `/last` для контроля качества публикаций

### Производительность:
- Мониторинг запускается автоматически каждые 30 минут
- Можно запускать вручную через `/admin` → "🔄 Запустить мониторинг"
- RSS источники обрабатываются быстрее Telegram каналов
- Логи помогают отслеживать все действия для аудита

## 📰 Система дайджестов

### Настройка автоматических дайджестов:
1. Используйте `/setdigest 09:00` для установки времени
2. Бот будет ежедневно отправлять дайджест в указанное время
3. Дайджест содержит 3-5 новых черновиков за последние 24 часа

### Управление дайджестами:
- **📄 Подробнее** - показывает полную информацию о черновике
- **✏️ Редактировать** - переходит к стандартной обработке черновика  
- **❌ Удалить** - удаляет черновик из очереди
- **✅ В канал** - автоматически создает пост и публикует в канал

### Особенности:
- Дайджест отправляется только один раз в день
- Если новых черновиков нет, приходит уведомление об этом
- Можно отключить командой `/setdigest off`
- Ручная отправка доступна через `/digest`

### Логирование дайджестов:
- Отправка дайджеста записывается в логи
- Все действия с постами из дайджеста логируются
- Быстрая публикация помечается как `quick_publish` 