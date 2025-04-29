# --- Bloque 1: Importaciones ---
import asyncio
import logging
import os
import random
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from kucoin.client import User as UserClient
from kucoin.client import Market as MarketClient

# --- Bloque 2: Cargar variables de entorno ---
load_dotenv()

API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

user_client = UserClient(API_KEY, SECRET_KEY, API_PASSPHRASE)
client = MarketClient()
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# --- Bloque 3: Variables globales ---
pares = ['SHIB-USDT', 'PEPE-USDT', 'FLOKI-USDT', 'BONK-USDT']
operacion_en_curso = False
saldo_actual = 0.0
TRAILING_STOP_PERCENT = 8  # Trailing Stop de -8%

# --- Bloque 4: Teclado personalizado ---
menu_principal = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton('🚀 Encender Bot')],
        [KeyboardButton('📊 Estado de Bot')],
        [KeyboardButton('📋 Estado de Orden')],
        [KeyboardButton('💰 Actualizar Saldo')]
    ],
    resize_keyboard=True
)

# --- Bloque 5: Funciones de utilidad ---
def calcular_trailing_stop(precio_entrada):
    stop_loss = precio_entrada * (1 - TRAILING_STOP_PERCENT / 100)
    return stop_loss

def calcular_kelly(win_rate, reward_risk_ratio):
    return (win_rate - (1 - win_rate) / reward_risk_ratio)

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

# --- Bloque 6: Comandos del bot ---
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer("✅ ZafroBot Dinámico Pro", reply_markup=menu_principal)

@dp.message_handler(lambda message: message.text == '💰 Actualizar Saldo')
async def actualizar_saldo(message: types.Message):
    global saldo_actual
    saldo_actual = await obtener_saldo()
    await message.answer(f"💵 Saldo disponible: {saldo_actual:.2f} USDT")

@dp.message_handler(lambda message: message.text == '🚀 Encender Bot')
async def encender_bot(message: types.Message):
    global operacion_en_curso
    operacion_en_curso = True
    await message.answer("🟢 Bot encendido. Escaneando el mercado...")
    asyncio.create_task(escaneo_mercado())

@dp.message_handler(lambda message: message.text == '🔴 Apagar Bot')
async def apagar_bot(message: types.Message):
    global operacion_en_curso
    operacion_en_curso = False
    await message.answer("🔴 Bot apagado.")

@dp.message_handler(lambda message: message.text == '📊 Estado de Bot')
async def estado_bot(message: types.Message):
    estado = "Activo" if operacion_en_curso else "Inactivo"
    await message.answer(f"📊 Estado del bot: {estado}")

@dp.message_handler(lambda message: message.text == '📋 Estado de Orden')
async def estado_orden_actual(message: types.Message):
    await message.answer("📋 Función de Estado de Orden activada.")

# --- Bloque 7: Lógica principal de escaneo y operaciones ---
async def escaneo_mercado():
    global operacion_en_curso
    global saldo_actual

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
                    logging.warning(f"⚠️ Monto de operación muy pequeño para {par}")
                    continue

                ticker = await client.get_ticker(par)
                precio_actual = float(ticker['price'])

                precio_entrada = precio_actual
                stop_loss = calcular_trailing_stop(precio_entrada)

                # Ejecutar compra
                await client.create_market_order(
                    symbol=par,
                    side='buy',
                    size=round(monto_operacion / precio_actual, 4)
                )
                logging.info(f"✅ Compra ejecutada en {par}")

                await bot.send_message(
                    CHAT_ID,
                    f"✅ COMPRA ejecutada en {par}\n"
                    f"Objetivo de Venta: {precio_entrada * 1.015:.6f}"
                )

                await gestionar_salida(par, precio_entrada, stop_loss)

        except Exception as e:
            logging.error(f"❌ Error general en escaneo de mercado: {e}")
        await asyncio.sleep(10)

async def gestionar_salida(par, precio_entrada, stop_loss):
    global operacion_en_curso

    await asyncio.sleep(15)

    while operacion_en_curso:
        try:
            ticker = await client.get_ticker(par)
            precio_actual = float(ticker['price'])

            if precio_actual >= precio_entrada * 1.015:
                await client.create_market_order(
                    symbol=par,
                    side='sell',
                    size=round(await obtener_balance(par), 4)
                )
                await bot.send_message(CHAT_ID, f"✅ Venta ejecutada en {par} (Objetivo alcanzado)")
                operacion_en_curso = False
                break

            if precio_actual <= stop_loss:
                await client.create_market_order(
                    symbol=par,
                    side='sell',
                    size=round(await obtener_balance(par), 4)
                )
                await bot.send_message(CHAT_ID, f"⚠️ Venta ejecutada en {par} (Trailing Stop)")
                operacion_en_curso = False
                break

        except Exception as e:
            logging.error(f"❌ Error en gestión de salida: {e}")
        await asyncio.sleep(5)

async def obtener_balance(par):
    try:
        symbol_base = par.split('-')[0]
        cuentas = user_client.get_account_list()
        for cuenta in cuentas:
            if cuenta['currency'] == symbol_base and cuenta['type'] == 'trade':
                return float(cuenta['available'])
        return 0.0
    except Exception as e:
        logging.error(f"Error al obtener balance: {e}")
        return 0.0

# --- Bloque 8: Lanzador del bot ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)