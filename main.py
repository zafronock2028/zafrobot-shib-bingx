import os
import asyncio
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)

bot_encendido = False

menu_teclado = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Encender"), KeyboardButton(text="❌ Apagar")],
        [KeyboardButton(text="💰 Actualizar Saldo"), KeyboardButton(text="📊 Estado")]
    ],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def bienvenida(message: types.Message):
    await message.answer("✅ ZafroBot Scalper PRO ha iniciado correctamente. Listo para recibir comandos.", reply_markup=menu_teclado)

async def obtener_saldo():
    cuentas = client.get_accounts()
    saldo = 0
    for cuenta in cuentas:
        if cuenta['type'] == 'trade' and cuenta['currency'] == 'USDT':
            saldo = float(cuenta['balance'])
    return saldo

async def notificar_deposito():
    saldo = await obtener_saldo()
    mensaje = f"💸 Depósito detectado. Saldo actualizado: {saldo:.2f} USDT disponible."
    await bot.send_message(chat_id=CHAT_ID, text=mensaje)

@dp.message(lambda message: message.text == "✅ Encender")
async def encender_bot(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🔔 Bot encendido. Escaneando el mercado...")
        asyncio.create_task(notificar_deposito())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda message: message.text == "❌ Apagar")
async def apagar_bot(message: types.Message):
    global bot_encendido
    if bot_encendido:
        bot_encendido = False
        await message.answer("🔕 Bot apagado.")
    else:
        await message.answer("⚠️ El bot ya está apagado.")

@dp.message(lambda message: message.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = await obtener_saldo()
    await message.answer(f"💰 Saldo actual disponible en Trading: {saldo:.2f} USDT")

@dp.message(lambda message: message.text == "📊 Estado")
async def estado_bot(message: types.Message):
    estado = "✅ Encendido" if bot_encendido else "❌ Apagado"
    await message.answer(f"📊 Estado actual del bot: {estado}")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
