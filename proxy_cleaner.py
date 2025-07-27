"""
Модуль для централизованной очистки переменных окружения от прокси
"""

import os
import logging

logger = logging.getLogger(__name__)

def clear_proxy_variables():
    """Очищает все переменные окружения, связанные с прокси"""
    proxy_vars = [
        'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
        'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy',
        'PROXY_URL', 'proxy_url',
        'TELEGRAM_PROXY', 'telegram_proxy',
        'OPENAI_PROXY', 'openai_proxy'
    ]
    
    cleared_vars = []
    for var in proxy_vars:
        if var in os.environ:
            del os.environ[var]
            cleared_vars.append(var)
    
    if cleared_vars:
        logger.info(f"Очищены переменные окружения: {', '.join(cleared_vars)}")
    
    return cleared_vars

def ensure_no_proxy_environment():
    """Гарантирует отсутствие прокси в окружении"""
    clear_proxy_variables()
    
    # Дополнительно устанавливаем пустые значения для ключевых переменных
    os.environ['HTTP_PROXY'] = ''
    os.environ['HTTPS_PROXY'] = ''
    os.environ['ALL_PROXY'] = ''
    os.environ['NO_PROXY'] = ''
    
    logger.info("Окружение очищено от прокси")

# Автоматически очищаем при импорте модуля
clear_proxy_variables() 