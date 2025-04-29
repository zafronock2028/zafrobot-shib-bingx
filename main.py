# === Bloque 1: Importaciones ===
import asyncio
import logging
import os
import random
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup

from kucoin.client import User as UserClient
from kucoin.client import Market as MarketClient

# === Bloque 2: Cargar variables de entorno ===
load_dotenv()

API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

user_client = UserClient(API_KEY, SECRET_KEY, API_PASSPHRASE)
client = MarketClient()
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# === Bloque 3: Variables globales ===
pares = ['SHIB-USDT', 'PEPE-USDT', 'FLOKI-USDT', 'BONK-USDT']
operacion_en_curso = False
saldo_actual = 0.0
TRAILING_STOP_PERCENT = 8  # Trailing Stop de -8%

# === Bloque 4: Funciones utilitarias ===
def calcular_trailing_stop(precio_entrada):
    stop_loss = precio_entrada * (1 - TRAILING_STOP_PERCENT / 100)
    return stop_loss

async def obtener_saldo():
    try:
        cuentas = user_client.get_account_list()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
        return 0.0
    except Exception as e:
        logging.error(f"Error al obtener saldo: {e}")
        return 0.0

async def calcular_monto_operacion(par):
    try:
        ticker = await client.get_ticker(par)
        volumen_24h_usdt = float(ticker['volValue'])
        max_monto = volumen_24h_usdt * 0.04
        monto_operacion = min(saldo_actual, max_monto)
        return monto_operacion
    except Exception as e:
        logging.error(f"Error al calcular monto de operación: {e}")
        return saldo_actual * 0.05

async def obtener_volumen_24h(par):
    try:
        data = await client.get_ticker(par)
        return float(data['volValue'])
    except Exception as e:
        logging.error(f"Error al obtener volumen 24h: {e}")
        return None

def calcular_kelly(win_rate, reward_risk_ratio):
    return (win_rate - (1 - win_rate) / reward_risk_ratio)

# === Teclado personalizado ===
menu_principal = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot")],
        [KeyboardButton(text="📋 Estado de la Orden")]
    ],
    resize_keyboard=True
)

# === Comandos básicos ===
@dp.message(Command(commands=["start"]))
async def start_command(message: Message):
    await message.answer("✅ ZafroBot Scalper Pro iniciado.", reply_markup=menu_principal)

@dp.message(lambda message: message.text == "📊 Estado del Bot")
async def estado_bot(message: Message):
    estado = "Activo ✅" if operacion_en_curso else "Inactivo 🛑"
    await message.answer(f"📊 Estado actual del bot: {estado}")

@dp.message(lambda message: message.text == "📋 Estado de la Orden")
async def estado_orden_actual(message: Message):
    await message.answer("📋 Función de Estado de la Orden ejecutada.")

@dp.message(lambda message: message.text == "🚀 Encender Bot")
async def encender_bot(message: Message):
    global operacion_en_curso
    operacion_en_curso = True
    await message.answer("🟢 Bot encendido. Escaneando mercado...")
    asyncio.create_task(escaneo_mercado())

@dp.message(lambda message: message.text == "🛑 Apagar Bot")
async def apagar_bot(message: Message):
    global operacion_en_curso
    operacion_en_curso = False
    await message.answer("🔴 Bot apagado.")

# === Escaneo de mercado y trading ===
async def escaneo_mercado():
    global saldo_actual
    global operacion_en_curso

    while operacion_en_curso:
        try:
            for par in pares:
                saldo_actual = await obtener_saldo()
                if saldo_actual < 5:
                    logging.warning("⚠️ Saldo insuficiente.")
                    await asyncio.sleep(10)
                    continue

                volumen_24h = await obtener_volumen_24h(par)
                if volumen_24h is None:
                    logging.warning(f"⚠️ No se pudo obtener volumen para {par}")
                    continue

                monto_operacion = min(saldo_actual, volumen_24h * 0.04)
                if monto_operacion < 5:
                    logging.warning(f"⚠️ Monto de operación muy bajo para {par}")
                    continue

                ticker = await client.get_ticker(par)
                precio_actual = float(ticker['price'])

                precio_entrada = precio_actual
                stop_loss = calcular_trailing_stop(precio_entrada)

                # Simula una compra (lógica real de compra iría aquí)
                logging.info(f"✅ Compra simulada en {par} a precio {precio_actual}")

                await bot.send_message(
                    CHAT_ID,
                    f"✅ COMPRA simulada en {par}\n"
                    f"🎯 Precio de Entrada: {precio_actual}\n"
                    f"🛡️ Stop Loss: {stop_loss}"
                )

                # Aquí iría tu lógica de venta
                await asyncio.sleep(10)

            await asyncio.sleep(15)

        except Exception as e:
            logging.error(f"❌ Error en escaneo de mercado: {e}")
            await asyncio.sleep(5)

# === Lanzador principal ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())