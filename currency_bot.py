import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
)
import requests
import nest_asyncio  # Для работы с вложенными циклами событий

# Активируем поддержку вложенных циклов событий
nest_asyncio.apply()

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния диалога
SELECT_ACTION, SELECT_CURRENCY, ENTER_AMOUNT = range(3)

# Ваш API-ключ для CurrencyAPI (замените на свой ключ)
API_KEY = "ваш_токен"

# URL для получения курсов валют (используем CurrencyAPI)
BASE_URL = f"https://api.currencyapi.com/v3/latest?apikey={API_KEY}&base_currency=RUB"

# Кнопки выбора валют
CURRENCIES = ['USD', 'EUR', 'CNY', 'KRW', 'JPY', 'KZT']

# Функция для получения курсов валют
def get_exchange_rates():
    try:
        response = requests.get(BASE_URL)
        data = response.json()
        if 'data' in data and data['data']:
            return {currency: data['data'][currency]['value'] for currency in CURRENCIES}
        else:
            logger.error("Failed to fetch exchange rates.")
            return None
    except Exception as e:
        logger.error(f"Error fetching exchange rates: {e}")
        return None

# Начало работы с ботом
async def start(update: Update, context: CallbackContext):
    await show_main_menu(update, context)
    return SELECT_ACTION

# Показ главного меню
async def show_main_menu(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Из рубля в валюту", callback_data="RUB_TO_CURRENCY")],
        [InlineKeyboardButton("Из валюты в рубль", callback_data="CURRENCY_TO_RUB")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )
    elif isinstance(update, Update) and update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text="Выберите действие:",
            reply_markup=reply_markup
        )

# Обработка выбора действия
async def select_action(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    action = query.data
    if action == "CLEAR_DIALOG":
        context.user_data.clear()  # Очищаем данные пользователя
        await query.edit_message_text(text="Диалог очищен. Выберите действие:")
        await show_main_menu(update, context)
        return SELECT_ACTION

    context.user_data['action'] = action

    if action == "RUB_TO_CURRENCY":
        await query.edit_message_text(
            text="Выберите валюту, в которую хотите конвертировать:",
            reply_markup=get_currency_keyboard()
        )
    elif action == "CURRENCY_TO_RUB":
        await query.edit_message_text(
            text="Выберите валюту, из которой хотите конвертировать:",
            reply_markup=get_currency_keyboard()
        )
    return SELECT_CURRENCY

# Создание клавиатуры с валютами
def get_currency_keyboard():
    keyboard = [[InlineKeyboardButton(currency, callback_data=currency)] for currency in CURRENCIES]
    return InlineKeyboardMarkup(keyboard)

# Выбор валюты
async def select_currency(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    currency = query.data
    context.user_data['currency'] = currency

    action = context.user_data['action']
    if action == "RUB_TO_CURRENCY":
        await query.edit_message_text(text="Введите сумму в рублях:")
    elif action == "CURRENCY_TO_RUB":
        await query.edit_message_text(text=f"Введите сумму в {currency}:")
    return ENTER_AMOUNT

# Ввод суммы
async def enter_amount(update: Update, context: CallbackContext):
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите положительное числовое значение.")
        await show_main_menu(update, context)  # Возвращаемся к главному меню
        return SELECT_ACTION

    context.user_data['amount'] = amount

    action = context.user_data['action']
    currency = context.user_data['currency']
    rates = get_exchange_rates()

    if not rates:
        await update.message.reply_text("Не удалось получить курсы валют. Попробуйте позже.")
        await show_main_menu(update, context)  # Возвращаемся к главному меню
        return SELECT_ACTION

    if action == "RUB_TO_CURRENCY":
        if currency not in rates:
            await update.message.reply_text(f"Курс для валюты {currency} недоступен.")
            await show_main_menu(update, context)  # Возвращаемся к главному меню
            return SELECT_ACTION
        rub_to_currency = rates[currency]
        result = amount * rub_to_currency
        await update.message.reply_text(
            f"{amount:.2f} RUB = {result:.2f} {currency}"
        )
    elif action == "CURRENCY_TO_RUB":
        if currency not in rates:
            await update.message.reply_text(f"Курс для валюты {currency} недоступен.")
            await show_main_menu(update, context)  # Возвращаемся к главному меню
            return SELECT_ACTION
        currency_to_rub = 1 / rates[currency] if rates[currency] != 0 else None
        if currency_to_rub is None:
            await update.message.reply_text(f"Курс для валюты {currency} равен нулю.")
            await show_main_menu(update, context)  # Возвращаемся к главному меню
            return SELECT_ACTION
        result = amount * currency_to_rub
        await update.message.reply_text(
            f"{amount:.2f} {currency} = {result:.2f} RUB"
        )

    # После завершения операции показываем главное меню
    await show_main_menu(update, context)
    return SELECT_ACTION

# Отмена операции
async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("Операция отменена.")
    await show_main_menu(update, context)  # Возвращаемся к главному меню
    return SELECT_ACTION

# Ошибки
async def error_handler(update: object, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")
    await show_main_menu(update, context)  # Возвращаемся к главному меню

# Главная функция
async def main():
    # Замените YOUR_TELEGRAM_BOT_TOKEN на ваш токен бота
    application = Application.builder().token("токен, который вы сгенинируете с помощью @BotFather").build()

    # Добавление обработчиков
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_ACTION: [CallbackQueryHandler(select_action)],
            SELECT_CURRENCY: [CallbackQueryHandler(select_currency)],
            ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(show_main_menu, pattern="^CLEAR_DIALOG$")
        ],
        per_chat=True,  # Указываем, что состояние сохраняется для каждого чата
        per_user=False  # Отключаем привязку к конкретному пользователю
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    # Запуск бота
    await application.run_polling()

if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
