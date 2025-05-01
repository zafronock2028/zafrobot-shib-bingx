
import os
import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Market, Trade, User

# Configuración
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASS = os.getenv("API_PASSPHRASE")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN, parse_mode="Markdown")
dp = Dispatcher()
market_client = Market()
trade_client = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)
user_client = User(API_KEY, SECRET_KEY, API_PASS)

# Variables globales
bot_encendido = False
operaciones_activas = []
historial_operaciones = []
ultimos_pares_operados = {}
tiempo_espera_reentrada = 600  # 10 minutos
max_operaciones = 3
pares = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT",
    "TURBO-USDT", "BONK-USDT", "KAS-USDT", "WIF-USDT", "SUI-USDT",
    "HYPE-USDT", "HYPER-USDT", "OM-USDT", "ENA-USDT"
]
ganancia_objetivo = 0.015
trailing_stop_base = -0.08
min_orden_usdt = 3.0
max_orden_usdt = 6.0

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="⛔ Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Estado de Orden Activa")],
        [KeyboardButton(text="🧾 Historial de Ganancias")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ ¡Bienvenido al Zafrobot Scalper V1 PRO!", reply_markup=keyboard)

@dp.message()
async def comandos(message: types.Message):
    global bot_encendido

    if message.text == "💰 Saldo":
        saldo = await obtener_saldo_disponible()
        await message.answer(f"💰 Tu saldo disponible es: {saldo:.2f} USDT")

    elif message.text == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido correctamente.")
            asyncio.create_task(loop_operaciones())
        else:
            await message.answer("⚠️ El bot ya está encendido.")

    elif message.text == "⛔ Apagar Bot":
        bot_encendido = False
        await message.answer("⛔ Bot apagado manualmente.")

    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_encendido else "⛔ APAGADO"
        await message.answer(f"📊 Estado actual del bot: {estado}")

    elif message.text == "📈 Estado de Orden Activa":
        if operaciones_activas:
            mensaje = ""
            for op in operaciones_activas:
                estado = "GANANCIA ✅" if op["ganancia"] > 0 else "PERDIENDO ❌"
                mensaje += (
                    f"📈 Par: {op['par']}
"
                    f"Entrada: {op['entrada']:.6f} USDT
"
                    f"Actual: {op['actual']:.6f} USDT
"
                    f"Ganancia: {op['ganancia']:.6f} USDT ({estado})

"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ No hay operaciones activas actualmente.")
