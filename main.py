import os
from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext.filters import TEXT, COMMAND
from messages import WELCOME_MESSAGE, INSTRUCTION_MESSAGE
from analysis import analyze_ticker, get_best_signals
from config import TELEGRAM_TOKEN

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
    await update.message.reply_text(
        WELCOME_MESSAGE, 
        parse_mode='Markdown',
        reply_markup=reply_keyboard
    )

async def instruction(update, context):
    await update.message.reply_text(
        INSTRUCTION_MESSAGE, 
        parse_mode='Markdown',
        reply_markup=reply_keyboard
    )

async def handle_ticker(update, context):
    ticker = update.message.text

    if ticker == "📈 Лучшее в лонг":
        signals = await get_best_signals('long', update)  # Передаем update для прогресса
        response = signals if signals else "❌ Подходящих пар не найдено. Попробуйте позже или выберите '📉 Лучшее в шорт'."
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_keyboard)

    elif ticker == "📉 Лучшее в шорт":
        signals = await get_best_signals('short', update)  # Передаем update для прогресса
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

        signal = await analyze_ticker(ticker.upper(), update)  # Передаем update для прогресса
        await update.message.reply_text(signal, parse_mode='Markdown', reply_markup=reply_keyboard)

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    print(f"Получен callback_data: {query.data}")  # Отладочный вывод
    # Этот обработчик оставлен на случай, если вернемся к InlineKeyboardMarkup
    await query.edit_message_text(
        "❌ Этот обработчик не используется. Используйте клавиатуру внизу.", 
        parse_mode='Markdown'
    )

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('instruction', instruction))
    application.add_handler(MessageHandler(TEXT & ~COMMAND, handle_ticker))
    application.add_handler(CallbackQueryHandler(button_handler))
    try:
        application.run_polling()
    except Exception as e:
        print(f"Ошибка при запуске: {e}")

if __name__ == '__main__':
    main()