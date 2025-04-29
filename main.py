import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from kucoin.client import Market, Trade, User
from kucoin.exceptions import KucoinAPIException
import aiohttp
from dotenv import load_dotenv
import random

load_dotenv()

API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Inicializar clientes de KuCoin
market_client = Market()
trade_client = Trade(API_KEY, SECRET_KEY, API_PASSPHRASE)
user_client = User(API_KEY, SECRET_KEY, API_PASSPHRASE)

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

pares = ['SHIB-USDT', 'PEPE-USDT', 'FLOKI-USDT', 'BONK-USDT', '1CAT-USDT']
operacion_en_curso = False
saldo_actual = 0.0

async def obtener_saldo():
    try:
        cuentas = user_client.get_account_list()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
        return 0.0
    except KucoinAPIException as e:
        logging.error(f"Error de API al obtener saldo: {e}")
        return 0.0async def calcular_monto_operacion(client, par, saldo_disponible):
    try:
        ticker = await client.get_ticker(par)
        volumen_24h_usdt = float(ticker['volValue'])  # volumen de 24h en USDT
        max_monto = volumen_24h_usdt * 0.04  # máximo 4% del volumen
        monto_operacion = min(saldo_disponible, max_monto)
        return monto_operacion
    except Exception as e:
        logging.error(f"Error al calcular monto de operación: {e}")
        return saldo_disponible * 0.05
    except Exception as e:
        logging.error(f"Error general al obtener saldo: {e}")
        return 0.0

async def obtener_volumen_24h(par):
    try:
        data = client.get_ticker(par)
        return float(data['volValue'])
    except Exception as e:
        logging.error(f"Error al obtener volumen 24h para {par}: {e}")
        return None

def calcular_kelly(win_rate, reward_risk_ratio):
    return (win_rate - (1 - win_rate) / reward_risk_ratio)

async def analizar_mercado():
    global operacion_en_curso
    while True:
        if operacion_en_curso:
            await asyncio.sleep(2)
            continue

        mejor_par = None
        mejor_score = -float('inf')

        for par in pares:
            volumen = await obtener_volumen_24h(par)
            if volumen is None:
                continue
            score = random.uniform(0.7, 1.3) * volumen  # Simula análisis inteligente
            if score > mejor_score:
                mejor_score = score
                mejor_par = par

        if mejor_par:
            await iniciar_operacion(mejor_par)
        await asyncio.sleep(2)

async def iniciar_operacion(par):
    global operacion_en_curso, saldo_actual
    operacion_en_curso = True

    saldo = await obtener_saldo()
    if saldo <= 0:
        logging.warning("Saldo insuficiente para operar.")
        operacion_en_curso = False
        return

    volumen = await obtener_volumen_24h(par)
    if not volumen:
        operacion_en_curso = False
        return

    monto_maximo = volumen * 0.04  # No usar más del 4%
    monto_ideal = min(saldo, monto_maximo)

    cantidad_a_comprar = monto_ideal * 0.95  # Deja un 5% libre por seguridad
    logging.info(f"Comprando {cantidad_a_comprar} USDT en {par}")

    try:
        precio_actual = float(client.get_ticker(par)['price'])
        cantidad = cantidad_a_comprar / precio_actual

        orden = client.create_market_order(par, 'buy', size=cantidad)
        logging.info(f"Orden de compra ejecutada: {orden}")
    except Exception as e:
        logging.error(f"Error al comprar: {e}")
        operacion_en_curso = False
        return

    await gestionar_venta(par, cantidad, precio_actual)

async def gestionar_venta(par, cantidad, precio_compra):
    global operacion_en_curso
    try:
        while True:
            precio_actual = float(client.get_ticker(par)['price'])
            ganancia = (precio_actual - precio_compra) / precio_compra * 100
            perdida = (precio_actual - precio_compra) / precio_compra * 100

            if ganancia >= random.choice([2, 2.5, 5, 6, 10]):
                orden = client.create_market_order(par, 'sell', size=cantidad)
                logging.info(f"Orden de venta ejecutada en ganancia: {orden}")
                await bot.send_message(CHAT_ID, f"✅ Operación cerrada en ganancia: {ganancia:.2f}% en {par}")
                break

            if perdida <= -8:
                orden = client.create_market_order(par, 'sell', size=cantidad)
                logging.info(f"Stop Loss activado: {orden}")
                await bot.send_message(CHAT_ID, f"⚠️ Stop Loss activado: {perdida:.2f}% en {par}")
                break

            await asyncio.sleep(2)
    except Exception as e:
        logging.error(f"Error al gestionar venta: {e}")
    finally:
        operacion_en_curso = False

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 Encender Bot", "🛑 Apagar Bot")
    markup.add("📊 Estado del Bot", "💰 Actualizar Saldo")
    markup.add("📈 Estado de Orden Actual")
    await message.answer("✅ ZafroBot Scalper PRO iniciado.\n\nSelecciona una opción:", reply_markup=markup)

@dp.message_handler(lambda message: message.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    asyncio.create_task(analizar_mercado())
    await message.answer("🟢 Bot encendido. Escaneando mercado...")

@dp.message_handler(lambda message: message.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    global operacion_en_curso
    operacion_en_curso = True
    await message.answer("🔴 Bot apagado manualmente.")

@dp.message_handler(lambda message: message.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = await obtener_saldo()
    await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

@dp.message_handler(lambda message: message.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    status = "✅ Bot activo" if not operacion_en_curso else "⏳ Operación en curso"
    await message.answer(status)

@dp.message_handler(lambda message: message.text == "📈 Estado de Orden Actual")
async def estado_orden_actual(message: types.Message):
    if operacion_en_curso:
        await message.answer("⏳ Orden actual: En operación...")
    else:
        await message.answer("✅ No hay órdenes abiertas.")

async def main():
    await dp.start_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())