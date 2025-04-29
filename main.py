import os
import asyncio
import logging
from kucoin.client import User as UserClient
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Credenciales de KuCoin
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

bot_encendido = False
pares = ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT"]

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("¡Bienvenido al Zafrobot Dinámico Pro Scalping!", reply_markup=keyboard)

@dp.message()
async def manejar_mensajes(message: types.Message):
    global bot_encendido
    texto = message.text

    if texto == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido. Operando en automático.")
            asyncio.create_task(iniciar_operacion())
        else:
            await message.answer("⚠️ El bot ya está encendido.")
    elif texto == "🛑 Apagar Bot":
        if bot_encendido:
            bot_encendido = False
            await message.answer("🛑 Bot apagado manualmente.")
        else:
            await message.answer("⚠️ El bot ya está apagado.")
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
            for par in pares:
                await analizar_par(par)
            await asyncio.sleep(60)
        except Exception as e:
            logging.error(f"Error general en operación: {e}")
            await asyncio.sleep(60)

async def analizar_par(par):
    try:
        klines = client.get_kline_data(par, kline_type='1min', limit=5)
        precios = [float(k[2]) for k in klines]
        promedio = sum(precios) / len(precios)
        ticker = client.get_ticker(par)
        precio_actual = float(ticker['price'])

        if precio_actual < promedio * 0.99:
            logging.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Oportunidad detectada en {par}: Precio actual {precio_actual:.6f}, Promedio {promedio:.6f}")
            # ejecutar orden de compra aquí
        else:
            logging.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {par}: Sin oportunidad. Precio actual {precio_actual:.6f}, Promedio {promedio:.6f}")
    except Exception as e:
        logging.error(f"Error analizando {par}: {e}")

async def monitorear_orden():
    try:
        # Aquí irá la lógica para monitorear las órdenes
        pass
    except Exception as e:
        logging.error(f"Error al monitorear orden: {e}")

def obtener_saldo():
    try:
        cuentas = client.get_account_list()
        usdt_cuenta = next((c for c in cuentas if c['currency'] == 'USDT' and c['type'] == 'trade'), None)
        if usdt_cuenta:
            return float(usdt_cuenta['available'])
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
    return 0.0

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())