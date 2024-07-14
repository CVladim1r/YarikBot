import logging
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import StatesGroup, State
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import asyncio
import os

API_TOKEN = '6848117166:AAGxWjBudAQulBcY6lCG1_cdwlArp3r4iKI'
SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 587
SMTP_LOGIN = "munka.help@mail.ru"
SMTP_PASSWORD = "K7hy32VXY0fA5Fbq7fTV"
RECIPIENT_EMAIL = "vladimir.973@list.ru"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

class Form(StatesGroup):
    name = State()
    email = State()
    tg_nick = State()
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
    await state.update_data(email=message.text)
    await message.answer("Введите ваш ник в Telegram:")
    await state.set_state(Form.tg_nick)

@router.message(StateFilter(Form.tg_nick))
async def process_telegram_nick(message: types.Message, state: FSMContext):
    await state.update_data(tg_nick=message.text)
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
    
    await message.answer("Пожалуйста, прикрепите файл или фотографию:", reply_markup=skip_button)
    await state.set_state(Form.document)

@router.callback_query(F.data == "skip_document", StateFilter(Form.document))
async def skip_document(callback_query: types.CallbackQuery, state: FSMContext):
    await state.update_data(file_path=None)
    await preview_application(callback_query.message, state)
    await callback_query.answer()

@router.message(StateFilter(Form.document), F.content_type == types.ContentType.DOCUMENT)
async def process_document(message: types.Message, state: FSMContext, bot: Bot):
    document_id = message.document.file_id
    document_info = await bot.get_file(document_id)
    document = await bot.download_file(document_info.file_path)

    file_path = f"./{message.document.file_name}"
    with open(file_path, "wb") as f:
        f.write(document.read())

    await state.update_data(file_path=file_path)
    await preview_application(message, state)

@router.message(StateFilter(Form.document), F.content_type == types.ContentType.PHOTO)
async def process_photo(message: types.Message, state: FSMContext, bot: Bot):
    photo_id = message.photo[-1].file_id
    photo_info = await bot.get_file(photo_id)
    photo = await bot.download_file(photo_info.file_path)

    file_path = f"./{photo_id}.jpg"
    with open(file_path, "wb") as f:
        f.write(photo.read())

    await state.update_data(file_path=file_path)
    await preview_application(message, state)

async def preview_application(message: types.Message, state: FSMContext):
    data = await state.get_data()
    app_number = data.get('app_number', os.urandom(4).hex())
    await state.update_data(app_number=app_number)

    body = f"""
    <b>Предварительный просмотр заявки:</b>
    <b>Номер заявки:</b> {app_number}
    <b>Имя:</b> {data['name']}
    <b>Email:</b> {data['email']}
    <b>Ник в Telegram:</b> {data['tg_nick']}
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
    await send_email(data)
    await callback_query.message.answer("Спасибо! Ваша заявка принята. Ожидайте, скоро с вами свяжется менеджер.")
    await state.clear()
    await callback_query.answer()

@router.callback_query(F.data == "start_over", StateFilter(Form.preview))
async def start_over_application(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cmd_start(callback_query.message, state)
    await callback_query.answer()

async def send_email(data):
    msg = MIMEMultipart()
    msg['From'] = SMTP_LOGIN
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = f"Новая заявка №{data['app_number']}"

    body = f"""
    <html>
        <head></head>
        <body>
            <p>Новая заявка была получена:</p>
            <table border="1" style="border-collapse: collapse;">
                <tr>
                    <th style="padding: 8px; text-align: left;">Номер заявки</th>
                    <td style="padding: 8px;">{data['app_number']}</td>
                </tr>
                <tr>
                    <th style="padding: 8px; text-align: left;">Имя</th>
                    <td style="padding: 8px;">{data['name']}</td>
                </tr>
                <tr>
                    <th style="padding: 8px; text-align: left;">Email</th>
                    <td style="padding: 8px;">{data['email']}</td>
                </tr>
                <tr>
                    <th style="padding: 8px; text-align: left;">Ник в Telegram</th>
                    <td style="padding: 8px;"><a href='https://t.me/{data['tg_nick']}'>{data['tg_nick']}</a></td>
                </tr>
                <tr>
                    <th style="padding: 8px; text-align: left;">Адрес</th>
                    <td style="padding: 8px;">{data['address']}</td>
                </tr>
                <tr>
                    <th style="padding: 8px; text-align: left;">Вопрос</th>
                    <td style="padding: 8px;">{data['question']}</td>
                </tr>
            </table>
        </body>
    </html>
    """

    msg.attach(MIMEText(body, 'html'))

    if data['file_path']:
        attachment = open(data['file_path'], "rb")
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(data['file_path'])}")
        msg.attach(part)

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_LOGIN, SMTP_PASSWORD)
    text = msg.as_string()
    server.sendmail(SMTP_LOGIN, RECIPIENT_EMAIL, text)
    server.quit()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
