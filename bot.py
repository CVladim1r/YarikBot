import logging
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import InputFile
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
    await message.answer("Пожалуйста, прикрепите файл:")
    await state.set_state(Form.document)

@router.message(StateFilter(Form.document), F.content_type == types.ContentType.DOCUMENT)
async def process_file(message: types.Message, state: FSMContext, bot: Bot):
    document_id = message.document.file_id
    document_info = await bot.get_file(document_id)
    document = await bot.download_file(document_info.file_path)

    file_path = f"./{message.document.file_name}"
    with open(file_path, "wb") as f:
        f.write(document.read())

    await state.update_data(file_path=file_path)
    data = await state.get_data()

    await send_email(data)

    await message.answer("Спасибо! Ваша заявка принята.")
    await state.clear()

async def send_email(data):
    msg = MIMEMultipart()
    msg['From'] = SMTP_LOGIN
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = "Новая заявка"

    body = f"""
    Имя: {data['name']}
    Email: {data['email']}
    Ник в Telegram: {data['tg_nick']}
    Адрес: {data['address']}
    Вопрос: {data['question']}
    """

    msg.attach(MIMEText(body, 'plain'))

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
