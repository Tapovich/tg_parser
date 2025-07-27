# Исправление кнопок "Анализ + советы" и "Подробнее"

## Проблема
Кнопки "Анализ + советы" и "Подробнее" не работали после уведомления о новом посте.

## Причины
1. **Закомментированные строки** в обработчиках `handlers.py`
2. **Отсутствие клавиатуры** при отправке уведомлений в `content_monitor.py`
3. **Недостающие импорты** функций из `chatgpt_integration.py`

## Исправления

### 1. Обработчики в `handlers.py`
**Исправлено:**
- ✅ Раскомментированы строки с `chatgpt_rewriter.get_rewrite_suggestions()`
- ✅ Раскомментированы строки с `chatgpt_rewriter._detect_content_type()`
- ✅ Добавлены импорты `from chatgpt_integration import chatgpt_rewriter`
- ✅ Добавлены импорты `from chatgpt_integration import get_manual_rewrite_prompt`
- ✅ Добавлена клавиатура в обработчики `new_post_details_`

### 2. Отправка уведомлений в `content_monitor.py`
**Исправлено:**
- ✅ Добавлена клавиатура `get_new_post_keyboard(post_data['id'])`
- ✅ Отправка клавиатуры отдельным сообщением
- ✅ Правильная передача ID поста в клавиатуру

### 3. Функции анализа
**Проверено:**
- ✅ `get_manual_rewrite_prompt()` существует в `chatgpt_integration.py`
- ✅ `chatgpt_rewriter.get_rewrite_suggestions()` работает
- ✅ `chatgpt_rewriter._detect_content_type()` работает

## Результат
- ✅ Кнопка "💡 Анализ + советы" работает
- ✅ Кнопка "📋 Подробнее" работает
- ✅ Кнопка "📝 Получить промпт" работает
- ✅ Кнопка "❌ Пропустить" работает
- ✅ Все кнопки сохраняются после нажатия

## Технические детали

### Обработчики
```python
@router.callback_query(F.data.startswith("new_post_analysis_"))
@router.callback_query(F.data.startswith("new_post_details_"))
@router.callback_query(F.data.startswith("new_post_manual_"))
@router.callback_query(F.data.startswith("new_post_skip_"))
```

### Клавиатура
```python
def get_new_post_keyboard(draft_id: int):
    # Кнопки: Получить промпт, Анализ + советы, Подробнее, Пропустить
```

### Отправка уведомлений
```python
# Отправляем текст
await self.safe_send_message(chat_id=admin_id, text=message_text, parse_mode="HTML")

# Отправляем клавиатуру
await bot.send_message(chat_id=admin_id, text="🎛 Действия с постом:", reply_markup=keyboard)
```

## Использование
1. Бот находит новый пост
2. Отправляет уведомление с текстом
3. Отправляет сообщение с кнопками действий
4. Все кнопки работают корректно
5. После нажатия кнопки показывается соответствующий анализ

## Статус
- ✅ Все кнопки исправлены и работают
- ✅ Анализ контента функционирует
- ✅ Промпты для ChatGPT генерируются
- ✅ Подробная информация отображается 