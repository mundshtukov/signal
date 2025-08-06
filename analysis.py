import requests
import asyncio
import random
from config import BINANCE_API_URL, COINGECKO_API_URL, ALTERNATIVE_API_URL
from utils import calculate_risk_reward, format_signal
from datetime import datetime, timedelta

async def sleep_random():
    """Случайная задержка от 0.7 до 0.9 секунды"""
    await asyncio.sleep(random.uniform(0.7, 0.9))

def validate_ticker(ticker):
    """Проверяет, существует ли торговая пара на Binance."""
    try:
        url = f"{BINANCE_API_URL}/api/v3/exchangeInfo"
        params = {'symbol': f"{ticker}USDT"}
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return 'symbols' in data and len(data['symbols']) > 0
    except requests.RequestException:
        return False

def get_klines(symbol, interval, limit=100):
    try:
        url = f"{BINANCE_API_URL}/api/v3/klines"
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при запросе к API для {symbol}: {e}")
        return None

def get_top_pairs():
    try:
        url = f"{BINANCE_API_URL}/api/v3/ticker/24hr"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        pairs = [p for p in response.json() if p['symbol'].endswith('USDT')]
        return sorted(pairs, key=lambda x: float(x['volume']) * float(x['lastPrice']), reverse=True)[:50]
    except requests.RequestException as e:
        print(f"Ошибка при получении топ-пар: {e}")
        return []

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

    # Этапы анализа тикера
    steps = [
        "Подключение к Binance API...",
        "Загрузка исторических данных...", 
        "Расчет SMA50 и SMA200...",
        "Определение уровней входа...",
        "Расчет риск/прибыль...",
        "Сигнал готов!"
    ]

    # Отправляем начальное сообщение с прогрессом
    progress_message = await update.message.reply_text("🔄 Запуск анализа...")

    if not validate_ticker(ticker):
        await progress_message.edit_text(f"❌ Ошибка: тикер {ticker} не найден. Попробуйте другой, например, BTC или ETH.")
        return f"❌ Ошибка: тикер {ticker} не найден. Попробуйте другой, например, BTC или ETH."

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
        await progress_message.edit_text(f"❌ Ошибка: нет данных для {ticker}. Попробуйте другую монету.")
        return f"❌ Ошибка: нет данных для {ticker}. Попробуйте другую монету."

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
        await progress_message.edit_text(f"❌ Ошибка: недостаточно данных для расчета тренда для {ticker}.")
        return f"❌ Ошибка: недостаточно данных для расчета тренда для {ticker}."

    # Этап 3 (50%) - расчет SMA (средне)
    await asyncio.sleep(1.2)
    progress_bars = format_progress_bars(3, 6, "🟦")
    steps_list = format_steps_list(steps, 3)
    progress_text = progress_bars + "\n" + "\n".join(steps_list)
    await progress_message.edit_text(progress_text)

    direction = 'Long' if sma_50_1d > sma_200_1d else 'Short'
    support, resistance = get_support_resistance_levels(data_4h, data_1h)

    if support is None or resistance is None:
        await progress_message.edit_text(f"❌ Ошибка: не удалось определить уровни для {ticker}.")
        return f"❌ Ошибка: не удалось определить уровни для {ticker}."

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
    return signal

async def get_best_signals(direction, update):
    # Этапы поиска лучших сигналов
    steps = [
        "Сканирование топ-50 пар...",
        "Проанализировано: 0/30",
        "Найдено подходящих: 0", 
        "Отбор завершен!"
    ]

    # Выбираем цвет квадратов
    square_type = "🟩" if direction == 'long' else "🟥"

    # Отправляем начальное сообщение с прогрессом
    progress_message = await update.message.reply_text("🔄 Запуск поиска...")

    pairs = get_top_pairs()
    if not pairs:
        await progress_message.edit_text("❌ Ошибка: не удалось получить список торговых пар.")
        return "❌ Ошибка: не удалось получить список торговых пар."

    # Этап 1 (25%) - сканирование (быстро)
    await asyncio.sleep(0.8)
    progress_bars = format_progress_bars(1, 4, square_type)
    steps_list = format_steps_list(steps, 1)
    progress_text = progress_bars + "\n" + "\n".join(steps_list)
    await progress_message.edit_text(progress_text)

    signals = []
    processed_count = 0
    found_signals = 0
    max_to_process = 30

    # Выполняем весь анализ в фоне сначала
    for pair in pairs:
        if processed_count >= max_to_process:
            break

        symbol = pair['symbol']
        processed_count += 1

        data_1d = get_klines(symbol, '1d', 200)
        data_4h = get_klines(symbol, '4h', 100)
        data_1h = get_klines(symbol, '1h', 50)

        if not (data_1d and data_4h and data_1h):
            print(f"Пропущен {symbol} из-за отсутствия данных.")
            continue

        current_price = float(data_1h[-1][4])
        sma_50_1d = calculate_sma(data_1d, 50)
        sma_200_1d = calculate_sma(data_1d, 200)

        if sma_50_1d is None or sma_200_1d is None:
            print(f"Пропущен {symbol} из-за отсутствия SMA данных.")
            continue

        # Исправлено: используем английские значения
        signal_direction = 'long' if sma_50_1d > sma_200_1d else 'short'
        print(f"{symbol}: SMA_50_1d={sma_50_1d:.2f}, SMA_200_1d={sma_200_1d:.2f}, Direction={signal_direction}")

        if signal_direction != direction:
            continue

        support, resistance = get_support_resistance_levels(data_4h, data_1h)

        if support is None or resistance is None:
            print(f"Пропущен {symbol} из-за невозможности определить уровни.")
            continue

        # Более гибкие условия входа
        entry_price = support * 1.005 if direction == 'long' else resistance * 0.995
        stop_loss = support * 0.98 if direction == 'long' else resistance * 1.02
        take_profit = resistance if direction == 'long' else support
        risk_reward = calculate_risk_reward(entry_price, stop_loss, take_profit)

        print(f"{symbol}: Entry={entry_price:.4f}, Stop={stop_loss:.4f}, Take={take_profit:.4f}, Risk/Reward={risk_reward:.2f}")

        # Сохраняем условие риск/прибыль >= 2.0
        if risk_reward < 2:
            print(f"Пропущен {symbol} из-за низкого Risk/Reward ({risk_reward:.2f}).")
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

    # Этап 2 (50%) - анализ (самый долгий)
    await asyncio.sleep(2.0)
    progress_bars = format_progress_bars(2, 4, square_type)
    steps[1] = f"Проанализировано: {processed_count}/30"
    steps_list = format_steps_list(steps, 2)
    progress_text = progress_bars + "\n" + "\n".join(steps_list)
    await progress_message.edit_text(progress_text)

    # Этап 3 (75%) - поиск сигналов (средне)
    await asyncio.sleep(1.5)
    progress_bars = format_progress_bars(3, 4, square_type)
    steps[1] = f"Проанализировано: {processed_count}/30"
    steps[2] = f"Найдено подходящих: {found_signals}"
    steps_list = format_steps_list(steps, 3)
    progress_text = progress_bars + "\n" + "\n".join(steps_list)
    await progress_message.edit_text(progress_text)

    # Этап 4 (100%) - финализация (быстро)
    await asyncio.sleep(0.7)
    progress_bars = format_progress_bars(4, 4, square_type)
    steps[1] = f"Проанализировано: {processed_count}/30"
    steps[2] = f"Найдено подходящих: {found_signals}"
    steps_list = format_steps_list(steps, 4)
    progress_text = progress_bars + "\n" + "\n".join(steps_list)
    await progress_message.edit_text(progress_text)

    await asyncio.sleep(1)  # Пауза 1 сек
    await progress_message.delete()  # Удаляем сообщение с прогрессом

    if not signals:
        opposite_direction = 'шорт' if direction == 'long' else 'лонг'
        return f"❌ Подходящих пар не найдено. Попробуйте позже или выберите 'Лучшее в {opposite_direction}'."

    return "\n" + "="*50 + "\n".join(signals)