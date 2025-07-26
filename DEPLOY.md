# Инструкция по развертыванию бота

## Требования к серверу
- Docker
- Docker Compose
- Git
- 1GB RAM минимум
- 10GB свободного места

## Шаги по установке

### 1. Клонирование репозитория
```bash
git clone [URL репозитория]
cd TG_Parcer
```

### 2. Настройка переменных окружения
Создайте файл `.env` в корневой директории:
```bash
cp env_template.txt .env
nano .env
```

Заполните все необходимые переменные:
```
BOT_TOKEN=ваш_токен_бота
ADMIN_ID=ваш_id
CHANNEL_ID=id_канала
API_ID=telethon_api_id
API_HASH=telethon_api_hash
PHONE_NUMBER=телефон_для_telethon
OPENAI_API_KEY=ваш_ключ_openai
```

### 3. Создание директории для данных
```bash
mkdir data
```

### 4. Запуск бота через Docker Compose
```bash
# Сборка и запуск
docker-compose up -d

# Проверка логов
docker-compose logs -f

# Перезапуск бота
docker-compose restart

# Остановка бота
docker-compose down
```

### 5. Проверка работоспособности
- Отправьте боту команду `/ping`
- Проверьте команду `/stats_all`
- Запустите тестовый мониторинг через `/monitor`

## Обновление бота

### Получение обновлений
```bash
git pull
docker-compose down
docker-compose up -d --build
```

## Резервное копирование

### Бэкап базы данных
База данных находится в директории `data/`. Регулярно делайте её резервную копию:
```bash
cp data/bot.db data/bot.db.backup
```

## Мониторинг и обслуживание

### Просмотр логов
```bash
# Последние логи
docker-compose logs --tail=100

# Логи в реальном времени
docker-compose logs -f

# Логи с временными метками
docker-compose logs -t
```

### Проверка использования ресурсов
```bash
docker stats
```

### Очистка логов
```bash
truncate -s 0 data/bot.log
```

## Устранение неполадок

### Бот не отвечает
1. Проверьте логи: `docker-compose logs -f`
2. Перезапустите бот: `docker-compose restart`
3. Проверьте переменные окружения: `docker-compose config`

### Ошибки мониторинга
1. Проверьте доступность каналов и RSS-источников
2. Проверьте правильность API_ID и API_HASH
3. Перезапустите сессию Telethon

## Контакты для поддержки
При возникновении проблем обращайтесь к разработчику. 