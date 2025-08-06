import requests
import asyncio
import random
import logging
from config import BYBIT_API_URL, COINGECKO_API_URL, ALTERNATIVE_API_URL
from utils import calculate_risk_reward, format_signal
from datetime import datetime, timedelta
import time

# Настраиваем логгер
logger = logging.getLogger(__name__)

# Улучшенные заголовки для обхода блокировки
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin'
}

async def sleep_random():
    """Случайная задержка от 0.5 до 1 секунды"""
    await asyncio.sleep(random.uniform(0.5, 1.0))

def make_request_with_retry(url, params=None, max_retries=3):
    """Делает запрос с повторными попытками"""
    
    for attempt in range(max_retries):
        try:
            # Добавляем случайную задержку между запросами
            time.sleep(random.uniform(0.3, 0.8))
            
            response = requests.get(
                url, 
                params=params, 
                headers=HEADERS, 
                timeout=15
            )
            
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                logger.warning(f"Rate limit hit, waiting longer...")
                time.sleep(random.uniform(2, 4))
                continue
            else:
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1, 2))
    
    return None

def validate_ticker(ticker):
    """Проверяет, существует ли торговая пара на Bybit."""
    try:
        url = f"{BYBIT_API_URL}/v5/market/instruments-info"
        params = {
            'category': 'spot',
            'symbol': f"{ticker}USDT"
        }
        
        response = make_request_with_retry(url, params)
        if response is None:
            logger.error(f"Failed to validate ticker {ticker} after all retries")
            return False
            
        data = response.json()
        return data.get('retCode') == 0 and len(data.get('result', {}).get('list', [])) > 0
    except Exception as e:
        logger.error(f"Error validating ticker {ticker}: {e}")
        return False

def get_klines(symbol, interval, limit=200):
    """Получает исторические данные с Bybit API"""
    try:
        # Преобразуем интервалы в формат Bybit
        bybit_intervals = {
            '1h': '60',
            '4h': '240', 
            '1d': 'D'
        }
        
        if interval not in bybit_intervals:
            logger.error(f"Unsupported interval: {interval}")
            return None
            
        url = f"{BYBIT_API_URL}/v5/market/kline"
        params = {
            'category': 'spot',
            'symbol': symbol,
            'interval': bybit_intervals[interval],
            'limit': limit
        }
        
        response = make_request_with_retry(url, params)
        if response is None:
            logger.error(f"Failed to get klines for {symbol} after all retries")
            return None
            
        data = response.json()
        if data.get('retCode') != 0:
            logger.error(f"Bybit API error for {symbol}: {data.get('retMsg')}")
            return None
            
        # Преобразуем формат данных Bybit в формат Binance для совместимости
        klines = data.get('result', {}).get('list', [])
        
        # Bybit возвращает данные в обратном порядке, исправляем это
        klines.reverse()
        
        # Преобразуем формат: Bybit [timestamp, open, high, low, close, volume, turnover]
        # в формат Binance [timestamp, open, high, low, close, volume, ...]
        converted_klines = []
        for kline in klines:
            converted_klines.append([
                int(kline[0]),  # timestamp
                kline[1],       # open
                kline[2],       # high
                kline[3],       # low
                kline[4],       # close
                kline[5],       # volume
                0,              # close_time (не используется)
                0,              # quote_asset_volume (не используется)
                0,              # number_of_trades (не используется)
                0,              # taker_buy_base_asset_volume (не используется)
                0,              # taker_buy_quote_asset_volume (не используется)
                0               # ignore (не используется)
            ])
        
        return converted_klines
    except Exception as e:
        logger.error(f"Error getting klines for {symbol}: {e}")
        return None

def get_top_pairs():
    """Получает топ торговые пары с Bybit"""
    try:
        url = f"{BYBIT_API_URL}/v5/market/tickers"
        params = {'category': 'spot'}
        
        response = make_request_with_retry(url, params)
        if response is None:
            logger.error("Failed to get top pairs after all retries, using fallback")
            return get_fallback_pairs()
            
        data = response.json()
        if data.get('retCode') != 0:
            logger.error(f"Bybit API error: {data.get('retMsg')}")
            return get_fallback_pairs()
            
        # Фильтруем только USDT пары и преобразуем в формат Binance
        pairs = []
        for item in data.get('result', {}).get('list', []):
            if item['symbol'].endswith('USDT'):
                pairs.append({
                    'symbol': item['symbol'],
                    'volume': item['volume24h'],
                    'lastPrice': item['lastPrice']
                })
        
        # Сортируем по объему торгов
        sorted_pairs = sorted(pairs, key=lambda x: float(x['volume']) * float(x['lastPrice']), reverse=True)[:50]
        logger.info(f"Retrieved {len(sorted_pairs)} top pairs from Bybit")
        return sorted_pairs
    except Exception as e:
        logger.error(f"Error getting top pairs: {e}")
        return get_fallback_pairs()

def get_fallback_pairs():
    """Возвращает популярные пары как fallback"""
    fallback_pairs = [
        {'symbol': 'BTCUSDT', 'volume': '1000000', 'lastPrice': '50000'},
        {'symbol': 'ETHUSDT', 'volume': '800000', 'lastPrice': '3000'},
        {'symbol': 'BNBUSDT', 'volume': '600000', 'lastPrice': '400'},
        {'symbol': 'ADAUSDT', 'volume': '500000', 'lastPrice': '0.5'},
        {'symbol': 'SOLUSDT', 'volume': '400000', 'lastPrice': '100'},
        {'symbol': 'XRPUSDT', 'volume': '350000', 'lastPrice': '0.6'},
        {'symbol': 'DOTUSDT', 'volume': '300000', 'lastPrice': '7'},
        {'symbol': 'DOGEUSDT', 'volume': '250000', 'lastPrice': '0.08'},
        {'symbol': 'AVAXUSDT', 'volume': '200000', 'lastPrice': '25'},
        {'symbol': 'MATICUSDT', 'volume': '180000', 'lastPrice': '0.8'},
        {'symbol': 'LINKUSDT', 'volume': '170000', 'lastPrice': '12'},
        {'symbol': 'UNIUSDT', 'volume': '160000', 'lastPrice': '8'},
        {'symbol': 'LTCUSDT', 'volume': '150000', 'lastPrice': '90'},
        {'symbol': 'BCHUSDT', 'volume': '140000', 'lastPrice': '250'},
        {'symbol': 'XLMUSDT', 'volume': '130000', 'lastPrice': '0.12'}
    ]
    logger.info("Using extended fallback pairs due to API error")
    return fallback_pairs

def calculate_sma(data, period):
    if not data or len(data) < period:
        return None
    closes = [float(candle[4]) for candle in data]
    return sum(closes[-period:]) / period

def calculate_rsi(data, period=14):
    if not data or len(data) < period:
        return None
    closes = [float(candle[4]) for candle in data]
    gains = losses = 0
    for i in range(1, period):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    return 100 - (100 / (1 + rs))

def get_support_resistance_levels(data_4h, data_1h):
    """Улучшенный расчет уровней поддержки и сопротивления"""
    if not data_4h or not data_1h:
        return None, None

    # Берем больше данных для более точного определения уровней
    recent_4h = data_4h[-30:]  # Последние 30 свечей 4h
    recent_1h = data_1h[-50:]  # Последние 50 свечей 1h

    # Уровни с 4h таймфрейма (более значимые)
    lows_4h = [float(candle[3]) for candle in recent_4h]
    highs_4h = [float(candle[2]) for candle in recent_4h]

    # Уровни с 1h таймфрейма (для точности входа)
    lows_1h = [float(candle[3]) for candle in recent_1h]
    highs_1h = [float(candle[2]) for candle in recent_1h]

    # Комбинированный подход: берем самые низкие минимумы и самые высокие максимумы
    support = min(min(lows_4h), min(lows_1h[-20:]))  # Последние 20 свечей 1h
    resistance = max(max(highs_4h), max(highs_1h[-20:]))

    return support, resistance

def format_progress_bars(current_step, total_steps, square_type="🟦"):
    """Форматирует прогресс-бары с квадратами"""
    filled = square_type * current_step
    empty = "⏳" * (total_steps - current_step)
    percentage = int((current_step / total_steps) * 100)
    return f"{filled}{empty} {percentage}%"

def format_steps_list(steps, current_step):
    """Форматирует список этапов с иконками статусов"""
    result = []
    for i, step_text in enumerate(steps):
        if i < current_step - 1:
            result.append(f"✅ {step_text}")
        elif i == current_step - 1:
            result.append(f"🔄 {step_text}")
    return result

async def analyze_ticker(ticker, update):
    symbol = f"{ticker}USDT"
    logger.info(f"Starting analysis for {symbol}")

    # Этапы анализа тикера
    steps = [
        "Подключение к Bybit API...",
        "Загрузка исторических данных...", 
        "Расчет SMA50 и SMA200...",
        "Определение уровней входа...",
        "Расчет риск/прибыль...",
        "Сигнал готов!"
    ]

    # Отправляем начальное сообщение с прогрессом
    progress_message = await update.message.reply_text("🔄 Запуск анализа...")

    if not validate_ticker(ticker):
        error_msg = f"❌ Ошибка: тикер {ticker} не найден на Bybit. Попробуйте другой, например, BTC или ETH."
        await progress_message.edit_text(error_msg)
        logger.warning(f"Ticker {ticker} not found")
        return error_msg

    try:
        # Этап 1 (17%) - подключение (быстро)
        await asyncio.sleep(0.7)
        progress_bars = format_progress_bars(1, 6, "🟦")
        steps_list = format_steps_list(steps, 1)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        data_1d = get_klines(symbol, '1d', 200)
        data_4h = get_klines(symbol, '4h', 100)
        data_1h = get_klines(symbol, '1h', 50)

        if not (data_1d and data_4h and data_1h):
            error_msg = f"❌ Ошибка: нет данных для {ticker}. Bybit API временно недоступно, попробуйте позже."
            await progress_message.edit_text(error_msg)
            logger.error(f"No data available for {symbol}")
            return error_msg

        # Этап 2 (33%) - загрузка данных (медленно)
        await asyncio.sleep(1.5)
        progress_bars = format_progress_bars(2, 6, "🟦")
        steps_list = format_steps_list(steps, 2)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        current_price = float(data_1h[-1][4])
        sma_50_1d = calculate_sma(data_1d, 50)
        sma_200_1d = calculate_sma(data_1d, 200)

        if sma_50_1d is None or sma_200_1d is None:
            error_msg = f"❌ Ошибка: недостаточно данных для расчета тренда для {ticker}."
            await progress_message.edit_text(error_msg)
            logger.error(f"Insufficient SMA data for {symbol}")
            return error_msg

        # Этап 3 (50%) - расчет SMA (средне)
        await asyncio.sleep(1.2)
        progress_bars = format_progress_bars(3, 6, "🟦")
        steps_list = format_steps_list(steps, 3)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        direction = 'Long' if sma_50_1d > sma_200_1d else 'Short'
        support, resistance = get_support_resistance_levels(data_4h, data_1h)

        if support is None or resistance is None:
            error_msg = f"❌ Ошибка: не удалось определить уровни для {ticker}."
            await progress_message.edit_text(error_msg)
            logger.error(f"Could not determine levels for {symbol}")
            return error_msg

        # Этап 4 (67%) - уровни входа (средне)
        await asyncio.sleep(1.0)
        progress_bars = format_progress_bars(4, 6, "🟦")
        steps_list = format_steps_list(steps, 4)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        entry_price = support * 1.005 if direction == 'Long' else resistance * 0.995  # Небольшой отступ
        stop_loss = support * 0.98 if direction == 'Long' else resistance * 1.02
        take_profit = resistance if direction == 'Long' else support
        risk_reward = calculate_risk_reward(entry_price, stop_loss, take_profit)

        # Этап 5 (83%) - риск/прибыль (быстрее)
        await asyncio.sleep(0.8)
        progress_bars = format_progress_bars(5, 6, "🟦")
        steps_list = format_steps_list(steps, 5)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        stop_loss_pct = ((stop_loss - entry_price) / entry_price) * 100
        take_profit_pct = ((take_profit - entry_price) / entry_price) * 100
        cancel_price = support * 0.99 if direction == 'Long' else resistance * 1.01

        explanation = f"{direction} на основе {'отскока от поддержки' if direction == 'Long' else 'отскока от сопротивления'} с подтверждением тренда."
        warning = "⚠️ Рекомендуем пропустить сигнал из-за низкого соотношения риск/прибыль." if risk_reward < 2 else ""

        # Этап 6 (100%) - готово (мгновенно)
        await asyncio.sleep(0.3)
        progress_bars = format_progress_bars(6, 6, "🟦")
        steps_list = format_steps_list(steps, 6)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        await asyncio.sleep(1)  # Пауза 1 сек

        signal = format_signal(symbol, current_price, direction, entry_price, stop_loss, take_profit, stop_loss_pct, take_profit_pct, risk_reward, cancel_price, warning, sma_50_1d, sma_200_1d, support, resistance)

        await progress_message.delete()  # Удаляем сообщение с прогрессом
        logger.info(f"Analysis completed for {symbol}")
        return signal

    except Exception as e:
        error_msg = f"❌ Произошла ошибка при анализе {ticker}. Bybit API временно недоступно, попробуйте позже."
        await progress_message.edit_text(error_msg)
        logger.error(f"Error during analysis of {symbol}: {e}")
        return error_msg

async def get_best_signals(direction, update):
    logger.info(f"Starting search for best {direction} signals")
    
    # Этапы поиска лучших сигналов
    steps = [
        "Сканирование топ-50 пар на Bybit...",
        "Проанализировано: 0/8",
        "Найдено подходящих: 0", 
        "Отбор завершен!"
    ]

    # Выбираем цвет квадратов
    square_type = "🟩" if direction == 'long' else "🟥"

    # Отправляем начальное сообщение с прогрессом
    progress_message = await update.message.reply_text("🔄 Запуск поиска...")

    pairs = get_top_pairs()
    if not pairs:
        error_msg = "❌ Ошибка: Bybit API временно недоступно. Попробуйте позже."
        await progress_message.edit_text(error_msg)
        logger.error("Could not get top pairs")
        return error_msg

    try:
        # Этап 1 (25%) - сканирование (быстро)
        await asyncio.sleep(0.8)
        progress_bars = format_progress_bars(1, 4, square_type)
        steps_list = format_steps_list(steps, 1)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        signals = []
        processed_count = 0
        found_signals = 0
        max_to_process = 8  # Уменьшили для стабильности

        # Выполняем весь анализ в фоне сначала
        for pair in pairs:
            if processed_count >= max_to_process:
                break

            symbol = pair['symbol']
            processed_count += 1

            try:
                # Добавляем задержку между запросами
                await asyncio.sleep(0.8)
                
                data_1d = get_klines(symbol, '1d', 200)
                data_4h = get_klines(symbol, '4h', 100)
                data_1h = get_klines(symbol, '1h', 50)

                if not (data_1d and data_4h and data_1h):
                    logger.debug(f"Skipped {symbol} due to missing data")
                    continue

                current_price = float(data_1h[-1][4])
                sma_50_1d = calculate_sma(data_1d, 50)
                sma_200_1d = calculate_sma(data_1d, 200)

                if sma_50_1d is None or sma_200_1d is None:
                    logger.debug(f"Skipped {symbol} due to missing SMA data")
                    continue

                # Исправлено: используем английские значения
                signal_direction = 'long' if sma_50_1d > sma_200_1d else 'short'

                if signal_direction != direction:
                    continue

                support, resistance = get_support_resistance_levels(data_4h, data_1h)

                if support is None or resistance is None:
                    logger.debug(f"Skipped {symbol} due to missing levels")
                    continue

                # Более гибкие условия входа
                entry_price = support * 1.005 if direction == 'long' else resistance * 0.995
                stop_loss = support * 0.98 if direction == 'long' else resistance * 1.02
                take_profit = resistance if direction == 'long' else support
                risk_reward = calculate_risk_reward(entry_price, stop_loss, take_profit)

                # Сохраняем условие риск/прибыль >= 2.0
                if risk_reward < 2:
                    logger.debug(f"Skipped {symbol} due to low Risk/Reward ({risk_reward:.2f})")
                    continue

                found_signals += 1
                stop_loss_pct = ((stop_loss - entry_price) / entry_price) * 100
                take_profit_pct = ((take_profit - entry_price) / entry_price) * 100
                cancel_price = support * 0.99 if direction == 'long' else resistance * 1.01

                # Исправлено: используем заглавные буквы для отображения
                display_direction = 'Long' if direction == 'long' else 'Short'

                signals.append(format_signal(symbol, current_price, display_direction, entry_price, stop_loss, take_profit, stop_loss_pct, take_profit_pct, risk_reward, cancel_price, "", sma_50_1d, sma_200_1d, support, resistance))

                if len(signals) >= 3:
                    break
                    
            except Exception as e:
                logger.error(f"Error processing pair {symbol}: {e}")
                continue

        # Этап 2 (50%) - анализ (самый долгий)
        await asyncio.sleep(2.0)
        progress_bars = format_progress_bars(2, 4, square_type)
        steps[1] = f"Проанализировано: {processed_count}/8"
        steps_list = format_steps_list(steps, 2)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        # Этап 3 (75%) - поиск сигналов (средне)
        await asyncio.sleep(1.5)
        progress_bars = format_progress_bars(3, 4, square_type)
        steps[1] = f"Проанализировано: {processed_count}/8"
        steps[2] = f"Найдено подходящих: {found_signals}"
        steps_list = format_steps_list(steps, 3)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        # Этап 4 (100%) - финализация (быстро)
        await asyncio.sleep(0.7)
        progress_bars = format_progress_bars(4, 4, square_type)
        steps[1] = f"Проанализировано: {processed_count}/8"
        steps[2] = f"Найдено подходящих: {found_signals}"
        steps_list = format_steps_list(steps, 4)
        progress_text = progress_bars + "\n" + "\n".join(steps_list)
        await progress_message.edit_text(progress_text)

        await asyncio.sleep(1)  # Пауза 1 сек
        await progress_message.delete()  # Удаляем сообщение с прогрессом

        if not signals:
            opposite_direction = 'шорт' if direction == 'long' else 'лонг'
            result = f"❌ Подходящих пар не найдено на Bybit. Попробуйте через несколько минут или выберите 'Лучшее в {opposite_direction}'."
            logger.info(f"No {direction} signals found")
            return result

        result = "\n" + "="*50 + "\n".join(signals)
        logger.info(f"Found {len(signals)} {direction} signals")
        return result

    except Exception as e:
        error_msg = f"❌ Произошла ошибка при поиске сигналов. Bybit API временно недоступно, попробуйте позже."
        await progress_message.edit_text(error_msg)
        logger.error(f"Error during {direction} signals search: {e}")
        return error_msg
