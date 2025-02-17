import logging
import asyncio
import re
import time
import traceback  # Добавляем импорт time
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile  # Добавляем импорт в начало файла
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from datetime import datetime, timedelta, timezone
import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.connection import MySQLConnection
from mysql.connector.pooling import MySQLConnectionPool
# from aiogram.dispatcher import FSMContext
# from aiogram.dispatcher.filters.state import State, StatesGroup

# Убираем неиспользуемые импорты и добавляем новые
import sys
from threading import Thread
from pymongo import MongoClient

# Добавляем после импортов
from datetime import datetime, timedelta
import asyncio
from typing import Dict, Set

# Добавляем новые импорты в начало файла после существующих
import signal
import aiohttp
from aiogram.exceptions import TelegramAPIError

# Добавляем импорт в начало файла
import signal
import sys
import atexit

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

# Получаем API токен из файла
with open("API.txt", "r") as file:
    API_TOKEN = file.read().strip()

# Получаем настройки базы данных из файла
def load_db_config():
    with open("db1.txt", "r", encoding='utf-8') as file:
        lines = file.readlines()
    return {
        "host": lines[0].strip(),
        "user": lines[1].strip(),
        "password": lines[2].strip(),
        "database": lines[3].strip(),
        "port": int(lines[4].strip())
    }

db_config = load_db_config()

# Получаем ID администраторов из файла
def load_admin_ids():
    with open("admin.txt", "r", encoding='utf-8') as file:
        return [int(line.strip()) for line in file.readlines()]

ADMIN_IDS = load_admin_ids()

# Создаем бота и диспетчер
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
router = Router()
dp = Dispatcher(storage=storage)
dp.include_router(router)

# Обновляем функцию подключения к базе данных
def get_db_connection():
    # Добавляем задержку перед первым подключением
    if not hasattr(get_db_connection, 'initialized'):
        time.sleep(2)  # Даем время на инициализацию модулей
        get_db_connection.initialized = True
    
    config = db_config.copy()
    config.update({
        'use_pure': True,  # Используем чистый Python имплементацию
        'connection_timeout': 15,
        # Удаляем проблемные параметры
        'get_warnings': False,
        'raise_on_warnings': False
    })
    
    try:
        return MySQLConnection(**config)  # Используем прямой класс подключения
    except mysql.connector.Error as err:
        log_error(f"Database connection error: {err}")
        raise

# Заменяем прямое создание таблиц на функцию инициализации
def init_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем существование таблиц
        cursor.execute("SHOW TABLES")
        existing_tables = {table[0] for table in cursor.fetchall()}
        
        # Список необходимых таблиц и их структуры
        tables = {
            'users': '''CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id VARCHAR(255),
                name VARCHAR(255),
                phone_number VARCHAR(50),
                email VARCHAR(255),
                english_level INT,
                modern_pc VARCHAR(10),
                response_date DATETIME,
                hr VARCHAR(255)
            )''',
            'feedback': '''CREATE TABLE IF NOT EXISTS feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id VARCHAR(255),
                feedback TEXT,
                response_date DATETIME
            )''',
            'admin_logs': '''CREATE TABLE IF NOT EXISTS admin_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                action VARCHAR(255),
                user_id VARCHAR(255),
                admin_id VARCHAR(255),
                timestamp DATETIME
            )''',
            'anonymous_feedback': '''CREATE TABLE IF NOT EXISTS anonymous_feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                feedback TEXT,
                response_date DATETIME
            )''',
            'reviews': '''CREATE TABLE IF NOT EXISTS reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                review TEXT,
                timestamp DATETIME
            )''',
            'interview_notifications': '''CREATE TABLE IF NOT EXISTS interview_notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                admin_id VARCHAR(255),
                user_tg_id VARCHAR(255),
                message_id INT
            )''',
            'user_logs': '''CREATE TABLE IF NOT EXISTS user_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id VARCHAR(255),
                action VARCHAR(255),
                status VARCHAR(50),
                timestamp DATETIME
            )'''
        }
        
        # Создаем только отсутствующие таблицы
        for table_name, create_sql in tables.items():
            if table_name not in existing_tables:
                print(f"Creating table {table_name}")
                cursor.execute(create_sql)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialization completed")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

# Заменяем старый блок создания таблиц на вызов функции
try:
    init_database()
except Exception as e:
    print(f"Failed to initialize database: {e}")
    sys.exit(1)

# Определяем состояния для FSM
class Form(StatesGroup):
    name = State()
    phone_number = State()
    email = State()
    english_level = State()
    modern_pc = State()
    confirm_text1 = State()
    confirm_text2 = State()
    video_interview = State()
    anonymous_feedback = State()
    waiting_feedback = State()  # добавляем новое состояние

# Состояния для FSM
class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()

# Клавиатуры
keyboard_yes_no = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Yes"), KeyboardButton(text="No")],
        [KeyboardButton(text="I need human help")]
    ],
    resize_keyboard=True
)

keyboard_start = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/start")]
    ],
    resize_keyboard=True
)

# Добавляем словарь пресетов перед основным кодом
preset_messages = {
    "Alex": """Hello! 🤝 This is Sergiy, the Staff Manager. I checked your task and it looks good! 
    👉I'm moving you to the next step and sharing your contact with our manager, Alex. He'll be in touch to teach you how to navigate the website. You can also reach him directly at: @agencytopmanager

Good luck and have a good day! 🌻""",
    "Stacy": """Hello! 🤝 This is Sergiy, the Staff Manager. I checked your task and it looks good! 
    👉I'm moving you to the next step and sharing your contact with our manager, Stacy. She'll be in touch to teach you how to navigate the website. You can also reach her directly at: 
@nakoz15

Good luck and have a good day!""",
    "Mila": """Hello! 🤝 This is Sergiy, the Staff Manager. I checked your task and it looks good! 
    👉I'm moving you to the next step and sharing your contact with our manager, Mila. She'll be in touch to teach you how to navigate the website. You can also reach her directly at: 
@Lyudmila_Burenko

Good luck and have a good day!""",
    "Nadia": """Hello! 🤝 This is Sergiy, the Staff Manager. I checked your task and it looks good! 
    👉I'm moving you to the next step and sharing your contact with our manager, Nadia. She'll be in touch to teach you how to navigate the website. You can also reach her directly at: 
@starnuit

Good luck and have a good day!""",
    "Phrase": """I reviewed your assignment, but it needs some improvements. The phrases you put together aren't exactly what's required. Please take another look at the instructions and examples and try to create something similar. You have one last chance to complete the task, and 24 hours to do so. Thank you.""",
    "Letter": """I reviewed your assignment, but it needs some improvements. The letter you composed isn't exactly what's required. Please take another look at the instructions and examples and try to create something similar. You have one last chance to complete the task, and 24 hours to do so. Thank you.""",
    "Finish": """After reviewing your resubmitted assignment, we regret to inform you that we are unable to offer you a position at this time. However, you are welcome to reapply in six months. Thank you for your time and interest in our company.""",
    "Bad": """Sorry, but we couldn't find a video interview associated with your name. Please make sure that you have submitted the video interview and used the same name and information when filling out the bot. You can start over anytime by using the /start command.""",
}

# Создаем класс для управления блокировками
class LockManager:
    def __init__(self):
        self.locks: Dict[int, datetime] = {}
        self.message_locks: Dict[str, Set[int]] = {}
        self.LOCK_DURATION = timedelta(minutes=5)
        self.CLEANUP_INTERVAL = 300  # 5 минут

    def is_locked(self, user_id: int) -> bool:
        if user_id not in self.locks:
            return False
        if datetime.now() - self.locks[user_id] > self.LOCK_DURATION:
            self.locks.pop(user_id, None)  # Безопасное удаление
            return False
        return True

    def add_lock(self, user_id: int) -> None:
        self.locks[user_id] = datetime.now()

    def is_message_processed(self, user_id: int, state: str) -> bool:
        if state not in self.message_locks:
            self.message_locks[state] = set()
            return False
        return user_id in self.message_locks[state]

    def mark_message_processed(self, user_id: int, state: str) -> None:
        if state not in self.message_locks:
            self.message_locks[state] = set()
        self.message_locks[state].add(user_id)

    async def cleanup_locks(self):
        while True:
            await asyncio.sleep(self.CLEANUP_INTERVAL)
            current_time = datetime.now()
            # Очистка временных блокировок
            self.locks = {
                user_id: lock_time
                for user_id, lock_time in self.locks.items()
                if current_time - lock_time <= self.LOCK_DURATION
            }
            # Очистка обработанных сообщений
            self.message_locks.clear()

# Создаем экземпляр LockManager
lock_manager = LockManager()

# Обработка команды /start
@router.message(Command(commands=["start"]))
async def start_command(message: types.Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        
        if lock_manager.is_locked(user_id):
            await message.reply("Please wait 5 minutes before starting a new registration.")
            return

        lock_manager.add_lock(user_id)
        
        # Проверяем соединение с базой данных
        try:
            conn = get_db_connection()
            conn.close()
        except Exception as e:
            log_error("Database connection error in start_command", e)
            await message.reply("Service temporarily unavailable. Please try again in a few minutes.")
            return

        await message.reply("Welcome to LERA agency! Please provide your name:")
        await state.set_state(Form.name)
        await log_user_action(user_id, "start_command", "success")
        
    except Exception as e:
        log_error("Error in start_command", e)
        await message.reply("An error occurred. Please try again or contact support.")
        await log_user_action(user_id, "start_command", "error")

# Обработка команды /preset Good {telegramid}
@router.message(Command(commands=["preset"]))
async def preset_command(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        command_parts = message.text.split()
        if len(command_parts) == 3:
            preset_name = command_parts[1]
            telegram_id = command_parts[2]
            
            if preset_name in preset_messages:
                try:
                    await bot.send_message(telegram_id, preset_messages[preset_name])
                    await message.reply(f"Preset message '{preset_name}' sent to {telegram_id}")
                except Exception as e:
                    await message.reply(f"Failed to send message to {telegram_id}: {e}")
            elif preset_name == "Good":
                try:
                    # Отправляем текст
                    with open("3.txt", "r", encoding='utf-8') as file:
                        text3 = file.read()
                    await bot.send_message(telegram_id, text3)
                    
                    # Отправляем видео, используя FSInputFile
                    try:
                        video = FSInputFile("3.mp4")
                        await bot.send_video(telegram_id, video)
                        await message.reply(f"Text and video sent to {telegram_id}")
                    except Exception as video_error:
                        await message.reply(f"Text sent but failed to send video: {video_error}")
                        
                except Exception as e:
                    await message.reply(f"Failed to send message to {telegram_id}: {e}")
            else:
                available_presets = ", ".join(list(preset_messages.keys()) + ["Good"])
                await message.reply(f"Invalid preset. Available presets: {available_presets}")
        else:
            await message.reply("Invalid command format. Use /preset <preset_name> <telegram_id>")
    else:
        await message.reply("You are not authorized to use this command.")

# Обработка команды /work {telegramid}
@router.message(Command(commands=["work"]))
async def work_command(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        command_parts = message.text.split()
        if len(command_parts) == 2:
            user_tg_id = command_parts[1]
            conn = get_db_connection()
            cursor = conn.cursor()

            # 1. Записываем ID админа в столбец HR
            cursor.execute("""
                UPDATE users 
                SET hr = %s, 
                    response_date = response_date  # Добавляем это чтобы точно обновилась запись
                WHERE telegram_id = %s
            """, (str(message.from_user.id), user_tg_id))

            # 2. Удаляем сообщения о видеоинтервью у ВСЕХ админов
            cursor.execute("""
                SELECT DISTINCT admin_id, message_id 
                FROM interview_notifications 
                WHERE user_tg_id = %s
            """, (user_tg_id,))
            
            notifications = cursor.fetchall()
            for admin_id, msg_id in notifications:
                try:
                    await bot.delete_message(chat_id=admin_id, message_id=msg_id)
                    print(f"Deleted message {msg_id} for admin {admin_id}")
                except Exception as e:
                    print(f"Could not delete message {msg_id} for admin {admin_id}: {e}")

            # Удаляем записи из таблицы уведомлений
            cursor.execute("DELETE FROM interview_notifications WHERE user_tg_id = %s", (user_tg_id,))

            # Проверяем, что изменения применились
            if cursor.rowcount > 0:
                print(f"Successfully deleted {cursor.rowcount} notification(s)")

            conn.commit()
            conn.close()

            await message.reply(f"✅ HR assigned: {message.from_user.id}\n🗑 Interview notifications cleared")
        else:
            await message.reply("Invalid command format. Use /work {telegramid}")
    else:
        await message.reply("You are not authorized to use this command.")

# Обработка ввода имени
@router.message(StateFilter(Form.name))
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.reply("Please provide your phone number (e.g., +123456789):")
    await state.set_state(Form.phone_number)

# Обработка ввода номера телефона
@router.message(StateFilter(Form.phone_number))
async def process_phone_number(message: types.Message, state: FSMContext):
    phone_number = message.text
    if re.match(r'^[\d\+\-\(\) ]+$', phone_number):
        await state.update_data(phone_number=phone_number)
        await message.reply("Please provide your email:")
        await state.set_state(Form.email)
    else:
        await message.reply("Please provide a valid phone number (digits, +, -, (, ) and spaces are allowed):")

# Обработка ввода email
@router.message(StateFilter(Form.email))
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    if re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        await state.update_data(email=email)
        await message.reply("Rate your English level from 1 to 10:")
        await state.set_state(Form.english_level)
    else:
        await message.reply("Please provide a valid email address:")

# Обработка уровня английского
@router.message(StateFilter(Form.english_level))
async def process_english_level(message: types.Message, state: FSMContext):
    try:
        english_level = int(message.text)
        if 1 <= english_level <= 10:
            await state.update_data(english_level=english_level)
            await message.reply("Do you have a modern PC or Laptop?", reply_markup=keyboard_yes_no)
            await state.set_state(Form.modern_pc)
        else:
            await message.reply("Please provide a valid number between 1 and 10.")
    except ValueError:
        await message.reply("Please provide a valid number between 1 and 10.")

# Функция для логирования действий пользователя
async def log_user_action(telegram_id, action, status="completed"):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO user_logs (telegram_id, action, status, timestamp)
                         VALUES (%s, %s, %s, %s)''',
                      (telegram_id, action, status, datetime.now(timezone.utc)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging user action: {e}")

# Обработка ответа на вопрос о наличии современного ПК
@router.message(StateFilter(Form.modern_pc))
async def process_modern_pc(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    if lock_manager.is_message_processed(user_id, str(current_state)):
        return

    if message.text.upper() in ["YES", "NO"]:
        lock_manager.mark_message_processed(user_id, str(current_state))
        if message.text.upper() in ["YES", "NO"]:
            await state.update_data(modern_pc=message.text)
            data = await state.get_data()

            # Записываем данные в базу
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO users (telegram_id, name, phone_number, email, english_level, modern_pc, response_date)
                              VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                           (message.from_user.id, data['name'], data['phone_number'], data['email'],
                            data['english_level'], data['modern_pc'], datetime.now(timezone.utc)))
            conn.commit()
            conn.close()

            # Логируем регистрацию
            await log_user_action(message.from_user.id, "registration", "completed")

            try:
                # Отправляем текст
                with open("1.txt", "r", encoding='utf-8') as file:
                    text1 = file.read()
                await message.reply(text1, reply_markup=keyboard_yes_no, disable_web_page_preview=True)
                
                # Отправляем видео
                try:
                    video = FSInputFile("1.mp4")
                    await bot.send_video(message.chat.id, video)
                except Exception as video_error:
                    print(f"Failed to send video 1: {video_error}")
                    await log_user_action(message.from_user.id, "send_video_1", "failed")
                
                await state.set_state(Form.confirm_text1)
                await log_user_action(message.from_user.id, "received_text_1")
                
            except Exception as e:
                print(f"Error in process_modern_pc: {e}")
                await log_user_action(message.from_user.id, "text_1_delivery", "failed")
                await message.reply("An error occurred. Please try again or contact support.")
        else:
            await message.reply("Please respond with Yes or No.")

# Обработка подтверждения текста 1
@router.message(StateFilter(Form.confirm_text1))
async def process_confirm_text1(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    if lock_manager.is_message_processed(user_id, str(current_state)):
        return

    if message.text.upper() == "YES":
        lock_manager.mark_message_processed(user_id, str(current_state))
        await log_user_action(message.from_user.id, "confirmed_text_1")
        try:
            # Отправляем текст
            with open("2.txt", "r", encoding='utf-8') as file:
                text2 = file.read()
            await message.reply(text2, reply_markup=keyboard_yes_no)
            
            # Отправляем видео
            try:
                video = FSInputFile("2.mp4")
                await bot.send_video(message.chat.id, video)
            except Exception as video_error:
                print(f"Failed to send video: {video_error}")
            
            await state.set_state(Form.confirm_text2)
            await log_user_action(message.from_user.id, "received_text_2")
        except Exception as e:
            await log_user_action(message.from_user.id, "text_2_delivery", "failed")
            print(f"Error in process_confirm_text1: {e}")
            await message.reply("An error occurred. Please try again or contact support.")
            
    elif message.text.upper() == "NO":
        await log_user_action(message.from_user.id, "rejected_text_1")
        await message.reply("We're sorry. But are you sure?", reply_markup=keyboard_yes_no)
        await state.set_state(Form.anonymous_feedback)
    elif message.text.upper() == "I NEED HUMAN HELP":
        await message.reply("Please contact our HR on Telegram: @HR_LERA_Meneger")
    else:
        await message.reply("You wrote something off-script. Sorry, I don't know how to respond. You can always start over by clicking the /start button.", reply_markup=keyboard_start)

# Обработка анонимного отзыва
@router.message(StateFilter(Form.anonymous_feedback))
async def process_anonymous_feedback(message: types.Message, state: FSMContext):
    if message.text.upper() == "YES":
        await message.reply(
            "Please provide us with feedback about what confused you about our vacancy. "
            "Your response will help us improve for future candidates. Thank you!"
        )
        await state.set_state(Form.waiting_feedback)
    elif message.text.upper() == "NO":
        with open("1.txt", "r", encoding='utf-8') as file:
            text1 = file.read()
        await message.reply(text1, reply_markup=keyboard_yes_no)
        await state.set_state(Form.confirm_text1)
    else:
        await message.reply("Please respond with Yes or No.")

# Обработка подтверждения текста 2
@router.message(StateFilter(Form.confirm_text2))
async def process_confirm_text2(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    if lock_manager.is_message_processed(user_id, str(current_state)):
        return

    if message.text.upper() == "YES":
        lock_manager.mark_message_processed(user_id, str(current_state))
        await log_user_action(message.from_user.id, "confirmed_text_2")
        await message.reply("👉 Did you complete the video interview? 👈 Please come back here and ❗️click Yes only if you have already completed the video interview.", reply_markup=keyboard_yes_no)
        await state.set_state(Form.video_interview)
    elif message.text.upper() == "NO":
        await log_user_action(message.from_user.id, "rejected_text_2")
        await message.reply("Did you complete the video interview?", reply_markup=keyboard_yes_no)
    elif message.text.upper() == "I NEED HUMAN HELP":
        await message.reply("Please contact our HR on Telegram: @HR_LERA_Meneger")
    else:
        await message.reply("You wrote something off-script. Sorry, I don't know how to respond. You can always start over by clicking the /start button.", reply_markup=keyboard_start)

# Обработка состояния Form.video_interview
@router.message(StateFilter(Form.video_interview))
async def process_video_interview(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    if lock_manager.is_message_processed(user_id, str(current_state)):
        return

    if message.text.upper() == "YES":
        lock_manager.mark_message_processed(user_id, str(current_state))
        await log_user_action(message.from_user.id, "completed_video_interview")
        conn = get_db_connection()
        cursor = conn.cursor()
        for admin_id in ADMIN_IDS:
            try:
                sent_msg = await bot.send_message(admin_id, f"User with ID {message.from_user.id} passed the video interview. Please check.")
                cursor.execute('''INSERT INTO interview_notifications (admin_id, user_tg_id, message_id)
                                  VALUES (%s, %s, %s)''',
                               (admin_id, message.from_user.id, sent_msg.message_id))
            except Exception as e:
                print(f"Failed to send message to admin {admin_id}: {e}")
        conn.commit()
        conn.close()
        await message.reply("Thank you! I have sent a request to HR to review your video interview. This usually takes between 24 to 48 hours. Please wait for our response.", reply_markup=keyboard_start)
        await state.clear()
    elif message.text.upper() == "NO":
        await log_user_action(message.from_user.id, "not_completed_video_interview")
        await message.reply("Did you complete the video interview?", reply_markup=keyboard_yes_no)
    elif message.text.upper() == "I NEED HUMAN HELP":
        await message.reply("Please contact our HR on Telegram: @HR_LERA_Meneger", reply_markup=keyboard_start)
    else:
        await message.reply("You wrote something off-script. Sorry, I don't know how to respond. You can always start over by clicking the /start button.", reply_markup=keyboard_start)

# Обработка отзыва
@router.message(StateFilter(Form.waiting_feedback))
async def process_feedback_text(message: types.Message, state: FSMContext):
    # Получаем имя пользователя из сохраненных данных
    data = await state.get_data()
    name = data.get('name', 'Anonymous')
    
    # Подключаемся к базе данных из db2.txt
    with open("db2.txt", "r", encoding='utf-8') as file:
        lines = file.readlines()
        db2_config = {
            "host": lines[0].strip(),
            "user": lines[1].strip(),
            "password": lines[2].strip(),
            "database": lines[3].strip(),
            "port": int(lines[4].strip()),
        }
    
    # Сохраняем отзыв
    conn = mysql.connector.connect(**db2_config)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO reviews (name, review, timestamp)
                     VALUES (%s, %s, %s)''', (name, message.text, datetime.now(timezone.utc)))
    conn.commit()
    conn.close()

    await message.reply("Thank you for your feedback! Have a great day!", reply_markup=keyboard_start)
    await state.clear()

# Обработчик команды /reply (должен быть перед общим обработчиком)
@router.message(Command("reply"))  # Изменяем определение команды
async def reply_command(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        try:
            # Получаем весь текст после команды
            full_text = message.text[7:].strip()
            # Находим первый пробел после ID
            space_index = full_text.find(' ')
            
            if space_index == -1:
                await message.reply("Invalid format. Use: /reply [telegram_id] {message}")
                return
                
            telegram_id = full_text[:space_index].strip()
            reply_text = full_text[space_index:].strip()
            
            if not telegram_id or not reply_text:
                await message.reply("Invalid format. Use: /reply [telegram_id] {message}")
                return
            
            try:
                # Отправляем сообщение пользователю
                await bot.send_message(telegram_id, reply_text)
                
                # Логируем действие администратора
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO admin_logs (action, user_id, admin_id, timestamp)
                                 VALUES (%s, %s, %s, %s)''',
                             ("custom_reply", telegram_id, str(message.from_user.id), 
                              datetime.now(timezone.utc)))
                conn.commit()
                conn.close()
                
                await message.reply(f"Message sent to {telegram_id} successfully!")
                
            except Exception as e:
                await message.reply(f"Failed to send message: {str(e)}")
                
        except Exception as e:
            await message.reply(f"Error processing command: {str(e)}\nUse: /reply [telegram_id] {message}")
    else:
        await message.reply("You are not authorized to use this command.")

# Добавляем команду для просмотра статистики
@router.message(Command(commands=["stats"]))
async def stats_command(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Получаем статистику по этапам
            cursor.execute("""
                SELECT action, COUNT(*) as count
                FROM user_logs
                GROUP BY action
                ORDER BY count DESC
            """)
            
            stats = cursor.fetchall()
            conn.close()
            
            response = "User Journey Statistics:\n\n"
            for action, count in stats:
                response += f"{action}: {count}\n"
            
            await message.reply(response)
        except Exception as e:
            await message.reply(f"Error getting statistics: {e}")
    else:
        await message.reply("You are not authorized to use this command.")

# Обработка неотловленных событий (должна быть после всех остальных обработчиков)
@router.message()
async def handle_unexpected_messages(message: types.Message):
    await message.reply("You wrote something off-script. Sorry, I don't know how to respond. You can always start over by clicking the /start button.", reply_markup=keyboard_start)

# Заменяем класс FileAndConsoleLogger на новую версию
class FileAndConsoleLogger:
    def __init__(self, log_filename="bot_log.txt", error_filename="error.txt"):
        self.terminal = sys.stdout
        self.log_filename = log_filename
        self.error_filename = error_filename
        
        # Создаем файлы, если их нет
        open(self.log_filename, 'a', encoding='utf-8').close()
        open(self.error_filename, 'a', encoding='utf-8').close()

    def write(self, message):
        try:
            timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
            formatted_message = f"{timestamp}{message}"
            
            # Записываем в консоль
            self.terminal.write(formatted_message)
            
            # Записываем в лог-файл
            with open(self.log_filename, "a", encoding='utf-8') as log_file:
                log_file.write(formatted_message)
            
            # Если это сообщение об ошибке, записываем также в error.txt
            if "Error" in message or "error" in message or "ERROR" in message or "Exception" in message:
                with open(self.error_filename, "a", encoding='utf-8') as error_file:
                    error_file.write(formatted_message)
        except Exception as e:
            # Если произошла ошибка при логировании, пишем в консоль
            self.terminal.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Logging error: {str(e)}\n")

    def flush(self):
        self.terminal.flush()

# Добавляем функцию для логирования ошибок
def log_error(error_message: str, error_details: Exception = None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {error_message}"
    if error_details:
        full_message += f"\nDetails: {str(error_details)}"
    
    try:
        with open("error.txt", "a", encoding='utf-8') as error_file:
            error_file.write(full_message + "\n")
        print(full_message)  # Также выводим в консоль/лог
    except Exception as e:
        print(f"Failed to log error: {str(e)}")

# Обновляем обработчик ошибок
@router.errors()
async def handle_errors(update: types.Update, exception: Exception):
    if isinstance(exception, TypeError) and 'FSMContext.__init__() missing 1 required positional argument' in str(exception):
        error_msg = "FSMContext initialization error detected. Ensure the Dispatcher is properly set up with FSMContext."
        log_error(error_msg, exception)
        logging.error(error_msg)
    else:
        error_msg = "An unexpected error occurred."
        log_error(error_msg, exception)
        logging.exception(error_msg)
    return True

# Функция отправки статистики
async def send_daily_stats():
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=23, minute=59, second=59)
        await asyncio.sleep((next_run - now).total_seconds())

        conn = get_db_connection()
        cursor = conn.cursor()

        day_before_yesterday = (now - timedelta(days=2)).date()
        cursor.execute("SELECT COUNT(*) FROM users WHERE response_date BETWEEN %s AND %s",
                       (day_before_yesterday, day_before_yesterday + timedelta(days=1)))
        day_before_count = cursor.fetchone()[0]

        yesterday = (now - timedelta(days=1)).date()
        cursor.execute("SELECT COUNT(*) FROM users WHERE response_date BETWEEN %s AND %s",
                       (yesterday, yesterday + timedelta(days=1)))
        yesterday_count = cursor.fetchone()[0]

        conn.close()

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"Day before yesterday: {day_before_count} applications.\n"
                                                 f"Yesterday: {yesterday_count} applications.\n"
                                                 f"Keep up the great work!")
            except Exception as e:
                print(f"Failed to send stats to admin {admin_id}: {e}")

# Добавляем класс для мониторинга здоровья бота
class BotHealthMonitor:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.last_ping = datetime.now()
        self.is_running = True
        self.restart_count = 0
        self.max_restarts = 5
        self.restart_interval = 300  # 5 минут между перезапусками

    async def check_telegram_connection(self) -> bool:
        try:
            await self.bot.get_me()
            self.last_ping = datetime.now()
            return True
        except Exception as e:
            print(f"Connection check failed: {e}")
            return False

    async def monitor(self):
        while self.is_running:
            try:
                is_connected = await self.check_telegram_connection()
                if not is_connected:
                    print("Bot connection lost, attempting restart...")
                    if self.restart_count < self.max_restarts:
                        self.restart_count += 1
                        await self.restart_bot()
                    else:
                        print("Maximum restart attempts reached")
                        await self.emergency_notification()
                        break
                else:
                    self.restart_count = 0
                await asyncio.sleep(60)  # Проверка каждую минуту
            except Exception as e:
                print(f"Monitor error: {e}")
                await asyncio.sleep(5)

    async def restart_bot(self):
        try:
            print("Restarting bot...")
            await self.bot.session.close()
            await asyncio.sleep(5)
            await dp.start_polling(self.bot)
            print("Bot restarted successfully")
        except Exception as e:
            print(f"Restart failed: {e}")

    async def emergency_notification(self):
        for admin_id in ADMIN_IDS:
            try:
                await self.bot.send_message(
                    admin_id,
                    "⚠️ ВНИМАНИЕ: Бот перестал отвечать и не может быть перезапущен автоматически. Требуется ручное вмешательство."
                )
            except Exception as e:
                print(f"Failed to send emergency notification to admin {admin_id}: {e}")

# Добавляем функцию для корректного завершения перед main()
async def cleanup():
    """Функция очистки перед завершением программы"""
    print("\nЗавершение работы бота...")
    try:
        # Закрываем соединения с базой данных
        try:
            conn = get_db_connection()
            conn.close()
            print("Соединение с базой данных закрыто")
        except:
            pass
        
        # Останавливаем бота
        try:
            await bot.session.close()
            print("Сессия бота закрыта")
        except:
            pass
        
    except Exception as e:
        print(f"Ошибка при завершении работы: {e}")
    finally:
        print("Бот остановлен")
        # Принудительно завершаем процесс
        sys.exit(0)

async def main():
    try:
        def signal_handler(signum, frame):
            print("\nПолучен сигнал завершения (Ctrl+C)")
            # Запускаем очистку и завершаем программу
            asyncio.create_task(cleanup())
            sys.exit(0)

        # Регистрируем обработчик сигнала
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        sys.stdout = FileAndConsoleLogger()
        print("Starting bot...")
        print("Для остановки бота нажмите Ctrl+C")

        # Создаем монитор здоровья бота
        health_monitor = BotHealthMonitor(bot)
        
        # Запускаем все фоновые задачи
        tasks = [
            asyncio.create_task(send_daily_stats()),
            asyncio.create_task(lock_manager.cleanup_locks()),
            asyncio.create_task(health_monitor.monitor())
        ]

        # Обработчик сигналов для корректного завершения
        def signal_handler(sig, frame):
            print("Shutdown signal received")
            health_monitor.is_running = False
            for task in tasks:
                task.cancel()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Запускаем бота с обработкой ошибок
        while health_monitor.is_running:
            try:
                await dp.start_polling(bot)
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(5)
                continue

    except KeyboardInterrupt:
        print("\nПолучена команда на остановку")
        await cleanup()
    except Exception as e:
        log_error("Critical error in main function", e)
        logging.error(f"Критическая ошибка: {e}")
        logging.error(traceback.format_exc())
        print("\nПроизошла ошибка. Проверьте файл bot_error.log для деталей.")
        await cleanup()
        return 1
    return 0

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
        sys.exit(0)

# Добавляем функцию для обработки callback-запросов
@router.callback_query()
async def process_callback_query(callback_query: types.CallbackQuery):
    data = callback_query.data.split(":")
    action = data[0]
    
    if (action == "apply"):
        user_id = str(callback_query.from_user.id)
        vacancy_id = data[1]
        
        # Подключаемся к MongoDB
        client = MongoClient("mongodb://localhost:27017/")
        db = client["mydatabase"]
        
        # Проверяем блокировку
        user_locks = db.UserLock
        existing_lock = user_locks.find_one({
            "userId": user_id,
            "vacancyId": vacancy_id,
            "timestamp": {"$gte": datetime.now() - timedelta(minutes=5)}
        })
        
        if existing_lock:
            await callback_query.answer("You have already applied for this position. Please try again later.", show_alert=True)
            return

        # Создаем блокировку
        user_locks.insert_one({
            "userId": user_id,
            "vacancyId": vacancy_id,
            "timestamp": datetime.now()
        })
        
        # Продолжаем обработку отклика
        await callback_query.answer("Your application has been received!", show_alert=True)