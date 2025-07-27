from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.utils.markdown import html_decoration as html
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime, timedelta, timezone
import html as html_escape
import logging
import os
import aiosqlite

logger = logging.getLogger(__name__)

# Очищаем переменные окружения от прокси на уровне модуля
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]
        logger.info(f"Handlers: удалена переменная окружения: {var}")

from config import config, is_admin
from database import db
from keyboards import (get_moderation_keyboard, get_admin_menu_keyboard, get_edit_confirmation_keyboard, 
                       get_drafts_keyboard, get_draft_action_keyboard, get_digest_keyboard, get_digest_navigation_keyboard,
                       get_new_post_keyboard)
from states import ContentModerationStates, AdminStates
from scheduler import scheduler
from aiogram import Bot
from emoji_config import add_emojis_to_post, apply_template, get_emoji, get_random_emoji, safe_html_with_emoji, get_emoji_with_fallback, FALLBACK_EMOJIS

router = Router()

async def safe_edit_message(obj, text: str, parse_mode: str = "HTML", reply_markup=None):
    """
    Безопасное редактирование сообщения или отправка нового с обработкой ошибок
    Работает с CallbackQuery (редактирование) и Message (новое сообщение)
    """
    try:
        if hasattr(obj, 'message') and hasattr(obj, 'answer'):
            # Это CallbackQuery - редактируем существующее сообщение
            await obj.message.edit_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        elif hasattr(obj, 'answer'):
            # Это Message - отправляем новое сообщение
            await obj.answer(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        else:
            # Неизвестный тип объекта
            logger.error(f"Неподдерживаемый тип объекта для safe_edit_message: {type(obj)}")
            
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Сообщение не изменилось, просто отвечаем пользователю
            if hasattr(obj, 'answer') and hasattr(obj, 'message'):
                # Это CallbackQuery
                await obj.answer("ℹ️ Содержимое уже актуально", show_alert=False)
        else:
            # Другая ошибка, логируем её
            logger.error(f"Ошибка в safe_edit_message: {e}")
            if hasattr(obj, 'answer') and hasattr(obj, 'message'):
                # Это CallbackQuery
                await obj.answer("❌ Ошибка обновления сообщения", show_alert=True)
            # Для Message просто логируем, не перебрасываем исключение

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start с Premium emoji"""
    user_id = message.from_user.id
    
    if is_admin(user_id):
        welcome_emoji = get_emoji("yellow_star")
        brain_emoji = get_emoji("brain")
        tech_emoji = get_emoji("tech")
        sparkle_emoji = get_emoji("sparkle")
        check_emoji = get_emoji("check")
        airplane_emoji = get_emoji("airplane")
        
        await message.answer(
            f"{welcome_emoji} <b>Добро пожаловать, администратор!</b>\n\n"
            f"{brain_emoji} Этот бот поможет вам автоматизировать процесс контент-менеджмента:\n"
            f"• Мониторит источники (каналы, RSS, X)\n"
            f"• Фильтрует по ключевым словам\n"
            f"• Перефразирует контент с помощью AI\n"
            f"• Отправляет на модерацию\n"
            f"• Публикует в ваш канал\n\n"
            f"{tech_emoji} <b>Доступные команды:</b>\n"
            f"/help - помощь\n"
            f"/ping - проверка работы\n"
            f"/admin - панель администратора\n\n"
            f"{sparkle_emoji} <i>Поддержка Premium emoji активна!</i>",
            parse_mode="HTML"
        )
    else:
        wave_emoji = get_emoji("smile")
        lock_emoji = get_emoji("warning")
        
        await message.answer(
            f"{wave_emoji} Привет! Я бот-редактор контента.\n\n"
            f"{lock_emoji} Доступ к боту ограничен. Если у вас есть права администратора, "
            "обратитесь к владельцу бота для настройки."
        )

@router.message(Command("ping"))
async def cmd_ping(message: Message):
    """Обработчик команды /ping"""
    await message.answer("🏓 Pong! Бот работает нормально.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """
🤖 <b>Telegram-бот Контент-редактор</b>

<b>Основные команды:</b>
/start - запуск бота
/ping - проверка работы
/help - это сообщение

<b>Для администраторов:</b>
/admin - панель управления
/guide - руководство по ручному режиму
/monitor - запустить проверку источников вручную
/demo_post - демо уведомления о новом найденном посте
/prompt - быстрый генератор промптов для любого текста
/manual - подробный анализ + промпт
/prompts - библиотека готовых промптов для ChatGPT

<b>Управление источниками:</b>
/add_rss [url] - добавить RSS-источник
/remove_rss [url] - удалить RSS-источник
/add_tg [@channel] - добавить Telegram-канал
/remove_tg [@channel] - удалить Telegram-канал
/list_sources - список всех активных источников

<b>Управление проверками:</b>
/check_times - показать время последней проверки источников
/reset_checks - сбросить время проверки (проверить заново все посты)
/reset_ids - сбросить только ID сообщений Telegram
/time_debug - диагностика проблем с временем
/force_monitor - принудительный мониторинг с сбросом времени
/check_channel @name - проверка конкретного канала

<b>Как работает бот (ручной режим):</b>
1. Мониторит указанные источники в реальном времени
2. Фильтрует контент по ключевым словам
3. Сразу присылает найденные посты с анализом
4. Предоставляет советы и готовые промпты для ChatGPT
5. Вы перефразируете через ChatGPT и публикуете

<b>Функции модерации:</b>
• ✅ Одобрить - опубликовать пост
• ✏️ Редактировать - изменить текст
• ❌ Удалить - отклонить пост

<b>Защита от спама:</b>
• Автоматическая защита от flood control
• Уведомления только о новых постах
• Задержки между отправками сообщений
    """
    
    await message.answer(help_text, parse_mode="HTML")

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админская панель"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа к админской панели.")
        return
    
    await message.answer(
        "🎛 <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_keyboard()
    )

@router.callback_query(F.data.startswith("approve_"))
async def callback_approve_post(callback: CallbackQuery):
    """Одобрение поста"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    post_id = int(callback.data.split("_")[1])
    
    # Получаем пост независимо от статуса для проверки
    post = await db.get_post_by_id(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден", show_alert=True)
        return
    
    # Проверяем, не был ли пост уже опубликован
    if post.get('status') == 'published':
        warning_emoji = get_emoji("warning")
        success_emoji = get_emoji("check")
        channel_emoji = get_emoji("airplane")
        time_emoji = get_emoji("clock")
        
        await callback.answer("⚠️ Этот пост уже опубликован", show_alert=True)
        await safe_edit_message(callback,
            f"{warning_emoji} <b>Пост уже опубликован ранее</b>\n\n"
            f"{success_emoji} Статус: Опубликован\n"
            f"{channel_emoji} Канал: {config.CHANNEL_ID}\n"
            f"{time_emoji} {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, что пост еще на модерации
    if post.get('status') != 'pending':
        await callback.answer(f"❌ Пост имеет статус '{post.get('status')}' и не может быть одобрен", show_alert=True)
        return
    
    # Публикуем в канал
    try:
        published_message = await publish_to_channel(callback.bot, post)
        
        if published_message:
            # Сохраняем факт публикации
            published_id = await db.add_published_post(
                pending_post_id=post_id,
                original_text=post['original_text'],
                published_text=post['rewritten_text'],
                source_url=post['source_url'],
                source_type=post['source_type'],
                channel_id=config.CHANNEL_ID,
                message_id=published_message.message_id
            )
            
            # Обновляем статус
            await db.update_post_status(post_id, "published")
            
            # Логируем действие
            await db.log_action(
                user_id=callback.from_user.id,
                action_type="approve_post",
                target_type="pending_post",
                target_id=post_id,
                details=f"Пост опубликован в канал {config.CHANNEL_ID}",
                old_value=post['rewritten_text'][:200],
                new_value=f"published_id:{published_id}, message_id:{published_message.message_id}"
            )
            
            safe_text = safe_html_with_emoji(post['rewritten_text'])
            await safe_edit_message(callback,
                f"✅ <b>Пост успешно опубликован в канале!</b>\n\n"
                f"<i>{safe_text}</i>\n\n"
                f"🔗 Ссылка: <a href='https://t.me/{config.CHANNEL_ID.replace('@', '')}/{published_message.message_id}'>Перейти к посту</a>",
                parse_mode="HTML"
            )
            
            await callback.answer("✅ Пост опубликован!")
        else:
            await callback.answer("❌ Ошибка публикации в канал", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка публикации поста: {e}")
        await callback.answer("❌ Ошибка публикации в канал", show_alert=True)

@router.callback_query(F.data.startswith("edit_"))
async def callback_edit_post(callback: CallbackQuery, state: FSMContext):
    """Редактирование поста"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    post_id = int(callback.data.split("_")[1])
    
    # Проверяем статус поста
    post = await db.get_post_by_id(post_id)
    if not post:
        await callback.answer("❌ Пост не найден", show_alert=True)
        return
    
    if post.get('status') != 'pending':
        await callback.answer("❌ Нельзя редактировать уже опубликованный пост", show_alert=True)
        return
    
    await state.set_state(ContentModerationStates.editing_content)
    await state.update_data(post_id=post_id)
    
    await safe_edit_message(callback,
        f"✏️ <b>Редактирование поста</b>\n\n"
        f"<b>Текущий текст:</b>\n<i>{post['rewritten_text']}</i>\n\n"
        f"📝 Отправьте новый текст для поста:",
        parse_mode="HTML"
    )
    
    await callback.answer()

@router.callback_query(F.data.startswith("delete_"))
async def callback_delete_post(callback: CallbackQuery):
    """Удаление поста"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    post_id = int(callback.data.split("_")[1])
    post = await db.get_pending_post(post_id)
    
    if post:
        # Логируем действие перед удалением
        await db.log_action(
            user_id=callback.from_user.id,
            action_type="reject_post",
            target_type="pending_post",
            target_id=post_id,
            details="Пост отклонен администратором",
            old_value=post['rewritten_text'][:200],
            new_value="rejected"
        )
    
    await db.update_post_status(post_id, "deleted")
    
    await safe_edit_message(callback,
        "❌ <b>Пост отклонен</b>\n\n"
        "Пост был отклонен и удален из очереди модерации.",
        parse_mode="HTML"
    )
    
    await callback.answer("❌ Пост отклонен")

@router.message(StateFilter(ContentModerationStates.editing_content))
async def handle_post_edit(message: Message, state: FSMContext):
    """Обработка отредактированного текста"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    post_id = data.get("post_id")
    
    if not post_id:
        await message.answer("❌ Ошибка: ID поста не найден")
        await state.clear()
        return
    
    new_text = message.text
    
    # Получаем старый текст для логирования
    post = await db.get_pending_post(post_id)
    old_text = post['rewritten_text'] if post else ""
    
    await db.update_post_text(post_id, new_text)
    
    # Логируем редактирование
    await db.log_action(
        user_id=message.from_user.id,
        action_type="edit_post",
        target_type="pending_post",
        target_id=post_id,
        details="Текст поста отредактирован",
        old_value=old_text[:200],
        new_value=new_text[:200]
    )
    
    safe_new_text = safe_html_with_emoji(new_text)
    await safe_edit_message(message,
        f"✏️ <b>Пост отредактирован</b>\n\n"
        f"<b>Новый текст:</b>\n<i>{safe_new_text}</i>\n\n"
        f"Что делать с постом?",
        parse_mode="HTML",
        reply_markup=get_moderation_keyboard(post_id)
    )
    
    await state.clear()

# Демонстрационная функция для создания тестового поста
async def create_demo_post():
    """Создает демонстрационный пост для тестирования с Premium emoji"""
    original_text = "Bitcoin price has reached new highs today, breaking the $50,000 barrier for the first time since last year."
    
    # Базовый текст без emoji для переписывания
    base_rewritten = "Биткоин снова взлетает! Цена пробила отметку в $50,000 впервые за последний год. Рынок криптовалют показывает отличную динамику роста."
    
    # Применяем шаблон "news" для crypto новостей
    rewritten_text = apply_template(base_rewritten, "news")
    
    post_id = await db.add_pending_post(
        original_text=original_text,
        rewritten_text=rewritten_text,
        source_url="https://example.com/news",
        source_type="demo"
    )
    
    return post_id

@router.message(Command("demo"))
async def cmd_demo(message: Message):
    """Команда для создания демо поста (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    post_id = await create_demo_post()
    post = await db.get_pending_post(post_id)
    
    await safe_edit_message(message,
        f"📝 <b>Новый пост на модерации</b>\n\n"
        f"<b>Оригинальный текст:</b>\n<i>{post['original_text']}</i>\n\n"
        f"<b>Переписанный текст:</b>\n<i>{post['rewritten_text']}</i>\n\n"
        f"<b>Источник:</b> {post['source_url']}\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_moderation_keyboard(post_id)
    )

@router.message(Command("setup"))
async def cmd_setup(message: Message):
    """Команда для первоначальной настройки (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Добавляем ключевые слова из конфига в базу
    keywords_added = 0
    for keyword in config.KEYWORDS:
        try:
            await db.add_keyword(keyword)
            keywords_added += 1
        except:
            pass  # Игнорируем дубликаты
    
    # Создаем демо черновик для тестирования с Premium emoji
    base_demo_text = 'Telegram выпустил новое обновление с поддержкой TON блокчейна и NFT функций. Пользователи теперь могут получать подарки в виде криптовалюты.'
    demo_text_with_emoji = apply_template(base_demo_text, "update")
    
    demo_draft_id = await db.add_content_draft(
        source_type='demo',
        source_name='Демо источник',
        original_text=demo_text_with_emoji,
        source_url='https://example.com/demo',
        source_date=datetime.now(timezone.utc).isoformat(),
        keywords_matched=['Telegram', 'TON', 'NFT', 'подарки', 'криптовалюта']
    )
    
    target_emoji = get_emoji("yellow_star")
    success_emoji = get_emoji("check")
    brain_emoji = get_emoji("brain")
    sparkle_emoji = get_emoji("sparkle")
    
    await safe_edit_message(message,
        f"{target_emoji} <b>Настройка завершена!</b>\n\n"
        f"{success_emoji} Добавлено ключевых слов: {keywords_added}\n"
        f"{success_emoji} Создан демо-черновик #{demo_draft_id}\n"
        f"{success_emoji} База данных инициализирована\n"
        f"{sparkle_emoji} Premium emoji активированы\n\n"
        f"{brain_emoji} <b>Теперь вы можете:</b>\n"
        f"• Использовать /admin для управления\n"
        f"• Запустить мониторинг источников\n"
        f"• Просмотреть черновики контента\n\n"
        f"Для полноценной работы не забудьте настроить переменные окружения для Telethon.",
        parse_mode="HTML"
    )

@router.message(Command("queue"))
async def cmd_queue(message: Message):
    """Показывает очередь черновиков (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    drafts = await db.get_content_drafts(status='new', limit=20)
    
    if not drafts:
        await safe_edit_message(message,
            "📭 <b>Очередь черновиков пуста</b>\n\n"
            "Все найденные материалы уже обработаны или мониторинг еще не запускался.",
            parse_mode="HTML"
        )
        return
    
    text = f"📋 <b>Очередь черновиков ({len(drafts)})</b>\n\n"
    
    for i, draft in enumerate(drafts[:10], 1):
        source_emoji = "📡" if draft['source_type'] == 'rss' else "💬"
        safe_source_name = safe_html_with_emoji(draft['source_name'])
        safe_text = safe_html_with_emoji(draft['original_text'][:80])
        
        text += f"{i}. {source_emoji} <b>{safe_source_name}</b>\n"
        text += f"📅 {draft['source_date'][:10] if draft['source_date'] else 'Неизвестно'}\n"
        text += f"🔍 {draft['keywords_matched']}\n"
        text += f"📝 {safe_text}{'...' if len(draft['original_text']) > 80 else ''}\n\n"
    
    if len(drafts) > 10:
        text += f"... и еще {len(drafts) - 10} черновиков"
    
    await safe_edit_message(message, text, parse_mode="HTML")

@router.message(Command("last"))
async def cmd_last(message: Message):
    """Показывает последние опубликованные посты (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    published_posts = await db.get_last_published_posts(limit=10)
    
    if not published_posts:
        await safe_edit_message(message,
            "📭 <b>Нет опубликованных постов</b>\n\n"
            "Пока ни один пост не был опубликован.",
            parse_mode="HTML"
        )
        return
    
    text = f"📰 <b>Последние опубликованные посты ({len(published_posts)})</b>\n\n"
    
    for i, post in enumerate(published_posts[:5], 1):
        safe_text = safe_html_with_emoji(post['published_text'][:100])
        published_date = post['published_at'][:19] if post['published_at'] else 'Неизвестно'
        
        text += f"{i}. <b>Пост #{post['id']}</b>\n"
        text += f"📅 {published_date}\n"
        text += f"📝 {safe_text}{'...' if len(post['published_text']) > 100 else ''}\n"
        if post['message_id'] and config.CHANNEL_ID:
            channel_username = config.CHANNEL_ID.replace('@', '')
            text += f"🔗 <a href='https://t.me/{channel_username}/{post['message_id']}'>Перейти к посту</a>\n"
        text += "\n"
    
    if len(published_posts) > 5:
        text += f"... и еще {len(published_posts) - 5} постов"
    
    await safe_edit_message(message, text, parse_mode="HTML")

@router.message(Command("stats"))
async def cmd_stats_detailed(message: Message):
    """Показывает детальную статистику (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        stats = await db.get_comprehensive_stats()
        
        text = f"📊 <b>Детальная статистика</b>\n\n"
        
        # Статистика черновиков
        text += f"📋 <b>Черновики:</b>\n"
        drafts = stats.get('drafts', {})
        text += f"• Новые: {drafts.get('new', 0)}\n"
        text += f"• Обработанные: {drafts.get('processed', 0)}\n"
        text += f"• Удаленные: {drafts.get('deleted', 0)}\n\n"
        
        # Статистика постов
        text += f"📝 <b>Посты на модерации:</b>\n"
        posts = stats.get('posts', {})
        text += f"• Ожидают: {posts.get('pending', 0)}\n"
        text += f"• Одобренные: {posts.get('approved', 0)}\n"
        text += f"• Опубликованные: {posts.get('published', 0)}\n"
        text += f"• Отклоненные: {posts.get('deleted', 0)}\n\n"
        
        # Общая статистика публикаций
        text += f"📰 <b>Публикации:</b>\n"
        text += f"• Всего опубликовано: {stats.get('published_total', 0)}\n\n"
        
        # Статистика по источникам
        text += f"📡 <b>Источники:</b> {len(config.RSS_SOURCES)} RSS + {len(config.TG_CHANNELS)} Telegram\n"
        text += f"🔍 <b>Ключевые слова:</b> {len(config.KEYWORDS)} слов\n"
        text += f"📰 <b>RSS категории:</b> Официальные, Новостные, Сообщество, Twitter-прокси\n"
        text += f"📡 <b>TG категории:</b> Официальные, Новостные, Аналитические, Специализированные\n"
        
        # Статистика по дням
        daily = stats.get('daily_published', {})
        if daily:
            text += f"\n📅 <b>Публикации за неделю:</b>\n"
            for date, count in list(daily.items())[:7]:
                text += f"• {date}: {count}\n"
        
        await safe_edit_message(message, text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await safe_edit_message(message, "❌ Ошибка получения статистики", parse_mode="HTML")

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Показывает текущие настройки (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        keywords = await db.get_keywords()
        
        text = f"⚙️ <b>Настройки бота</b>\n\n"
        
        # Основные настройки
        text += f"🤖 <b>Основные настройки:</b>\n"
        text += f"• Admin ID: {config.ADMIN_ID}\n"
        text += f"• Канал: {config.CHANNEL_ID or 'Не настроен'}\n"
        text += f"• База данных: {config.DATABASE_URL}\n\n"
        
        # RSS источники
        text += f"📰 <b>RSS источники ({len(config.RSS_SOURCES)}):</b>\n"
        
        # Показываем только основные источники для краткости
        main_sources = [
            'https://ton.org/blog/rss.xml',
            'https://tginfo.me/feed/', 
            'https://tonstatus.io/rss',
            'https://mirror.xyz/tonsociety.eth/rss'
        ]
        
        shown_count = 0
        for source in config.RSS_SOURCES:
            if source in main_sources and shown_count < 4:
                if 'ton.org/blog' in source:
                    text += f"• TON Foundation Blog\n"
                elif 'tginfo.me' in source:
                    text += f"• TGInfo (Telegram новости)\n"
                elif 'tonstatus.io' in source:
                    text += f"• TON Status\n"
                elif 'tonsociety.eth' in source:
                    text += f"• TON Society\n"
                shown_count += 1
        
        if len(config.RSS_SOURCES) > 4:
            text += f"• ... и еще {len(config.RSS_SOURCES) - 4} источников\n"
        
        text += f"• Команда '/rss' для полного списка\n"
        text += "\n"
        
        # Telegram каналы
        text += f"💬 <b>Telegram каналы ({len(config.TG_CHANNELS)}):</b>\n"
        for i, channel in enumerate(config.TG_CHANNELS, 1):
            text += f"{i}. {channel}\n"
        text += "\n"
        
        # Ключевые слова
        text += f"🔍 <b>Ключевые слова ({len(keywords)}):</b>\n"
        keywords_text = ", ".join(keywords[:20])  # Показываем первые 20
        if len(keywords) > 20:
            keywords_text += f" ... (+{len(keywords) - 20})"
        text += f"{keywords_text}\n\n"
        
        # Состояние Telethon
        text += f"📱 <b>Telethon:</b>\n"
        if config.API_ID and config.API_HASH:
            text += f"• Настроен ✅\n"
        else:
            text += f"• Не настроен ❌\n"
        
        await safe_edit_message(message, text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка получения настроек: {e}")
        await safe_edit_message(message, "❌ Ошибка получения настроек", parse_mode="HTML")

@router.message(Command("logs"))
async def cmd_logs(message: Message):
    """Показывает последние логи действий (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        logs = await db.get_action_logs(limit=20)
        
        if not logs:
            await safe_edit_message(message,
                "📭 <b>Логи действий пусты</b>\n\n"
                "Пока не было выполнено ни одного действия.",
                parse_mode="HTML"
            )
            return
        
        text = f"📜 <b>Последние действия ({len(logs)})</b>\n\n"
        
        for i, log in enumerate(logs[:10], 1):
            action_emoji = {
                'approve_post': '✅',
                'reject_post': '❌',
                'edit_post': '✏️',
                'create_post_from_draft': '📝',
                'delete_draft': '🗑'
            }.get(log['action_type'], '📋')
            
            action_name = {
                'approve_post': 'Одобрен пост',
                'reject_post': 'Отклонен пост',
                'edit_post': 'Отредактирован пост',
                'create_post_from_draft': 'Создан пост из черновика',
                'delete_draft': 'Удален черновик'
            }.get(log['action_type'], log['action_type'])
            
            log_time = log['created_at'][:19] if log['created_at'] else 'Неизвестно'
            
            text += f"{action_emoji} <b>{action_name}</b>\n"
            text += f"📅 {log_time}\n"
            text += f"🎯 {log['target_type']} #{log['target_id']}\n"
            if log['details']:
                text += f"💬 {log['details']}\n"
            text += "\n"
        
        if len(logs) > 10:
            text += f"... и еще {len(logs) - 10} записей"
        
        await safe_edit_message(message, text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка получения логов: {e}")
        await safe_edit_message(message, "❌ Ошибка получения логов", parse_mode="HTML")

@router.message(Command("setdigest"))
async def cmd_setdigest(message: Message, state: FSMContext):
    """Настройка времени ежедневного дайджеста (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Проверяем, есть ли аргумент времени
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if args:
        time_str = args[0]
        # Проверяем формат времени HH:MM
        if len(time_str) == 5 and time_str[2] == ':':
            try:
                hours, minutes = map(int, time_str.split(':'))
                if 0 <= hours <= 23 and 0 <= minutes <= 59:
                    # Сохраняем настройки
                    await db.set_digest_time(config.ADMIN_ID, time_str)
                    
                    await safe_edit_message(message,
                        f"⏰ <b>Время дайджеста установлено</b>\n\n"
                        f"📅 Ежедневно в {time_str}\n"
                        f"📋 Дайджест будет содержать 3-5 новых потенциальных постов\n\n"
                        f"Для отключения используйте: /setdigest off",
                        parse_mode="HTML"
                    )
                    return
            except ValueError:
                pass
        
        # Проверяем команду отключения
        if time_str.lower() in ['off', 'отключить', 'disable']:
            await db.disable_digest(config.ADMIN_ID)
            await safe_edit_message(message,
                "🔕 <b>Дайджест отключен</b>\n\n"
                "Автоматическая рассылка остановлена.",
                parse_mode="HTML"
            )
            return
    
    # Если неправильный формат или нет аргументов
    current_settings = await db.get_digest_settings(config.ADMIN_ID)
    current_time = current_settings['digest_time'] if current_settings else "не настроено"
    
    await safe_edit_message(message,
        f"⏰ <b>Настройка ежедневного дайджеста</b>\n\n"
        f"📅 Текущее время: {current_time}\n\n"
        f"<b>Использование:</b>\n"
        f"<code>/setdigest 09:00</code> - установить время\n"
        f"<code>/setdigest off</code> - отключить дайджест\n\n"
        f"<b>Формат времени:</b> ЧЧ:ММ (24-часовой формат)\n"
        f"<b>Пример:</b> 09:00, 14:30, 18:45",
        parse_mode="HTML"
    )

@router.message(Command("digest"))
async def cmd_digest(message: Message):
    """Отправляет дайджест вручную (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    await safe_edit_message(message, "📰 Формирую дайджест...")
    await send_daily_digest(message.bot, config.ADMIN_ID)

@router.message(Command("test_post"))
async def cmd_test_post(message: Message):
    """Команда для создания тестового поста с публикацией и Premium emoji (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Базовый текст для переписывания
    original_text = "Тестовая новость: Telegram интегрирует новые функции TON блокчейна для улучшения пользовательского опыта."
    base_rewritten = "Большие новости! Telegram объявил о новой интеграции с TON блокчейном, которая откроет пользователям доступ к инновационным функциям Web3 прямо в мессенджере! Ожидаются улучшения в работе с криптовалютой и NFT."
    
    # Применяем шаблон "update" для новостей об обновлениях
    rewritten_with_emoji = apply_template(base_rewritten, "update")
    
    # Создаем тестовый пост
    post_id = await db.add_pending_post(
        original_text=original_text,
        rewritten_text=rewritten_with_emoji,
        source_url="https://example.com/test-news",
        source_type="test"
    )
    
    # Получаем созданный пост
    post = await db.get_pending_post(post_id)
    
    # Отправляем админу на модерацию
    await send_post_for_moderation(message.bot, config.ADMIN_ID, post)
    
    success_emoji = get_emoji("check")
    await safe_edit_message(message,
        f"{success_emoji} <b>Тестовый пост создан!</b>\n\n"
        "📬 Пост отправлен вам в личные сообщения для модерации.\n"
        "Вы можете одобрить его для публикации в канал.",
        parse_mode="HTML"
    )

async def send_daily_digest(bot: Bot, admin_id: int):
    """Отправляет ежедневный дайджест новых черновиков"""
    try:
        # Получаем новые черновики
        drafts = await db.get_digest_drafts(limit=5)
        
        if not drafts:
            # Если нет новых черновиков, отправляем уведомление
            await bot.send_message(
                admin_id,
                "📭 <b>Ежедневный дайджест</b>\n\n"
                "За последние 24 часа новых потенциальных постов не найдено.\n"
                "Проверьте работу мониторинга или настройки фильтрации.",
                parse_mode="HTML"
            )
            return
        
        # Формируем дайджест
        text = f"📰 <b>Ежедневный дайджест</b>\n"
        text += f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
        text += f"Найдено {len(drafts)} новых потенциальных постов:\n\n"
        
        # Отправляем заголовок дайджеста
        await bot.send_message(
            admin_id,
            text,
            parse_mode="HTML",
            reply_markup=get_digest_navigation_keyboard()
        )
        
        # Отправляем каждый черновик отдельным сообщением
        for i, draft in enumerate(drafts, 1):
            source_emoji = "📡" if draft['source_type'] == 'rss' else "💬"
            safe_source_name = safe_html_with_emoji(draft['source_name'])
            safe_text = safe_html_with_emoji(draft['original_text'][:150])
            
            draft_text = f"{i}. {source_emoji} <b>{safe_source_name}</b>\n\n"
            draft_text += f"🔍 <i>{draft['keywords_matched']}</i>\n\n"
            draft_text += f"📝 {safe_text}{'...' if len(draft['original_text']) > 150 else ''}\n\n"
            draft_text += f"📅 {draft['source_date'][:19] if draft['source_date'] else 'Неизвестно'}"
            
            await bot.send_message(
                admin_id,
                draft_text,
                parse_mode="HTML",
                reply_markup=get_digest_keyboard(draft['id'])
            )
        
        # Обновляем время последней отправки
        await db.update_digest_last_sent(admin_id)
        
        # Логируем отправку дайджеста
        await db.log_action(
            user_id=admin_id,
            action_type="digest_sent",
            target_type="digest",
            target_id=0,
            details=f"Отправлен дайджест с {len(drafts)} черновиками",
            new_value=str(len(drafts))
        )
        
        logger.info(f"Дайджест отправлен админу {admin_id}, {len(drafts)} черновиков")
        
    except Exception as e:
        logger.error(f"Ошибка отправки дайджеста: {e}")

# Обработчики для кнопок дайджеста
@router.callback_query(F.data.startswith("digest_detail_"))
async def callback_digest_detail(callback: CallbackQuery):
    """Показывает подробную информацию о посте из дайджеста"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[2])
    draft = await db.get_draft_by_id(draft_id)
    
    if not draft:
        await callback.answer("❌ Черновик не найден", show_alert=True)
        return
    
    source_emoji = "📡" if draft['source_type'] == 'rss' else "💬"
    safe_source_name = safe_html_with_emoji(draft['source_name'])
    safe_keywords = safe_html_with_emoji(draft['keywords_matched'] or '')
    safe_url = safe_html_with_emoji(draft['source_url'] or '')
    safe_text = safe_html_with_emoji(draft['original_text'])
    
    text = f"📋 <b>Подробная информация</b>\n\n"
    text += f"{source_emoji} <b>Источник:</b> {safe_source_name}\n"
    text += f"📅 <b>Дата:</b> {draft['source_date'][:19] if draft['source_date'] else 'Неизвестно'}\n"
    text += f"🔍 <b>Ключевые слова:</b> {safe_keywords}\n"
    text += f"🔗 <b>Ссылка:</b> {safe_url}\n\n"
    text += f"📝 <b>Полный текст:</b>\n{safe_text}"
    
    await safe_edit_message(callback,
        text,
        parse_mode="HTML",
        reply_markup=get_digest_keyboard(draft_id)
    )

@router.callback_query(F.data.startswith("digest_edit_"))
async def callback_digest_edit(callback: CallbackQuery):
    """Редактирование поста из дайджеста"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[2])
    draft = await db.get_draft_by_id(draft_id)
    
    if not draft:
        await callback.answer("❌ Черновик не найден", show_alert=True)
        return
    
    # Переходим к обычной обработке черновика
    await callback_process_draft(callback)

@router.callback_query(F.data.startswith("digest_delete_"))
async def callback_digest_delete(callback: CallbackQuery):
    """Удаление поста из дайджеста"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[2])
    draft = await db.get_draft_by_id(draft_id)
    
    if draft:
        # Логируем удаление
        await db.log_action(
            user_id=callback.from_user.id,
            action_type="delete_draft",
            target_type="content_draft",
            target_id=draft_id,
            details="Черновик удален из дайджеста",
            old_value=draft['original_text'][:200],
            new_value="deleted"
        )
    
    await db.update_draft_status(draft_id, 'deleted')
    
    await safe_edit_message(callback,
        "❌ <b>Черновик удален</b>\n\n"
        "Пост был удален из дайджеста.",
        parse_mode="HTML"
    )
    
    await callback.answer("🗑 Черновик удален")

@router.callback_query(F.data.startswith("digest_publish_"))
async def callback_digest_publish(callback: CallbackQuery):
    """Быстрая публикация поста из дайджеста"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[2])
    draft = await db.get_draft_by_id(draft_id)
    
    if not draft:
        await callback.answer("❌ Черновик не найден", show_alert=True)
        return
    
    # В ручном режиме создаем базовую версию для предпросмотра
    from content_rewriter import rewrite_post
    rewritten_text = rewrite_post(draft['original_text'], style="auto")
    
    # Создаем пост на модерацию
    post_id = await db.add_pending_post(
        original_text=draft['original_text'],
        rewritten_text=rewritten_text,
        source_url=draft['source_url'],
        source_type=draft['source_type']
    )
    
    # Обновляем статус черновика
    await db.update_draft_status(draft_id, 'processed')
    
    # Логируем создание поста
    await db.log_action(
        user_id=callback.from_user.id,
        action_type="create_post_from_digest",
        target_type="content_draft",
        target_id=draft_id,
        details=f"Создан пост #{post_id} из дайджеста",
        old_value=draft['original_text'][:200],
        new_value=rewritten_text[:200]
    )
    
    # Получаем созданный пост и сразу публикуем
    post = await db.get_pending_post(post_id)
    if post:
        published_message = await publish_to_channel(callback.bot, post)
        
        if published_message:
            # Сохраняем факт публикации
            published_id = await db.add_published_post(
                pending_post_id=post_id,
                original_text=post['original_text'],
                published_text=post['rewritten_text'],
                source_url=post['source_url'],
                source_type=post['source_type'],
                channel_id=config.CHANNEL_ID,
                message_id=published_message.message_id
            )
            
            # Обновляем статус
            await db.update_post_status(post_id, "published")
            
            # Логируем публикацию
            await db.log_action(
                user_id=callback.from_user.id,
                action_type="quick_publish",
                target_type="pending_post",
                target_id=post_id,
                details=f"Быстрая публикация из дайджеста в канал {config.CHANNEL_ID}",
                old_value=post['rewritten_text'][:200],
                new_value=f"published_id:{published_id}, message_id:{published_message.message_id}"
            )
            
            channel_username = config.CHANNEL_ID.replace('@', '') if config.CHANNEL_ID.startswith('@') else config.CHANNEL_ID
            safe_text = safe_html_with_emoji(post['rewritten_text'][:100])
            
            await safe_edit_message(callback,
                f"✅ <b>Пост опубликован!</b>\n\n"
                f"📝 {safe_text}{'...' if len(post['rewritten_text']) > 100 else ''}\n\n"
                f"🔗 <a href='https://t.me/{channel_username}/{published_message.message_id}'>Перейти к посту</a>",
                parse_mode="HTML"
            )
            
            await callback.answer("✅ Пост опубликован в канале!")
        else:
            await callback.answer("❌ Ошибка публикации в канал", show_alert=True)

@router.callback_query(F.data == "refresh_digest")
async def callback_refresh_digest(callback: CallbackQuery):
    """Обновление дайджеста"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    await safe_edit_message(callback, "🔄 Обновляем дайджест...")
    await send_daily_digest(callback.bot, config.ADMIN_ID)

@router.callback_query(F.data == "digest_settings")
async def callback_digest_settings(callback: CallbackQuery):
    """Настройки дайджеста"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    settings = await db.get_digest_settings(config.ADMIN_ID)
    
    if settings:
        text = f"⚙️ <b>Настройки дайджеста</b>\n\n"
        text += f"⏰ Время отправки: {settings['digest_time']}\n"
        text += f"📅 Последняя отправка: {settings['last_sent'][:19] if settings['last_sent'] else 'Не отправлялся'}\n"
        text += f"✅ Статус: Включен\n\n"
        text += f"Для изменения используйте: /setdigest ЧЧ:ММ"
    else:
        text = f"⚙️ <b>Настройки дайджеста</b>\n\n"
        text += f"❌ Дайджест не настроен\n\n"
        text += f"Для настройки используйте: /setdigest ЧЧ:ММ"
    
    await safe_edit_message(callback, text, parse_mode="HTML")

@router.callback_query(F.data == "add_keywords")
async def callback_add_keywords(callback: CallbackQuery, state: FSMContext):
    """Добавление ключевых слов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    current_keywords = await db.get_keywords()
    keywords_text = ", ".join(current_keywords[:20])
    if len(current_keywords) > 20:
        keywords_text += f" ... (+{len(current_keywords) - 20})"
    
    text = f"🔍 <b>Управление ключевыми словами</b>\n\n"
    text += f"<b>Текущие ключевые слова ({len(current_keywords)}):</b>\n"
    text += f"{keywords_text}\n\n"
    text += f"📝 Отправьте новые ключевые слова через запятую:\n"
    text += f"<i>Пример: криптовалюта, блокчейн, токен</i>"
    
    await safe_edit_message(callback, text, parse_mode="HTML")
    await state.set_state(AdminStates.adding_keywords)

@router.callback_query(F.data == "manage_sources")
async def callback_manage_sources(callback: CallbackQuery):
    """Управление источниками"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    text = f"📡 <b>Управление источниками</b>\n\n"
    
    # RSS источники
    text += f"📰 <b>RSS источники ({len(config.RSS_SOURCES)}):</b>\n"
    
    # Показываем только основные источники для краткости
    main_sources = [
        'https://ton.org/blog/rss.xml',
        'https://tginfo.me/feed/', 
        'https://tonstatus.io/rss',
        'https://mirror.xyz/tonsociety.eth/rss'
    ]
    
    shown_count = 0
    for source in config.RSS_SOURCES:
        if source in main_sources and shown_count < 4:
            if 'ton.org/blog' in source:
                text += f"• TON Foundation Blog\n"
            elif 'tginfo.me' in source:
                text += f"• TGInfo (Telegram новости)\n"
            elif 'tonstatus.io' in source:
                text += f"• TON Status\n"
            elif 'tonsociety.eth' in source:
                text += f"• TON Society\n"
            shown_count += 1
    
    if len(config.RSS_SOURCES) > 4:
        text += f"• ... и еще {len(config.RSS_SOURCES) - 4} источников\n"
    
    text += f"• Команда '/rss' для полного списка\n"
    text += "\n"
    
    # Telegram каналы
    text += f"💬 <b>Telegram каналы ({len(config.TG_CHANNELS)}):</b>\n"
    for i, channel in enumerate(config.TG_CHANNELS, 1):
        text += f"{i}. {channel}\n"
    text += "\n"
    
    text += f"⚙️ <b>Настройка источников:</b>\n"
    text += f"• RSS источники настраиваются в файле config.py\n"
    text += f"• Telegram каналы также в config.py\n"
    text += f"• После изменений перезапустите бота\n\n"
    text += f"📊 <b>Статус мониторинга:</b>\n"
    text += f"• Автоматический запуск каждые {config.MONITORING_INTERVAL_MINUTES} минут\n"
    text += f"• Ручной запуск через '🔄 Запустить мониторинг'\n"
    text += f"• Telegram каналов: {len(config.TG_CHANNELS)} (расширенный список)\n"
    text += f"• RSS источников: {len(config.RSS_SOURCES)}\n"
    text += f"• Команда '/channels' для детального просмотра\n"
    text += f"• Последние результаты в '/queue'"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Запустить мониторинг", callback_data="manual_monitoring"),
        InlineKeyboardButton(text="📋 Черновики", callback_data="view_drafts")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")
    )
    
    await safe_edit_message(callback, text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "channel_settings")
async def callback_channel_settings(callback: CallbackQuery):
    """Настройки канала"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    text = f"⚙️ <b>Настройки канала для публикации</b>\n\n"
    
    if config.CHANNEL_ID:
        text += f"📢 <b>Текущий канал:</b> {config.CHANNEL_ID}\n\n"
        
        # Проверяем возможность публикации
        try:
            # Попробуем получить информацию о канале
            chat_info = await callback.bot.get_chat(config.CHANNEL_ID)
            text += f"✅ <b>Статус:</b> Канал доступен\n"
            text += f"📊 <b>Название:</b> {chat_info.title}\n"
            text += f"👥 <b>Участников:</b> {chat_info.member_count if hasattr(chat_info, 'member_count') else 'Неизвестно'}\n"
            
            # Проверяем права бота
            bot_member = await callback.bot.get_chat_member(config.CHANNEL_ID, callback.bot.id)
            if bot_member.can_post_messages:
                text += f"🔐 <b>Права:</b> Есть права на публикацию ✅\n"
            else:
                text += f"🔐 <b>Права:</b> Нет прав на публикацию ❌\n"
                
        except Exception as e:
            text += f"❌ <b>Ошибка:</b> {str(e)}\n"
            text += f"🔧 Проверьте настройки канала\n"
    else:
        text += f"❌ <b>Канал не настроен</b>\n\n"
        text += f"Добавьте CHANNEL_ID в файл .env\n"
    
    text += f"\n📋 <b>Инструкция:</b>\n"
    text += f"1. Добавьте бота в канал как администратора\n"
    text += f"2. Включите права 'Publish Messages'\n"
    text += f"3. Укажите CHANNEL_ID в .env файле\n"
    text += f"4. Перезапустите бота\n\n"
    text += f"🆔 <b>Формат CHANNEL_ID:</b>\n"
    text += f"• @username - для публичных каналов\n"
    text += f"• -100123456789 - для приватных каналов\n\n"
    text += f"🔍 Для получения ID используйте @userinfobot"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🧪 Тест публикации", callback_data="test_channel"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")
    )
    
    await safe_edit_message(callback, text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "test_channel")
async def callback_test_channel(callback: CallbackQuery):
    """Тест публикации в канал"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    if not config.CHANNEL_ID:
        await callback.answer("❌ Канал не настроен", show_alert=True)
        return
    
    try:
        # Отправляем тестовое сообщение
        test_message = await callback.bot.send_message(
            config.CHANNEL_ID,
            "🧪 Тестовое сообщение от бота\n\nЭто сообщение подтверждает, что бот может публиковать в канале."
        )
        
        await callback.answer("✅ Тест прошел успешно!")
        
        # Логируем тест
        await db.log_action(
            user_id=callback.from_user.id,
            action_type="test_channel",
            target_type="channel",
            target_id=0,
            details=f"Тест публикации в канал {config.CHANNEL_ID}",
            new_value=f"message_id:{test_message.message_id}"
        )
        
        channel_username = config.CHANNEL_ID.replace('@', '') if config.CHANNEL_ID.startswith('@') else config.CHANNEL_ID
        
        await safe_edit_message(callback,
            f"✅ <b>Тест публикации успешен!</b>\n\n"
            f"📢 Канал: {config.CHANNEL_ID}\n"
            f"📝 ID сообщения: {test_message.message_id}\n"
            f"🔗 <a href='https://t.me/{channel_username}/{test_message.message_id}'>Перейти к сообщению</a>\n\n"
            f"Бот готов к публикации постов!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="🔙 Назад", callback_data="channel_settings")
            ).as_markup()
        )
        
    except Exception as e:
        await safe_edit_message(callback, f"❌ Ошибка: {str(e)}", show_alert=True)

@router.message(StateFilter(AdminStates.adding_keywords))
async def handle_add_keywords(message: Message, state: FSMContext):
    """Обработка добавления ключевых слов"""
    if not is_admin(message.from_user.id):
        return
    
    keywords_text = message.text.strip()
    new_keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
    
    if not new_keywords:
        await message.answer("❌ Не указаны ключевые слова. Попробуйте еще раз.")
        return
    
    added_count = 0
    for keyword in new_keywords:
        try:
            await db.add_keyword(keyword)
            added_count += 1
        except:
            pass  # Игнорируем дубликаты
    
    # Логируем добавление
    await db.log_action(
        user_id=message.from_user.id,
        action_type="add_keywords",
        target_type="keywords",
        target_id=0,
        details=f"Добавлено ключевых слов: {added_count}",
        new_value=", ".join(new_keywords)
    )
    
    await safe_edit_message(message,
        f"✅ <b>Ключевые слова добавлены</b>\n\n"
        f"📝 Добавлено: {added_count} из {len(new_keywords)}\n"
        f"🔍 Новые слова: {', '.join(new_keywords)}\n\n"
        f"Теперь мониторинг будет искать контент с этими словами.",
        parse_mode="HTML"
    )
    
    await state.clear()

@router.callback_query(F.data == "view_drafts")
async def callback_view_drafts(callback: CallbackQuery):
    """Просмотр черновиков контента"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    drafts = await db.get_content_drafts(status='new', limit=10)
    
    if not drafts:
        await safe_edit_message(callback,
            "📭 <b>Нет новых черновиков</b>\n\n"
            "Все найденные материалы уже обработаны или мониторинг еще не запускался.",
            parse_mode="HTML",
            reply_markup=get_admin_menu_keyboard()
        )
        return
    
    text = "📋 <b>Черновики контента</b>\n\n"
    
    for i, draft in enumerate(drafts[:5], 1):
        source_emoji = "📡" if draft['source_type'] == 'rss' else "💬"
        # Экранируем HTML символы с сохранением emoji
        safe_source_name = safe_html_with_emoji(draft['source_name'])
        safe_keywords = safe_html_with_emoji(draft['keywords_matched'] or '')
        safe_text = safe_html_with_emoji(draft['original_text'][:100])
        
        text += f"{i}. {source_emoji} <b>{safe_source_name}</b>\n"
        text += f"📅 {draft['source_date'][:10] if draft['source_date'] else 'Неизвестно'}\n"
        text += f"🔍 Ключевые слова: {safe_keywords}\n"
        text += f"📝 {safe_text}{'...' if len(draft['original_text']) > 100 else ''}\n\n"
    
    text += f"Показано {len(drafts[:5])} из {len(drafts)} черновиков"
    
    # Создаем inline кнопки для каждого черновика
    builder = InlineKeyboardBuilder()
    for i, draft in enumerate(drafts[:5], 1):
        builder.row(
            InlineKeyboardButton(
                text=f"{i}. Обработать",
                callback_data=f"process_draft_{draft['id']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="view_drafts"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")
    )
    
    await safe_edit_message(callback, text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("process_draft_"))
async def callback_process_draft(callback: CallbackQuery):
    """Обработка конкретного черновика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[2])
    draft = await db.get_draft_by_id(draft_id)
    
    if not draft:
        await callback.answer("❌ Черновик не найден", show_alert=True)
        return
    
    source_emoji = "📡" if draft['source_type'] == 'rss' else "💬"
    
    # Экранируем HTML символы с сохранением emoji
    safe_source_name = safe_html_with_emoji(draft['source_name'])
    safe_keywords = safe_html_with_emoji(draft['keywords_matched'] or '')
    safe_url = safe_html_with_emoji(draft['source_url'] or '')
    safe_text = safe_html_with_emoji(draft['original_text'])
    
    text = f"📋 <b>Черновик #{draft_id}</b>\n\n"
    text += f"{source_emoji} <b>Источник:</b> {safe_source_name}\n"
    text += f"📅 <b>Дата:</b> {draft['source_date'][:19] if draft['source_date'] else 'Неизвестно'}\n"
    text += f"🔍 <b>Ключевые слова:</b> {safe_keywords}\n"
    text += f"🔗 <b>Ссылка:</b> {safe_url}\n\n"
    text += f"📝 <b>Оригинальный текст:</b>\n<i>{safe_text}</i>"
    
    await safe_edit_message(callback,
        text,
        parse_mode="HTML",
        reply_markup=get_draft_action_keyboard(draft_id)
    )

@router.callback_query(F.data.startswith("rewrite_draft_"))
async def callback_rewrite_draft(callback: CallbackQuery):
    """Запуск перефразирования черновика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[2])
    draft = await db.get_draft_by_id(draft_id)
    
    if not draft:
        await callback.answer("❌ Черновик не найден", show_alert=True)
        return
    
    # В ручном режиме создаем базовую версию для предпросмотра
    from content_rewriter import rewrite_post
    rewritten_text = rewrite_post(draft['original_text'], style="auto")
    
    # Создаем пост на модерацию
    post_id = await db.add_pending_post(
        original_text=draft['original_text'],
        rewritten_text=rewritten_text,
        source_url=draft['source_url'],
        source_type=draft['source_type']
    )
    
    # Обновляем статус черновика
    await db.update_draft_status(draft_id, 'processed')
    
    # Логируем создание поста из черновика
    await db.log_action(
        user_id=callback.from_user.id,
        action_type="create_post_from_draft",
        target_type="content_draft",
        target_id=draft_id,
        details=f"Создан пост #{post_id} из черновика",
        old_value=draft['original_text'][:200],
        new_value=rewritten_text[:200]
    )
    
    # Отправляем пост на модерацию админу (в личные сообщения)
    post_data = await db.get_pending_post(post_id)
    if post_data:
        await send_post_for_moderation(callback.bot, config.ADMIN_ID, post_data)
    
    # Экранируем переписанный текст с сохранением emoji
    safe_rewritten_text = safe_html_with_emoji(rewritten_text)
    
    await safe_edit_message(callback,
        f"✅ <b>Пост создан и отправлен на модерацию</b>\n\n"
        f"<b>Переписанный текст:</b>\n<i>{safe_rewritten_text}</i>\n\n"
        f"📬 Пост отправлен вам в личные сообщения для модерации.",
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("delete_draft_"))
async def callback_delete_draft(callback: CallbackQuery):
    """Удаление черновика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[2])
    draft = await db.get_draft_by_id(draft_id)
    
    if draft:
        # Логируем удаление черновика
        await db.log_action(
            user_id=callback.from_user.id,
            action_type="delete_draft",
            target_type="content_draft",
            target_id=draft_id,
            details="Черновик удален администратором",
            old_value=draft['original_text'][:200],
            new_value="deleted"
        )
    
    await db.update_draft_status(draft_id, 'deleted')
    
    await safe_edit_message(callback, "🗑 Черновик удален")
    await callback_view_drafts(callback)

@router.callback_query(F.data == "manual_monitoring")
async def callback_manual_monitoring(callback: CallbackQuery):
    """Запуск мониторинга вручную"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    await safe_edit_message(callback, "🔄 Запускаем мониторинг...")
    
    # Запускаем мониторинг
    success = await scheduler.run_manual_monitoring()
    
    if success:
        await safe_edit_message(callback,
            "✅ <b>Мониторинг завершен</b>\n\n"
            "Новые материалы найдены и добавлены в черновики.\n"
            "Проверьте раздел 'Черновики контента' для просмотра.",
            parse_mode="HTML",
            reply_markup=get_admin_menu_keyboard()
        )
    else:
        await safe_edit_message(callback,
            "❌ <b>Ошибка мониторинга</b>\n\n"
            "Не удалось выполнить мониторинг. Проверьте логи.",
            parse_mode="HTML",
            reply_markup=get_admin_menu_keyboard()
        )

@router.callback_query(F.data == "back_to_admin")
async def callback_back_to_admin(callback: CallbackQuery):
    """Возврат в админское меню"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    await safe_edit_message(callback,
        "🎛 <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_menu_keyboard()
    )

async def publish_to_channel(bot: Bot, post: dict):
    """Публикует пост в канал с Premium emoji"""
    try:
        # Проверяем настройки канала
        if not config.CHANNEL_ID:
            logger.error("CHANNEL_ID не настроен")
            return None
        
        # Определяем тип контента для выбора шаблона emoji
        post_text = post['rewritten_text'].lower()
        if 'airdrop' in post_text or 'подарок' in post_text or 'раздача' in post_text:
            template = "airdrop"
        elif 'обновление' in post_text or 'update' in post_text or 'релиз' in post_text:
            template = "update"
        elif 'анализ' in post_text or 'статистика' in post_text or 'chart' in post_text:
            template = "analysis"
        else:
            template = "news"
        
        # Применяем шаблон emoji к тексту
        enhanced_text = apply_template(post['rewritten_text'], template)
        
        # Добавляем подпись канала с emoji
        signature_emoji = get_emoji("shine")
        if not enhanced_text.endswith('\n'):
            enhanced_text += '\n'
        enhanced_text += f"\n{signature_emoji} Подписывайтесь на канал!"
        
        # Публикуем пост с HTML parse_mode для поддержки emoji
        message = await bot.send_message(
            chat_id=config.CHANNEL_ID,
            text=enhanced_text,
            parse_mode="HTML"
        )
        
        logger.info(f"Пост опубликован в канале {config.CHANNEL_ID} с шаблоном {template}, message_id: {message.message_id}")
        return message
        
    except Exception as e:
        logger.error(f"Ошибка публикации в канал: {e}")
        return None

async def send_post_for_moderation(bot: Bot, admin_id: int, post: dict):
    """Отправляет пост админу для модерации с Premium emoji"""
    try:
        # Добавляем Premium emoji к переписанному тексту для предпросмотра
        enhanced_rewritten = add_emojis_to_post(post['rewritten_text'], style="thematic")
        
        # Экранируем текст для безопасного отображения с сохранением emoji
        safe_original = safe_html_with_emoji(post['original_text'])
        safe_rewritten = safe_html_with_emoji(enhanced_rewritten)
        safe_url = safe_html_with_emoji(post.get('source_url', ''))
        
        # Добавляем emoji к заголовку модерации
        header_emoji = get_emoji("envelope")
        text = f"{header_emoji} <b>Новый пост на модерации</b>\n\n"
        
        original_emoji = get_emoji("brain")
        text += f"{original_emoji} <b>Оригинальный текст:</b>\n<i>{safe_original}</i>\n\n"
        
        rewritten_emoji = get_emoji("sparkle")
        text += f"{rewritten_emoji} <b>Переписанный текст с emoji:</b>\n<i>{safe_rewritten}</i>\n\n"
        
        if safe_url:
            link_emoji = get_emoji("airplane")
            text += f"{link_emoji} <b>Источник:</b> {safe_url}\n\n"
        
        action_emoji = get_emoji("yellow_star")
        text += f"{action_emoji} Выберите действие:"
        
        message = await bot.send_message(
            chat_id=admin_id,
            text=text,
            parse_mode="HTML",
            reply_markup=get_moderation_keyboard(post['id'])
        )
        
        logger.info(f"Пост #{post['id']} отправлен на модерацию админу {admin_id}")
        return message
        
    except Exception as e:
        logger.error(f"Ошибка отправки поста на модерацию: {e}")
        return None

@router.callback_query(F.data == "stats")
async def callback_stats(callback: CallbackQuery):
    """Показывает статистику бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    try:
        # Статистика публикаций
        pub_stats = await db.get_published_posts_stats()
        
        # Статистика черновиков
        drafts_new = await db.get_content_drafts(status='new', limit=1000)
        drafts_processed = await db.get_content_drafts(status='processed', limit=1000)
        
        # Статистика постов на модерации
        pending_posts = await db.get_content_drafts(status='pending', limit=1000)
        
        text = f"�� <b>Статистика бота</b>\n\n"
        text += f"📰 <b>Опубликованные посты:</b>\n"
        text += f"• Всего: {pub_stats['total']}\n"
        text += f"• За 24 часа: {pub_stats['last_24h']}\n"
        text += f"• За 7 дней: {pub_stats['last_7d']}\n\n"
        text += f"📋 <b>Черновики:</b>\n"
        text += f"• Новые: {len(drafts_new)}\n"
        text += f"• Обработанные: {len(drafts_processed)}\n\n"
        text += f"⏳ <b>На модерации:</b> {len(pending_posts)}\n\n"
        text += f"🔄 <b>Мониторинг:</b> Каждые {config.MONITORING_INTERVAL_MINUTES} минут\n"
        text += f"📡 <b>Источники:</b> {len(config.RSS_SOURCES)} RSS + {len(config.TG_CHANNELS)} Telegram\n"
        text += f"🔍 <b>Ключевые слова:</b> {len(config.KEYWORDS)} слов\n"
        text += f"📰 <b>RSS категории:</b> Официальные, Новостные, Сообщество, Twitter-прокси\n"
        text += f"📡 <b>TG категории:</b> Официальные, Новостные, Аналитические, Специализированные\n"
        
        await safe_edit_message(callback,
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")
            ).as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await safe_edit_message(callback, "❌ Ошибка получения статистики", show_alert=True)

@router.message(Command("emoji"))
async def cmd_emoji(message: Message):
    """Команда для тестирования Premium emoji (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Демонстрируем различные типы emoji
    text = f"{get_emoji('yellow_star')} <b>Тест Premium Emoji</b>\n\n"
    
    text += f"{get_emoji('brain')} <b>Тематические emoji:</b>\n"
    text += f"• Блокчейн: {get_emoji('diamond')}\n"
    text += f"• Обновления: {get_emoji('reload')}\n"
    text += f"• Подарки: {get_emoji('gift')}\n"
    text += f"• Технологии: {get_emoji('tech')}\n"
    text += f"• Успех: {get_emoji('check')}\n\n"
    
    text += f"{get_emoji('sparkle')} <b>Случайные emoji:</b>\n"
    for i in range(5):
        text += f"• {get_random_emoji()}\n"
    
    text += f"\n{get_emoji('heart')} <b>Шаблоны постов:</b>\n"
    
    # Демо новостей
    news_demo = "TON блокчейн достигает новых высот"
    text += f"\n📰 <b>News шаблон:</b>\n"
    text += f"{apply_template(news_demo, 'news')}\n"
    
    # Демо обновления
    update_demo = "Telegram выпустил важное обновление"
    text += f"\n🔄 <b>Update шаблон:</b>\n"
    text += f"{apply_template(update_demo, 'update')}\n"
    
    # Демо airdrop
    airdrop_demo = "Новая раздача токенов для пользователей"
    text += f"\n🎁 <b>Airdrop шаблон:</b>\n"
    text += f"{apply_template(airdrop_demo, 'airdrop')}\n"
    
    await safe_edit_message(message, text, parse_mode="HTML")

@router.message(Command("test_duplicate"))
async def cmd_test_duplicate(message: Message):
    """Команда для тестирования исправления дублирования (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Создаем тестовый пост для проверки дублирования
    test_text = "Тест исправления дублирования постов"
    base_rewritten = "Проверяем, что пост публикуется только один раз, даже если нажать 'Одобрить' несколько раз."
    rewritten_with_emoji = apply_template(base_rewritten, "news")
    
    post_id = await db.add_pending_post(
        original_text=test_text,
        rewritten_text=rewritten_with_emoji,
        source_url="https://example.com/test-duplicate",
        source_type="test_duplicate"
    )
    
    post = await db.get_post_by_id(post_id)
    
    if post:
        await send_post_for_moderation(message.bot, config.ADMIN_ID, post)
        
        test_emoji = get_emoji("check")
        warning_emoji = get_emoji("warning")
        
        await safe_edit_message(message,
            f"{test_emoji} <b>Тест дублирования создан!</b>\n\n"
            f"📝 ID поста: {post_id}\n"
            f"📬 Пост отправлен на модерацию\n\n"
            f"{warning_emoji} <b>Как тестировать:</b>\n"
            f"1. Нажмите 'Одобрить' → пост опубликуется\n"
            f"2. Попробуйте нажать 'Одобрить' еще раз\n"
            f"3. Должно появиться предупреждение о повторной публикации\n\n"
            f"✅ Дублирование исправлено!",
            parse_mode="HTML"
        )
    else:
        await safe_edit_message(message, "❌ Ошибка создания тестового поста")

@router.message(Command("interval"))
async def cmd_set_monitoring_interval(message: Message):
    """Команда для настройки интервала мониторинга (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Парсим аргументы команды
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if not args:
        # Показываем текущие настройки
        clock_emoji = get_emoji("clock") 
        settings_emoji = get_emoji("tech")
        info_emoji = get_emoji("brain")
        
        text = f"{settings_emoji} <b>Настройки интервалов мониторинга</b>\n\n"
        text += f"{clock_emoji} <b>Текущие интервалы:</b>\n"
        text += f"• Общий мониторинг: {config.MONITORING_INTERVAL_MINUTES} мин\n"
        text += f"• RSS проверка: {config.RSS_CHECK_INTERVAL_MINUTES} мин\n"
        text += f"• Telegram проверка: {config.TG_CHECK_INTERVAL_MINUTES} мин\n\n"
        
        text += f"{info_emoji} <b>Как изменить:</b>\n"
        text += f"• `/interval 3` - общий интервал 3 минуты\n"
        text += f"• `/interval urgent` - режим срочных новостей (1-2 мин)\n"
        text += f"• `/interval normal` - обычный режим (5-7 мин)\n"
        text += f"• `/interval slow` - медленный режим (15-30 мин)\n\n"
        
        warning_emoji = get_emoji("warning")
        text += f"{warning_emoji} <i>Изменения применятся после перезапуска</i>"
        
        await safe_edit_message(message, text, parse_mode="HTML")
        return
    
    # Обрабатываем команды
    command = args[0].lower()
    
    if command == "urgent":
        new_interval = 2
        rss_interval = 1
        tg_interval = 3
        mode_name = "🔥 Срочные новости"
    elif command == "normal":
        new_interval = 5
        rss_interval = 3
        tg_interval = 7
        mode_name = "⚡ Обычный режим"
    elif command == "slow":
        new_interval = 15
        rss_interval = 10
        tg_interval = 20
        mode_name = "🐌 Медленный режим"
    elif command.isdigit():
        new_interval = int(command)
        if new_interval < 1 or new_interval > 60:
            await message.answer("❌ Интервал должен быть от 1 до 60 минут")
            return
        rss_interval = max(1, new_interval - 2)
        tg_interval = new_interval + 2
        mode_name = f"🎯 Пользовательский ({new_interval} мин)"
    else:
        await message.answer("❌ Неверная команда. Используйте: urgent, normal, slow или число")
        return
    
    # Обновляем значения в config (временно, до перезапуска)
    config.MONITORING_INTERVAL_MINUTES = new_interval
    config.RSS_CHECK_INTERVAL_MINUTES = rss_interval
    config.TG_CHECK_INTERVAL_MINUTES = tg_interval
    
    success_emoji = get_emoji("check")
    rocket_emoji = get_emoji("airplane")
    
    await safe_edit_message(message,
        f"{success_emoji} <b>Интервал мониторинга обновлен!</b>\n\n"
        f"{rocket_emoji} <b>Режим:</b> {mode_name}\n"
        f"• Общий интервал: {new_interval} мин\n"
        f"• RSS: {rss_interval} мин\n"
        f"• Telegram: {tg_interval} мин\n\n"
        f"✨ <b>Изменения активны!</b> Следующий цикл через {new_interval} минут.\n\n"
        f"💡 <i>Для постоянного сохранения добавьте в .env:</i>\n"
        f"`MONITORING_INTERVAL_MINUTES={new_interval}`",
        parse_mode="HTML"
    )

@router.message(Command("test_emoji"))
async def cmd_test_emoji(message: Message):
    """Команда для тестирования исправления Premium emoji (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Создаем тестовый пост с emoji для проверки
    test_original = "Тест исправления Premium emoji"
    test_rewritten = apply_template("Проверяем, что Premium emoji теперь работают корректно и отображаются как анимированные иконки, а не как HTML теги.", "news")
    
    post_id = await db.add_pending_post(
        original_text=test_original,
        rewritten_text=test_rewritten,
        source_url="https://example.com/test-emoji",
        source_type="test_emoji"
    )
    
    post = await db.get_post_by_id(post_id)
    
    if post:
        await send_post_for_moderation(message.bot, config.ADMIN_ID, post)
        
        success_emoji = get_emoji("check")
        sparkle_emoji = get_emoji("sparkle")
        warning_emoji = get_emoji("warning")
        
        await safe_edit_message(message,
            f"{success_emoji} <b>Тест Premium emoji создан!</b>\n\n"
            f"📝 ID поста: {post_id}\n"
            f"📬 Пост отправлен на модерацию\n\n"
            f"{sparkle_emoji} <b>Что проверить:</b>\n"
            f"1. В сообщении модерации должны быть анимированные emoji\n"
            f"2. Не должно быть HTML тегов типа `&lt;tg-emoji&gt;`\n"
            f"3. При публикации emoji должны сохраниться\n\n"
            f"{warning_emoji} <i>Если видите HTML теги - emoji не работают</i>\n"
            f"✅ <i>Если видите анимированные иконки - все исправлено!</i>",
            parse_mode="HTML"
        )
    else:
        await safe_edit_message(message, "❌ Ошибка создания тестового поста")

@router.message(Command("channels"))
async def cmd_check_channels(message: Message):
    """Команда для проверки статуса всех каналов мониторинга (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    channels_emoji = get_emoji("tower")
    check_emoji = get_emoji("check")
    warning_emoji = get_emoji("warning")
    
    text = f"{channels_emoji} <b>Статус каналов мониторинга</b>\n\n"
    text += f"📊 <b>Всего каналов:</b> {len(config.TG_CHANNELS)}\n\n"
    
    # Группируем каналы по категориям
    official_channels = [
        '@durov', '@telegram', '@toncoin'
    ]
    
    news_channels = [
        '@tginfo', '@cryptotonhunter', '@ton_society', 
        '@ton_blockchain', '@tonstatus'
    ]
    
    analytics_channels = [
        '@Exploitex', '@the_club_100', '@cryptover1'
    ]
    
    specialized_channels = [
        '@toncaps', '@tap2earn_ru', '@tonnft', '@gifts_ru'
    ]
    
    text += f"🏢 <b>Официальные ({len(official_channels)}):</b>\n"
    for channel in official_channels:
        text += f"• {channel}\n"
    
    text += f"\n📰 <b>Новостные ({len(news_channels)}):</b>\n"
    for channel in news_channels:
        text += f"• {channel}\n"
    
    text += f"\n📈 <b>Аналитические ({len(analytics_channels)}):</b>\n"
    for channel in analytics_channels:
        text += f"• {channel}\n"
    
    text += f"\n🎯 <b>Специализированные ({len(specialized_channels)}):</b>\n"
    for channel in specialized_channels:
        text += f"• {channel}\n"
    
    # Считаем остальные каналы
    categorized = official_channels + news_channels + analytics_channels + specialized_channels
    other_channels = [ch for ch in config.TG_CHANNELS if ch not in categorized]
    
    if other_channels:
        text += f"\n🔹 <b>Дополнительные ({len(other_channels)}):</b>\n"
        for channel in other_channels:
            text += f"• {channel}\n"
    
    text += f"\n{check_emoji} <b>Мониторинг:</b>\n"
    text += f"• Интервал: {config.TG_CHECK_INTERVAL_MINUTES} мин\n"
    text += f"• Следующая проверка через: {config.MONITORING_INTERVAL_MINUTES} мин\n"
    text += f"• Статус: Активен\n\n"
    
    text += f"{warning_emoji} <b>Важно:</b>\n"
    text += f"• Убедитесь что у бота есть доступ к каналам\n"
    text += f"• Некоторые каналы могут требовать подписки\n"
    text += f"• Каналы с пометкой 'реф' могут быть реферальными"
    
    await safe_edit_message(message, text, parse_mode="HTML")

@router.message(Command("test_keywords"))
async def cmd_test_keywords(message: Message):
    """Команда для тестирования логики поиска ключевых слов (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    from content_monitor import content_monitor
    
    # Тестовые примеры
    test_cases = [
        # Тест длинных слов (должны находить похожие)
        "В новом обновлении добавили фичи",  # обновление → обновления
        "Запуски новых ботов продолжаются",   # запуск → запуски, бот → боты  
        "Криптовалютные новости сегодня",     # криптовалюта → криптовалютные
        
        # Тест коротких слов (точное совпадение)
        "Новый бот от Telegram",              # должен найти: бот, Telegram
        "Работает отлично",                   # НЕ должен найти "бот" в "работает"
        "Тон музыки изменился",               # НЕ должен найти "тон" (контекст не про TON)
        
        # Тест фраз
        "TG Premium теперь доступен",         # должен найти: TG Premium
        "Telegram Gifts запущены",            # должен найти: Telegram, Gifts
        
        # Тест русских слов
        "Раздачи и подарки от Дурова",       # должен найти: раздача, подарки
        "НФТ коллекция готова",               # должен найти: НФТ
    ]
    
    search_emoji = get_emoji("brain")
    check_emoji = get_emoji("check") 
    cross_emoji = get_emoji("cross")
    
    text = f"{search_emoji} <b>Тест логики ключевых слов</b>\n\n"
    text += f"📊 <b>Всего ключевых слов:</b> {len(config.KEYWORDS)}\n\n"
    
    for i, test_text in enumerate(test_cases, 1):
        found_keywords = content_monitor.check_keywords(test_text)
        
        if found_keywords:
            text += f"{check_emoji} <b>Тест {i}:</b>\n"
            text += f"📝 Текст: <i>{test_text}</i>\n"
            text += f"🔍 Найдено: {', '.join(found_keywords[:5])}"
            if len(found_keywords) > 5:
                text += f" (+{len(found_keywords) - 5})"
            text += f"\n\n"
        else:
            text += f"{cross_emoji} <b>Тест {i}:</b>\n"
            text += f"📝 Текст: <i>{test_text}</i>\n"
            text += f"🔍 Ключевые слова не найдены\n\n"
    
    # Статистика по категориям
    english_keywords = [kw for kw in config.KEYWORDS if all(ord(c) < 128 for c in kw if c.isalpha())]
    russian_keywords = [kw for kw in config.KEYWORDS if any(ord(c) >= 1024 for c in kw)]
    phrases = [kw for kw in config.KEYWORDS if ' ' in kw]
    
    text += f"📈 <b>Статистика ключевых слов:</b>\n"
    text += f"• Английские: {len(english_keywords)}\n"
    text += f"• Русские: {len(russian_keywords)}\n"
    text += f"• Фразы: {len(phrases)}\n\n"
    
    text += f"💡 <b>Логика поиска:</b>\n"
    text += f"• Фразы: точное совпадение\n"
    text += f"• Длинные слова (5+): поиск подстроки\n"
    text += f"• Короткие слова (3-4): границы слов\n\n"
    
    text += f"🧪 <b>Примеры работы:</b>\n"
    text += f"• 'запуск' найдет 'запуски', 'запуска'\n"
    text += f"• 'бот' НЕ найдет в слове 'работа'\n"
    text += f"• 'обновление' найдет 'обновления'"
    
    await safe_edit_message(message, text, parse_mode="HTML")

@router.message(Command("rss"))
async def cmd_check_rss(message: Message):
    """Команда для проверки статуса RSS источников (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    rss_emoji = get_emoji("tower")
    check_emoji = get_emoji("check")
    warning_emoji = get_emoji("warning")
    
    text = f"{rss_emoji} <b>Статус RSS источников</b>\n\n"
    text += f"📊 <b>Всего источников:</b> {len(config.RSS_SOURCES)}\n\n"
    
    # Категории RSS источников
    categories = {
        "🏢 Официальные TON": [
            'https://ton.org/blog/rss.xml',
            'https://ton.org/rss.xml'
        ],
        "📰 Новостные агрегаторы": [
            'https://tginfo.me/feed/',
            'https://tonstatus.io/rss'
        ],
        "🌐 Экосистема и сообщество": [
            'https://mirror.xyz/tonsociety.eth/rss',
            'https://medium.com/feed/@tonblockchain',
            'https://tonwhales.com/blog/rss.xml'
        ],
        "🐦 Twitter через прокси": [
            'https://nitter.net/telegram/rss',
            'https://rsshub.app/twitter/user/ton_blockchain',
            'https://rsshub.app/twitter/user/durov',
            'https://nitter.net/durov/rss'
        ]
    }
    
    for category, sources in categories.items():
        count = len([s for s in sources if s in config.RSS_SOURCES])
        text += f"{category} <b>({count}):</b>\n"
        
        for source in sources:
            if source in config.RSS_SOURCES:
                # Получаем название источника
                if 'ton.org/blog' in source:
                    name = "TON Foundation Blog"
                elif 'ton.org/rss' in source:
                    name = "TON Foundation"
                elif 'tginfo.me' in source:
                    name = "TGInfo"
                elif 'tonstatus.io' in source:
                    name = "TON Status"
                elif 'tonsociety.eth' in source:
                    name = "TON Society"
                elif 'tonblockchain' in source:
                    name = "TON Community"
                elif 'tonwhales.com' in source:
                    name = "TON Whales"
                elif 'telegram/rss' in source:
                    name = "Telegram (Nitter)"
                elif 'ton_blockchain' in source:
                    name = "TON (RSSHub)"
                elif 'durov' in source and 'rsshub' in source:
                    name = "Durov (RSSHub)"
                elif 'durov' in source and 'nitter' in source:
                    name = "Durov (Nitter)"
                else:
                    name = source.split('/')[2] if '/' in source else source
                
                text += f"• {name}\n"
        text += "\n"
    
    # Остальные источники (если есть)
    categorized_sources = []
    for sources in categories.values():
        categorized_sources.extend(sources)
    
    other_sources = [s for s in config.RSS_SOURCES if s not in categorized_sources]
    if other_sources:
        text += f"🔹 <b>Дополнительные ({len(other_sources)}):</b>\n"
        for source in other_sources:
            domain = source.split('/')[2] if '/' in source else source
            text += f"• {domain}\n"
        text += "\n"
    
    text += f"{check_emoji} <b>Мониторинг RSS:</b>\n"
    text += f"• Интервал: {config.RSS_CHECK_INTERVAL_MINUTES} мин\n"
    text += f"• Следующая проверка через: {config.MONITORING_INTERVAL_MINUTES} мин\n"
    text += f"• Статус: Активен\n\n"
    
    text += f"{warning_emoji} <b>Важно:</b>\n"
    text += f"• Nitter может периодически недоступен\n"
    text += f"• RSSHub требует стабильного интернета\n"
    text += f"• Medium может ограничивать частые запросы\n"
    text += f"• Используйте '/admin' → 'Запустить мониторинг' для проверки"
    
    await safe_edit_message(message, text, parse_mode="HTML")

@router.message(Command("debug_emoji"))
async def cmd_debug_emoji(message: Message):
    """Подробная диагностика emoji (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    from emoji_config import get_emoji_with_fallback, FALLBACK_EMOJIS
    
    # Тест 1: Сравнение Premium и обычных emoji
    await safe_edit_message(message,
        f"🔍 <b>Тест 1: Сравнение emoji</b>\n\n"
        f"<b>Premium emoji:</b> {get_emoji('yellow_star')} {get_emoji('check')} {get_emoji('heart')}\n"
        f"<b>Обычные emoji:</b> ⭐ ✅ ❤️\n\n"
        f"<b>Если видите одинаковые:</b> Premium emoji не работают\n"
        f"<b>Если видите разные:</b> Premium emoji работают!",
        parse_mode="HTML"
    )
    
    # Тест 2: Детальная проверка
    premium_star = get_emoji("yellow_star")
    await safe_edit_message(message,
        f"🔍 <b>Тест 2: Детальная проверка</b>\n\n"
        f"<b>Сырой HTML код:</b>\n"
        f"<code>{premium_star}</code>\n\n"
        f"<b>Отображение:</b>\n"
        f"{premium_star} ← должна быть анимированная звезда\n\n"
        f"<b>Проверка parse_mode:</b> HTML активен",
        parse_mode="HTML"
    )
    
    # Тест 3: Информация о клиенте
    await safe_edit_message(message,
        f"🔍 <b>Тест 3: Диагностика клиента</b>\n\n"
        f"👤 <b>Информация:</b>\n"
        f"• ID: {message.from_user.id}\n"
        f"• Username: @{message.from_user.username or 'не указан'}\n"
        f"• Имя: {message.from_user.first_name}\n"
        f"• Язык: {message.from_user.language_code or 'не указан'}\n\n"
        f"📱 <b>Premium emoji НЕ работают в:</b>\n"
        f"❌ Веб-версии Telegram (web.telegram.org)\n"
        f"❌ Некоторых десктопных клиентах\n"
        f"❌ Старых версиях приложений\n\n"
        f"✅ <b>Premium emoji работают в:</b>\n"
        f"✅ Мобильных приложениях (iOS/Android)\n"
        f"✅ Telegram Desktop (новые версии)\n"
        f"✅ Только с подходящими emoji ID",
        parse_mode="HTML"
    )
    
    # Тест 4: Fallback режим
    await safe_edit_message(message,
        f"🔍 <b>Тест 4: Режим совместимости</b>\n\n"
        f"<b>С Premium emoji:</b>\n"
        f"{get_emoji_with_fallback('yellow_star', True)} Важные новости\n"
        f"{get_emoji_with_fallback('check', True)} Проверка пройдена\n"
        f"{get_emoji_with_fallback('heart', True)} Нравится\n\n"
        f"<b>Только обычные emoji:</b>\n"
        f"{get_emoji_with_fallback('yellow_star', False)} Важные новости\n"
        f"{get_emoji_with_fallback('check', False)} Проверка пройдена\n"
        f"{get_emoji_with_fallback('heart', False)} Нравится\n\n"
        f"💡 <b>Рекомендация:</b> Попробуйте мобильное приложение!",
        parse_mode="HTML"
    )

@router.message(Command("test_rewrite"))
async def cmd_test_rewrite(message: Message):
    """Команда для тестирования новой системы переписывания (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Тестовые тексты разных типов
    test_cases = [
        {
            "type": "Новости",
            "original": "Telegram объявляет о партнерстве с TON Foundation для интеграции блокчейн технологий в мессенджер",
            "style": "news"
        },
        {
            "type": "Обновление", 
            "original": "Выпущена новая версия Telegram с поддержкой Premium emoji и улучшенной работой ботов",
            "style": "update"
        },
        {
            "type": "Airdrop",
            "original": "Запущена раздача токенов TON для активных пользователей Telegram Premium",
            "style": "airdrop"
        },
        {
            "type": "Короткий текст",
            "original": "TON растет в цене",
            "style": "auto"
        }
    ]
    
    test_emoji = get_emoji("brain")
    await safe_edit_message(message,
        f"{test_emoji} <b>Тестирование системы переписывания</b>\n\n"
        f"🔄 Генерирую качественные посты из разных типов контента...",
        parse_mode="HTML"
    )
    
    for i, test_case in enumerate(test_cases, 1):
        try:
            # Переписываем текст
            rewritten = rewrite_post(test_case["original"], test_case["style"])
            
            # Отправляем результат
            await message.answer(
                f"📝 <b>Тест {i}: {test_case['type']}</b>\n\n"
                f"<b>Исходный текст:</b>\n<i>{test_case['original']}</i>\n\n"
                f"<b>Переписанный пост:</b>\n{rewritten}\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Было символов: {len(test_case['original'])}\n"
                f"• Стало символов: {len(rewritten)}\n"
                f"• Увеличение: {len(rewritten) - len(test_case['original'])}",
                parse_mode="HTML"
            )
        except Exception as e:
            await message.answer(
                f"❌ <b>Ошибка в тесте {i}:</b> {str(e)}",
                parse_mode="HTML"
            )
    
    success_emoji = get_emoji("check")
    await message.answer(
        f"{success_emoji} <b>Тестирование завершено!</b>\n\n"
        f"🎯 <b>Преимущества новой системы:</b>\n"
        f"• Автоматическое определение типа контента\n"
        f"• Расширение коротких текстов до полноценных постов\n"
        f"• Добавление контекста и call-to-action\n"
        f"• Улучшение вовлеченности с помощью эмоций\n"
        f"• Интеграция с Premium emoji\n\n"
        f"💡 <b>Теперь все посты будут качественными и развернутыми!</b>",
        parse_mode="HTML"
    )

@router.message(Command("manual"))
async def cmd_manual_rewrite(message: Message, state: FSMContext):
    """Команда для ручного перефразирования с советами и готовыми промптами (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    brain_emoji = get_emoji("brain")
    await safe_edit_message(message,
        f"{brain_emoji} <b>Ручное перефразирование с ChatGPT</b>\n\n"
        f"📝 Отправьте исходный пост, который нужно перефразировать.\n"
        f"Я проанализирую его и дам советы + готовый промпт для ChatGPT!",
        parse_mode="HTML"
    )
    
    await state.set_state(ContentModerationStates.waiting_for_manual_rewrite)

@router.message(StateFilter(ContentModerationStates.waiting_for_manual_rewrite))
async def handle_manual_rewrite(message: Message, state: FSMContext):
    """Обработка текста для ручного перефразирования"""
    if not is_admin(message.from_user.id):
        return
    
    original_text = message.text
    
    # Получаем советы что нужно улучшить
    # suggestions = chatgpt_rewriter.get_rewrite_suggestions(original_text)
    
    # Определяем тип контента
    # content_type = chatgpt_rewriter._detect_content_type(original_text)
    type_names = {
        "news": "📰 Новость",
        "update": "🔄 Обновление", 
        "airdrop": "🎁 Airdrop",
        "analysis": "📊 Аналитика"
    }
    
    # Формируем ответ с советами
    response_text = f"🎯 <b>Анализ поста для перефразирования</b>\n\n"
    response_text += f"📋 <b>Тип контента:</b> {type_names.get(content_type, '📝 Общий')}\n"
    response_text += f"📏 <b>Длина:</b> {len(original_text)} символов\n\n"
    
    if suggestions:
        response_text += f"💡 <b>Что нужно улучшить:</b>\n"
        for i, (key, suggestion) in enumerate(suggestions.items(), 1):
            response_text += f"{i}. {suggestion}\n"
        response_text += "\n"
    else:
        response_text += f"✅ <b>Текст хорошего качества, но можно улучшить стилистику</b>\n\n"
    
    response_text += f"📝 <b>Исходный текст:</b>\n<i>{safe_html_with_emoji(original_text)}</i>\n\n"
    
    await safe_edit_message(message, response_text, parse_mode="HTML")
    
    # Генерируем готовый промпт для ChatGPT
    copyable_prompt = get_manual_rewrite_prompt(original_text, content_type)
    
    sparkle_emoji = get_emoji("sparkle")
    await message.answer(
        f"{sparkle_emoji} <b>Готовый промпт для ChatGPT</b>\n\n"
        f"📋 Скопируйте текст ниже и вставьте в ChatGPT:",
        parse_mode="HTML"
    )
    
    # Отправляем промпт отдельным сообщением для удобного копирования
    await message.answer(
        f"<code>{copyable_prompt}</code>",
        parse_mode="HTML"
    )
    
    gift_emoji = get_emoji("gift")
    await message.answer(
        f"{gift_emoji} <b>Инструкция:</b>\n\n"
        f"1️⃣ Скопируйте промпт выше\n"
        f"2️⃣ Откройте ChatGPT\n"
        f"3️⃣ Вставьте промпт и нажмите Enter\n"
        f"4️⃣ Получите качественный пост!\n\n"
        f"🔄 Для нового поста используйте /manual",
        parse_mode="HTML"
    )
    
    await state.clear()

@router.message(Command("chatgpt"))  
async def cmd_chatgpt_demo(message: Message):
    """Демонстрация автоматического перефразирования через ChatGPT API (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    if not config.OPENAI_API_KEY:
        await safe_edit_message(message,
            f"⚠️ <b>OpenAI API ключ не настроен</b>\n\n"
            f"Добавьте OPENAI_API_KEY в .env файл для использования ChatGPT.",
            parse_mode="HTML"
        )
        return
    
    # Тестовые посты для демонстрации
    test_posts = [
        "TON блокчейн показывает рост на 15% за последние 24 часа",
        "Telegram выпустил обновление с новыми функциями для ботов", 
        "Запущена раздача 1000 TON для активных пользователей",
        "Аналитики прогнозируют рост криптовалютного рынка"
    ]
    
    robot_emoji = get_emoji("tech")
    await safe_edit_message(message,
        f"{robot_emoji} <b>Демонстрация ChatGPT перефразирования</b>\n\n"
        f"🔄 Тестирую автоматическое улучшение постов...",
        parse_mode="HTML"
    )
    
    for i, original in enumerate(test_posts, 1):
        try:
            # Перефразируем через ChatGPT
            rewritten = await rewrite_post_with_ai(original, use_chatgpt=True)
            
            await message.answer(
                f"📝 <b>Тест {i}</b>\n\n"
                f"<b>Исходный текст:</b>\n<i>{original}</i>\n\n"
                f"<b>ChatGPT результат:</b>\n{rewritten}\n\n"
                f"📊 Улучшение: {len(original)} → {len(rewritten)} символов",
                parse_mode="HTML"
            )
            
        except Exception as e:
            await message.answer(
                f"❌ <b>Ошибка в тесте {i}:</b> {str(e)}",
                parse_mode="HTML"
            )
    
    success_emoji = get_emoji("check")
    await message.answer(
        f"{success_emoji} <b>Демонстрация завершена!</b>\n\n"
        f"🤖 <b>ChatGPT автоматически:</b>\n"
        f"• Создает энергичные заголовки\n"
        f"• Убирает ссылки и лишние символы\n"
        f"• Добавляет контекст и эмоции\n"
        f"• Структурирует информацию\n"
        f"• Добавляет призыв к действию\n\n"
        f"💡 Теперь все посты будут профессионального качества!",
        parse_mode="HTML"
    )

@router.message(Command("prompts"))
async def cmd_ready_prompts(message: Message):
    """Показывает готовые промпты для разных типов контента (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    book_emoji = get_emoji("brain")
    await safe_edit_message(message,
        f"{book_emoji} <b>Готовые промпты для ChatGPT</b>\n\n"
        f"📚 Выберите тип контента для получения готового промпта:",
        parse_mode="HTML"
    )
    
    # Отправляем все готовые промпты
    for content_type, prompt_template in READY_PROMPTS.items():
        type_names = {
            "news": "📰 Новости",
            "update": "🔄 Обновления",
            "airdrop": "🎁 Airdrop",
            "analysis": "📊 Аналитика"
        }
        
        await message.answer(
            f"<b>{type_names.get(content_type, content_type.upper())}</b>\n\n"
            f"<code>{prompt_template}</code>",
            parse_mode="HTML"
        )
    
    sparkle_emoji = get_emoji("sparkle")
    await message.answer(
        f"{sparkle_emoji} <b>Как использовать:</b>\n\n"
        f"1️⃣ Выберите подходящий промпт\n"
        f"2️⃣ Замените [ВСТАВЬ СЮДА ИСХОДНЫЙ ПОСТ] на ваш текст\n"
        f"3️⃣ Скопируйте в ChatGPT\n"
        f"4️⃣ Получите качественный результат!\n\n"
        f"💡 <b>Совет:</b> Для персонализированных промптов используйте /manual",
        parse_mode="HTML"
    )

@router.message(Command("ai"))
async def cmd_ai_settings(message: Message):
    """Настройки AI перефразирования (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    settings_emoji = get_emoji("tech")
    
    # Проверяем статус OpenAI API
    openai_status = "✅ Настроен" if config.OPENAI_API_KEY else "❌ Не настроен"
    
    await safe_edit_message(message,
        f"{settings_emoji} <b>Настройки AI перефразирования</b>\n\n"
        f"🤖 <b>ChatGPT API:</b> {openai_status}\n"
        # f"🎯 <b>Стиль канала:</b> {chatgpt_rewriter.channel_style['theme']}\n"
        # f"📝 <b>Тон:</b> {chatgpt_rewriter.channel_style['tone']}\n"
        # f"👥 <b>Аудитория:</b> {chatgpt_rewriter.channel_style['audience']}\n"
        # f"📏 <b>Длина постов:</b> {chatgpt_rewriter.channel_style['length']}\n\n"
        f"⚡ <b>Доступные команды:</b>\n"
        f"• /manual - ручное перефразирование с советами\n"
        f"• /chatgpt - демо автоматического перефразирования\n"
        f"• /prompts - готовые промпты для ChatGPT\n"
        f"• /ai - эти настройки\n\n"
        f"💡 <b>Автоматический режим:</b> Все новые посты автоматически перефразируются через ChatGPT API",
        parse_mode="HTML"
    )
    
    if not config.OPENAI_API_KEY:
        await message.answer(
            f"⚠️ <b>Настройка OpenAI API:</b>\n\n"
            f"1️⃣ Получите API ключ на https://platform.openai.com/\n"
            f"2️⃣ Добавьте в .env файл:\n"
            f"<code>OPENAI_API_KEY=your_api_key_here</code>\n"
            f"3️⃣ Перезапустите бота\n\n"
            f"💰 <b>Стоимость:</b> ~$0.002 за пост (очень дешево)",
            parse_mode="HTML"
        )

# Обработчики для новых найденных постов
@router.callback_query(F.data.startswith("new_post_analysis_"))
async def callback_new_post_analysis(callback: CallbackQuery):
    """Подробный анализ поста с советами по улучшению и готовым промптом"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[3])
    draft = await db.get_draft_by_id(draft_id)
    
    if not draft:
        await callback.answer("❌ Пост не найден", show_alert=True)
        return
    
    # Получаем детальный анализ
    from chatgpt_integration import chatgpt_rewriter
    suggestions = chatgpt_rewriter.get_rewrite_suggestions(draft['original_text'])
    content_type = chatgpt_rewriter._detect_content_type(draft['original_text'])
    
    type_names = {
        "news": "📰 Новость",
        "update": "🔄 Обновление", 
        "airdrop": "🎁 Airdrop/Раздача",
        "analysis": "📊 Аналитика"
    }
    
    brain_emoji = get_emoji("brain")
    analysis_text = f"{brain_emoji} <b>Детальный анализ поста</b>\n\n"
    analysis_text += f"🎯 <b>Тип контента:</b> {type_names.get(content_type, '📝 Общий')}\n"
    analysis_text += f"📏 <b>Длина:</b> {len(draft['original_text'])} символов\n"
    analysis_text += f"📅 <b>Источник:</b> {safe_html_with_emoji(draft.get('source_name', 'Неизвестно'))}\n\n"
    
    if suggestions:
        analysis_text += f"💡 <b>Что нужно улучшить:</b>\n"
        for i, (key, suggestion) in enumerate(suggestions.items(), 1):
            analysis_text += f"{i}. {suggestion}\n"
        analysis_text += "\n"
    else:
        analysis_text += f"✅ <b>Текст хорошего качества!</b>\nТребуется только стилистическая обработка.\n\n"
    
    # Рекомендации по стилю в зависимости от типа
    style_tips = {
        "airdrop": "🎁 Создайте ощущение срочности и ценности предложения",
        "news": "📰 Добавьте сенсационный заголовок и экспертный комментарий", 
        "update": "🔄 Подчеркните важность улучшений для пользователей",
        "analysis": "📊 Сделайте акцент на значимости данных для рынка"
    }
    
    tip = style_tips.get(content_type, "📝 Сделайте текст более энергичным и вовлекающим")
    analysis_text += f"🎨 <b>Совет по стилю:</b>\n{tip}\n\n"
    
    analysis_text += f"📝 <b>Исходный текст:</b>\n<i>{safe_html_with_emoji(draft['original_text'])}</i>\n\n"
    
    # Добавляем промпт для ChatGPT
    from chatgpt_integration import get_manual_rewrite_prompt
    copyable_prompt = get_manual_rewrite_prompt(draft['original_text'], content_type)
    sparkle_emoji = get_emoji("sparkle")
    analysis_text += f"{sparkle_emoji} <b>Готовый промпт для ChatGPT:</b>\n<code>{copyable_prompt}</code>\n\n"
    analysis_text += f"⚡ Используйте этот промпт для ручного перефразирования!"
    
    # Оставляем клавиатуру с кнопками
    from keyboards import get_new_post_keyboard
    await safe_edit_message(callback, analysis_text, parse_mode="HTML", reply_markup=get_new_post_keyboard(draft_id))

@router.callback_query(F.data.startswith("new_post_manual_"))
async def callback_new_post_manual(callback: CallbackQuery):
    """Ручное перефразирование с готовым промптом"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[3])
    draft = await db.get_draft_by_id(draft_id)
    
    if not draft:
        await callback.answer("❌ Пост не найден", show_alert=True)
        return
    
    # Получаем советы и анализ
    from chatgpt_integration import chatgpt_rewriter
    suggestions = chatgpt_rewriter.get_rewrite_suggestions(draft['original_text'])
    content_type = chatgpt_rewriter._detect_content_type(draft['original_text'])
    
    type_names = {
        "news": "📰 Новость",
        "update": "🔄 Обновление", 
        "airdrop": "🎁 Airdrop",
        "analysis": "📊 Аналитика"
    }
    
    # Формируем анализ
    analysis_text = f"🎯 <b>Ручное перефразирование</b>\n\n"
    analysis_text += f"📋 <b>Тип контента:</b> {type_names.get(content_type, '📝 Общий')}\n"
    analysis_text += f"📏 <b>Длина:</b> {len(draft['original_text'])} символов\n\n"
    
    if suggestions:
        analysis_text += f"💡 <b>Что нужно улучшить:</b>\n"
        for i, suggestion in enumerate(list(suggestions.values())[:4], 1):
            analysis_text += f"{i}. {suggestion}\n"
        analysis_text += "\n"
    
    analysis_text += f"📝 <b>Исходный текст:</b>\n<i>{safe_html_with_emoji(draft['original_text'])}</i>\n\n"
    
    # Добавляем готовый промпт
    from chatgpt_integration import get_manual_rewrite_prompt
    copyable_prompt = get_manual_rewrite_prompt(draft['original_text'], content_type)
    sparkle_emoji = get_emoji("sparkle")
    analysis_text += f"{sparkle_emoji} <b>Готовый промпт для ChatGPT:</b>\n\n<code>{copyable_prompt}</code>\n\n"
    analysis_text += f"📋 <b>Инструкция:</b>\n1. Скопируйте промпт выше\n2. Вставьте в ChatGPT\n3. Получите перефразированный пост"
    
    # Оставляем клавиатуру с кнопками
    from keyboards import get_new_post_keyboard
    await safe_edit_message(callback, analysis_text, parse_mode="HTML", reply_markup=get_new_post_keyboard(draft_id))

@router.callback_query(F.data.startswith("new_post_details_"))
async def callback_new_post_details(callback: CallbackQuery):
    """Подробная информация о новом посте"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[3])
    draft = await db.get_draft_by_id(draft_id)
    
    if not draft:
        await callback.answer("❌ Пост не найден", show_alert=True)
        return
    
    # Подробная информация
    details_text = f"📋 <b>Подробная информация</b>\n\n"
    details_text += f"🆔 <b>ID:</b> #{draft_id}\n"
    details_text += f"📡 <b>Источник:</b> {safe_html_with_emoji(draft.get('source_name', 'Неизвестно'))}\n"
    details_text += f"📅 <b>Дата:</b> {draft.get('source_date', 'Неизвестно')[:19]}\n"
    details_text += f"🔍 <b>Ключевые слова:</b> {safe_html_with_emoji(', '.join(draft.get('keywords_matched', [])))}\n"
    
    if draft.get('source_url'):
        details_text += f"🔗 <b>Ссылка:</b> {safe_html_with_emoji(draft['source_url'])}\n"
    
    details_text += f"\n📝 <b>Полный текст:</b>\n<i>{safe_html_with_emoji(draft['original_text'])}</i>\n\n"
    
    # Технический анализ
    from chatgpt_integration import chatgpt_rewriter
    content_type = chatgpt_rewriter._detect_content_type(draft['original_text'])
    suggestions = chatgpt_rewriter.get_rewrite_suggestions(draft['original_text'])
    
    type_names = {
        "news": "📰 Новость",
        "update": "🔄 Обновление", 
        "airdrop": "🎁 Airdrop/Раздача",
        "analysis": "📊 Аналитика"
    }
    
    details_text += f"🎯 <b>Тип контента:</b> {type_names.get(content_type, '📝 Общий')}\n"
    details_text += f"📊 <b>Символов:</b> {len(draft['original_text'])}\n"
    details_text += f"🔧 <b>Требует улучшений:</b> {len(suggestions)}\n"
    
    # Оставляем клавиатуру с кнопками
    from keyboards import get_new_post_keyboard
    await safe_edit_message(callback, details_text, parse_mode="HTML", reply_markup=get_new_post_keyboard(draft_id))

@router.callback_query(F.data.startswith("new_post_skip_"))
async def callback_new_post_skip(callback: CallbackQuery):
    """Пропустить пост"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    draft_id = int(callback.data.split("_")[3])
    
    # Обновляем статус на "skipped"
    await db.update_draft_status(draft_id, 'skipped')
    
    skip_emoji = get_emoji("cross")
    await safe_edit_message(callback,
        f"{skip_emoji} <b>Пост пропущен</b>\n\n"
        f"📊 ID #{draft_id} помечен как пропущенный.\n"
        f"Пост не будет больше предлагаться для обработки.",
        parse_mode="HTML"
    )

@router.message(Command("test_clean"))
async def cmd_test_clean(message: Message):
    """Тестирование улучшенной системы очистки текста (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Ваш проблемный пост как пример
    problematic_text = """🎁 Раздача! **🍷**** ПАШОК ТЕСТИРУЕТ НОВУЮ ОБНОВУ!** На кадрах можно заметить, как **Павел** **Дуров** после сегодняшней **обновы** заходит и сам тестирует, и так же пытается загрузить **новые** **подарки**, но это никак не выходит... 😣 __красава? __ ❤️ - харош 🤯 - подарки то когда епта ➖➖➖➖➖➖➖➖➖➖➖ **🥈**[**Купить подарки 1 **](|****❤️**[**Купить подарки 2**]( ** | ⭐️ [**Наш чат**]( | [⭐️]( - купить звёзды за рубли**](!"""
    
    clean_emoji = get_emoji("tech")
    await safe_edit_message(message,
        f"{clean_emoji} <b>Тест улучшенной системы очистки</b>\n\n"
        f"🧪 Проверяю очистку проблемного текста...",
        parse_mode="HTML"
    )
    
    # Показываем исходный текст
    await message.answer(
        f"📝 <b>ИСХОДНЫЙ текст (проблемный):</b>\n\n"
        f"<code>{problematic_text[:500]}...</code>",
        parse_mode="HTML"
    )
    
    # Очищаем текст
    # cleaned_text = chatgpt_rewriter.clean_source_text(problematic_text)
    
    await message.answer(
        f"✨ <b>ОЧИЩЕННЫЙ текст:</b>\n\n"
        f"<i>{cleaned_text}</i>\n\n"
        f"📊 <b>Результат очистки:</b>\n"
        f"• Было символов: {len(problematic_text)}\n"
        f"• Стало символов: {len(cleaned_text)}\n"
        f"• Убрано мусора: {len(problematic_text) - len(cleaned_text)} символов",
        parse_mode="HTML"
    )
    
    # Теперь тестируем ChatGPT (если настроен)
    if config.OPENAI_API_KEY:
        robot_emoji = get_emoji("brain")
        await message.answer(
            f"{robot_emoji} <b>Тест ChatGPT с очищенным текстом:</b>\n\n"
            f"🔄 Отправляю в ChatGPT...",
            parse_mode="HTML"
        )
        
        try:
            # Перефразируем через ChatGPT
            # rewritten = await chatgpt_rewriter.rewrite_with_chatgpt(problematic_text)
            
            if rewritten:
                await message.answer(
                    f"🤖 <b>Результат ChatGPT:</b>\n\n"
                    f"{rewritten}\n\n"
                    f"📊 <b>Финальная статистика:</b>\n"
                    f"• Исходный текст: {len(problematic_text)} символов\n"
                    f"• Очищенный: {len(cleaned_text)} символов\n"
                    f"• Результат ChatGPT: {len(rewritten)} символов\n\n"
                    f"✅ <b>Проверьте:</b> Нет ли битых ссылок и мусора?",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ ChatGPT не смог обработать текст")
                
        except Exception as e:
            await message.answer(f"❌ <b>Ошибка ChatGPT:</b> {str(e)}")
    else:
        await message.answer(
            f"⚠️ <b>OpenAI API не настроен</b>\n\n"
            f"Для полного теста добавьте OPENAI_API_KEY в .env файл"
        )
    
    success_emoji = get_emoji("check")
    await message.answer(
        f"{success_emoji} <b>Тест системы очистки завершен!</b>\n\n"
        f"🔧 <b>Улучшения в новой системе:</b>\n"
        f"• Убирает Markdown форматирование (**текст**)\n"
        f"• Удаляет все битые ссылки [text]()\n"
        f"• Очищает спецсимволы ➖ и рамки\n"
        f"• Убирает упоминания и хештеги\n"
        f"• Проверяет результат ChatGPT\n"
        f"• Повторная очистка если нужно\n\n"
        f"💡 Теперь посты будут чистыми и читаемыми!",
        parse_mode="HTML"
    )

@router.message(Command("prompt"))
async def cmd_quick_prompt(message: Message, state: FSMContext):
    """Быстрое получение промпта для любого текста (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    sparkle_emoji = get_emoji("sparkle")
    await safe_edit_message(message,
        f"{sparkle_emoji} <b>Быстрый генератор промптов</b>\n\n"
        f"📝 Отправьте любой текст, и я дам:\n"
        f"• Анализ что нужно улучшить\n"
        f"• Готовый промпт для ChatGPT\n"
        f"• Советы по стилистике\n\n"
        f"💡 Просто вставьте исходный пост:",
        parse_mode="HTML"
    )
    
    await state.set_state(ContentModerationStates.waiting_for_manual_rewrite)

@router.message(Command("guide"))
async def cmd_manual_guide(message: Message):
    """Руководство по ручному режиму работы с постами (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    book_emoji = get_emoji("brain")
    await safe_edit_message(message,
        f"{book_emoji} <b>Руководство по ручному режиму</b>\n\n"
        f"🤖 <b>Как работает бот:</b>\n"
        f"1️⃣ Мониторит {len(config.TG_CHANNELS)} Telegram каналов\n"
        f"2️⃣ Проверяет {len(config.RSS_SOURCES)} RSS источников\n"
        f"3️⃣ Находит посты по {len(config.KEYWORDS)} ключевым словам\n"
        f"4️⃣ <b>Сразу присылает вам</b> с анализом и кнопками\n\n"
        
        f"📱 <b>Когда находит пост, вы получаете:</b>\n"
        f"• Исходный текст\n"
        f"• Тип контента (новость/обновление/airdrop)\n"
        f"• Советы что улучшить\n"
        f"• Кнопки для действий\n\n"
        
        f"🎯 <b>Ваши действия:</b>\n"
        f"📝 <b>\"Ручной промпт\"</b> → готовый промпт для ChatGPT\n"
        f"📋 <b>\"Подробнее\"</b> → детальный анализ\n"
        f"❌ <b>\"Пропустить\"</b> → игнорировать пост\n\n"
        
        f"⚡ <b>Быстрые команды:</b>\n"
        f"/prompt - получить промпт для любого текста\n"
        f"/manual - анализ + промпт\n"
        f"/prompts - библиотека готовых промптов\n\n"
        
        f"💡 <b>Workflow:</b>\n"
        f"Пост найден → Анализ → Промпт → ChatGPT → Готово!",
        parse_mode="HTML"
    )

@router.message(Command("monitor"))
async def cmd_start_monitoring(message: Message):
    """Запуск мониторинга для проверки системы уведомлений (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    from scheduler import scheduler
    
    monitor_emoji = get_emoji("tech")
    await safe_edit_message(message,
        f"{monitor_emoji} <b>Запуск мониторинга источников</b>\n\n"
        f"🔄 Проверяю источники контента...",
        parse_mode="HTML"
    )
    
    try:
        # Запускаем ручной мониторинг
        result = await scheduler.run_manual_monitoring()
        
        if result:
            success_emoji = get_emoji("check")
            await message.answer(
                f"{success_emoji} <b>Мониторинг завершен!</b>\n\n"
                f"📊 <b>Источники проверены:</b>\n"
                f"• {len(config.TG_CHANNELS)} Telegram каналов\n"
                f"• {len(config.RSS_SOURCES)} RSS источников\n"
                f"• {len(config.KEYWORDS)} ключевых слов\n\n"
                f"💌 <b>Если найдены новые посты</b> - вы получите уведомления с кнопками для анализа и получения промптов!\n\n"
                f"⏰ Автоматический мониторинг: каждые {config.MONITORING_INTERVAL_MINUTES} минут",
                parse_mode="HTML"
            )
        else:
            await message.answer("⚠️ Мониторинг завершен с ошибками. Проверьте логи.")
            
    except Exception as e:
        await message.answer(f"❌ <b>Ошибка мониторинга:</b> {str(e)}")

@router.message(Command("demo_post"))
async def cmd_demo_post_notification(message: Message):
    """Демонстрация уведомления о новом найденном посте (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Создаем демо черновик
    demo_text = "TON блокчейн объявляет о новом партнерстве с крупной биржей. Ожидается значительный рост объемов торгов и увеличение ликвидности экосистемы."
    
    demo_draft_id = await db.add_content_draft(
        source_type='demo',
        source_name='Демо источник - тест уведомлений',
        original_text=demo_text,
        source_url='https://example.com/demo-partnership',
        source_date=datetime.now(timezone.utc).isoformat(),
        keywords_matched=['TON', 'партнерство', 'биржа', 'ликвидность']
    )
    
    # Имитируем уведомление о новом посте
    from content_monitor import content_monitor
    draft = await db.get_draft_by_id(demo_draft_id)
    
    if draft:
        await content_monitor.send_new_post_to_admin(message.bot, config.ADMIN_ID, draft)
        
        demo_emoji = get_emoji("gift")
        await safe_edit_message(message,
            f"{demo_emoji} <b>Демо уведомление отправлено!</b>\n\n"
            f"📬 Проверьте сообщение выше - так выглядят уведомления о новых найденных постах.\n\n"
            f"🎯 <b>Попробуйте кнопки:</b>\n"
            f"📝 \"Получить промпт\" - готовый промпт для ChatGPT\n"
            f"💡 \"Анализ + советы\" - детальный анализ\n"
            f"📋 \"Подробнее\" - техническая информация\n\n"
            f"💡 ID демо поста: #{demo_draft_id}",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка создания демо поста")

@router.message(lambda m: m.text and not m.text.startswith("/"))
async def handle_free_text(message: Message):
    """Автоматическое перефразирование любого текста через ChatGPT (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    if not config.OPENAI_API_KEY:
        await message.answer(
            "⚠️ <b>OpenAI API ключ не настроен</b>\n\n"
            "Добавьте OPENAI_API_KEY в .env файл для использования ChatGPT.",
            parse_mode="HTML"
        )
        return
    
    original_text = message.text
    robot_emoji = get_emoji("tech")
    await message.answer(f"{robot_emoji} <b>Перефразирую через ChatGPT...</b>", parse_mode="HTML")
    
    try:
        rewritten = await rewrite_post_with_ai(original_text)
        if rewritten:
            sparkle_emoji = get_emoji("sparkle")
            await message.answer(
                f"{sparkle_emoji} <b>Готовый текст:</b>\n\n"
                f"<i>{safe_html_with_emoji(rewritten)}</i>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "⚠️ <b>Не удалось получить ответ от ChatGPT</b>\n\n"
                "Попробуйте еще раз или проверьте настройки API.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка ChatGPT: {e}")
        await message.answer(
            f"❌ <b>Ошибка при обращении к ChatGPT:</b> {e}",
            parse_mode="HTML"
        )

@router.message(Command("add_rss"))
async def cmd_add_rss(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав доступа.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Укажите ссылку на RSS: /add_rss https://example.com/feed.xml")
        return
    url = args[1].strip()
    from database import db
    await db.add_source("rss", url)
    await message.answer(f"✅ RSS источник добавлен: {url}")

@router.message(Command("remove_rss"))
async def cmd_remove_rss(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав доступа.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Укажите ссылку на RSS: /remove_rss https://example.com/feed.xml")
        return
    url = args[1].strip()
    from database import db
    await db.remove_source("rss", url)
    await message.answer(f"🗑 RSS источник удалён: {url}")

@router.message(Command("add_tg"))
async def cmd_add_tg(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав доступа.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Укажите username канала: /add_tg @channel")
        return
    channel = args[1].strip()
    from database import db
    await db.add_source("tg", channel)
    await message.answer(f"✅ TG канал добавлен: {channel}")

@router.message(Command("remove_tg"))
async def cmd_remove_tg(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав доступа.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Укажите username канала: /remove_tg @channel")
        return
    channel = args[1].strip()
    from database import db
    await db.remove_source("tg", channel)
    await message.answer(f"🗑 TG канал удалён: {channel}")

@router.message(Command("list_sources"))
async def cmd_list_sources(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав доступа.")
        return
    from database import db
    rss = await db.get_sources("rss")
    tg = await db.get_sources("tg")
    text = "<b>🔗 Активные RSS источники:</b>\n" + ("\n".join([s['source_url'] for s in rss]) or "Нет")
    text += "\n\n<b>💬 Активные TG каналы:</b>\n" + ("\n".join([s['source_url'] for s in tg]) or "Нет")
    await message.answer(text, parse_mode="HTML")

@router.message(Command("stats_source"))
async def cmd_source_stats(message: Message):
    """Показывает статистику по конкретному источнику"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав доступа.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "⚠️ Укажите источник:\n"
            "/stats_source @channel - для Telegram канала\n"
            "/stats_source https://example.com/rss - для RSS"
        )
        return

    source = args[1].strip()
    source_type = 'tg' if source.startswith('@') else 'rss'
    
    stats = await db.get_channel_stats(source_type, source)
    if not stats:
        await message.answer(f"❌ Статистика для {source} не найдена")
        return
    
    stats = stats[0]  # Берем первую запись
    
    # Форматируем статистику
    text = f"📊 <b>Статистика источника {source}</b>\n\n"
    
    text += f"📈 <b>Общая информация:</b>\n"
    text += f"• Всего постов: {stats['total_posts']}\n"
    text += f"• Релевантных постов: {stats['matched_posts']}\n"
    text += f"• Среднее в день: {stats['avg_posts_per_day']}\n"
    
    if stats['last_post_date']:
        text += f"• Последний пост: {stats['last_post_date'][:16]}\n"
    
    text += f"\n🔍 <b>Топ ключевых слов:</b>\n"
    for kw, count in stats['most_used_keywords'].items():
        text += f"• {kw}: {count} раз\n"
    
    text += f"\n⏰ <b>Активность по часам:</b>\n"
    hours = stats['activity_hours']
    max_posts = max(hours.values()) if hours else 1
    for hour in sorted(hours.keys(), key=int):
        count = hours[hour]
        bars = "█" * int((count / max_posts) * 10)
        text += f"{hour.zfill(2)}:00 {bars} ({count})\n"
    
    text += f"\n🔄 Обновлено: {stats['updated_at'][:16]}"
    
    await message.answer(text, parse_mode="HTML")

@router.message(Command("stats_all"))
async def cmd_all_stats(message: Message):
    """Показывает общую статистику по всем источникам"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав доступа.")
        return
    
    all_stats = await db.get_channel_stats()
    if not all_stats:
        await message.answer("❌ Статистика пока не собрана")
        return
    
    # Группируем по типу источника
    tg_stats = [s for s in all_stats if s['source_type'] == 'tg']
    rss_stats = [s for s in all_stats if s['source_type'] == 'rss']
    
    text = "📊 <b>Общая статистика источников</b>\n\n"
    
    # Telegram каналы
    text += "💬 <b>Telegram каналы:</b>\n"
    total_tg_posts = sum(s['total_posts'] for s in tg_stats)
    total_tg_matched = sum(s['matched_posts'] for s in tg_stats)
    text += f"• Каналов: {len(tg_stats)}\n"
    text += f"• Всего постов: {total_tg_posts}\n"
    text += f"• Релевантных: {total_tg_matched}\n"
    if tg_stats:
        text += "\nТоп каналов по активности:\n"
        for stat in sorted(tg_stats, key=lambda x: x['total_posts'], reverse=True)[:5]:
            text += f"• {stat['source_url']}: {stat['total_posts']} постов\n"
    
    # RSS ленты
    text += "\n📰 <b>RSS источники:</b>\n"
    total_rss_posts = sum(s['total_posts'] for s in rss_stats)
    total_rss_matched = sum(s['matched_posts'] for s in rss_stats)
    text += f"• Источников: {len(rss_stats)}\n"
    text += f"• Всего записей: {total_rss_posts}\n"
    text += f"• Релевантных: {total_rss_matched}\n"
    if rss_stats:
        text += "\nТоп RSS по активности:\n"
        for stat in sorted(rss_stats, key=lambda x: x['total_posts'], reverse=True)[:5]:
            text += f"• {stat['source_url']}: {stat['total_posts']} записей\n"
    
    # Общая статистика
    text += f"\n📈 <b>Итого:</b>\n"
    text += f"• Источников: {len(all_stats)}\n"
    text += f"• Всего постов: {total_tg_posts + total_rss_posts}\n"
    text += f"• Релевантных: {total_tg_matched + total_rss_matched}\n"
    
    await message.answer(text, parse_mode="HTML")

@router.message(Command("reset_checks"))
async def cmd_reset_checks(message: Message):
    """Сбрасывает время проверки и ID сообщений для всех источников"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        from content_monitor import content_monitor
        
        status_text = "🔄 <b>Сброс проверок</b>\n\n"
        
        # Сбрасываем время проверки для всех источников
        for channel in config.TG_CHANNELS:
            await db.set_setting(f"last_check_tg_{channel}", 
                               (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat())
            # Сбрасываем ID сообщений для Telegram
            await db.set_setting(f"last_message_id_tg_{channel}", "")
        
        for rss_url in config.RSS_SOURCES:
            await db.set_setting(f"last_check_rss_{rss_url}", 
                               (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat())
        
        status_text += f"\n✅ <b>Все проверки сброшены!</b>\n\n"
        status_text += "Теперь бот будет проверять:\n"
        status_text += "• Telegram: последние 10 сообщений (при первой проверке)\n"
        status_text += "• RSS: последние 48 часов\n\n"
        status_text += "Используйте /force_monitor для запуска проверки"
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка сброса проверок: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("check_times"))
async def cmd_check_times(message: Message):
    """Показывает время последней проверки и ID сообщений"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        from content_monitor import content_monitor
        
        status_text = "⏰ <b>Статус проверок</b>\n\n"
        
        # Проверяем несколько каналов
        test_channels = ['@durov', '@telegram', '@toncoin']
        status_text += "📱 <b>Telegram каналы:</b>\n"
        
        for channel in test_channels:
            # Время последней проверки
            last_check = await content_monitor._get_last_check_time(f"tg_{channel}")
            last_check_str = last_check.strftime('%d.%m %H:%M') if last_check else "Нет"
            
            # ID последнего сообщения
            last_id = await content_monitor._get_last_message_id(f"tg_{channel}")
            last_id_str = str(last_id) if last_id else "Нет"
            
            status_text += f"• {channel}:\n"
            status_text += f"  ⏰ Время: {last_check_str}\n"
            status_text += f"  🆔 ID: {last_id_str}\n"
        
        # Проверяем RSS
        if config.RSS_SOURCES:
            status_text += f"\n📡 <b>RSS источники:</b>\n"
            for rss_url in config.RSS_SOURCES[:3]:  # Показываем первые 3
                last_check = await content_monitor._get_last_check_time(f"rss_{rss_url}")
                last_check_str = last_check.strftime('%d.%m %H:%M') if last_check else "Нет"
                status_text += f"• {rss_url}: {last_check_str}\n"
        
        status_text += f"\n💡 <b>Как работает:</b>\n"
        status_text += "• Telegram: отслеживание по ID сообщений\n"
        status_text += "• RSS: отслеживание по времени\n"
        status_text += "• При первой проверке: последние 10 сообщений\n"
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка проверки времени: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("test_notification"))
async def cmd_test_notification(message: Message):
    """Тестирует отправку уведомления о новом посте"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        # Создаем тестовый пост
        test_draft_id = await db.add_content_draft(
            source_type='test',
            source_name='Тестовый источник',
            original_text='Это тестовое уведомление для проверки работы бота. Содержит ключевые слова: Telegram, TON, NFT.',
            source_url='https://example.com/test',
            source_date=datetime.now(timezone.utc).isoformat(),
            keywords_matched=['Telegram', 'TON', 'NFT']
        )
        
        # Получаем созданный черновик
        draft = await db.get_draft_by_id(test_draft_id)
        
        if draft:
            # Имитируем уведомление
            from content_monitor import content_monitor
            await content_monitor.send_new_post_to_admin(message.bot, message.from_user.id, draft)
            
            await message.answer(
                f"✅ <b>Тестовое уведомление отправлено!</b>\n\n"
                f"📋 ID тестового поста: #{test_draft_id}\n"
                f"🔍 Проверьте сообщение выше - должно появиться уведомление с кнопками.",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка создания тестового поста")
            
    except Exception as e:
        logger.error(f"Ошибка тестирования уведомления: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("bot_status"))
async def cmd_bot_status(message: Message):
    """Показывает статус бота и content_monitor"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        from content_monitor import content_monitor
        
        status_text = "🤖 <b>Статус бота и мониторинга</b>\n\n"
        
        # Статус бота
        bot_info = await message.bot.get_me()
        status_text += f"📱 <b>Бот:</b> @{bot_info.username}\n"
        status_text += f"🆔 <b>ID:</b> {bot_info.id}\n"
        status_text += f"📝 <b>Имя:</b> {bot_info.first_name}\n\n"
        
        # Статус content_monitor
        status_text += f"🔍 <b>Content Monitor:</b>\n"
        status_text += f"• Бот установлен: {'✅' if content_monitor.bot_instance else '❌'}\n"
        status_text += f"• Telethon клиент: {'✅' if content_monitor.tg_client else '❌'}\n"
        status_text += f"• HTTP сессия: {'✅' if content_monitor.session else '❌'}\n"
        status_text += f"• Ключевые слова: {len(content_monitor.keywords)}\n\n"
        
        # Статус базы данных
        try:
            drafts_count = await db.get_content_drafts_count()
            status_text += f"💾 <b>База данных:</b>\n"
            status_text += f"• Черновиков: {drafts_count}\n"
        except Exception as e:
            status_text += f"❌ Ошибка БД: {e}\n"
        
        # Проверка уведомлений
        status_text += f"\n🔔 <b>Тест уведомлений:</b>\n"
        if content_monitor.bot_instance:
            status_text += "• Бот доступен для уведомлений ✅\n"
            status_text += "• Используйте /test_notification для проверки\n"
        else:
            status_text += "• Бот НЕ доступен для уведомлений ❌\n"
            status_text += "• Проверьте инициализацию в main.py\n"
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("force_monitor"))
async def cmd_force_monitor(message: Message):
    """Принудительный запуск мониторинга с подробной диагностикой"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        from content_monitor import content_monitor
        
        # Проверяем статус content_monitor
        status_text = "🔍 <b>Принудительный мониторинг</b>\n\n"
        
        # Проверяем бота
        if content_monitor.bot_instance:
            status_text += "✅ Бот доступен\n"
        else:
            status_text += "❌ Бот НЕ доступен!\n"
            await message.answer(status_text, parse_mode="HTML")
            return
        
        # Проверяем Telethon
        if content_monitor.tg_client:
            status_text += "✅ Telethon клиент доступен\n"
        else:
            status_text += "❌ Telethon клиент НЕ доступен\n"
        
        # Проверяем ключевые слова
        keywords_count = len(content_monitor.keywords)
        status_text += f"✅ Ключевых слов: {keywords_count}\n"
        
        # Проверяем каналы
        channels_count = len(config.TG_CHANNELS)
        status_text += f"✅ Telegram каналов: {channels_count}\n"
        
        # Проверяем RSS
        rss_count = len(config.RSS_SOURCES)
        status_text += f"✅ RSS источников: {rss_count}\n\n"
        
        await message.answer(status_text, parse_mode="HTML")
        
        # Запускаем мониторинг
        await message.answer("🔄 <b>Запускаю мониторинг...</b>", parse_mode="HTML")
        
        # Сбрасываем время проверки для всех источников
        for channel in config.TG_CHANNELS:
            await db.set_setting(f"last_check_tg_{channel}", 
                               (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat())
        
        for rss_url in config.RSS_SOURCES:
            await db.set_setting(f"last_check_rss_{rss_url}", 
                               (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat())
        
        await message.answer("⏰ <b>Время проверки и ID сообщений сброшены</b>", parse_mode="HTML")
        
        # Запускаем мониторинг
        await content_monitor.run_monitoring_cycle()
        
        await message.answer("✅ <b>Мониторинг завершен!</b>\n\nПроверьте логи для подробной информации.", parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка принудительного мониторинга: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("check_channel"))
async def cmd_check_channel(message: Message):
    """Проверяет конкретный канал на наличие новых постов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Укажите канал: /check_channel @channel_name")
        return
    
    channel = args[1].strip()
    if not channel.startswith('@'):
        channel = '@' + channel
    
    try:
        from content_monitor import content_monitor
        
        if not content_monitor.tg_client:
            await message.answer("❌ Telethon клиент не инициализирован")
            return
        
        await message.answer(f"🔍 <b>Проверяю канал {channel}...</b>", parse_mode="HTML")
        
        # Получаем ID последнего сообщения
        last_message_id = await content_monitor._get_last_message_id(f"tg_{channel}")
        if not last_message_id:
            last_message_id = "Нет (первая проверка)"
        
        await message.answer(f"🆔 <b>ID последнего сообщения:</b> {last_message_id}", parse_mode="HTML")
        
        # Получаем сообщения
        entity = await content_monitor.tg_client.get_entity(channel)
        messages = await content_monitor.tg_client.get_messages(
            entity, 
            limit=20
        )
        
        await message.answer(f"📊 <b>Найдено {len(messages)} сообщений</b>", parse_mode="HTML")
        
        new_messages = 0
        matched_messages = 0
        
        # Сортируем по ID (новые первыми)
        messages.sort(key=lambda m: m.id, reverse=True)
        
        for message in messages:
            if not message.text:
                continue
            
            # Проверяем, новое ли это сообщение
            if last_message_id != "Нет (первая проверка)" and message.id <= int(last_message_id):
                continue
            
            new_messages += 1
            
            # Проверяем ключевые слова
            matched_keywords = content_monitor.check_keywords(message.text)
            if matched_keywords:
                matched_messages += 1
                await message.answer(
                    f"🎯 <b>Найден релевантный пост:</b>\n\n"
                    f"🆔 ID: {message.id}\n"
                    f"📅 {message.date}\n"
                    f"🔍 Ключевые слова: {', '.join(matched_keywords)}\n"
                    f"📝 {message.text[:200]}...",
                    parse_mode="HTML"
                )
        
        await message.answer(
            f"📈 <b>Результат проверки канала {channel}:</b>\n\n"
            f"• Новых сообщений: {new_messages}\n"
            f"• Релевантных постов: {matched_messages}\n"
            f"• Последний ID: {last_message_id}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка проверки канала {channel}: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("time_debug"))
async def cmd_time_debug(message: Message):
    """Диагностика проблем с временем"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        from datetime import timezone
        from content_monitor import content_monitor
        
        # Текущее время в разных часовых поясах
        utc_now = datetime.now(timezone.utc)
        local_now = datetime.now()  # Локальное время сервера
        
        status_text = "🕐 <b>Диагностика времени</b>\n\n"
        status_text += f"🌍 <b>UTC время:</b> {utc_now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        status_text += f"🏠 <b>Локальное время сервера:</b> {local_now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        status_text += f"🇺🇿 <b>Узбекское время (UTC+5):</b> {(utc_now + timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Проверяем время последней проверки для нескольких каналов
        test_channels = ['@durov', '@telegram', '@toncoin']
        status_text += "📊 <b>Время последней проверки каналов:</b>\n"
        
        for channel in test_channels:
            last_check = await content_monitor._get_last_check_time(f"tg_{channel}")
            if last_check:
                status_text += f"• {channel}: {last_check.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            else:
                status_text += f"• {channel}: Нет записи\n"
        
        status_text += f"\n🔍 <b>Проблема:</b>\n"
        status_text += "Бот использует UTC время, а Telegram сообщения тоже в UTC.\n"
        status_text += "Если время последней проверки новее, чем время сообщений,\n"
        status_text += "бот будет пропускать новые посты.\n\n"
        
        status_text += "💡 <b>Решение:</b>\n"
        status_text += "Используйте /reset_checks для сброса времени\n"
        status_text += "или /force_monitor для принудительной проверки"
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка диагностики времени: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("reset_ids"))
async def cmd_reset_ids(message: Message):
    """Сбрасывает только ID сообщений для Telegram каналов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    try:
        status_text = "🔄 <b>Сброс ID сообщений</b>\n\n"
        
        # Сбрасываем только ID сообщений для Telegram каналов
        for channel in config.TG_CHANNELS:
            await db.set_setting(f"last_message_id_tg_{channel}", "")
            status_text += f"✅ {channel}: ID сброшен\n"
        
        status_text += f"\n✅ <b>ID сообщений сброшены!</b>\n\n"
        status_text += "Теперь при следующей проверке бот будет:\n"
        status_text += "• Обрабатывать только последние 10 сообщений\n"
        status_text += "• Не трогать старые посты\n"
        status_text += "• Начать отслеживание с текущего момента\n\n"
        status_text += "Используйте /force_monitor для запуска проверки"
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка сброса ID: {e}")
        await message.answer(f"❌ Ошибка: {e}")