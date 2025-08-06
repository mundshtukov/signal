import os
import logging
import asyncio
from threading import Thread
from flask import Flask
from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext.filters import TEXT, COMMAND
from messages import WELCOME_MESSAGE, INSTRUCTION_MESSAGE
from analysis import analyze_ticker, get_best_signals
from config import TELEGRAM_TOKEN

# Настройка логирования для Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Flask приложение для health check
app = Flask(__name__)

@app.route('/')
def health_check():
    return {'status': 'Bot is running', 'message': 'CryptoSignalBot is healthy'}, 200

@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

@app.route('/status')
def status():
    return {'bot': 'active', 'service': 'telegram-crypto-bot'}, 200

def run_flask():
    """Запускает Flask сервер в отдельном потоке"""
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Фиксированная клавиатура внизу с эмодзи
reply_keyboard = ReplyKeyboardMarkup(
    [
        ["📈 Лучшее в лонг", "📉 Лучшее в шорт"],
        ["📋 Инструкция"]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

async def start(update, context):
    logger.info(f"User {update.effective_user.id} started the bot")
    await update.message.reply_text(
        WELCOME_MESSAGE, 
        parse_mode='Markdown',
        reply_markup=reply_keyboard
    )

async def instruction(update, context):
    logger.info(f"User {update.effective_user.id} requested instructions")
    await update.message.reply_text(
        INSTRUCTION_MESSAGE, 
        parse_mode='Markdown',
        reply_markup=reply_keyboard
    )

async def handle_ticker(update, context):
    ticker = update.message.text
    user_id = update.effective_user.id
    
    try:
        if ticker == "📈 Лучшее в лонг":
            logger.info(f"User {user_id} requested best long signals")
            signals = await get_best_signals('long', update)
            response = signals if signals else "❌ Подходящих пар не найдено. Попробуйте позже или выберите '📉 Лучшее в шорт'."
            await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_keyboard)

        elif ticker == "📉 Лучшее в шорт":
            logger.info(f"User {user_id} requested best short signals")
            signals = await get_best_signals('short', update)
            response = signals if signals else "❌ Подходящих пар не найдено. Попробуйте позже или выберите '📈 Лучшее в лонг'."
            await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_keyboard)

        elif ticker == "📋 Инструкция":
            await update.message.reply_text(INSTRUCTION_MESSAGE, parse_mode='Markdown', reply_markup=reply_keyboard)

        else:
            # Обработка пользовательского тикера
            ignored_inputs = ['/START', '/INSTRUCTION']
            if ticker.upper() in [i.upper() for i in ignored_inputs]:
                await update.message.reply_text(
                    "❌ Пожалуйста, введите тикер монеты (например, BTC, ETH).",
                    parse_mode='Markdown',
                    reply_markup=reply_keyboard
                )
                return

            logger.info(f"User {user_id} analyzing ticker: {ticker}")
            signal = await analyze_ticker(ticker.upper(), update)
            await update.message.reply_text(signal, parse_mode='Markdown', reply_markup=reply_keyboard)
            
    except Exception as e:
        logger.error(f"Error handling ticker {ticker} for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.",
            reply_markup=reply_keyboard
        )

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    logger.info(f"Received callback_data: {query.data}")
    await query.edit_message_text(
        "❌ Этот обработчик не используется. Используйте клавиатуру внизу.", 
        parse_mode='Markdown'
    )

def main():
    # Проверяем наличие токена
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not found in environment variables!")
        raise ValueError("TELEGRAM_TOKEN environment variable is required")
    
    # Запускаем Flask сервер в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask health check server started")
    
    logger.info("Starting CryptoSignalBot...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('instruction', instruction))
    application.add_handler(MessageHandler(TEXT & ~COMMAND, handle_ticker))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    try:
        logger.info("Bot is running with polling...")
        application.run_polling()
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == '__main__':
    main()
