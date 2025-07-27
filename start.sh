#!/bin/bash

# Очищаем переменные окружения от прокси
unset HTTP_PROXY
unset HTTPS_PROXY
unset ALL_PROXY
unset NO_PROXY
unset http_proxy
unset https_proxy
unset all_proxy
unset no_proxy

# Устанавливаем переменные окружения для Python
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Обновляем pip и устанавливаем зависимости
pip install --upgrade pip
pip install --upgrade httpx openai

# Запускаем приложение
python main.py 