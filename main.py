import logging
import os
import sys
import signal
import json
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class InterviewBot:
    def __init__(self, token):
        self.token = token
        self.sheet_service = None
        self.google_connected = False
        self.setup_google_sheets()
    
    def setup_google_sheets(self):
        """Настройка подключения к Google Sheets через Google API"""
        try:
            logger.info("🔧 Настраиваю Google Sheets API...")
            
            # Проверяем существование credentials.json
            if not os.path.exists('credentials.json'):
                logger.warning("❌ Файл credentials.json не найден, проверяю переменные окружения...")
                # Пробуем загрузить из переменных окружения
                creds_json = os.environ.get('GOOGLE_CREDENTIALS')
                if creds_json:
                    try:
                        creds_data = json.loads(creds_json)
                        with open('credentials.json', 'w') as f:
                            json.dump(creds_data, f)
                        logger.info("✅ Credentials загружены из переменной окружения GOOGLE_CREDENTIALS")
                    except Exception as e:
                        logger.error(f"❌ Ошибка загрузки credentials из env: {e}")
                        return False
                else:
                    logger.error("❌ GOOGLE_CREDENTIALS также не установлена в переменных окружения")
                    return False
            
            # Загружаем credentials
            try:
                creds = service_account.Credentials.from_service_account_file(
                    'credentials.json',
                    scopes=SCOPES
                )
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки credentials из файла: {e}")
                return False
            
            # Создаем сервис
            try:
                self.sheet_service = build('sheets', 'v4', credentials=creds)
                logger.info("✅ Сервис Google Sheets создан")
            except Exception as e:
                logger.error(f"❌ Ошибка создания сервиса Google Sheets: {e}")
                return False
            
            # Проверяем подключение к таблице
            try:
                logger.info("🔍 Проверяю подключение к таблице...")
                
                # Сначала пробуем получить информацию о таблице
                spreadsheet_info = self.sheet_service.spreadsheets().get(
                    spreadsheetId=SPREADSHEET_ID
                ).execute()
                
                logger.info(f"✅ Таблица найдена: {spreadsheet_info.get('properties', {}).get('title', 'Без названия')}")
                
                # Проверяем, есть ли заголовки
                result = self.sheet_service.spreadsheets().values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range='A1:I1'
                ).execute()
                
                headers = result.get('values', [])
                if headers:
                    logger.info(f"✅ Заголовки таблицы: {headers[0]}")
                else:
                    # Создаем заголовки если их нет
                    logger.info("📝 Создаю заголовки таблицы...")
                    if self._create_headers():
                        logger.info("✅ Заголовки успешно созданы")
                
                self.google_connected = True
                logger.info("✅ Google Sheets API подключен успешно!")
                return True
                
            except HttpError as error:
                logger.error(f"❌ Ошибка доступа к таблице: {error}")
                if error.resp.status == 403:
                    logger.error("⚠️  Нет доступа к таблице!")
                    logger.error("Service Account Email: telegram-bot-service@telegram-bot-sheets-485811.iam.gserviceaccount.com")
                    logger.error("1. Откройте таблицу в браузере")
                    logger.error("2. Нажмите 'Поделиться' (Share)")
                    logger.error("3. Добавьте email выше с правами 'Редактор' (Editor)")
                elif error.resp.status == 404:
                    logger.error(f"❌ Таблица не найдена! SPREADSHEET_ID: {SPREADSHEET_ID}")
                    logger.error("Проверьте правильность ID таблицы")
                else:
                    logger.error(f"❌ Неизвестная ошибка HTTP: {error.resp.status}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Общая ошибка подключения к Google Sheets: {e}", exc_info=True)
            return False
    
    def _create_headers(self):
        """Создание заголовков таблицы"""
        try:
            headers = [
                ["ФИО абитуриента", "Собеседующий", "Канонические препятствия",
                 "Духовник", "Впечатления", "Проблемы в учебе",
                 "Комментарии", "Вердикт", "Дата"]
            ]
            
            body = {
                'values': headers
            }
            
            self.sheet_service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range='A1:I1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            logger.info("✅ Заголовки созданы")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания заголовков: {e}")
            return False
    
    async def save_to_sheet(self, data):
        """Сохранение данных в Google Sheets"""
        if not self.google_connected or not self.sheet_service:
            logger.warning("⚠️  Данные НЕ сохранены (Google Sheets отключен)")
            await self.save_to_local_file(data)
            return False
        
        try:
            logger.info("💾 Начинаю сохранение данных в Google Sheets...")
            
            # Собираем впечатления из шагов 5-10
            impressions_parts = []
            for i in range(1, 7):
                key = f'impressions_{i}'
                value = data.get(key)
                if value and value != 'None' and value != '' and value != 'Затрудняюсь ответить':
                    impressions_parts.append(value)
            
            impressions_str = "; ".join(impressions_parts) if impressions_parts else ""
            
            # Формируем строку для записи
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
            
            # Очищаем данные
            row_data = ['' if cell is None else str(cell) for cell in row_data]
            
            logger.info(f"📝 Данные для сохранения:")
            for i, cell in enumerate(row_data):
                logger.info(f"  {chr(65+i)}: {cell}")
            
            # Определяем следующую строку
            try:
                result = self.sheet_service.spreadsheets().values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range='A:A',
                    majorDimension='COLUMNS'
                ).execute()
                
                values = result.get('values', [])
                
                if values and len(values) > 0:
                    # Считаем все непустые ячейки в колонке A
                    column_a = values[0]
                    # Фильтруем пустые строки
                    non_empty_cells = [cell for cell in column_a if cell and str(cell).strip()]
                    next_row = len(non_empty_cells) + 1
                    logger.info(f"📊 Найдено {len(non_empty_cells)} непустых ячеек в колонке A")
                else:
                    next_row = 2  # Начинаем со второй строки (после заголовков)
                    logger.info("📊 Таблица пуста, начинаем со строки 2")
                
                logger.info(f"📝 Буду записывать в строку {next_row}")
                
                # Подготовка данных для записи
                body = {
                    'values': [row_data]
                }
                
                # Записываем данные
                update_response = self.sheet_service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f'A{next_row}',
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                
                logger.info(f"✅ Данные успешно сохранены в строку {next_row}!")
                logger.info(f"📊 Обновлено ячеек: {update_response.get('updatedCells', 0)}")
                logger.info(f"📊 Обновлено строк: {update_response.get('updatedRows', 0)}")
                logger.info(f"📊 Обновлено колонок: {update_response.get('updatedColumns', 0)}")
                
                return True
                
            except HttpError as error:
                logger.error(f"❌ Ошибка при определении строки: {error}")
                # Пробуем записать в строку 2
                logger.info("🔄 Пробую записать в строку 2...")
                body = {
                    'values': [row_data]
                }
                
                update_response = self.sheet_service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range='A2',
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                
                logger.info(f"✅ Данные успешно сохранены в строку 2!")
                return True
                
        except HttpError as error:
            logger.error(f"❌ Ошибка Google Sheets API: {error}")
            if error.resp.status == 403:
                logger.error("⚠️  Нет прав на запись в таблицу!")
            await self.save_to_local_file(data)
            return False
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при сохранении: {e}", exc_info=True)
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
            
            # Также сохраняем в простом текстовом формате для удобства
            txt_filename = "backup_data.txt"
            with open(txt_filename, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                for key, value in data.items():
                    f.write(f"{key}: {value}\n")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в локальный файл: {e}")
            return False
    
    def get_main_keyboard(self):
        """Создает основную клавиатуру с кнопкой перезапуска"""
        keyboard = [['🔄 Перезапустить бот']]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработчик команды /start"""
        context.user_data.clear()
        
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
        if update.message.text == '🔄 Перезапустить бот':
            return await self.restart_handler(update, context)
        
        context.user_data['impressions_2'] = update.message.text
        
        keyboard = [
            ['Из церковной семьи', 'Из не церковной семьи'],
            ['Затрудняюсь ответить'],
            ['🔄 Перезапустить бot']
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
                "✅ Данные успешно сохранены в Google Sheets!\n\n"
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
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        print("💡 Установите переменную окружения BOT_TOKEN")
        print("💡 В Railway: Settings → Variables → Add New Variable")
        print("💡 Имя: BOT_TOKEN, Значение: ваш_токен_бота")
        return
    
    print("🚀 Запускаю бота...")
    
    print("\n🔍 ДИАГНОСТИКА:")
    print(f"Python версия: {sys.version}")
    print(f"Текущая директория: {os.getcwd()}")
    print(f"Файл credentials.json существует: {os.path.exists('credentials.json')}")
    print(f"BOT_TOKEN установлен: {'Да' if BOT_TOKEN else 'Нет'}")
    print(f"GOOGLE_CREDENTIALS установлена: {'Да' if os.environ.get('GOOGLE_CREDENTIALS') else 'Нет'}")
    print(f"Spreadsheet ID: {SPREADSHEET_ID}")
    print(f"Service Account Email: telegram-bot-service@telegram-bot-sheets-485811.iam.gserviceaccount.com")
    print("="*50)
    
    bot = InterviewBot(BOT_TOKEN)
    application = bot.create_application()
    
    print("\n" + "="*50)
    if bot.google_connected:
        print("✅ GOOGLE SHEETS ПОДКЛЮЧЕН УСПЕШНО!")
        print("✅ Данные будут сохраняться напрямую в таблицу")
    else:
        print("⚠️  GOOGLE SHEETS НЕ ПОДКЛЮЧЕН")
        print("⚠️  Данные будут сохраняться в локальный файл backup_data.json")
        print("\n💡 РЕКОМЕНДАЦИИ:")
        print("1. Откройте таблицу: https://docs.google.com/spreadsheets/d/1JvUD3CSFdgtsUVqir6zUfB5oC42NtP4YGOlZOVNRLho")
        print("2. Нажмите 'Поделиться' (Share)")
        print("3. Добавьте email: telegram-bot-service@telegram-bot-sheets-485811.iam.gserviceaccount.com")
        print("4. Дайте права 'Редактор' (Editor)")
        print("5. Перезапустите бота")
    print("="*50)
    print("🤖 Бот запущен!")
    print("📱 Используйте команду /start для начала опроса")
    print("🔄 Кнопка 'Перезапустить бот' доступна всегда")
    print("="*50)
    
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()