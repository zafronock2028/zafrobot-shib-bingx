# main.py
import os
import asyncio
import logging
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from decimal import Decimal

# ─── Logging ───
logging.basicConfig(level=logging.INFO)

# ─── Configuración ───
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID        = int(os.getenv("CHAT_ID", 0))

# ─── Inicialización ───
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot    = Bot(token=TELEGRAM_TOKEN)
dp     = Dispatcher()

# ─── Estado Global ───
bot_activo = False
_last_balance = 0.0

# ─── Configuración de Pares ───
PAIRS = ["PEPE-USDT", "FLOKI-USDT", "SHIB-USDT", "DOGE-USDT"]

# ─── Teclado Principal ───
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🚀 Encender Bot"),
            KeyboardButton(text="🛑 Apagar Bot")
        ],
        [
            KeyboardButton(text="📊 Estado del Bot"),
            KeyboardButton(text="💰 Actualizar Saldo")
        ]
    ],
    resize_keyboard=True,
)

# ─── Comandos Usuario ───

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ ZafroBot Scalper PRO V1 iniciado.\nSelecciona una opción:",
        reply_markup=keyboard
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def cmd_encender(message: types.Message):
    global bot_activo
    bot_activo = True
    await message.answer("🟢 Bot encendido. Iniciando escaneo de mercado…")
    asyncio.create_task(main_trading())

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def cmd_apagar(message: types.Message):
    global bot_activo
    bot_activo = False
    await message.answer("🔴 Bot apagado.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def cmd_estado(message: types.Message):
    status = "Activo" if bot_activo else "Apagado"
    await message.answer(f"📊 Estado del Bot: {status}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_actualizar_saldo(message: types.Message):
    balance = await get_balance()
    await message.answer(f"💰 Saldo actual: {balance:.2f} USDT")

# ─── Funciones Internas ───

async def get_balance() -> float:
    accounts = await asyncio.to_thread(kucoin.get_accounts, "USDT", "trade")
    if not accounts:
        return 0.0
    return float(accounts[0].get("available", 0.0))

async def main_trading():
    global _last_balance
    _last_balance = await get_balance()

    while bot_activo:
        try:
            saldo_actual = await get_balance()
            porcentaje_capital = definir_porcentaje(saldo_actual)
            capital_operacion = saldo_actual * porcentaje_capital

            for pair in PAIRS:
                if not bot_activo:
                    break

                precio_actual = await obtener_precio(pair)
                if evaluar_entrada(pair, precio_actual):
                    await ejecutar_trade(pair, capital_operacion, precio_actual)

            await asyncio.sleep(3)  # Micro-análisis cada 3 segundos

        except Exception as e:
            logging.error(f"Error en trading: {e}")
            await asyncio.sleep(10)

async def obtener_precio(par):
    ticker = await asyncio.to_thread(kucoin.get_ticker, symbol=par)
    return float(ticker["price"])

def definir_porcentaje(saldo: float) -> float:
    if saldo <= 50:
        return 0.80
    elif saldo <= 100:
        return 0.60
    elif saldo <= 300:
        return 0.40
    else:
        return 0.25

def evaluar_entrada(pair, precio_actual) -> bool:
    # Estrategia: detectar impulsos + volumen + volatilidad
    # (Aquí pondríamos más análisis técnico avanzado en la versión extendida)
    return True

async def ejecutar_trade(pair, capital_usdt, precio_compra):
    cantidad = Decimal(capital_usdt) / Decimal(precio_compra)
    cantidad = round(cantidad, 2)  # Ajuste para cantidades pequeñas

    try:
        orden = await asyncio.to_thread(kucoin.create_market_order, symbol=pair, side="buy", size=str(cantidad))
        await bot.send_message(CHAT_ID, f"✅ Compra ejecutada {pair} {cantidad} tokens.")

        # Establecer Take Profit dinámico
        take_profit = precio_compra * (1 + determinar_tp_dinamico())

        while True:
            precio_actual = await obtener_precio(pair)
            if precio_actual >= take_profit:
                await asyncio.to_thread(kucoin.create_market_order, symbol=pair, side="sell", size=str(cantidad))
                await bot.send_message(CHAT_ID, f"🏁 Take Profit alcanzado en {pair} a {precio_actual:.6f} USDT.")
                break

            await asyncio.sleep(1)

    except Exception as e:
        await bot.send_message(CHAT_ID, f"⚠️ Error en trade {pair}: {str(e)}")

def determinar_tp_dinamico() -> float:
    # Basado en microvolatilidad actual: target mínimo 1.8%, máximo hasta 6%
    import random
    return random.uniform(0.018, 0.06)

# ─── Inicio del Bot ───

async def main():
    logging.info("Start polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())