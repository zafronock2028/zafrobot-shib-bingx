import os
import asyncio
import logging
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import random

# ─── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── Configuración de Entorno ─────────────────────────────────────────────
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

# ─── Clientes ─────────────────────────────────────────────────────────────
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ───────────────────────────────────────────────────
_last_balance: float = 0.0
bot_encendido = False
operacion_activa = None
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]

# ─── Teclado de Telegram ──────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")]
    ],
    resize_keyboard=True,
)# ─── Funciones Internas ─────────────────────────────────────────────────────

async def obtener_balance():
    cuenta = await asyncio.to_thread(kucoin.get_accounts, currency="USDT", type="trade")
    if cuenta:
        return float(cuenta[0].get('available', 0))
    return 0.0

def obtener_precio(par):
    simbolo = par.replace("/", "-")
    ticker = kucoin.get_ticker(symbol=symbolo)
    return float(ticker["price"])

def calcular_cantidad(balance, precio):
    if balance >= 50:
        porcentaje = 0.5  # 50% del saldo si es más de 50 USDT
    elif balance >= 10:
        porcentaje = 0.9  # 90% si es entre 10 y 50 USDT (modo agresivo)
    else:
        porcentaje = 0.7  # 70% si es menos de 10 USDT
    monto = balance * porcentaje
    cantidad = monto / precio
    return round(cantidad, 6)

def analizar_entrada(par, precio_actual):
    """Simula análisis técnico mejorado basado en volumen/lógica futura"""
    return random.choice([True, False, False, False])  # Más selectivo

def ejecutar_compra(par, cantidad):
    simbolo = par.replace("/", "-")
    try:
        orden = kucoin.create_market_order(symbol=simbolo, side="buy", size=cantidad)
        return orden
    except Exception as e:
        logging.error(f"Error comprando {par}: {str(e)}")
        return None# ─── Funciones de Operación y Monitoreo ─────────────────────────────────────

async def monitorear_operacion(par, precio_entrada, cantidad):
    global operacion_activa
    objetivo = precio_entrada * random.uniform(1.025, 1.06)  # Objetivo: 2.5% a 6%
    stop_loss = precio_entrada * 0.985  # Stop Loss de -1.5%
    simbolo = par.replace("/", "-")

    while bot_encendido and operacion_activa:
        precio_actual = await asyncio.to_thread(obtener_precio, par)

        if precio_actual >= objetivo:
            await bot.send_message(CHAT_ID, f"🎯 ¡Take Profit alcanzado en {par}!\nPrecio actual: {precio_actual:.8f}")
            operacion_activa = None
            break
        elif precio_actual <= stop_loss:
            await bot.send_message(CHAT_ID, f"⚡ ¡Stop Loss activado en {par}!\nPrecio actual: {precio_actual:.8f}")
            operacion_activa = None
            break

        await asyncio.sleep(5)

async def operar():
    global _last_balance, operacion_activa
    _last_balance = await obtener_balance()

    while bot_encendido:
        try:
            balance = await obtener_balance()

            if operacion_activa:
                await asyncio.sleep(5)
                continue

            if balance < 5:
                await bot.send_message(CHAT_ID, f"⚠️ Saldo insuficiente ({balance:.2f} USDT). Esperando...")
                await asyncio.sleep(30)
                continue

            par = random.choice(pares)
            precio_actual = await asyncio.to_thread(obtener_precio, par)

            if analizar_entrada(par, precio_actual):
                cantidad = calcular_cantidad(balance, precio_actual)
                if cantidad > 0:
                    orden = await asyncio.to_thread(ejecutar_compra, par, cantidad)
                    if orden:
                        operacion_activa = par
                        await bot.send_message(CHAT_ID, f"✅ Compra ejecutada en {par} a {precio_actual:.8f}\nCantidad: {cantidad}")
                        await monitorear_operacion(par, precio_actual, cantidad)

            await asyncio.sleep(3)

        except Exception as e:
            logging.error(f"Error general en operar(): {str(e)}")
            await asyncio.sleep(10)# ─── Comandos de Telegram ────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ *ZafroBot PRO Scalper Inteligente* iniciado.\n\nSelecciona una opción:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def cmd_encender(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido. Analizando mercado…")
        asyncio.create_task(operar())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def cmd_apagar(message: types.Message):
    global bot_encendido, operacion_activa
    bot_encendido = False
    operacion_activa = None
    await message.answer("🔴 Bot apagado manualmente.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def cmd_estado(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual: {estado}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_actualizar_saldo(message: types.Message):
    balance = await obtener_balance()
    await message.answer(f"💰 Saldo disponible: {balance:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def cmd_estado_orden(message: types.Message):
    if operacion_activa:
        await message.answer(f"📈 Operación abierta en: {operacion_activa}")
    else:
        await message.answer("📈 No hay operaciones abiertas actualmente.")# ─── Lanzamiento del Bot ────────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())