import asyncio
import asyncpg
import io
import logging
import os
import psycopg2
import random
import sys
from aiogram import Bot, Dispatcher
from aiogram import types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, BotCommand
from aiogram.utils.keyboard import InlineKeyboardBuilder
from docx import Document
from sheets import update_google_sheet

dp = Dispatcher()

ADMIN_ID = 5654406350
correct_answer = None


class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_surname = State()
    waiting_for_phone = State()
    waiting_for_group = State()


class AdminStates(StatesGroup):
    waiting_for_admin_id = State()


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Start the bot"),
        BotCommand(command="/ranking", description="Show leaderboard"),
        BotCommand(command="/admin", description="Admin panel"),
    ]
    await bot.set_my_commands(commands)


async def get_db_connection():
    return await asyncpg.connect(
        database='pdp',
        user='postgres',
        password='1',
        host='localhost',
        port='5432'
    )


async def save_user_data(name, surname, phone, group, telegram_id):
    if await is_user_registered(telegram_id):
        print(f"Пользователь с telegram_id={telegram_id} уже зарегистрирован.")
        return
    conn = await get_db_connection()
    try:
        await conn.execute(
            "INSERT INTO users (name, surname, phone, group_name, telegram_id) VALUES ($1, $2, $3, $4, $5)",
            name, surname, phone, group, telegram_id
        )
        print("Пользователь успешно добавлен.")
    finally:
        await conn.close()


async def update_user_score(telegram_id, score):
    conn = await get_db_connection()
    try:
        await conn.execute(
            "UPDATE users SET score = score + $1 WHERE telegram_id = $2",
            score, telegram_id
        )
    finally:
        await conn.close()


async def is_user_registered(telegram_id):
    conn = await get_db_connection()
    try:
        return await conn.fetchval("SELECT 1 FROM users WHERE telegram_id = $1", telegram_id) is not None
    finally:
        await conn.close()


async def is_admin(telegram_id):
    conn = await get_db_connection()
    try:
        return await conn.fetchval("SELECT 1 FROM admins WHERE telegram_id = $1", telegram_id) is not None
    finally:
        await conn.close()


async def add_admin(telegram_id):
    conn = await get_db_connection()
    try:
        await conn.execute("INSERT INTO admins (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING", telegram_id)
    finally:
        await conn.close()


async def get_all_admins():
    conn = await get_db_connection()
    try:
        return await conn.fetch("SELECT telegram_id FROM admins")
    finally:
        await conn.close()


async def get_random_question():
    conn = await get_db_connection()
    try:
        return await conn.fetchrow(
            "SELECT id, question_text, answer_a, answer_b, answer_c, answer_d, correct_answer FROM questions ORDER BY RANDOM() LIMIT 1")
    finally:
        await conn.close()


async def get_question_by_id(question_id):
    conn = await get_db_connection()
    try:
        return await conn.fetchrow("SELECT * FROM questions WHERE id = $1", question_id)
    finally:
        await conn.close()


async def add_questions_from_docx(file_path):
    conn = await asyncpg.connect(database='pdp', user='postgres', password='1', host='localhost', port='5432')
    document = Document(file_path)
    question_data = []
    current_question = {}

    for para in document.paragraphs:
        text = para.text.strip()
        if text.startswith("Savol:"):
            current_question = {'question': text.split(':', 1)[1].strip()}
        elif text.startswith("A)") or text.startswith("B)") or text.startswith("C)") or text.startswith("D)"):
            if 'question' in current_question:
                option_label = text[0]
                current_question[option_label.lower()] = text.split(')', 1)[1].strip()
        elif text.startswith("javob)"):
            if 'question' in current_question:
                current_question['correct'] = text.split(')', 1)[1].strip()
                if all(key in current_question for key in ['a', 'b', 'c', 'd', 'correct']):
                    question_data.append(current_question)
                    current_question = {}

    for question in question_data:
        if all(key in question for key in ['question', 'a', 'b', 'c', 'd', 'correct']):
            try:
                print("Executing insert with:", question)
                await conn.execute("""
                    INSERT INTO questions (question_text, answer_a, answer_b, answer_c, answer_d, correct_answer)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, question['question'], question['a'], question['b'], question['c'], question['d'],
                                   question['correct'])
            except Exception as e:
                print("Failed to insert question:", question)
                print("Error:", e)
        else:
            print("Question missing required fields:", question)

    await conn.close()
    return len(question_data)


@dp.message(F.content_type == 'document')
async def handle_document_upload(message: types.Message):
    document = message.document
    file_info = await message.bot.get_file(document.file_id)
    file_data = io.BytesIO()
    await message.bot.download_file(file_info.file_path, destination=file_data)
    file_data.seek(0)
    num_questions = await add_questions_from_docx(file_data)
    await message.answer(f"{num_questions} ta savol muvaffaqiyatli yuklandi.")


@dp.message(Command('ranking'))
async def show_ranking(message: types.Message):
    conn = await get_db_connection()
    try:
        ranking = await conn.fetch(
            "SELECT name, surname, score FROM users ORDER BY score DESC"
        )

        if not ranking:
            await message.answer("Hozircha reyting mavjud emas.")
            return

        ranking_message = "🏆 Reyting:\n\n"
        for i, row in enumerate(ranking, 1):
            ranking_message += f"{i}. {row['name']} {row['surname']} — {row['score']} Ball\n"

        await message.answer(ranking_message)
    finally:
        await conn.close()


@dp.message(Command('start'))
async def start_command(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    if not await is_user_registered(telegram_id):
        await message.answer("Ismingizni kiriting:")
        await state.set_state(RegistrationStates.waiting_for_name)
    else:
        await start_game(message)


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

    registered = await is_user_registered(message.from_user.id)
    if not registered:
        await save_user_data(name, surname, phone, group, message.from_user.id)
        await message.answer(
            "Registratsiya muvafaqiyatli! Endi uyinni boshlasangiz buladi.",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="✅ Boshlash")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
    else:
        await message.answer("Siz registratsiya qilib bulgansiz.")

    await state.set_state(None)


@dp.message(lambda message: message.text == "✅ Boshlash")
async def start_game(message: types.Message):
    await message.answer("Игра началась!", reply_markup=types.ReplyKeyboardRemove())

    question = await get_random_question()
    if question:
        question_id, question_text, answer_a, answer_b, answer_c, answer_d, correct_answer = question
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="A", callback_data=f"answer_{question_id}_A"),
            InlineKeyboardButton(text="B", callback_data=f"answer_{question_id}_B"),
            InlineKeyboardButton(text="C", callback_data=f"answer_{question_id}_C"),
            InlineKeyboardButton(text="D", callback_data=f"answer_{question_id}_D")
        )
        builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
        sanitized_text = f"{question_text}\nA: {answer_a}\nB: {answer_b}\nC: {answer_c}\nD: {answer_d}"
        await message.answer(sanitized_text, reply_markup=builder.as_markup(), parse_mode=None)
    else:
        await message.answer("Savollar tugadi! Uyin uchun raxmat.")


@dp.callback_query(lambda callback: callback.data == 'cancel')
async def cancel_game(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Uyin tuxtatildi.")
    await callback.answer()


@dp.callback_query(lambda callback: callback.data.startswith('answer_'))
async def handle_answer(callback: types.CallbackQuery):
    try:
        action, question_id_str, selected_option = callback.data.split('_')
        question_id = int(question_id_str)
        question = await get_question_by_id(question_id)

        if question:
            _, _, _, _, _, _, correct_answer = question
            if selected_option.lower() == correct_answer.lower():
                await update_user_score(callback.from_user.id, 1)
                await update_google_sheet(callback.from_user.username, 1)

            await callback.message.delete()

            await start_game(callback.message)

        else:
            await callback.message.answer("Savol topilmadi.")
    except Exception as e:
        await callback.message.answer(f"Xato: {e}")
    finally:
        await callback.answer()


@dp.message(Command('admin'))
async def admin_panel(message: types.Message):
    is_admin_status = await is_admin(message.from_user.id)
    if is_admin_status:
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
    await callback.message.answer("Iltimos savollarni .docx formatda yuklang")
    await callback.answer()


@dp.callback_query(lambda callback: callback.data == 'add_admin')
async def handle_add_admin(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Yangi Adminni Telegram ID sini kiriting")
    await state.set_state(AdminStates.waiting_for_admin_id)
    await callback.answer()


@dp.message(StateFilter(AdminStates.waiting_for_admin_id))
async def add_admin_by_id(message: types.Message, state: FSMContext):
    try:
        new_admin_id = int(message.text)
        await add_admin(new_admin_id)
        await message.answer(f"{new_admin_id} ID foydalanuvchi adminlarga qushildi.")
        await state.clear()
    except ValueError:
        await message.answer("Xato: Tugri Telegram ID Kiriting")


@dp.callback_query(lambda callback: callback.data == 'show_admins')
async def show_admins(callback: types.CallbackQuery):
    admins = await get_all_admins()
    if admins:
        admin_list = "\n".join([str(admin['telegram_id']) for admin in admins])
        await callback.message.answer(f"Adminlar ruyxati:\n{admin_list}")
    else:
        await callback.message.answer("Adminlar topilmadi.")
    await callback.answer()


async def main():
    bot = Bot(token="7611301913:AAExAJXVMmrOdZ6vDzz9IQejkEJYCZM6D7g",
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await set_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
