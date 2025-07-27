# Исправление проблем с часовыми поясами (datetime)

## Проблема
Ошибка: `can't compare offset-naive and offset-aware datetimes`

## Причина
Сравнение datetime объектов с разными часовыми поясами:
- `datetime.now()` - naive datetime (без часового пояса)
- `message.date` от Telethon - aware datetime (с UTC)

## Исправления

### 1. ContentMonitor - Telegram обработка
**Исправлено:**
- ✅ `datetime.now(timezone.utc)` вместо `datetime.now()`
- ✅ Проверка и добавление `tzinfo=timezone.utc` для `last_check_time`
- ✅ Правильное сравнение с `message.date` (уже имеет часовой пояс)

### 2. ContentMonitor - RSS обработка
**Исправлено:**
- ✅ `datetime.now(timezone.utc)` вместо `datetime.now()`
- ✅ Создание RSS дат с `tzinfo=timezone.utc`
- ✅ Правильное сравнение дат публикации

### 3. Handlers - все datetime операции
**Исправлено:**
- ✅ `datetime.now(timezone.utc)` во всех местах
- ✅ Добавлен импорт `from datetime import timezone`
- ✅ Исправлены команды `/reset_checks` и `/check_times`

### 4. База данных - сохранение времени
**Исправлено:**
- ✅ Сохранение времени с UTC: `datetime.now(timezone.utc).isoformat()`
- ✅ Чтение времени с проверкой часового пояса
- ✅ Автоматическое добавление `tzinfo=timezone.utc` при необходимости

## Технические детали

### Проблемные места
```python
# Было (ошибка):
datetime.now() - timedelta(hours=24)
message.date <= last_check_time  # naive vs aware

# Стало (исправлено):
datetime.now(timezone.utc) - timedelta(hours=24)
message.date <= last_check_time  # aware vs aware
```

### Обработка дат из БД
```python
def _get_last_check_time(self, source_key: str):
    dt = datetime.fromisoformat(result)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
```

### RSS даты
```python
# Создание дат с UTC
pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
```

## Результат
- ✅ Нет больше ошибок с часовыми поясами
- ✅ Правильное сравнение дат в Telegram
- ✅ Правильное сравнение дат в RSS
- ✅ Корректное сохранение времени в БД
- ✅ Все команды работают без ошибок

## Статус
- ✅ Все datetime операции исправлены
- ✅ Добавлен импорт timezone
- ✅ Исправлены все проблемные места
- ✅ Готово к деплою 