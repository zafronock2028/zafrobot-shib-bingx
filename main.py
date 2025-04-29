import os
import asyncio
from kucoin.client import User as UserClient
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()

# Credenciales de KuCoin (usando los nombres correctos)
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")

# Token del Bot de Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Crear cliente de KuCoin
client = UserClient(API_KEY, SECRET_KEY, API_PASSPHRASE)

# Crear Bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Configurar teclado
keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🚀 Encender Bot")],
    [KeyboardButton(text="🛑 Apagar Bot")],
    [KeyboardButton(text="💰 Saldo")],
    [KeyboardButton(text="📊 Estado Bot")]
], resize_keyboard=True)

# Variable para controlar el encendido del bot
bot_encendido = False

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("¡Bienvenido al Zafrobot Dinámico Pro Scalping SHIB/USDT!", reply_markup=keyboard)

@dp.message()
async def manejar_mensajes(message: types.Message):
    global bot_encendido
    texto = message.text

    if texto == "🚀 Encender Bot":
        bot_encendido = True
        await message.answer("✅ Bot encendido. Operando en automático.")
        asyncio.create_task(iniciar_operacion())

    elif texto == "🛑 Apagar Bot":
        bot_encendido = False
        await message.answer("🛑 Bot apagado manualmente.")

    elif texto == "💰 Saldo":
        saldo = obtener_saldo()
        await message.answer(f"💰 Tu saldo disponible es: {saldo:.2f} USDT")

    elif texto == "📊 Estado Bot":
        estado = "ENCENDIDO ✅" if bot_encendido else "APAGADO 🛑"
        await message.answer(f"📊 Estado actual del bot: {estado}")

async def iniciar_operacion():
    global bot_encendido
    while bot_encendido:
        try:
            saldo = obtener_saldo()
            if saldo > 5:  # Ejemplo de lógica simple
                print("Comprando SHIB...")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Error en operación: {e}")
            await asyncio.sleep(10)

def obtener_saldo():
    try:
        cuentas = client.get_account_list()
        usdt_cuenta = next((c for c in cuentas if c['currency'] == 'USDT' and c['type'] == 'trade'), None)
        if usdt_cuenta:
            return float(usdt_cuenta['available'])
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
    return 0.0

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())