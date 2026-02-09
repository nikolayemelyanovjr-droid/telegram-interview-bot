import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
import os
import sys
import signal
import time
from datetime import datetime

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
            logger.info("🔧 Начинаю настройку Google Sheets...")
            
            # Пробуем получить credentials из файла
            if os.path.exists('credentials.json'):
                with open('credentials.json', 'r') as f:
                    creds_data = json.load(f)
                    logger.info("✅ Файл credentials.json найден")
            else:
                # Пробуем получить из переменной окружения
                credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
                if not credentials_json:
                    logger.error("❌ Не найден ни файл credentials.json, ни переменная GOOGLE_CREDENTIALS")
                    return False
                creds_data = json.loads(credentials_json)
                logger.info("✅ Использую GOOGLE_CREDENTIALS из переменных окружения")
            
            # Проверяем необходимые ключи
            required_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email', 'client_id']
            missing_keys = [key for key in required_keys if key not in creds_data]
            if missing_keys:
                logger.error(f"❌ В credentials отсутствуют ключи: {missing_keys}")
                return False
            
            # Настраиваем scope
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
            
            # Создаем credentials
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_data, scope)
            client = gspread.authorize(creds)
            
            # Открываем таблицу
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            
            # Получаем лист
            try:
                worksheet = spreadsheet.worksheet(SHEET_NAME)
                logger.info(f"✅ Найден лист: {SHEET_NAME}")
            except:
                worksheet = spreadsheet.get_worksheet(0)
                logger.info(f"✅ Использую первый лист таблицы")
            
            self.sheet = worksheet
            self.google_connected = True
            
            # Проверяем заголовки столбцов
            headers = self.sheet.row_values(1)
            if not headers:
                # Создаем заголовки
                headers = [
                    "ФИО абитуриента", "Собеседующий", "Канонические препятствия",
                    "Духовник", "Впечатления", "Проблемы в учебе",
                    "Комментарии", "Вердикт", "Дата"
                ]
                self.sheet.append_row(headers)
                logger.info("✅ Созданы заголовки столбцов")
            
            logger.info("✅ Google Sheets подключен успешно!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка Google Sheets: {e}", exc_info=True)
            self.google_connected = False
            return False
    
    async def save_to_sheet(self, data):
        """Сохранение данных в Google Sheets"""
        if not self.google_connected:
            logger.warning("⚠️  Данные НЕ сохранены (Google Sheets отключен)")
            return False
        
        try:
            # Собираем все впечатления (шаги 5-10) в одну строку для столбца E
            impressions_steps = [
                data.get('impressions_1', ''),  # Шаг 5
                data.get('impressions_2', ''),  # Шаг 6
                data.get('impressions_3', ''),  # Шаг 7
                data.get('impressions_4', ''),  # Шаг 8
                data.get('impressions_5', ''),  # Шаг 9
                data.get('impressions_6', '')   # Шаг 10
            ]
            
            # Фильтруем пустые значения и объединяем
            impressions_list = [imp for imp in impressions_steps if imp]
            impressions_str = "; ".join(impressions_list) if impressions_list else ""
            
            # Формируем строку для записи (столбцы A-I)
            row = [
                data.get('fio', ''),                    # A: ФИО абитуриента
                data.get('interviewer', ''),            # B: Собеседующий
                data.get('canonical_obstacles', ''),    # C: Канонические препятствия
                data.get('spiritual_guide', ''),        # D: Духовник
                impressions_str,                        # E: Впечатления (шаги 5-10)
                data.get('problems', ''),               # F: Проблемы в учебе
                data.get('comments', ''),               # G: Комментарии
                data.get('verdict', ''),                # H: Вердикт
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # I: Дата
            ]
            
            # Заменяем None на пустые строки
            row = ['' if cell is None else str(cell) for cell in row]
            
            logger.info(f"📝 Записываю строку: {row}")
            
            # Записываем в таблицу
            self.sheet.append_row(row)
            
            logger.info("✅ Данные успешно сохранены в Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}", exc_info=True)
            return False
    
    def get_main_keyboard(self):
        """Создает основную клавиатуру с кнопкой перезапуска"""
        keyboard = [['🔄 Перезапустить бот']]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик команды /start"""
        # Очищаем данные предыдущего опроса
        context.user_data.clear()
        
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
            "Здравствуйте!\n"
            "Поделитесь своим впечатлением от собеседования.\n\n"
            "Шаг 1: Введите ФИО абитуриента:",
            reply_markup=self.get_main_keyboard()
        )
        return FIO
    
    async def get_fio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Шаг 1: Получение ФИО абитуриента"""
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
        """Шаг 2: Получение информации о собеседующем"""
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
        """Шаг 3: Получение информации о канонических препятствиях"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        answer = update.message.text
        context.user_data['canonical_obstacles'] = answer
        
        # Проверяем: если ответ "Есть канонические препятствия, НЕ можем принять в ПСТБИ"
        # то пропускаем шаги 4-12 и переходим сразу к шагу 13
        if answer == 'Есть канонические препятствия, НЕ можем принять в ПСТБИ':
            keyboard = [
                ['Да', 'Нет'],
                ['Надо посоветоваться', 'Пока пускай поступает на БФ, через год посмотрим'],
                ['🔄 Перезапустить бот']
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            await update.message.reply_text(
                "Шаг 13: Ваш вердикт: допускаем ли мы абитуриента к вступительному экзамену?",
                reply_markup=reply_markup
            )
            return VERDICT
        
        # Если любой другой ответ - переходим к шагу 4
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
        """Шаг 4: Получение информации о духовнике"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['spiritual_guide'] = update.message.text
        
        keyboard = [
            ['Общительный, открытый', 'Замкнутый'],
            ['Слишком общительный', 'Затрудняюсь ответить'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            "Шаг 5: Ваши впечатления от общения с абитуриентом",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_1
    
    async def get_impressions_1(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Шаг 5: Впечатления от общения"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['impressions_1'] = update.message.text
        
        keyboard = [
            ['Давно в церкви', 'Недавно в церкви'],
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
        """Шаг 6: Как давно в церкви"""
        if update.message.text == '🔄 Перезапустить бot':
            return await self.restart_handler(update, context)
        
        context.user_data['impressions_2'] = update.message.text
        
        keyboard = [
            ['Из церковной семьи', 'Из не церковной семьи'],
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
        """Шаг 7: Из какой семьи"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['impressions_3'] = update.message.text
        
        keyboard = [
            ['Помогает в храме', 'Ничем не занят в храме'],
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
        """Шаг 8: Помощь в храме"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['impressions_4'] = update.message.text
        
        keyboard = [
            ['Жена из церковной семьи', 'Жена из не церковной семьи'],
            ['Не женат', 'Затрудняюсь ответить'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            "Шаг 9: Еще немного",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_5
    
    async def get_impressions_5(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Шаг 9: Семейное положение"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['impressions_5'] = update.message.text
        
        keyboard = [
            ['Состоявшийся мужчина', 'Вполне зрелый'],
            ['Совсем еще не зрелый', 'Затрудняюсь ответить'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            "Шаг 10: Почти закончили",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_6
    
    async def get_impressions_6(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Шаг 10: Зрелость"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['impressions_6'] = update.message.text
        
        keyboard = [['🔄 Перезапустить бот']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            "Шаг 11: Какие проблемы, как вам кажется, могут возникнуть в процессе учебы?\n"
            "(если никаких, напишите 'нет')",
            reply_markup=reply_markup
        )
        return PROBLEMS
    
    async def get_problems(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Шаг 11: Проблемы в учебе"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['problems'] = update.message.text
        
        keyboard = [['🔄 Перезапустить бот']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            "Шаг 12: Ваши общие впечатления и комментарии",
            reply_markup=reply_markup
        )
        return COMMENTS
    
    async def get_comments(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Шаг 12: Комментарии"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['comments'] = update.message.text
        
        keyboard = [
            ['Да', 'Нет'],
            ['Надо посоветоваться', 'Пока пускай поступает на БФ, через год посмотрим'],
            ['🔄 Перезапустить бот']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            "Шаг 13: Ваш вердикт: допускаем ли мы абитуриента к вступительному экзамену?",
            reply_markup=reply_markup
        )
        return VERDICT
    
    async def get_verdict(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Шаг 13: Вердикт"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['verdict'] = update.message.text
        
        # Сохраняем данные в Google Sheets
        success = await self.save_to_sheet(context.user_data)
        
        if success:
            keyboard = [['Далее'], ['🔄 Перезапустить бот']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            await update.message.reply_text(
                "Спасибо!\n"
                "Чтобы отправить еще один отзыв, нажмите 'Далее'",
                reply_markup=reply_markup
            )
        else:
            keyboard = [['🔄 Перезапустить бот']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            await update.message.reply_text(
                "❌ Произошла ошибка при сохранении данных.\n\n"
                "Попробуйте еще раз, нажав '🔄 Перезапустить бот'",
                reply_markup=reply_markup
            )
        
        return CONFIRM
    
    async def confirm_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик кнопки 'Далее' - начинает новый опрос"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        # Очищаем данные и начинаем новый опрос
        context.user_data.clear()
        
        await update.message.reply_text(
            "🔄 Начинаем новый опрос!\n\n"
            "Здравствуйте!\n"
            "Поделитесь своим впечатлением от собеседования.\n\n"
            "Шаг 1: Введите ФИО абитуриента:",
            reply_markup=self.get_main_keyboard()
        )
        return FIO
    
    async def cancel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик отмены"""
        await update.message.reply_text(
            "Опрос отменен. Для начала нового нажмите /start.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    def create_application(self):
        """Создание приложения с обработчиками"""
        application = Application.builder().token(self.token).build()
        
        restart_filter = filters.Regex('^🔄 Перезапустить бот$')
        
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', self.start_handler),
                MessageHandler(restart_filter, self.restart_handler)
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
                    MessageHandler(filters.Regex('^Далее$'), self.confirm_next),
                    MessageHandler(restart_filter, self.restart_handler)
                ],
            },
            fallbacks=[
                CommandHandler('start', self.start_handler),
                MessageHandler(restart_filter, self.restart_handler),
                CommandHandler('cancel', self.cancel_handler)
            ],
            allow_reentry=True,
        )
        
        application.add_handler(CommandHandler('start', self.start_handler))
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
        return
    
    print("🚀 Запускаю бота...")
    
    # Добавляем диагностику
    print("\n🔍 Диагностика окружения:")
    print(f"Python версия: {sys.version}")
    print(f"Текущая директория: {os.getcwd()}")
    print(f"Существует credentials.json: {os.path.exists('credentials.json')}")
    
    bot = InterviewBot(BOT_TOKEN)
    application = bot.create_application()
    
    print("\n" + "="*50)
    if bot.google_connected:
        print("✅ БОТ ЗАПУЩЕН И РАБОТАЕТ!")
        print("✅ Google Sheets подключен!")
    else:
        print("⚠️  БОТ ЗАПУЩЕН В РЕЖИМЕ БЕЗ GOOGLE SHEETS")
        print("⚠️  Данные НЕ будут сохраняться в таблицу")
    print("="*50)
    print("📱 Имя вашего бота: (то, что вы указали в @BotFather)")
    print("💬 Команда для запуска: /start")
    print("🔄 Кнопка перезапуска доступна всегда")
    print("🔄 Кнопка 'Далее' для нового опроса в конце")
    print("="*50)
    
    # Запускаем бота
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()