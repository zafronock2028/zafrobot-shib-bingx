# main.py
import os
import asyncio
import logging
from kucoin.client import Client
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── Configuración ────────────────────────────────────────────────────────────
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

# ─── Clientes ─────────────────────────────────────────────────────────────────
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Estado global ─────────────────────────────────────────────────────────────
bot_encendido = False
_last_balance = 0.0

# ─── Teclado principal ─────────────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🚀 Encender Bot"),
            KeyboardButton(text="🛑 Apagar Bot"),
        ],
        [
            KeyboardButton(text="📊 Estado del Bot"),
            KeyboardButton(text="💰 Actualizar Saldo"),
        ],
    ],
    resize_keyboard=True,
)

# ─── Comandos de usuario ───────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(msg):
    await msg.answer(
        "✅ ZafroBot Scalper PRO V1 iniciado.\nSelecciona una opción:",
        reply_markup=keyboard
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def cmd_encender(msg):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await msg.answer("🟢 Bot encendido. Iniciando escaneo de mercado…")
        asyncio.create_task(analizar_y_operar())
    else:
        await msg.answer("⚡ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def cmd_apagar(msg):
    global bot_encendido
    bot_encendido = False
    await msg.answer("🔴 Bot apagado correctamente.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def cmd_estado(msg):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await msg.answer(f"📊 Estado actual del Bot: {estado}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_actualizar_saldo(msg):
    bal = await obtener_balance()
    await msg.answer(f"💰 Saldo actual en Trading Wallet: {bal:.2f} USDT")

# ─── Funciones internas ───────────────────────────────────────────────────────

async def obtener_balance() -> float:
    accounts = await asyncio.to_thread(kucoin.get_accounts)
    balance = 0.0
    for acc in accounts:
        if acc["currency"] == "USDT" and acc["type"] == "trade":
            balance = float(acc["available"])
            break
    return balance

async def analizar_y_operar():
    global _last_balance
    pares = ["PEPE-USDT", "FLOKI-USDT", "SHIB-USDT", "DOGE-USDT"]

    while bot_encendido:
        for par in pares:
            try:
                ticker = await asyncio.to_thread(kucoin.get_ticker, par)
                last_price = float(ticker['price'])
                vol24h = float(ticker['volValue'])

                # Parámetros de lógica profesional:
                if vol24h > 100000 and last_price > 0:
                    balance = await obtener_balance()

                    if balance > 5:  # Operar sólo si saldo disponible > 5 USDT
                        capital_uso = calcular_capital(balance)
                        await ejecutar_compra(par, last_price, capital_uso)
                        await asyncio.sleep(5)  # Pausa breve entre operaciones
            except Exception as e:
                logging.error(f"Error analizando {par}: {e}")

        await asyncio.sleep(30)  # Esperar un poco antes de escanear de nuevo

async def ejecutar_compra(par, precio_actual, cantidad_usar):
    try:
        qty = cantidad_usar / precio_actual
        qty = round(qty, 2)  # Ajustamos para evitar decimales raros

        orden = await asyncio.to_thread(kucoin.create_market_order, par, "buy", funds=cantidad_usar)

        await bot.send_message(
            CHAT_ID,
            f"✅ Nueva operación ejecutada:\n\n"
            f"🪙 **Par:** {par}\n"
            f"💲 **Precio de entrada:** {precio_actual:.8f} USDT\n"
            f"💰 **Capital usado:** {cantidad_usar:.2f} USDT\n"
            f"⏰ **Hora:** {datetime.now().strftime('%H:%M:%S')}"
        )

    except Exception as e:
        await bot.send_message(CHAT_ID, f"⚠️ Error al ejecutar la compra en {par}: {str(e)}")

def calcular_capital(balance):
    if balance <= 50:
        return balance * 0.80
    elif balance <= 100:
        return balance * 0.60
    elif balance <= 300:
        return balance * 0.40
    else:
        return balance * 0.25

# ─── Arranque del bot ─────────────────────────────────────────────────────────

async def main():
    logging.info("Start polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())