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
dp = Dispatcher(bot)

# --- Bloque 3: Variables globales ---
pares = ['SHIB-USDT', 'PEPE-USDT', 'FLOKI-USDT', 'BONK-USDT']
operacion_en_curso = False
saldo_actual = 0.0

TRAILING_STOP_PERCENT = 8  # Trailing Stop de -8%

# --- Bloque 4: Funciones utilitarias ---
def calcular_trailing_stop(precio_entrada):
    stop_loss = precio_entrada * (1 - TRAILING_STOP_PERCENT / 100)
    return stop_loss

# --- Bloque 5: Funciones de trading ---
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

# --- Teclado personalizado ---
menu_principal = ReplyKeyboardMarkup(resize_keyboard=True)
menu_principal.add(KeyboardButton('🚀 Encender Bot'))
menu_principal.add(KeyboardButton('📈 Estado del Bot'))
menu_principal.add(KeyboardButton('📋 Estado de la Orden'))

# --- Comandos básicos ---
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer("✅ ZafroBot Scalper Pro Activo", reply_markup=menu_principal)

@dp.message_handler(lambda message: message.text == '📈 Estado del Bot')
async def estado_bot(message: types.Message):
    estado = "Activo" if operacion_en_curso else "Inactivo"
    await message.answer(f"📊 Estado del Bot: {estado}")

@dp.message_handler(lambda message: message.text == '📋 Estado de la Orden')
async def estado_orden_actual(message: types.Message):
    await message.answer("📋 Función de Estado de Orden aún en desarrollo.")

@dp.message_handler(lambda message: message.text == '🚀 Encender Bot')
async def encender_bot(message: types.Message):
    global operacion_en_curso, saldo_actual
    saldo_actual = await obtener_saldo()
    if saldo_actual < 5:
        await message.answer("⚠️ Saldo insuficiente para operar.")
        return
    operacion_en_curso = True
    await message.answer(f"✅ Bot encendido. Saldo disponible: {saldo_actual} USDT")
    asyncio.create_task(escaneo_mercado())

@dp.message_handler(commands=['stop'])
async def apagar_bot(message: types.Message):
    global operacion_en_curso
    operacion_en_curso = False
    await message.answer("🔴 Bot apagado manualmente.")

# --- Lanzador de AIOgram ---
if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)

# --- Función principal de escaneo ---
async def escaneo_mercado():
    global operacion_en_curso, saldo_actual
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
                    logging.warning("⚠️ No se pudo obtener volumen.")
                    continue

                monto_operacion = min(saldo_actual, volumen_24h * 0.04)
                if monto_operacion < 5:
                    logging.warning("⚠️ Monto de operación muy pequeño.")
                    continue

                ticker = await client.get_ticker(par)
                precio_actual = float(ticker['price'])

                precio_entrada = precio_actual
                stop_loss = calcular_trailing_stop(precio_entrada)

                # Ejecutar compra
                orden_compra = await client.create_market_order(
                    symbol=par,
                    side='buy',
                    size=round(monto_operacion / precio_actual, 2)
                )
                logging.info(f"✅ Compra ejecutada en {par}")

                await bot.send_message(
                    CHAT_ID,
                    f"✅ COMPRA ejecutada en {par}"
                )

                await gestionar_salida(par, precio_entrada)

        except Exception as e:
            logging.error(f"❌ Error en escaneo de mercado: {e}")

        await asyncio.sleep(5)

# --- Función para gestionar salida (venta) ---
async def gestionar_salida(par, precio_entrada):
    global operacion_en_curso
    stop_loss = calcular_trailing_stop(precio_entrada)
    try:
        while operacion_en_curso:
            ticker = await client.get_ticker(par)
            precio_actual = float(ticker['price'])

            if precio_actual >= precio_entrada * 1.015:
                await client.create_market_order(
                    symbol=par,
                    side='sell',
                    size=round(await obtener_balance_simbolo(par), 2)
                )
                logging.info(f"✅ Venta ejecutada (Objetivo alcanzado) {par}")
                await bot.send_message(
                    CHAT_ID,
                    f"✅ VENTA ejecutada en {par} (Ganancia alcanzada)"
                )
                operacion_en_curso = False
                break

            if precio_actual <= stop_loss:
                await client.create_market_order(
                    symbol=par,
                    side='sell',
                    size=round(await obtener_balance_simbolo(par), 2)
                )
                logging.info(f"⚠️ Venta ejecutada por Trailing Stop {par}")
                await bot.send_message(
                    CHAT_ID,
                    f"⚠️ VENTA ejecutada en {par} (Trailing Stop)"
                )
                operacion_en_curso = False
                break

            await asyncio.sleep(5)

    except Exception as e:
        logging.error(f"❌ Error en gestión de salida: {e}")

# --- Función para obtener balance del par ---
async def obtener_balance_simbolo(par):
    try:
        symbol_base = par.split('-')[0]
        cuentas = user_client.get_account_list()
        for cuenta in cuentas:
            if cuenta['currency'] == symbol_base:
                return float(cuenta['available'])
        return 0.0
    except Exception as e:
        logging.error(f"Error al obtener balance de símbolo: {e}")
        return 0.0