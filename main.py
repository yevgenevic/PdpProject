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


def is_user_registred(telegram_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE telegram_id = %s", (telegram_id,)
    )
    result = cursor.fetchone()[0]
    cursor.close()
    connection.close()
    return result > 0


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
    if is_user_registred(telegram_id):
        await message.answer("siz registartsiya qilgansiz")
        await start_game(message)
    else:
        await message.answer("Ismingiz:")
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

    save_user_data(name, surname, phone, group, message.from_user.id)

    await message.answer("Registratsiyadan muvaffaqiyatli utdingiz pasdagi tugmani bosing.")
    await message.answer("",reply_markup=types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="✅ Boshlash")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    ))

    await state.set_state(None)


@dp.message(lambda message: message.text == "✅ Boshlash")
async def start_game(message: types.Message):
    await message.answer("Uyin boshlandi!")

    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="A", callback_data="answer_a"),
            types.InlineKeyboardButton(text="B", callback_data="answer_b"),
        ],
        [
            types.InlineKeyboardButton(text="C", callback_data="answer_c"),
            types.InlineKeyboardButton(text="D", callback_data="answer_d"),
        ],
    ])

    await message.answer("Javobni tanlang:", reply_markup=builder)


@dp.callback_query(lambda callback: callback.data.startswith('answer_'))
async def handle_answer(callback: types.CallbackQuery):
    global correct_answer
    user_answer = callback.data
    username = callback.from_user.username
    telegram_id = callback.from_user.id
    if correct_answer:
        if user_answer == correct_answer:
            await callback.message.answer("Tugri!")

            update_google_sheet(username, 1)

            update_user_score(telegram_id, 1)
        else:
            await callback.message.answer("Notogri!")
    else:
        await callback.message.answer("Javoblar hali mavjud emas.")

    await callback.answer()


@dp.message(Command('admin'))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="A", callback_data="set_answer_a"),
            InlineKeyboardButton(text="B", callback_data="set_answer_b")
        )
        builder.row(
            InlineKeyboardButton(text="C", callback_data="set_answer_c"),
            InlineKeyboardButton(text="D", callback_data="set_answer_d")
        )

        await message.answer("Tugri javob qaysi?:", reply_markup=builder.as_markup())
    else:
        await message.answer("siz admin emassiz.")


@dp.callback_query(lambda callback: callback.data.startswith('set_answer_'))
async def set_correct_answer(callback: types.CallbackQuery):
    global correct_answer

    if callback.from_user.id == ADMIN_ID:
        correct_answer = callback.data.replace("set_", "")
        await callback.message.answer(f"Tugri javob belgilandi {correct_answer.upper()}.")
    else:
        await callback.message.answer("Imkoniyatingiz yoq.")

    await callback.answer()


async def main() -> None:
    bot = Bot(token="7611301913:AAExAJXVMmrOdZ6vDzz9IQejkEJYCZM6D7g",
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
