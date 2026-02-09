
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
import os
import sys
import signal
from datetime import datetime
import time

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
        self.last_error = None
        self.setup_google_sheets()
    
    def setup_google_sheets(self):
        """Настройка подключения к Google Sheets с подробной диагностикой"""
        try:
            logger.info("="*50)
            logger.info("🔧 НАЧИНАЮ ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS")
            logger.info("="*50)
            
            # 1. Проверяем наличие файла
            if not os.path.exists('credentials.json'):
                logger.error("❌ Файл credentials.json не найден!")
                self.google_connected = False
                return False
            
            logger.info("✅ Файл credentials.json найден")
            
            # 2. Читаем файл
            with open('credentials.json', 'r') as f:
                creds_data = json.load(f)
            
            # 3. Проверяем обязательные поля
            required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email', 'client_id']
            missing_fields = [field for field in required_fields if field not in creds_data]
            
            if missing_fields:
                logger.error(f"❌ Отсутствуют поля: {missing_fields}")
                return False
            
            logger.info(f"✅ Все обязательные поля присутствуют")
            logger.info(f"📧 Client email: {creds_data['client_email']}")
            logger.info(f"🔑 Private key ID: {creds_data['private_key_id'][:20]}...")
            
            # 4. Проверяем формат private_key
            private_key = creds_data['private_key']
            if private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                logger.info("✅ Private key имеет правильный формат")
            else:
                logger.warning("⚠️ Private key может иметь неправильный формат")
                # Пробуем исправить
                if '\\n' in private_key:
                    private_key = private_key.replace('\\n', '\n')
                    creds_data['private_key'] = private_key
                    logger.info("✅ Заменены \\n на переносы строк")
            
            # 5. Проверяем время сервера
            server_time = datetime.utcnow()
            logger.info(f"⏰ Время сервера (UTC): {server_time}")
            
            # 6. Настраиваем scope
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
            
            logger.info("🔄 Создаю credentials...")
            
            # 7. Создаем credentials
            try:
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_data, scope)
                logger.info("✅ Credentials созданы успешно")
            except Exception as e:
                logger.error(f"❌ Ошибка создания credentials: {e}")
                return False
            
            # 8. Авторизуемся
            logger.info("🔐 Авторизуюсь в Google API...")
            try:
                client = gspread.authorize(creds)
                logger.info("✅ Авторизация успешна")
            except Exception as e:
                logger.error(f"❌ Ошибка авторизации: {e}")
                return False
            
            # 9. Открываем таблицу
            logger.info(f"📊 Открываю таблицу с ID: {SPREADSHEET_ID}")
            try:
                spreadsheet = client.open_by_key(SPREADSHEET_ID)
                logger.info("✅ Таблица найдена")
            except Exception as e:
                logger.error(f"❌ Не удалось открыть таблицу: {e}")
                logger.error("⚠️  Проверьте:")
                logger.error("1. Правильность Spreadsheet ID")
                logger.error(f"2. Доступ для сервисного аккаунта: {creds_data['client_email']}")
                logger.error("3. Что таблица существует и доступна")
                return False
            
            # 10. Получаем лист
            try:
                worksheet = spreadsheet.worksheet(SHEET_NAME)
                logger.info(f"✅ Лист '{SHEET_NAME}' найден")
            except Exception as e:
                logger.warning(f"⚠️  Лист '{SHEET_NAME}' не найден, использую первый лист: {e}")
                worksheet = spreadsheet.get_worksheet(0)
            
            if not worksheet:
                logger.error("❌ Не удалось получить лист таблицы")
                return False
            
            self.sheet = worksheet
            self.google_connected = True
            
            # 11. Проверяем доступ на запись
            try:
                # Пробуем прочитать заголовки
                headers = worksheet.row_values(1)
                if headers:
                    logger.info(f"✅ Заголовки найдены: {headers}")
                else:
                    # Создаем заголовки
                    headers = [
                        "ФИО абитуриента", "Собеседующий", "Канонические препятствия",
                        "Духовник", "Впечатления", "Проблемы в учебе",
                        "Комментарии", "Вердикт", "Дата"
                    ]
                    worksheet.append_row(headers)
                    logger.info("✅ Созданы новые заголовки")
                
                logger.info("="*50)
                logger.info("✅ GOOGLE SHEETS ПОДКЛЮЧЕН УСПЕШНО!")
                logger.info("="*50)
                return True
                
            except Exception as e:
                logger.error(f"❌ Ошибка проверки доступа: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при подключении: {e}", exc_info=True)
            self.google_connected = False
            return False
    
    async def save_to_sheet(self, data):
        """Сохранение данных в Google Sheets"""
        if not self.google_connected:
            logger.warning("⚠️  Данные НЕ сохранены (Google Sheets отключен)")
            # Можно добавить локальное сохранение в файл как временное решение
            await self.save_to_local_file(data)
            return False
        
        try:
            logger.info("💾 Начинаю сохранение данных в Google Sheets...")
            
            # Собираем впечатления из шагов 5-10
            impressions_parts = []
            for i in range(1, 7):
                key = f'impressions_{i}'
                value = data.get(key)
                if value and value != 'None' and value != '':
                    impressions_parts.append(value)
            
            impressions_str = "; ".join(impressions_parts) if impressions_parts else ""
            
            # Формируем строку для записи (9 столбцов A-I)
            row_data = [
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
            
            # Очищаем данные от None
            row_data = ['' if cell is None else str(cell) for cell in row_data]
            
            logger.info(f"📝 Данные для сохранения: {row_data}")
            
            # Пробуем сохранить с повторными попытками
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.sheet.append_row(row_data)
                    logger.info(f"✅ Данные успешно сохранены в строку {self.sheet.row_count}")
                    
                    # Выводим подтверждение в логи
                    logger.info("="*50)
                    logger.info("✅ ДАННЫЕ УСПЕШНО СОХРАНЕНЫ В GOOGLE SHEETS")
                    logger.info("="*50)
                    
                    return True
                    
                except Exception as e:
                    logger.error(f"❌ Попытка {attempt + 1}/{max_retries} не удалась: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Ждем 2 секунды перед повторной попыткой
                    else:
                        # Сохраняем локально как fallback
                        await self.save_to_local_file(data)
                        return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка при подготовке данных: {e}", exc_info=True)
            await self.save_to_local_file(data)
            return False
    
    async def save_to_local_file(self, data):
        """Сохранение данных в локальный файл как временное решение"""
        try:
            filename = "backup_data.json"
            file_data = []
            
            # Читаем существующие данные если файл есть
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    try:
                        file_data = json.load(f)
                    except:
                        file_data = []
            
            # Добавляем новые данные
            data_with_timestamp = data.copy()
            data_with_timestamp['saved_at'] = datetime.now().isoformat()
            file_data.append(data_with_timestamp)
            
            # Сохраняем
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Данные сохранены в локальный файл {filename}")
            logger.warning("⚠️  Эти данные нужно будет вручную перенести в Google Sheets")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в локальный файл: {e}")
    
    def get_main_keyboard(self):
        """Создает основную клавиатуру с кнопкой перезапуска"""
        keyboard = [['🔄 Перезапустить бот']]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик команды /start"""
        # Очищаем данные предыдущего опроса
        context.user_data.clear()
        
        # Показываем статус подключения
        status_msg = "✅ Google Sheets подключен" if self.google_connected else "⚠️  Google Sheets отключен - данные сохраняются локально"
        
        await update.message.reply_text(
            f"Здравствуйте!\n"
            f"Поделитесь своим впечатлением от собеседования.\n\n"
            f"Статус: {status_msg}\n\n"
            f"Шаг 1: Введите ФИО абитуриента:",
            reply_markup=self.get_main_keyboard()
        )
        return FIO
    
    async def restart_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик кнопки '🔄 Перезапустить бот'"""
        # Очищаем данные предыдущего опроса
        context.user_data.clear()
        
        status_msg = "✅ Google Sheets подключен" if self.google_connected else "⚠️  Google Sheets отключен - данные сохраняются локально"
        
        await update.message.reply_text(
            f"🔄 Бот перезапущен!\n\n"
            f"Здравствуйте!\n"
            f"Поделитесь своим впечатлением от собеседования.\n\n"
            f"Статус: {status_msg}\n\n"
            f"Шаг 1: Введите ФИО абитуриента:",
            reply_markup=self.get_main_keyboard()
        )
        return FIO
    
    # ОСТАЛЬНЫЕ МЕТОДЫ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ
    # (get_fio, get_interviewer, get_canonical_obstacles и т.д.)
    # Я вставлю их как есть из предыдущего корректного кода
    
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
            ['🔄 Перезапустить бot']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            "Шаг 6: Продолжаем",
            reply_markup=reply_markup
        )
        return IMPRESSIONS_2
    
    async def get_impressions_2(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Шаг 6: Как давно в церкви"""
        if update.message.text == '🔄 Перезапустить бот':
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
        
        # Сохраняем данные
        success = await self.save_to_sheet(context.user_data)
        
        if success:
            keyboard = [['Далее'], ['🔄 Перезапустить бот']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            await update.message.reply_text(
                "✅ Данные успешно сохранены!\n\n"
                "Спасибо!\n"
                "Чтобы отправить еще один отзыв, нажмите 'Далее'",
                reply_markup=reply_markup
            )
        else:
            if self.google_connected:
                message = "❌ Произошла ошибка при сохранении в Google Sheets.\nДанные сохранены локально."
            else:
                message = "⚠️  Google Sheets отключен. Данные сохранены локально в backup_data.json"
            
            keyboard = [['Далее'], ['🔄 Перезапустить бот']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            await update.message.reply_text(
                f"{message}\n\n"
                "Спасибо!\n"
                "Чтобы отправить еще один отзыв, нажмите 'Далее'",
                reply_markup=reply_markup
            )
        
        return CONFIRM
    
    async def confirm_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик кнопки 'Далее' - начинает новый опрос"""
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        # Очищаем данные и начинаем новый опрос
        context.user_data.clear()
        
        status_msg = "✅ Google Sheets подключен" if self.google_connected else "⚠️  Google Sheets отключен - данные сохраняются локально"
        
        await update.message.reply_text(
            f"🔄 Начинаем новый опрос!\n\n"
            f"Здравствуйте!\n"
            f"Поделитесь своим впечатлением от собеседования.\n\n"
            f"Статус: {status_msg}\n\n"
            f"Шаг 1: Введите ФИО абитуриента:",
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
    
    # Диагностика
    print("\n🔍 ДИАГНОСТИКА:")
    print(f"Python версия: {sys.version}")
    print(f"Текущая директория: {os.getcwd()}")
    print(f"Файл credentials.json существует: {os.path.exists('credentials.json')}")
    print(f"Spreadsheet ID: {SPREADSHEET_ID}")
    print(f"Service Account email: telegram-bot-service@telegram-bot-sheets-485811.iam.gserviceaccount.com")
    print("="*50)
    
    bot = InterviewBot(BOT_TOKEN)
    application = bot.create_application()
    
    print("\n" + "="*50)
    if bot.google_connected:
        print("✅ GOOGLE SHEETS ПОДКЛЮЧЕН УСПЕШНО!")
    else:
        print("⚠️  GOOGLE SHEETS НЕ ПОДКЛЮЧЕН")
        print("⚠️  Данные будут сохраняться в локальный файл backup_data.json")
        print("⚠️  ПРОВЕРЬТЕ:")
        print("1. Что сервисный аккаунт добавлен в Google Sheets как редактор")
        print(f"2. Email: telegram-bot-service@telegram-bot-sheets-485811.iam.gserviceaccount.com")
        print("3. Правильность Spreadsheet ID")
        print("4. Доступность таблицы")
    print("="*50)
    print("🤖 Бот запущен!")
    print("📱 Используйте команду /start для начала опроса")
    print("🔄 Кнопка 'Перезапустить бот' доступна всегда")
    print("="*50)
    
    # Запускаем бота
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()