# === Bloque 1: Importaciones ===
import asyncio
import logging
import os
import random
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client

# === Bloque 2: Cargar variables de entorno ===
load_dotenv()

API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
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

# === Bloque 5: Funciones de trading ===
async def obtener_saldo():
    try:
        cuentas = client.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
        return 0.0
    except Exception as e:
        logging.error(f"Error al obtener saldo: {e}")
        return 0.0

async def obtener_volumen_24h(par):
    try:
        data = client.get_ticker(par)
        return float(data['volValue'])
    except Exception as e:
        logging.error(f"Error al obtener volumen 24h: {e}")
        return None

def calcular_kelly(win_rate, reward_risk_ratio):
    return (win_rate - (1 - win_rate) / reward_risk_ratio)

async def calcular_monto_operacion(par):
    try:
        ticker = client.get_ticker(par)
        volumen_24h_usdt = float(ticker['volValue'])
        max_monto = volumen_24h_usdt * 0.04
        monto_operacion = min(saldo_actual, max_monto)
        return monto_operacion
    except Exception as e:
        logging.error(f"Error al calcular monto operacion: {e}")
        return saldo_actual * 0.05

# === Bloque 6: Teclado principal ===
menu_principal = ReplyKeyboardMarkup(resize_keyboard=True)
menu_principal.add(KeyboardButton('🚀 Encender Bot'))
menu_principal.add(KeyboardButton('🔴 Apagar Bot'))
menu_principal.add(KeyboardButton('📈 Estado del Bot'))
menu_principal.add(KeyboardButton('📄 Estado de Orden'))

# === Bloque 7: Comandos básicos ===
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer("✅ ZafroBot Dinámico Pro activado", reply_markup=menu_principal)

@dp.message_handler(lambda message: message.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global operacion_en_curso
    operacion_en_curso = True
    await message.answer("🟢 Bot encendido. Escaneando mercado...")
    asyncio.create_task(escaneo_mercado())

@dp.message_handler(lambda message: message.text == "🔴 Apagar Bot")
async def apagar_bot(message: types.Message):
    global operacion_en_curso
    operacion_en_curso = False
    await message.answer("🔴 Bot apagado.")

@dp.message_handler(lambda message: message.text == "📈 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "Activo" if operacion_en_curso else "Apagado"
    await message.answer(f"📈 Estado actual del bot: {estado}")

@dp.message_handler(lambda message: message.text == "📄 Estado de Orden")
async def estado_orden_actual(message: types.Message):
    await message.answer("📄 Función de Estado de orden activada")

# === Bloque 8: Escaneo del mercado ===
async def escaneo_mercado():
    global operacion_en_curso, saldo_actual
    saldo_actual = await obtener_saldo()

    while operacion_en_curso:
        try:
            for par in pares:
                saldo_actual = await obtener_saldo()
                if saldo_actual < 5:
                    logging.warning("⚠️ Saldo insuficiente")
                    await asyncio.sleep(10)
                    continue

                volumen_24h = await obtener_volumen_24h(par)
                if volumen_24h is None:
                    logging.warning(f"⚠️ No se pudo obtener volumen de {par}")
                    continue

                monto_operacion = min(saldo_actual, volumen_24h * 0.04)
                if monto_operacion < 5:
                    logging.warning(f"⚠️ Monto muy pequeño para operar en {par}")
                    continue

                ticker = client.get_ticker(par)
                precio_actual = float(ticker['price'])

                precio_compra = precio_actual
                precio_objetivo = precio_compra * 1.015

                orden_compra = client.create_market_order(
                    symbol=par,
                    side='buy',
                    size=round(monto_operacion / precio_compra, 4)
                )
                logging.info(f"✅ Compra ejecutada en {par}")
                await bot.send_message(
                    CHAT_ID,
                    f"✅ COMPRA ejecutada en {par}\nObjetivo de venta: {precio_objetivo:.6f}"
                )

                await gestionar_salida(par, precio_compra)
        except Exception as e:
            logging.error(f"❌ Error en escaneo de mercado: {e}")

        await asyncio.sleep(10)

# === Bloque 9: Gestión de salida ===
async def gestionar_salida(par, precio_entrada):
    global operacion_en_curso
    stop_loss = calcular_trailing_stop(precio_entrada)

    while operacion_en_curso:
        try:
            ticker = client.get_ticker(par)
            precio_actual = float(ticker['price'])

            if precio_actual >= precio_entrada * 1.015:
                await client.create_market_order(
                    symbol=par,
                    side='sell',
                    size=round(await obtener_saldo() / precio_actual, 4)
                )
                logging.info(f"✅ Venta ejecutada por objetivo alcanzado en {par}")
                await bot.send_message(
                    CHAT_ID,
                    f"✅ VENTA ejecutada en {par}\nGanancia: 1.5%"
                )
                operacion_en_curso = False
                break

            if precio_actual <= stop_loss:
                await client.create_market_order(
                    symbol=par,
                    side='sell',
                    size=round(await obtener_saldo() / precio_actual, 4)
                )
                logging.info(f"⚠️ Venta ejecutada por Trailing Stop en {par}")
                await bot.send_message(
                    CHAT_ID,
                    f"⚠️ VENTA por Trailing Stop en {par}"
                )
                operacion_en_curso = False
                break

        except Exception as e:
            logging.error(f"❌ Error en gestión de salida: {e}")

        await asyncio.sleep(5)

# === Bloque 10: Lanzador de AIogram ===
if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)