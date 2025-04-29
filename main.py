# === Bloque 1: Importaciones ===
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

# === Bloque 2: Cargar variables de entorno ===
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

# === Bloque 3: Variables globales ===
pares = ['SHIB-USDT', 'PEPE-USDT', 'FLOKI-USDT', 'BONK-USDT']
operacion_en_curso = False
saldo_actual = 0.0
TRAILING_STOP_PERCENT = 8  # Trailing Stop -8%

# === Bloque 4: Funciones utilitarias ===
def calcular_trailing_stop(precio_entrada):
    return precio_entrada * (1 - TRAILING_STOP_PERCENT / 100)

# === Bloque 5: Funciones principales ===
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
        volumen_24h = float(ticker['volValue'])
        return min(saldo_actual, volumen_24h * 0.04)
    except Exception as e:
        logging.error(f"Error al calcular monto: {e}")
        return saldo_actual * 0.05

async def obtener_volumen_24h(par):
    try:
        data = await client.get_ticker(par)
        return float(data['volValue'])
    except Exception as e:
        logging.error(f"Error volumen 24h: {e}")
        return None

async def obtener_balance(par):
    try:
        base = par.split('-')[0]
        cuentas = user_client.get_account_list()
        for cuenta in cuentas:
            if cuenta['currency'] == base and cuenta['type'] == 'trade':
                return float(cuenta['available'])
        return 0.0
    except Exception as e:
        logging.error(f"Error balance {par}: {e}")
        return 0.0

# === Bloque 6: Teclado Telegram ===
menu_principal = ReplyKeyboardMarkup(resize_keyboard=True)
menu_principal.add(KeyboardButton('🚀 Encender Bot'))
menu_principal.add(KeyboardButton('📊 Estado del Bot'))
menu_principal.add(KeyboardButton('📋 Estado de Orden'))

# === Bloque 7: Comandos de Telegram ===
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("✅ ¡ZafroBot Scalper PRO Activo!", reply_markup=menu_principal)

@dp.message_handler(lambda message: message.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "🟢 Activo" if operacion_en_curso else "🔴 Apagado"
    await message.answer(f"📊 Estado: {estado}")

@dp.message_handler(lambda message: message.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global operacion_en_curso
    operacion_en_curso = True
    await message.answer("🚀 Bot encendido. Analizando mercado...")
    asyncio.create_task(escaneo_mercado())

@dp.message_handler(lambda message: message.text == "📋 Estado de Orden")
async def estado_orden(message: types.Message):
    await message.answer("📋 Aún no hay una orden activa.")

# === Bloque 8: Trading Automático ===
async def escaneo_mercado():
    global operacion_en_curso, saldo_actual

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
                    continue

                monto = await calcular_monto_operacion(par)
                if monto < 5:
                    continue

                ticker = await client.get_ticker(par)
                precio_actual = float(ticker['price'])
                precio_objetivo = precio_actual * 1.025

                await client.create_market_order(
                    symbol=par,
                    side="buy",
                    size=round(monto / precio_actual, 2)
                )
                await bot.send_message(
                    CHAT_ID,
                    f"✅ Compra en {par} realizada.\nObjetivo: {precio_objetivo:.6f}"
                )

                await gestionar_salida(par, precio_actual)
                break

        except Exception as e:
            logging.error(f"Error escaneo mercado: {e}")

        await asyncio.sleep(5)

async def gestionar_salida(par, precio_entrada):
    global operacion_en_curso
    stop_loss = calcular_trailing_stop(precio_entrada)

    while operacion_en_curso:
        try:
            ticker = await client.get_ticker(par)
            precio_actual = float(ticker['price'])

            if precio_actual >= precio_entrada * 1.025:
                await client.create_market_order(
                    symbol=par,
                    side="sell",
                    size=round(await obtener_balance(par), 2)
                )
                await bot.send_message(CHAT_ID, f"✅ Vendido {par} con ganancia")
                operacion_en_curso = False
                break

            if precio_actual <= stop_loss:
                await client.create_market_order(
                    symbol=par,
                    side="sell",
                    size=round(await obtener_balance(par), 2)
                )
                await bot.send_message(CHAT_ID, f"⚡ Vendido {par} por Trailing Stop")
                operacion_en_curso = False
                break

            await asyncio.sleep(5)

        except Exception as e:
            logging.error(f"Error gestión salida: {e}")

# === Bloque 9: Lanzador Bot ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())