from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_moderation_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для модерации постов"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{post_id}"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{post_id}")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_{post_id}")
    )
    
    return builder.as_markup()

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Админская клавиатура"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📋 Черновики контента", callback_data="view_drafts"),
        InlineKeyboardButton(text="🔄 Запустить мониторинг", callback_data="manual_monitoring")
    )
    builder.row(
        InlineKeyboardButton(text="📝 Ключевые слова", callback_data="add_keywords"),
        InlineKeyboardButton(text="📡 Источники", callback_data="manage_sources")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки канала", callback_data="channel_settings"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats")
    )
    
    return builder.as_markup()

def get_drafts_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура для навигации по черновикам"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"drafts_page_{page-1}" if page > 0 else "drafts_page_0"),
        InlineKeyboardButton(text="▶️ Далее", callback_data=f"drafts_page_{page+1}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_admin")
    )
    
    return builder.as_markup()

def get_draft_action_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий для черновика"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✍️ Переписать", callback_data=f"rewrite_draft_{draft_id}"),
        InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_draft_{draft_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 К списку", callback_data="view_drafts")
    )
    
    return builder.as_markup()

def get_edit_confirmation_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения после редактирования"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Сохранить", callback_data=f"save_edit_{post_id}"),
        InlineKeyboardButton(text="↩️ Отмена", callback_data=f"cancel_edit_{post_id}")
    )
    
    return builder.as_markup()

def get_digest_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для поста в дайджесте"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📄 Подробнее", callback_data=f"digest_detail_{draft_id}"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"digest_edit_{draft_id}")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Удалить", callback_data=f"digest_delete_{draft_id}"),
        InlineKeyboardButton(text="✅ В канал", callback_data=f"digest_publish_{draft_id}")
    )
    
    return builder.as_markup()

def get_digest_navigation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура навигации для дайджеста"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить дайджест", callback_data="refresh_digest"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="digest_settings")
    )
    
    return builder.as_markup() 

def get_new_post_keyboard(draft_id: int):
    """Клавиатура для новых найденных постов"""
    builder = InlineKeyboardBuilder()
    
    # Первый ряд - действия с постом
    builder.add(InlineKeyboardButton(
        text="📝 Получить промпт",
        callback_data=f"new_post_manual_{draft_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="💡 Анализ + советы",
        callback_data=f"new_post_analysis_{draft_id}"
    ))
    
    # Второй ряд - дополнительные действия
    builder.add(InlineKeyboardButton(
        text="📋 Подробнее",
        callback_data=f"new_post_details_{draft_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Пропустить",
        callback_data=f"new_post_skip_{draft_id}"
    ))
    
    builder.adjust(2, 2)
    return builder.as_markup() 