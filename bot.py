import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
import os
import re
import asyncio
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import StatesGroup, State

# Конфигурация
API_TOKEN = '1177090472:AAG8WP9HE29i2M2snlvRCiz9miQ00umR7NM'
SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 587
SMTP_USERNAME = "munka.help@mail.ru"
SMTP_PASSWORD = "K7hy32VXY0fA5Fbq7fTV"
RECIPIENT_EMAIL = "vladimir.973@list.ru"
FILES_DIR = 'files'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

class Form(StatesGroup):
    name = State()
    email = State()
    contacts = State()
    address = State()
    question = State()
    document = State()
    preview = State()

@router.message(Command(commands=["start"]))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Добро пожаловать! Пожалуйста, введите ваше имя:")
    await state.set_state(Form.name)

@router.message(StateFilter(Form.name))
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите вашу почту:")
    await state.set_state(Form.email)

@router.message(StateFilter(Form.email))
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    if re.match(r"[^@]+@[^@]+\.[^@]+", email):
        await state.update_data(email=email)
        await message.answer("Введите ваши контактные данные (например, номер телефона):")
        await state.set_state(Form.contacts)
    else:
        await message.answer("Некорректный email. Пожалуйста, введите заново:")

@router.message(StateFilter(Form.contacts))
async def process_contacts(message: types.Message, state: FSMContext):
    await state.update_data(contacts=message.text)
    await message.answer("Введите вашу территорию проживания (адрес):")
    await state.set_state(Form.address)

@router.message(StateFilter(Form.address))
async def process_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("Введите ваш вопрос:")
    await state.set_state(Form.question)

@router.message(StateFilter(Form.question))
async def process_question(message: types.Message, state: FSMContext):
    await state.update_data(question=message.text)
    
    skip_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_document")]
    ])
    
    await message.answer("Пожалуйста, прикрепите файлы или фотографии (отправьте все файлы поочередно):", reply_markup=skip_button)
    await state.set_state(Form.document)

@router.callback_query(F.data == "skip_document", StateFilter(Form.document))
async def skip_document(callback_query: types.CallbackQuery, state: FSMContext):
    await state.update_data(files=[])
    await preview_application(callback_query.message, state)
    await callback_query.answer()

@router.message(StateFilter(Form.document), F.content_type == types.ContentType.DOCUMENT)
async def process_document(message: types.Message, state: FSMContext, bot: Bot):
    document = await bot.download(message.document.file_id)
    data = await state.get_data()
    app_number = data.get('app_number', os.urandom(4).hex())
    user_dir = os.path.join(FILES_DIR, app_number)

    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    file_path = os.path.join(user_dir, message.document.file_name)
    with open(file_path, 'wb') as f:
        f.write(document.read())

    files = data.get('files', [])
    files.append(file_path)
    await state.update_data(app_number=app_number, files=files)
    
    skip_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_document")]
    ])
    
    await message.answer("Файл получен. Отправьте еще файлы или нажмите 'Пропустить', если больше нет файлов.", reply_markup=skip_button)

@router.message(StateFilter(Form.document), F.content_type == types.ContentType.PHOTO)
async def process_photo(message: types.Message, state: FSMContext, bot: Bot):
    photo = await bot.download(message.photo[-1].file_id)
    data = await state.get_data()
    app_number = data.get('app_number', os.urandom(4).hex())
    user_dir = os.path.join(FILES_DIR, app_number)

    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    file_name = f"{message.photo[-1].file_id}.jpg"
    file_path = os.path.join(user_dir, file_name)
    with open(file_path, 'wb') as f:
        f.write(photo.read())

    files = data.get('files', [])
    files.append(file_path)
    await state.update_data(app_number=app_number, files=files)
    
    skip_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_document")]
    ])
    
    await message.answer("Фотография получена. Отправьте еще файлы или нажмите 'Пропустить', если больше нет файлов.", reply_markup=skip_button)

async def preview_application(message: types.Message, state: FSMContext):
    data = await state.get_data()
    app_number = data.get('app_number')

    body = f"""
    <b>Предварительный просмотр заявки:</b>
    <b>Номер заявки:</b> {app_number}
    <b>Имя:</b> {data['name']}
    <b>Email:</b> {data['email']}
    <b>Контакты:</b> {data['contacts']}
    <b>Адрес:</b> {data['address']}
    <b>Вопрос:</b> {data['question']}
    """

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отправить", callback_data="send_application")],
        [InlineKeyboardButton(text="Начать заново", callback_data="start_over")]
    ])

    await message.answer(body, reply_markup=buttons, parse_mode="HTML")
    await state.set_state(Form.preview)

@router.callback_query(F.data == "send_application", StateFilter(Form.preview))
async def confirm_send_application(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    files = data.get('files', [])
    
    if files:
        file_path = files[0]  # Путь к файлу
    else:
        file_path = None
    
    logger.info(f"File path for email attachment: {file_path}")  # Отладочное сообщение
    
    await send_email_with_attachment(
        RECIPIENT_EMAIL, 
        f"Новая заявка №{data.get('app_number', 'Unknown')}",
        f"Поступила новая заявка:\nИмя: {data['name']}\nEmail: {data['email']}\nКонтакты: {data['contacts']}\nАдрес: {data['address']}\nВопрос: {data['question']}",
        file_path
    )
    
    await callback_query.message.answer("Спасибо! Ваша заявка принята. Ожидайте, скоро с вами свяжется менеджер.")
    await state.clear()
    await callback_query.answer()



@router.callback_query(F.data == "start_over", StateFilter(Form.preview))
async def start_over_application(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cmd_start(callback_query.message, state)
    await callback_query.answer()


async def send_email_with_attachment(to_email, subject, body, file_path=None):
    msg = MIMEMultipart()
    msg['From'] = SMTP_USERNAME
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
    if file_path and os.path.isfile(file_path):
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type, mime_subtype = mime_type.split('/', 1) if mime_type else ('application', 'octet-stream')
        
        with open(file_path, 'rb') as file:
            part = MIMEBase(mime_type, mime_subtype)
            part.set_payload(file.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
            msg.attach(part)
    
    # Отправка письма
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
    
    logger.info(f"Email sent to {to_email} with attachment {file_path if file_path else 'no attachment'}")
async def main():
    if not os.path.exists(FILES_DIR):
        os.makedirs(FILES_DIR)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
