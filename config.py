import os
import logging

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# API URLs - переходим на Bybit
BYBIT_API_URL = 'https://api.bybit.com'
COINGECKO_API_URL = 'https://api.coingecko.com/api/v3'
ALTERNATIVE_API_URL = 'https://api.alternative.me'

# Логируем статус конфигурации (без показа самого токена)
if TELEGRAM_TOKEN:
    logger.info("TELEGRAM_TOKEN loaded successfully")
else:
    logger.warning("TELEGRAM_TOKEN not found in environment variables")
