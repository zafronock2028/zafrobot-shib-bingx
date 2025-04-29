# main.py
import os
import asyncio
import logging
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
import aiohttp

# Configuración del log
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno
API_KEY        = os.getenv("API_KEY")
SECRET_KEY     = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

# Inicializar KuCoin y Telegram
kucoin = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Estado del bot
bot_encendido = False
orden_activa = None
pares = ["PEPE-USDT", "FLOKI-USDT", "SHIB-USDT", "DOGE-USDT"]

# Teclado de Telegram
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="💰 Saldo"), KeyboardButton(text="📊 Estado del Bot")],
        [KeyboardButton(text="📈 Orden Activa")],
    ],
    resize_keyboard=True
)@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "✅ Bienvenido al ZafroBot Dinámico PRO Scalping\n\nUsa los botones para controlar el bot.",
        reply_markup=keyboard
    )

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "🟢 ENCENDIDO" if bot_encendido else "🔴 APAGADO"
    await message.answer(f"📡 Estado actual del bot: {estado}")

@dp.message(lambda m: m.text == "💰 Saldo")
async def ver_saldo(message: types.Message):
    saldo = obtener_saldo()
    await message.answer(f"💰 Saldo disponible en USDT (Spot): {saldo:.2f}")

@dp.message(lambda m: m.text == "📈 Orden Activa")
async def ver_orden_activa(message: types.Message):
    if orden_activa:
        await message.answer(f"📈 Orden en curso:\nPar: {orden_activa['par']}\nPrecio Entrada: {orden_activa['entrada']:.6f}\nCantidad: {orden_activa['cantidad']}")
    else:
        await message.answer("⏳ No hay ninguna orden activa en este momento.")

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("✅ Bot encendido. Analizando oportunidades...")
        asyncio.create_task(loop_operaciones())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🛑 Bot apagado.")async def loop_operaciones():
    global bot_encendido
    while bot_encendido:
        for par in pares:
            try:
                volumen = obtener_volumen_24h(par)
                saldo = obtener_saldo()
                if saldo < 5:
                    await bot.send_message(CHAT_ID, f"⚠️ Saldo insuficiente ({saldo:.2f} USDT)")
                    await asyncio.sleep(10)
                    continue

                precio = obtener_precio_actual(par)
                promedio = obtener_promedio_precio(par)

                if precio < promedio * 0.99:
                    cantidad = calcular_cantidad(par, saldo, precio, volumen)
                    if cantidad:
                        ejecutar_compra(par, cantidad)
                        await bot.send_message(CHAT_ID, f"✅ Entrada en {par} a {precio:.6f} por {cantidad} unidades")
                        await monitorear_trailing_stop(par, precio, cantidad)
            except Exception as e:
                await bot.send_message(CHAT_ID, f"❌ Error: {e}")
        await asyncio.sleep(2)

def obtener_precio_actual(par):
    ticker = kucoin.get_ticker(par)
    return float(ticker["price"])

def obtener_promedio_precio(par):
    velas = kucoin.get_kline_data(symbol=par, kline_type="1min", limit=5)
    cierres = [float(v[2]) for v in velas]
    return sum(cierres) / len(cierres)

def obtener_volumen_24h(par):
    ticker = kucoin.get_ticker(par)
    return float(ticker["volValue"])

def calcular_cantidad(par, saldo, precio, volumen):
    max_inversion = min(saldo * 0.80, volumen * 0.04)
    cantidad = max_inversion / precio
    return round(cantidad, 2 if "DOGE" in par else 0)

def ejecutar_compra(par, cantidad):
    kucoin.create_market_order(symbol=par, side="buy", size=cantidad)
    global orden_activa
    orden_activa = {"par": par, "entrada": obtener_precio_actual(par), "cantidad": cantidad}async def monitorear_trailing_stop(par, precio_entrada, cantidad):
    global orden_activa, bot_encendido
    trailing_stop = -0.08  # -8%
    take_profit_inicial = 0.025  # 2.5%
    precio_maximo = precio_entrada

    while bot_encendido:
        try:
            precio_actual = obtener_precio_actual(par)
            if precio_actual > precio_maximo:
                precio_maximo = precio_actual

            variacion = (precio_actual - precio_entrada) / precio_entrada

            if variacion >= take_profit_inicial:
                if (precio_actual - precio_maximo) / precio_maximo <= trailing_stop:
                    kucoin.create_market_order(symbol=par, side="sell", size=cantidad)
                    await bot.send_message(CHAT_ID, f"💰 Operación cerrada en {par} con trailing stop.\nGanancia: {variacion*100:.2f}%")
                    orden_activa = None
                    break
        except Exception as e:
            await bot.send_message(CHAT_ID, f"❌ Error monitoreando orden: {e}")
        await asyncio.sleep(3)def obtener_saldo():
    try:
        cuentas = kucoin.get_accounts()
        spot = next((c for c in cuentas if c["currency"] == "USDT" and c["type"] == "trade"), None)
        return float(spot["available"]) if spot else 0.0
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return 0.0

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())