# from aiogram import types
# from aiogram.fsm.context import FSMContext
#
# from sheets import *
# from .main import *
#
#
# class RegistrationStates:
#     waiting_for_name = 'waiting_for_name'
#     waiting_for_surname = 'waiting_for_surname'
#     waiting_for_phone = 'waiting_for_phone'
#     waiting_for_group = 'waiting_for_group'
#
#
# @dp.message(commands=['start'])
# async def start_registration(message: types.Message):
#     await message.answer("Введите ваше имя:")
#     await RegistrationStates.waiting_for_name.set()
#
#
# @dp.message(state=RegistrationStates.waiting_for_name)
# async def process_name(message: types.Message, state: FSMContext):
#     await state.update_data(name=message.text)
#     await message.answer("Введите вашу фамилию:")
#     await RegistrationStates.waiting_for_surname.set()
#
#
# @dp.message(state=RegistrationStates.waiting_for_surname)
# async def process_surname(message: types.Message, state: FSMContext):
#     await state.update_data(surname=message.text)
#     await message.answer("Введите ваш номер телефона:")
#     await RegistrationStates.waiting_for_phone.set()
#
#
# @dp.message(state=RegistrationStates.waiting_for_phone)
# async def process_phone(message: types.Message, state: FSMContext):
#     await state.update_data(phone=message.text)
#     await message.answer("Введите вашу группу:")
#     await RegistrationStates.waiting_for_group.set()
#
#
# @dp.message_handler(state=RegistrationStates.waiting_for_group)
# async def process_group(message: types.Message, state: FSMContext):
#     user_data = await state.get_data()
#     name = user_data.get('name')
#     surname = user_data.get('surname')
#     phone = user_data.get('phone')
#     group = message.text
#
#     # Сохранение данных в Google Sheets
#     save_user_data(name, surname, phone, group)
#
#     await message.answer("Регистрация завершена! Теперь выберите правильный ответ:")
#
#     # Отправка вопроса с вариантами ответов
#     await show_question(message)
#
#     await state.finish()
#
#
#
# def save_user_data(name, surname, phone, group):
#     worksheet = connect_to_google_sheets()
#     # Добавляем данные пользователя в таблицу
#     worksheet.append_row([name, surname, phone, group, 0])
