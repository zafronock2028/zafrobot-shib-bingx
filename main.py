# ---- Bloque 1: Importaciones ----
import asyncio
import logging
import os
import random
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from kucoin.client import Client

# ---- Bloque 2: Cargar variables de entorno ----
load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

client = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# ---- Bloque 3: Variables globales ----
pares = ['SHIB-USDT', 'PEPE-USDT', 'FLOKI-USDT', 'BONK-USDT']
operacion_en_curso = False
saldo_actual = 0.0
TRAILING_STOP_PERCENT = 8  # 8%

# ---- Bloque 4: Funciones Utilitarias ----
def calcular_trailing_stop(precio_entrada):
    stop_loss = precio_entrada * (1 - TRAILING_STOP_PERCENT / 100)
    return stop_loss

async def obtener_saldo():
    try:
        accounts = client.get_accounts()
        for acc in accounts:
            if acc['currency'] == 'USDT' and acc['type'] == 'trade':
                return float(acc['available'])
        return 0.0
    except Exception as e:
        logging.error(f"Error al obtener saldo: {e}")
        return 0.0

async def obtener_precio(par):
    try:
        ticker = client.get_ticker(symbol=par)
        return float(ticker['price'])
    except Exception as e:
        logging.error(f"Error al obtener precio: {e}")
        return None

async def comprar(par, monto):
    try:
        client.create_market_order(par, 'buy', funds=monto)
        return True
    except Exception as e:
        logging.error(f"Error en compra: {e}")
        return False

async def vender(par, cantidad):
    try:
        client.create_market_order(par, 'sell', size=cantidad)
        return True
    except Exception as e:
        logging.error(f"Error en venta: {e}")
        return False

# ---- Bloque 5: Lógica del Bot ----
async def escanear_mercado():
    global operacion_en_curso
    global saldo_actual

    while operacion_en_curso:
        try:
            saldo_actual = await obtener_saldo()
            if saldo_actual < 5:
                logging.warning("Saldo insuficiente para operar.")
                await asyncio.sleep(10)
                continue

            par = random.choice(pares)
            precio_entrada = await obtener_precio(par)
            if precio_entrada is None:
                await asyncio.sleep(5)
                continue

            monto_operacion = saldo_actual * 0.8
            compra_exitosa = await comprar(par, monto_operacion)

            if compra_exitosa:
                await bot.send_message(CHAT_ID, f"✅ Compra ejecutada en {par} a {precio_entrada}")
                stop_loss = calcular_trailing_stop(precio_entrada)

                while True:
                    precio_actual = await obtener_precio(par)
                    if precio_actual is None:
                        await asyncio.sleep(5)
                        continue

                    if precio_actual >= precio_entrada * 1.015:
                        await vender(par, await obtener_saldo())
                        await bot.send_message(CHAT_ID, f"✅ Venta por ganancia en {par}")
                        operacion_en_curso = False
                        break
                    elif precio_actual <= stop_loss:
                        await vender(par, await obtener_saldo())
                        await bot.send_message(CHAT_ID, f"⚠️ Venta por Trailing Stop en {par}")
                        operacion_en_curso = False
                        break

                    await asyncio.sleep(10)
        except Exception as e:
            logging.error(f"Error en escaneo: {e}")
            await asyncio.sleep(10)

# ---- Bloque 6: Comandos de Telegram ----
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("✅ Bot iniciado correctamente.")

@dp.message_handler(commands=['encender'])
async def cmd_encender(message: types.Message):
    global operacion_en_curso
    if not operacion_en_curso:
        operacion_en_curso = True
        await bot.send_message(CHAT_ID, "✅ Bot encendido y escaneando mercado.")
        asyncio.create_task(escanear_mercado())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message_handler(commands=['apagar'])
async def cmd_apagar(message: types.Message):
    global operacion_en_curso
    operacion_en_curso = False
    await message.answer("⛔ Bot apagado.")

# ---- Lanzador del Bot ----
if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)