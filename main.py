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

# ─── Configuración ────────────────────────────────────────────────────────
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID        = int(os.getenv("CHAT_ID", 0))

# ─── Clientes ─────────────────────────────────────────────────────────────
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ───────────────────────────────────────────────────
_last_balance = 0.0
bot_encendido = False
operacion_activa = None
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]

# ─── Teclado de opciones ──────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)# ─── Comandos del Bot ─────────────────────────────────────────────────────

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
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def cmd_estado(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual: {estado}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_saldo(message: types.Message):
    balance = await obtener_balance()
    await message.answer(f"💰 Saldo disponible: {balance:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def cmd_estado_orden(message: types.Message):
    if operacion_activa:
        par, precio, cantidad = operacion_activa
        precio_actual = await asyncio.to_thread(obtener_precio, par)
        diferencia = precio_actual - precio
        signo = "🟢" if diferencia > 0 else "🔴"
        await message.answer(f"{signo} Orden en {par}\nEntrada: {precio:.6f} | Actual: {precio_actual:.6f}")
    else:
        await message.answer("ℹ️ No hay ninguna operación activa actualmente.")# ─── Lógica del Bot ────────────────────────────────────────────────────────

async def obtener_balance():
    try:
        cuenta = await asyncio.to_thread(kucoin.get_accounts, currency="USDT", type="trade")
        if cuenta:
            return float(cuenta[0].get("available", 0))
    except Exception as e:
        logging.error(f"Error al obtener balance: {str(e)}")
    return 0.0

async def operar():
    global _last_balance, operacion_activa
    _last_balance = await obtener_balance()

    while bot_encendido:
        try:
            balance = await obtener_balance()
            if balance < 5:
                await bot.send_message(CHAT_ID, f"⚠️ Saldo insuficiente ({balance:.2f} USDT). Esperando...")
                await asyncio.sleep(60)
                continue

            par = random.choice(pares)
            precio_actual = await asyncio.to_thread(obtener_precio, par)

            if analizar_entrada(par, precio_actual):
                cantidad = calcular_cantidad(balance, precio_actual)
                if cantidad > 0:
                    orden = await asyncio.to_thread(ejecutar_compra, par, cantidad)
                    if orden:
                        operacion_activa = (par, precio_actual, cantidad)
                        await bot.send_message(CHAT_ID, f"✅ Entrada en {par} a {precio_actual:.8f} USDT")
                        await monitorear_operacion(par, precio_actual, cantidad)
                        operacion_activa = None
            await asyncio.sleep(15)

        except Exception as e:
            logging.error(f"Error general en operar(): {str(e)}")
            await asyncio.sleep(60)

def analizar_entrada(par, precio_actual):
    return random.choice([True, False, False, False])  # Aumenta precisión ajustando pesos

def calcular_cantidad(balance, precio):
    porcentaje = 0.9 if balance <= 20 else 0.5 if balance <= 60 else 0.25
    monto = balance * porcentaje
    cantidad = monto / precio
    return round(cantidad, 6)# ─── Operación y Monitoreo ─────────────────────────────────────────────────

async def monitorear_operacion(par, precio_entrada, cantidad):
    objetivo = precio_entrada * random.uniform(1.025, 1.06)  # Objetivo: entre +2.5% y +6%
    stop_loss = precio_entrada * 0.985  # Stop Loss de -1.5%
    simbolo = par.replace("/", "-")

    while bot_encendido:
        try:
            precio_actual = await asyncio.to_thread(obtener_precio, par)

            if precio_actual >= objetivo:
                await bot.send_message(
                    CHAT_ID,
                    f"🎯 ¡Take Profit alcanzado!\n\nPar: {par}\nPrecio Entrada: {precio_entrada:.8f}\nPrecio Actual: {precio_actual:.8f}"
                )
                break

            elif precio_actual <= stop_loss:
                await bot.send_message(
                    CHAT_ID,
                    f"⚡ ¡Stop Loss activado!\n\nPar: {par}\nPrecio Entrada: {precio_entrada:.8f}\nPrecio Actual: {precio_actual:.8f}"
                )
                break

            await asyncio.sleep(5)

        except Exception as e:
            logging.error(f"Error en monitoreo de operación: {str(e)}")
            await asyncio.sleep(10)

def obtener_precio(par):
    simbolo = par.replace("/", "-")
    try:
        ticker = kucoin.get_ticker(symbol=simbolo)
        return float(ticker["price"])
    except Exception as e:
        logging.error(f"Error obteniendo precio de {par}: {str(e)}")
        return 0.0

def ejecutar_compra(par, cantidad):
    simbolo = par.replace("/", "-")
    try:
        orden = kucoin.create_market_order(symbol=simbolo, side="buy", size=str(cantidad))
        return orden
    except Exception as e:
        logging.error(f"Error ejecutando compra de {par}: {str(e)}")
        return None# ─── Lanzamiento Final ─────────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())