import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from kucoin.client import Client
from kucoin.exceptions import KucoinAPIException

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

client = Client(API_KEY, API_SECRET)

pares = ["SHIB/USDT", "DOGE/USDT", "PEPE/USDT", "FLOKI/USDT"]
modo_agresivo = True
bot_activo = Falsedef obtener_saldo_disponible():
    try:
        cuentas = client.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
        return 0.0
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

def obtener_volumen(par):
    try:
        symbol = par.replace("/", "-")
        ticker = client.get_ticker(symbol)
        return float(ticker['volValue'])
    except Exception as e:
        logging.error(f"Error obteniendo volumen de {par}: {e}")
        return 0.0

def calcular_monto_operacion(saldo):
    if saldo < 10:
        return 0
    if modo_agresivo:
        return round(saldo * 0.9, 2)
    elif saldo > 100:
        return round(saldo * 0.5, 2)
    else:
        return round(saldo * 0.7, 2)def evaluar_condiciones_entrada(par):
    try:
        symbol = par.replace("/", "-")
        kline = client.get_kline_data(symbol, '1min', limit=2)
        if len(kline) < 2:
            return False
        close_anterior = float(kline[-2][2])
        close_actual = float(kline[-1][2])
        diferencia = ((close_actual - close_anterior) / close_anterior) * 100
        volumen = obtener_volumen(par)
        return diferencia > 0.25 and volumen > 1000
    except Exception as e:
        logging.error(f"Error analizando condiciones en {par}: {e}")
        return False

def operar(par):
    try:
        symbol = par.replace("/", "-")
        saldo = obtener_saldo_disponible()
        monto = calcular_monto_operacion(saldo)
        if monto <= 0:
            return
        if evaluar_condiciones_entrada(par):
            order = client.create_market_order(symbol=symbol, side='buy', funds=monto)
            logging.info(f"Compra realizada en {par} con {monto} USDT")
        else:
            logging.info(f"No se cumplen condiciones en {par}")
    except Exception as e:
        logging.error(f"Error ejecutando compra de {par}: {e}")async def ciclo_operativo():
    global bot_activo
    while bot_activo:
        try:
            for par in pares:
                operar(par)
                await asyncio.sleep(2)  # Tiempo entre revisiones de pares
            await asyncio.sleep(10)  # Pausa entre ciclos completos
        except Exception as e:
            logging.error(f"Error en el ciclo operativo: {e}")
            await asyncio.sleep(10)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🚀 Encender Bot", callback_data="encender"),
        InlineKeyboardButton("🛑 Apagar Bot", callback_data="apagar"),
    )
    await message.answer("Bienvenido a ZafroBot PRO Scalper Inteligente", reply_markup=markup)

@dp.callback_query_handler()
async def callbacks(call: types.CallbackQuery):
    global bot_activo
    if call.data == "encender":
        if not bot_activo:
            bot_activo = True
            await call.message.answer("🟢 Bot encendido. Empezando a escanear...")
            asyncio.create_task(ciclo_operativo())
        else:
            await call.message.answer("⚠️ El bot ya está activo.")
    elif call.data == "apagar":
        if bot_activo:
            bot_activo = False
            await call.message.answer("🔴 Bot apagado.")
        else:
            await call.message.answer("⚠️ El bot ya estaba apagado.")async def main():
    await dp.start_polling()

if __name__ == "__main__":
    logging.info("Iniciando ZafroBot PRO...")
    asyncio.run(main())