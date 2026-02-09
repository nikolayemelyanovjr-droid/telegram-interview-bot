import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
import os
import sys
import signal

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для состояний разговора
(
    FIO, INTERVIEWER, CANONICAL_OBSTACLES, SPIRITUAL_GUIDE,
    IMPRESSIONS_1, IMPRESSIONS_2, IMPRESSIONS_3, IMPRESSIONS_4,
    IMPRESSIONS_5, IMPRESSIONS_6, PROBLEMS, COMMENTS, VERDICT, CONFIRM
) = range(14)

# Константы для Google Sheets
SPREADSHEET_ID = "1JvUD3CSFdgtsUVqir6zUfB5oC42NtP4YGOlZOVNRLho"
SHEET_NAME = "Ответы"

class InterviewBot:
    def __init__(self, token):
        self.token = token
        self.sheet = None
        self.google_connected = False
        self.setup_google_sheets()

       def setup_google_sheets(self):
        """Настройка подключения к Google Sheets"""
        try:
            # Сначала пробуем файл credentials.json
            if os.path.exists('credentials.json'):
                with open('credentials.json', 'r') as f:
                    creds_data = json.load(f)
                    logger.info("✅ Файл credentials.json найден")
            else:
                # Если нет файла, пробуем переменную окружения
                credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
                if not credentials_json:
                    logger.error("❌ Не найден ни файл credentials.json, ни переменная GOOGLE_CREDENTIALS")
                    return False
                creds_data = json.loads(credentials_json)
                logger.info("✅ Использую GOOGLE_CREDENTIALS из переменных окружения")
            
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Создаем credentials из словаря
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_data, scope)            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            
            try:
                worksheet = spreadsheet.worksheet(SHEET_NAME)
            except:
                worksheet = spreadsheet.get_worksheet(0)
            
            self.sheet = worksheet
            self.google_connected = True
            logger.info("✅ Google Sheets подключен!")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Sheets: {e}")
            self.google_connected = False
            return False
    
    async def save_to_sheet(self, data):
        """Сохранение данных в Google Sheets"""
        if not self.google_connected:
            logger.warning("⚠️ Google Sheets не подключен, пропускаю сохранение")
            return False
        
        try:
            # Собираем все впечатления в одну строку
            impressions = []
            for i in range(1, 7):
                key = f'impressions_{i}'
                if data.get(key):
                    impressions.append(data[key])

            impressions_str = ", ".join(impressions) if impressions else ""

            row = [
                data.get('fio', ''),
                data.get('interviewer', ''),
                data.get('canonical_obstacles', ''),
                data.get('spiritual_guide', ''),
                impressions_str,
                data.get('problems', ''),
                data.get('comments', ''),
                data.get('verdict', ''),
            ]

            self.sheet.append_row(row)
            logger.info("✅ Данные сохранены в Google Sheets")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
            return False

    def get_main_keyboard(self, include_next=False):
        """Создает основную клавиатуру с кнопкой перезапуска"""
        keyboard = []

        # Добавляем кнопку перезапуска в начало
        restart_button = [['🔄 Перезапустить бот']]
        keyboard.extend(restart_button)

        # Если нужно добавить кнопку "Далее" (в конце опроса)
        if include_next:
            keyboard.append(['Далее'])

        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик команды /start - работает ВСЕГДА"""
        # Очищаем данные предыдущего опроса
        context.user_data.clear()

        # Отправляем сообщение с кнопкой перезапуска
        await update.message.reply_text(
            "Здравствуйте!\n"
            "Поделитесь своим впечатлением от собеседования.\n\n"
            "Шаг 1: Введите ФИО абитуриента:",
            reply_markup=self.get_main_keyboard()
        )
        return FIO

    async def restart_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик кнопки '🔄 Перезапустить бот'"""
        # Очищаем данные предыдущего опроса
        context.user_data.clear()

        await update.message.reply_text(
            "🔄 Бот перезапущен!\n\n"
            "Начинаем новый опрос.\n\n"
            "Шаг 1: Введите ФИО абитуриента:",
            reply_markup=self.get_main_keyboard()
        )
        return FIO

    async def get_fio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение ФИО"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['fio'] = update.message.text

        keyboard = [
            ['прот. Николай Емельянов', 'прот. Константин Стриевский'],
            ['иер. Иван Воробьев', 'иер. Алексей Захаров'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 2: Кто проводил собеседование?",
            reply_markup=reply_markup
        )
        return INTERVIEWER

    async def get_interviewer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение информации о собеседующем"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['interviewer'] = update.message.text

        keyboard = [
            ['Есть канонические препятствия, НЕ можем принять в ПСТБИ'],
            ['Есть канонические препятствия, нужно благословение владыки'],
            ['Надо посоветоваться с проректором'],
            ['Нет канонических препятствий, можем принять в ПСТБИ'],
            ['Нет канонических препятствий, с поступлением стоит подождать'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 3: Наличие канонических препятствий.",
            reply_markup=reply_markup
        )
        return CANONICAL_OBSTACLES

    async def get_canonical_obstacles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение информации о канонических препятствиях"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        answer = update.message.text
        context.user_data['canonical_obstacles'] = answer

        # Проверка на особый случай (прямой переход к вердикту)
        if answer == 'Есть канонические препятствия, НЕ можем принять в ПСТБИ':
            keyboard = [
                ['Да', 'Нет', 'Надо посоветоваться'],
                ['Пока пусть поступает на БФ, через год посмотрим'],
                ['🔄 Перезапустить бот']
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

            await update.message.reply_text(
                "Шаг 13: Ваш вердикт: допускаем ли мы абитуриента к вступительному экзамену?",
                reply_markup=reply_markup
            )
            return VERDICT

        # Все остальные варианты продолжают опрос с шага 4
        keyboard = [
            ['Есть духовник, благословил учиться'],
            ['Есть духовник, готов благословить учиться'],
            ['Есть духовник, пока не готов благословить учиться'],
            ['Духовника как такового нет, есть священник, который готов благословить учиться'],
            ['Нет духовника'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 4: Наличие духовника и благословения на поступление",
            reply_markup=reply_markup
        )
        return SPIRITUAL_GUIDE

    async def get_spiritual_guide(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение информации о духовнике"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бot':
            return await self.restart_handler(update, context)

        context.user_data['spiritual_guide'] = update.message.text

        keyboard = [
            ['Общительный, открытый'],
            ['Замкнутый'],
            ['Слишком общительный'],
            ['Затрудняюсь ответить'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 5: Ваши впечатления от общения с абитуриентом",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_1

    async def get_impressions_1(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение первого впечатления"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['impressions_1'] = update.message.text

        keyboard = [
            ['Давно в церкви'],
            ['Недавно в церкви'],
            ['Затрудняюсь ответить'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 6: Продолжаем",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_2

    async def get_impressions_2(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение второго впечатления"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['impressions_2'] = update.message.text

        keyboard = [
            ['Из церковной семьи'],
            ['Из не церковной семьи'],
            ['Затрудняюсь ответить'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 7: Продолжаем",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_3

    async def get_impressions_3(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение третьего впечатления"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['impressions_3'] = update.message.text

        keyboard = [
            ['Помогает в храме'],
            ['Ничем не занят в храме'],
            ['Затрудняюсь ответить'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 8: Продолжаем",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_4

    async def get_impressions_4(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение четвертого впечатления"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['impressions_4'] = update.message.text

        keyboard = [
            ['Жена из церковной семьи'],
            ['Жена из не церковной семьи'],
            ['Не женат'],
            ['Затрудняюсь ответить'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 9: Еще немного",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_5

    async def get_impressions_5(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение пятого впечатления"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['impressions_5'] = update.message.text

        keyboard = [
            ['Состоявшийся мужчина'],
            ['Вполне зрелый'],
            ['Совсем еще не зрелый'],
            ['Затрудняюсь ответить'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 10: Почти закончили",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_6

    async def get_impressions_6(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение шестого впечатления"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['impressions_6'] = update.message.text

        # Для текстовых ответов показываем кнопку перезапуска отдельно
        keyboard = [['🔄 Перезапустить бот']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 11: Какие проблемы, как вам кажется, могут возникнуть в процессе учебы? "
            "(если никаких, напишите 'нет')\n\n"
            "Вы можете ввести текст ответа, а кнопка перезапуска всегда доступна:",
            reply_markup=reply_markup
        )
        return PROBLEMS

    async def get_problems(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение информации о возможных проблемах"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['problems'] = update.message.text

        # Для текстовых ответов показываем кнопку перезапуска отдельно
        keyboard = [['🔄 Перезапустить бот']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 12: Ваши общие впечатления и комментарии\n\n"
            "Вы можете ввести текст ответа, а кнопка перезапуска всегда доступна:",
            reply_markup=reply_markup
        )
        return COMMENTS

    async def get_comments(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение общих комментариев"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['comments'] = update.message.text

        keyboard = [
            ['Да', 'Нет', 'Надо посоветоваться'],
            ['Пока пусть поступает на БФ, через год посмотрим'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Шаг 13: Ваш вердикт: допускаем ли мы абитуриента к вступительному экзамену?",
            reply_markup=reply_markup
        )
        return VERDICT

    async def get_verdict(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение вердикта"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        context.user_data['verdict'] = update.message.text

        # Сохраняем данные
        if await self.save_to_sheet(context.user_data):
            save_status = "✅ Данные успешно сохранены в таблицу"
        else:
            save_status = "⚠️ Данные НЕ сохранены в таблицу"

        # В конце опроса показываем кнопку "Далее" и "Перезапустить"
        keyboard = [
            ['Далее'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            f"Спасибо!\n{save_status}\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
        return CONFIRM

    async def confirm_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка нажатия 'Далее'"""
        # Если нажата кнопка перезапуска
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)

        # Очищаем данные предыдущего опроса
        context.user_data.clear()

        await update.message.reply_text(
            "Отлично! Начинаем новый опрос.\n\n"
            "Шаг 1: Введите ФИО абитуриента:",
            reply_markup=self.get_main_keyboard()
        )
        return FIO

    async def cancel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отмена разговора"""
        await update.message.reply_text(
            'Опрос отменен. Нажмите /start или кнопку "🔄 Перезапустить бот" чтобы начать заново.',
            reply_markup=self.get_main_keyboard()
        )
        return ConversationHandler.END

    def create_application(self):
        """Создание приложения с обработчиками"""
        application = Application.builder().token(self.token).build()

        # Создаем фильтр для кнопки перезапуска
        restart_filter = filters.Regex('^🔄 Перезапустить бот$')

        # ОСНОВНОЙ ConversationHandler для опроса
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', self.start_handler),
                MessageHandler(restart_filter, self.restart_handler),
                MessageHandler(filters.Regex('^Далее$'), self.confirm_next)
            ],
            states={
                FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_fio)],
                INTERVIEWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_interviewer)],
                CANONICAL_OBSTACLES: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_canonical_obstacles)],
                SPIRITUAL_GUIDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_spiritual_guide)],
                IMPRESSIONS_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_impressions_1)],
                IMPRESSIONS_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_impressions_2)],
                IMPRESSIONS_3: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_impressions_3)],
                IMPRESSIONS_4: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_impressions_4)],
                IMPRESSIONS_5: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_impressions_5)],
                IMPRESSIONS_6: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_impressions_6)],
                PROBLEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_problems)],
                COMMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_comments)],
                VERDICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_verdict)],
                CONFIRM: [
                    MessageHandler(restart_filter, self.restart_handler),
                    MessageHandler(filters.Regex('^Далее$'), self.confirm_next)
                ],
            },
            fallbacks=[
                CommandHandler('start', self.start_handler),
                MessageHandler(restart_filter, self.restart_handler),
                CommandHandler('cancel', self.cancel_handler)
            ],
            allow_reentry=True,
        )

        # Добавляем отдельные обработчики
        application.add_handler(CommandHandler('start', self.start_handler))

        # Добавляем ConversationHandler
        application.add_handler(conv_handler)

        return application

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    print(f"\n📶 Получен сигнал {signum}, завершаю работу...")
    sys.exit(0)

def main():
    """Основная функция запуска бота"""
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Получаем токен из переменной окружения
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        print("💡 Установите переменную окружения BOT_TOKEN")
        print("   Или используйте тестовый токен: 8218773605:AAHIA8W0e-OOIhsZV_O0lSeKMWaV_AoSuUY")
        return
    
    print("🚀 Запускаю бота...")
    print(f"🤖 Токен: {BOT_TOKEN[:10]}...{BOT_TOKEN[-10:]}")
    
    bot = InterviewBot(BOT_TOKEN)
    application = bot.create_application()
    
    print("\n✅ БОТ ЗАПУЩЕН И РАБОТАЕТ!")
    print("=" * 50)
    print("📱 Откройте Telegram и найдите своего бота")
    print("💬 Отправьте команду /start")
    print("⏰ Бот будет работать 24/7 на Railway.app")
    print("=" * 50)
    
    # Запускаем бота
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()
{
  "type": "service_account",
  "project_id": "telegram-bot-sheets-485811",
  "private_key_id": "af9becacfd73731caa1c9895f275800227775dc8",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCRkeNYSmDNiPaw\nJYUGLC88zi7pZJ9BISTdI2xWjziaMdT4kCehlWY76Uivpe9TZ4v2UigRWKNUbdWa\nyjoWc3Dwpmeuf61b2G51sgX8cT46mWBshv9ccGmBz7G8hGuNBPZ2LQqtcTSDz6D1\nE3xfeJ2DmTgMu/T8mU/J7IEnaaQvHHkcMabPDuTpYwdclkMRTrWKpO+u1fBeeBen\npTiKhppkHEelH/IiXJG5wRN/FihZcwvdYRy0YgjGH/L4BtSP6n+dZF91fR1kFnBB\n3RbcBRu/Sa98eX6+cormaOOIwNdwEnCBR8DF23yX6PM323q/mz+6mEgjNgICXhIR\ngUGpI+9XAgMBAAECggEADfcqEXYpRu6x6mcSSQWDwdiiC+zsXmPSO1wpPT15fhZa\nMT9bN5eAR5UmgdUKJ3B5FZ7LwayrfSKznUMND/3vqUnw2BisEz8QJQusPIv8uJB7\nlxqodKZ2nAHGzA6dzT/bPHrIjUIEE/U41h14qPKGyHF/POS3W/7okB233x+CceAR\nv6uEzsIkY17KjwRufFTdr3BcOpQ43n5p66I6Y23cka+L4mHSSm2gYN7VQKSAjFK1\nThHzbA1EaU3JNtX7kLeIIFSKchcaaXA74EpOLUhONa84f5iAev05/v3XLw39jWFd\nQN4HAbb7l2RCLKt66yhGxdOmZfW1S7g/ICzMF3YN+QKBgQDKGpgVvAPf9UyURjlT\nxtZu5RSl67cC0b4IkvX8/2iN7DNyVXTgvaTQCGUKYGxAV35oqoUshgGE3/WU6xBc\nxKqfPDsMvCU6T3JClkvxFpyy0Q8zTkZZ/0BV2W2JADwrAiU8Nn/yJ71oz4jr014P\nNA2RhLeyL3DLlTCsYImB28Y2gwKBgQC4Y8fRO2lJvC9axW1txg/taqlXm7SO/lSH\nLQKzQVya+k+mwlAjIKCMSx7LEKJ64O6vAd3wDP59+ugRdlhPLez7/72hHjU7tuC6\nIvTLRG5uoZtwhtsFqQivb2h3YYmXgJxS7QHoBNQ4vOhIkOjD4b305/g9rcQ3hDu4\nKlrAnTmrnQKBgAY56YOJ5kipAvHyc+Or1YFXF1rBN0Mj+QnElUV1DOCKbU9RaKdf\n0EsEZzB5pfwZdfB9iFrFyhgw2hz7XOauvF7peRw8U51HQ0rf3HkR7EPqAuDewXYW\nUgITD7fPxQrCJymCuFBafxBSjHJPca9gOCbKguo/YeczsmstEi9o+ONHAoGBAIEl\ncfi8UfxRECHVkdWHGfTB9iXkasyUmgOrpO6EYyYxF8TG6HYSDiD1JHY6CnNiRArT\nleziTQVTzWMdrrCWjBvcfabxj3tplXEJtscAARD/o+1mptUKFYk60MJ80HAKpnL2\niZVGfJXYyiC5Ti6UWAXGy3n30SzJM0LEd5fdB12JAoGAPdUeHEjjfIc2w+xonPZn\nkt90o/f4ioOGmEno1Koy39zyTgsz9jVqTqPXterr9LMjmqiThQv4vvcLvhq9C8jP\nE+grpbcCcl+Zw2S0xQkGlnF8SDclPvcJbOVXEskVH9PVSJcyF4igZEplscNFDdg/\nE/WMG1atM/QC+soPwz1QZuA=\n-----END PRIVATE KEY-----\n",
  "client_email": "telegram-bot-service@telegram-bot-sheets-485811.iam.gserviceaccount.com",
  "client_id": "112623196965203691240",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/telegram-bot-service%40telegram-bot-sheets-485811.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
Add credentials.json file and update Google Sheets connection
