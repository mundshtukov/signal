import os
from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext.filters import TEXT, COMMAND
from messages import WELCOME_MESSAGE, INSTRUCTION_MESSAGE
from analysis import analyze_ticker, get_best_signals
from config import TELEGRAM_TOKEN
from aiohttp import web
import asyncio

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
        signals = await get_best_signals('long', update)
        response = signals if signals else "❌ Подходящих пар не найдено. Попробуйте позже или выберите '📉 Лучшее в шорт'."
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_keyboard)
    elif ticker == "📉 Лучшее в шорт":
        signals = await get_best_signals('short', update)
        response = signals if signals else "❌ Подходящих пар не найдено. Попробуйте позже или выберите '📈 Лучшее в лонг'."
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_keyboard)
    elif ticker == "📋 Инструкция":
        await update.message.reply_text(INSTRUCTION_MESSAGE, parse_mode='Markdown', reply_markup=reply_keyboard)
    else:
        ignored_inputs = ['/START', '/INSTRUCTION']
        if ticker.upper() in [i.upper() for i in ignored_inputs]:
            await update.message.reply_text(
                "❌ Пожалуйста, введите тикер монеты (например, BTC, ETH).",
                parse_mode='Markdown',
                reply_markup=reply_keyboard
            )
            return
        signal = await analyze_ticker(ticker.upper(), update)
        await update.message.reply_text(signal, parse_mode='Markdown', reply_markup=reply_keyboard)

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    print(f"Получен callback_data: {query.data}")
    await query.edit_message_text(
        "❌ Этот обработчик не используется. Используйте клавиатуру внизу.", 
        parse_mode='Markdown'
    )

async def health_check(request):
    return web.Response(text="OK")

async def start_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    port = int(os.getenv('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"HTTP-сервер запущен на порту {port}")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('instruction', instruction))
    application.add_handler(MessageHandler(TEXT & ~COMMAND, handle_ticker))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем HTTP-сервер и polling одновременно
    loop = asyncio.get_event_loop()
    loop.create_task(start_server())
    application.run_polling()

if __name__ == '__main__':
    main()
