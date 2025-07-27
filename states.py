from aiogram.fsm.state import State, StatesGroup
import os

# Очищаем переменные окружения от прокси на уровне модуля
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]

class ContentModerationStates(StatesGroup):
    """Состояния для модерации контента"""
    waiting_for_approval = State()
    editing_content = State()
    waiting_for_edit = State()
    waiting_for_manual_rewrite = State()

class AdminStates(StatesGroup):
    """Состояния для админских функций"""
    adding_keywords = State()
    managing_sources = State()
    setting_channel = State()
    editing_sources = State() 