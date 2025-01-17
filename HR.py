import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from datetime import datetime, timedelta, timezone
import mysql.connector
# from aiogram.dispatcher import FSMContext
# from aiogram.dispatcher.filters.state import State, StatesGroup

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

# Получаем API токен из файла
with open("API.txt", "r") as file:
    API_TOKEN = file.read().strip()

# Получаем настройки базы данных из файла
def load_db_config():
    with open("db1.txt", "r") as file:
        lines = file.readlines()
    return {
        "host": lines[0].strip(),
        "user": lines[1].strip(),
        "password": lines[2].strip(),
        "database": lines[3].strip(),
        "port": int(lines[4].strip()),
    }

db_config = load_db_config()

# Получаем ID администраторов из файла
def load_admin_ids():
    with open("admin.txt", "r") as file:
        return [int(line.strip()) for line in file.readlines()]

ADMIN_IDS = load_admin_ids()

# Создаем бота и диспетчер
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
router = Router()
dp = Dispatcher(storage=storage)
dp.include_router(router)

# Функция подключения к базе данных
def get_db_connection():
    return mysql.connector.connect(**db_config)

# Создаем таблицы, если их нет
conn = get_db_connection()
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id VARCHAR(255),
    name VARCHAR(255),
    phone_number VARCHAR(50),
    email VARCHAR(255),
    english_level INT,
    modern_pc VARCHAR(10),
    response_date DATETIME,
    hr VARCHAR(255)
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id VARCHAR(255),
    feedback TEXT,
    response_date DATETIME
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action VARCHAR(255),
    user_id VARCHAR(255),
    admin_id VARCHAR(255),
    timestamp DATETIME
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS anonymous_feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255),
    feedback TEXT,
    response_date DATETIME
)''')

conn.commit()
conn.close()

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

# Обработка команды /start
@router.message(Command(commands=["start"]))
async def start_command(message: types.Message, state: FSMContext):
    await message.reply("Welcome! Please provide your name:")
    await state.set_state(Form.name)

# Обработка ввода имени
@router.message(StateFilter(Form.name))
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.reply("Please provide your phone number (e.g., +123456789):")
    await state.set_state(Form.phone_number)

# Обработка ввода номера телефона
@router.message(StateFilter(Form.phone_number))
async def process_phone_number(message: types.Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    await message.reply("Please provide your email:")
    await state.set_state(Form.email)

# Обработка ввода email
@router.message(StateFilter(Form.email))
async def process_email(message: types.Message, state: FSMContext):
    await state.update_data(email=message.text)
    await message.reply("Rate your English level from 1 to 10:")
    await state.set_state(Form.english_level)

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

# Обработка ответа на вопрос о наличии современного ПК
@router.message(StateFilter(Form.modern_pc))
async def process_modern_pc(message: types.Message, state: FSMContext):
    if message.text in ["Yes", "No"]:
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

        with open("1.txt", "r") as file:
            text1 = file.read()

        await message.reply(text1, reply_markup=keyboard_yes_no)
        await state.set_state(Form.confirm_text1)
    else:
        await message.reply("Please respond with Yes or No.")

# Обработка подтверждения текста 1
@router.message(StateFilter(Form.confirm_text1))
async def process_confirm_text1(message: types.Message, state: FSMContext):
    if message.text == "Yes":
        with open("2.txt", "r") as file:
            text2 = file.read()

        await message.reply(text2, reply_markup=keyboard_yes_no)
        await state.set_state(Form.confirm_text2)
    elif message.text == "No":
        await message.reply("Are you sure?", reply_markup=keyboard_yes_no)
        await state.set_state(Form.anonymous_feedback)
    elif message.text == "I need human help":
        await message.reply("Please contact our HR on Telegram: @hr_contact")
    else:
        await message.reply("You wrote something off-script. Sorry, I don't know how to respond. You can always start over by clicking the /start button.", reply_markup=keyboard_start)

# Обработка анонимного отзыва
@router.message(StateFilter(Form.anonymous_feedback))
async def process_anonymous_feedback(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("name", "Anonymous")
    feedback = message.text

    # Записываем отзыв в базу данных
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO anonymous_feedback (name, feedback, response_date)
                      VALUES (%s, %s, %s)''',
                   (name, feedback, datetime.now(timezone.utc)))
    conn.commit()
    conn.close()

    await message.reply("Thank you for your feedback! We appreciate your input.", reply_markup=keyboard_start)
    await state.clear()

# Обработка подтверждения текста 2
@router.message(StateFilter(Form.confirm_text2))
async def process_confirm_text2(message: types.Message, state: FSMContext):
    if message.text == "Yes":
        await message.reply("Did you complete the video interview?", reply_markup=keyboard_yes_no)
        await state.set_state(Form.video_interview)
    elif message.text == "No":
        await message.reply("Are you sure?", reply_markup=keyboard_yes_no)
        await state.set_state(Form.anonymous_feedback)
    elif message.text == "I need human help":
        await message.reply("Please contact our HR on Telegram: @hr_contact")
    else:
        await message.reply("You wrote something off-script. Sorry, I don't know how to respond. You can always start over by clicking the /start button.", reply_markup=keyboard_start)

# Обработка состояния Form.video_interview
@router.message(StateFilter(Form.video_interview))
async def process_video_interview(message: types.Message, state: FSMContext):
    if message.text == "Yes":
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"User with ID {message.from_user.id} passed the video interview. Please check.")
            except Exception as e:
                print(f"Failed to send message to admin {admin_id}: {e}")
        await message.reply("Thank you! Your response has been recorded.", reply_markup=keyboard_start)
        await state.clear()
    elif message.text == "No":
        await message.reply("Thank you for your response. Let us know if you need assistance.", reply_markup=keyboard_start)
        await state.clear()
    elif message.text == "I need human help":
        await message.reply("Please contact our HR on Telegram: @hr_contact", reply_markup=keyboard_start)
    else:
        await message.reply("You wrote something off-script. Sorry, I don't know how to respond. You can always start over by clicking the /start button.", reply_markup=keyboard_start)

# Обработка неотловленных событий
@router.message()
async def handle_unexpected_messages(message: types.Message):
    await message.reply("You wrote something off-script. Sorry, I don't know how to respond. You can always start over by clicking the /start button.", reply_markup=keyboard_start)

# Исправление ошибки FSMContext
@router.errors()
async def handle_errors(update: types.Update, exception):
    if isinstance(exception, TypeError) and 'FSMContext.__init__() missing 1 required positional argument' in str(exception):
        logging.error("FSMContext initialization error detected. Ensure the Dispatcher is properly set up with FSMContext.")
    else:
        logging.exception("An unexpected error occurred.")
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

# Обработчик для ответа "Yes"
@router.message(F.text.lower() == "yes")
async def process_yes(message: types.Message):
    await message.answer("Что именно вас смутило? Пожалуйста напишите нам, чтобы мы могли улучшиться для будущих работников.")
    await FeedbackStates.waiting_for_feedback.set()

# Обработчик для получения отзыва
@router.message(StateFilter(FeedbackStates.waiting_for_feedback))
async def process_feedback(message: types.Message, state: FSMContext):
    feedback = message.text
    await state.update_data(feedback=feedback)
    
    submit_button = KeyboardButton("Submit")
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(submit_button)
    await message.answer("Нажм��те 'Submit' для отправки отзыва.", reply_markup=keyboard)

# Обработчик для кнопки "Submit"
@router.message(F.text.lower() == "submit", StateFilter(FeedbackStates.waiting_for_feedback))
async def submit_feedback(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    feedback = user_data['feedback']
    
    # Сохранение отзыва в базу данных (пример)
    save_feedback_to_db(feedback)
    
    await message.answer("Спасибо за ваш отзыв!", reply_markup=types.ReplyKeyboardRemove())
    await state.finish()

def save_feedback_to_db(feedback):
    # Пример функции для сохранения отзыва в базу данных
    # Реализуйте сохранение в вашу базу данных здесь
    pass

# Запуск бота
async def main():
    try:
        asyncio.create_task(send_daily_stats())
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
