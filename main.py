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
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_data, scope)
            client = gspread.authorize(creds)
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
            logger.error(f"❌ Ошибка Google Sheets: {e}")
            self.google_connected = False
            return False
    
    async def save_to_sheet(self, data):
        """Сохранение данных в Google Sheets"""
        if not self.google_connected:
            logger.warning("⚠️  Данные НЕ сохранены (Google Sheets отключен)")
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
    
    # ВСТАВЬТЕ СЮДА ВСЕ ОСТАЛЬНЫЕ ФУНКЦИИ ИЗ ВАШЕГО ИСХОДНОГО КОДА
    # (get_interviewer, get_canonical_obstacles, get_spiritual_guide, и т.д.)
    # КОПИРУЙТЕ ИХ ИЗ ВАШЕГО СТАРОГО ФАЙЛА main.py
    
    async def get_interviewer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Получение информации о собеседующем"""
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
    
    # ПРОДОЛЖАЙТЕ ВСТАВЛЯТЬ ВСЕ ОСТАЛЬНЫЕ ФУНКЦИИ...
    # (вставьте ВСЕ функции до метода create_application)
    
    def create_application(self):
        """Создание приложения с обработчиками"""
        application = Application.builder().token(self.token).build()
        
        restart_filter = filters.Regex('^🔄 Перезапустить бот$')
        
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
    
    bot = InterviewBot(BOT_TOKEN)
    application = bot.create_application()
    
    print("\n" + "="*50)
    print("✅ БОТ ЗАПУЩЕН И РАБОТАЕТ!")
    print("="*50)
    print("📱 Имя вашего бота: (то, что вы указали в @BotFather)")
    print("💬 Команда для запуска: /start")
    print("🔄 Кнопка перезапуска доступна всегда")
    print("="*50)
    
    # Запускаем бота
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()
