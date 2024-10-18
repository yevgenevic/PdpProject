import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sheets import update_google_sheet
import psycopg2
from docx import Document
import random
import os
from aiogram import types, F

dp = Dispatcher()

ADMIN_ID = 5654406350
correct_answer = None


class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_surname = State()
    waiting_for_phone = State()
    waiting_for_group = State()


def get_db_connection():
    return psycopg2.connect(
        dbname='pdp',
        user='postgres',
        password='1',
        host='localhost',
        port='5432'
    )


def save_user_data(name, surname, phone, group, telegram_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO users (name, surname, phone, group_name, telegram_id) VALUES (%s, %s, %s, %s, %s)",
        (name, surname, phone, group, telegram_id)
    )
    connection.commit()
    cursor.close()
    connection.close()


def update_user_score(telegram_id, score):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE users SET score = score + %s WHERE telegram_id = %s",
        (score, telegram_id)
    )
    connection.commit()
    cursor.close()
    connection.close()


def is_user_registered(telegram_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT 1 FROM users WHERE telegram_id = %s", (telegram_id,))
    user_exists = cursor.fetchone() is not None
    cursor.close()
    connection.close()
    return user_exists


def is_admin(telegram_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT telegram_id FROM admins WHERE telegram_id = %s", (telegram_id,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    return result is not None


def add_admin(telegram_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO admins (telegram_id) VALUES (%s) ON CONFLICT DO NOTHING", (telegram_id,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def get_all_admins():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT telegram_id FROM admins")
    admins = cursor.fetchall()
    cursor.close()
    connection.close()
    return admins


def get_random_question():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT id, question_text, answer_a, answer_b, answer_c, answer_d, correct_answer FROM questions ORDER BY RANDOM() LIMIT 1")
    question = cursor.fetchone()
    cursor.close()
    connection.close()
    return question


def get_question_by_id(question_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM questions WHERE id = %s", (question_id,))
    question = cursor.fetchone()
    cursor.close()
    connection.close()
    return question


def add_questions_from_docx(file_path):
    connection = get_db_connection()
    cursor = connection.cursor()

    document = Document(file_path)
    question_data = []

    current_question = {}
    for para in document.paragraphs:
        text = para.text.strip()
        if text.startswith("Savol:"):
            current_question['question'] = text[6:].strip()
        elif text.startswith("Javob A:"):
            current_question['a'] = text[8:].strip()
        elif text.startswith("Javob B:"):
            current_question['b'] = text[8:].strip()
        elif text.startswith("Javob C:"):
            current_question['c'] = text[8:].strip()
        elif text.startswith("Javob D:"):
            current_question['d'] = text[8:].strip()
        elif text.startswith("Tug'ri javob:"):
            current_question['correct'] = text[13:].strip()

        if 'question' in current_question and 'correct' in current_question:
            question_data.append(current_question)
            current_question = {}

    for question in question_data:
        cursor.execute("""
                INSERT INTO questions (question_text, answer_a, answer_b, answer_c, answer_d, correct_answer)
                VALUES (%s, %s, %s, %s, %s, %s) 
            """, (
            question['question'], question['a'], question['b'], question['c'], question['d'], question['correct']))

    connection.commit()
    cursor.close()
    connection.close()

    return len(question_data)


@dp.message(Command('ranking'))
async def show_ranking(message: types.Message):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT name, surname, score FROM users ORDER BY score DESC"
    )
    ranking = cursor.fetchall()
    cursor.close()
    connection.close()

    if not ranking:
        await message.answer("Hozircha reyting mavjud emas.")
        return

    ranking_message = "🏆 Reyting:\n\n"
    for i, row in enumerate(ranking, 1):
        ranking_message += f"{i}. {row[0]} {row[1]} — {row[2]} Ball\n"

    await message.answer(ranking_message)


@dp.message(Command('start'))
async def start_command(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    if is_user_registered(telegram_id):
        await message.answer("siz registratsiya qilib bulgansz!")
        await start_game(message)
    else:
        await message.answer("Ismingizni kiriting:")
        await state.set_state(RegistrationStates.waiting_for_name)


@dp.message(StateFilter(RegistrationStates.waiting_for_name))
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Familiyangiz:")
    await state.set_state(RegistrationStates.waiting_for_surname)


@dp.message(StateFilter(RegistrationStates.waiting_for_surname))
async def process_surname(message: types.Message, state: FSMContext):
    await state.update_data(surname=message.text)
    await message.answer("Telefon nomeriz:")
    await state.set_state(RegistrationStates.waiting_for_phone)


@dp.message(StateFilter(RegistrationStates.waiting_for_phone))
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Qaysi guruhda uqiysiz:")
    await state.set_state(RegistrationStates.waiting_for_group)


@dp.message(StateFilter(RegistrationStates.waiting_for_group))
async def process_group(message: types.Message, state: FSMContext):
    user_data = await state.get_data()

    name = user_data.get('name')
    surname = user_data.get('surname')
    phone = user_data.get('phone')
    group = message.text

    if not is_user_registered(message.from_user.id):
        save_user_data(name, surname, phone, group, message.from_user.id)
        await message.answer("Registratsiya muvafaqiyatli! Endi uyinni boshlasangiz buladi.",
                             reply_markup=types.ReplyKeyboardMarkup(
                                 keyboard=[
                                     [types.KeyboardButton(text="✅ Boshlash")]
                                 ],
                                 resize_keyboard=True,
                                 one_time_keyboard=True
                             ))
    else:
        await message.answer("Siz registratsiya qilib bulgansiz.")

    await state.set_state(None)


@dp.message(lambda message: message.text == "✅ Boshlash")
async def start_game(message: types.Message):
    await message.answer("Uyin boshlandi!")

    question = get_random_question()

    if question:
        question_id, question_text, answer_a, answer_b, answer_c, answer_d, correct_answer = question
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="A", callback_data=f"answer_{question_id}_a"),
            InlineKeyboardButton(text="B", callback_data=f"answer_{question_id}_b")
        )
        builder.row(
            InlineKeyboardButton(text="C", callback_data=f"answer_{question_id}_c"),
            InlineKeyboardButton(text="D", callback_data=f"answer_{question_id}_d")
        )

        await message.answer(f"{question_text}\nA: {answer_a}\nB: {answer_b}\nC: {answer_c}\nD: {answer_d}",
                             reply_markup=builder.as_markup())
    else:
        await message.answer("Savollar topilmadi.")


@dp.callback_query(lambda callback: callback.data.startswith('answer_'))
async def handle_answer(callback: types.CallbackQuery):
    _, question_id, selected_option = callback.data.split('_')
    question = get_question_by_id(question_id)

    if question and selected_option == question[-1].lower():
        await callback.message.answer("Tugri!")
        update_user_score(callback.from_user.id, 1)
        update_google_sheet(callback.from_user.username, 1)

    else:
        await callback.message.answer("Xato!")

    await callback.answer()


@dp.message(Command('admin'))
async def admin_panel(message: types.Message):
    if is_admin(message.from_user.id):
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="Admin qushish", callback_data="add_admin"),
            InlineKeyboardButton(text="Adminlarni kurish", callback_data="show_admins")
        )
        builder.row(
            InlineKeyboardButton(text="Savollar qushish", callback_data="upload_questions")
        )

        await message.answer("Tanlang:", reply_markup=builder.as_markup())
    else:
        await message.answer("Sizda admin panelga ruxsat yoq")


@dp.callback_query(lambda callback: callback.data == 'upload_questions')
async def handle_upload_questions(callback: types.CallbackQuery):
    await callback.message.answer("Iltimos savollarni  .docx formatda yuklang")
    await callback.answer()


@dp.message(F.content_type == 'document')
async def handle_document_upload(message: types.Message):
    document = message.document
    os.makedirs('questions', exist_ok=True)
    file = await message.bot.get_file(document.file_id)
    file_path = f"questions/{document.file_name}"
    await message.bot.download_file(file.file_path, file_path)
    num_questions = add_questions_from_docx(file_path)
    await message.answer(f"{num_questions} ta savol muvaffaqiyatli yuklandi.")


@dp.callback_query(lambda callback: callback.data == 'add_admin')
async def handle_add_admin(callback: types.CallbackQuery):
    await callback.message.answer("Yangi Adminni Telegram ID sini kiriting")
    await callback.answer()


@dp.message()
async def add_admin_by_id(message: types.Message):
    try:
        new_admin_id = int(message.text)
        add_admin(new_admin_id)
        await message.answer(f"{new_admin_id} ID foydalanuvchi adminlarga qushildi.")
        add_admin(new_admin_id)
    except ValueError:
        await message.answer("Xato: Tugri Telegram ID Kiriting")


@dp.callback_query(lambda callback: callback.data == 'show_admins')
async def show_admins(callback: types.CallbackQuery):
    admins = get_all_admins()
    if admins:
        admin_list = "\n".join([str(admin[0]) for admin in admins])
        await callback.message.answer(f"Adminlar ruyxati:\n{admin_list}")
    else:
        await callback.message.answer("Adminlar topilmadi.")
    await callback.answer()


async def main() -> None:
    bot = Bot(token="7611301913:AAExAJXVMmrOdZ6vDzz9IQejkEJYCZM6D7g",
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
