# main.py

import asyncio
import logging
import os
import random
import math
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Client
from dotenv import load_dotenv

load_dotenv()

# ─── Configuración de API Keys ─────────────────────────────────────────────
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# ─── Inicializar Clientes ──────────────────────────────────────────────────
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ────────────────────────────────────────────────────
bot_encendido = False
operacion_activa = None
_last_balance = 0.0

# Pares a escanear
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]

# Modo dinámico
modo_agresivo = True

# ─── Teclado de Telegram ───────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")]
    ],
    resize_keyboard=True,
)# ─── Funciones de Análisis y Gestión de Capital ────────────────────────────

async def obtener_balance():
    """Obtiene el saldo disponible en USDT."""
    cuenta = await asyncio.to_thread(kucoin.get_accounts, currency="USDT", type="trade")
    if cuenta:
        return float(cuenta[0].get('available', 0))
    return 0.0

async def obtener_precio(par):
    """Obtiene el precio actual del par."""
    simbolo = par.replace("/", "-")
    ticker = await asyncio.to_thread(kucoin.get_ticker, symbol=simbolo)
    return float(ticker["price"])

async def analizar_entrada(par):
    """Simula un análisis real: volumen + micro tendencia positiva."""
    simbolo = par.replace("/", "-")
    ticker = await asyncio.to_thread(kucoin.get_ticker, symbol=simbolo)

    try:
        volumen_24h = float(ticker.get("volValue", 0))
        precio = float(ticker.get("price", 0))

        if volumen_24h > 100000 and precio > 0:  # Filtro de liquidez y precio válido
            movimiento = random.uniform(-0.2, 0.5)  # Simulamos micro tendencia
            return movimiento > 0.1  # Solo entrar si la tendencia es positiva
    except Exception as e:
        logging.error(f"Error analizando entrada en {par}: {str(e)}")

    return False

def calcular_monto_kelly(saldo_total):
    """Calcula el monto a invertir usando criterio de Kelly simplificado."""
    ventaja = 0.55  # Probabilidad de éxito estimada
    desventaja = 0.45  # Riesgo de pérdida
    kelly_fraction = (ventaja - desventaja) / ventaja
    monto_invertir = saldo_total * kelly_fraction

    # Ajuste dinámico por tipo de saldo
    if saldo_total <= 20:
        monto_invertir *= 1.2  # Más agresivo
    elif saldo_total >= 100:
        monto_invertir *= 0.7  # Más conservador

    return max(round(monto_invertir, 2), 5)  # No menos de $5# ─── Funciones de Operación ────────────────────────────────────────────────

async def ejecutar_compra(par, monto_usdt):
    """Ejecuta una orden de compra en KuCoin usando fondos USDT."""
    simbolo = par.replace("/", "-")
    try:
        orden = await asyncio.to_thread(
            kucoin.create_market_order,
            symbol=simbolo,
            side="buy",
            funds=str(monto_usdt)
        )
        return orden
    except Exception as e:
        logging.error(f"Error ejecutando compra en {par}: {str(e)}")
        return None

async def monitorear_operacion(par, precio_entrada):
    """Monitorea la operación abierta buscando Take Profit o Stop Loss dinámico."""
    objetivo = precio_entrada * random.uniform(1.025, 1.06)  # Entre 2.5% y 6% de ganancia
    stop_loss = precio_entrada * 0.985  # Stop Loss de -1.5%

    simbolo = par.replace("/", "-")

    while bot_encendido:
        try:
            precio_actual = await obtener_precio(par)

            if precio_actual >= objetivo:
                await bot.send_message(
                    CHAT_ID,
                    f"🎯 ¡Take Profit alcanzado en {par}!\nPrecio entrada: {precio_entrada:.6f} ➔ Precio actual: {precio_actual:.6f}"
                )
                break
            elif precio_actual <= stop_loss:
                await bot.send_message(
                    CHAT_ID,
                    f"⚡ ¡Stop Loss activado en {par}!\nPrecio entrada: {precio_entrada:.6f} ➔ Precio actual: {precio_actual:.6f}"
                )
                break

            await asyncio.sleep(5)

        except Exception as e:
            logging.error(f"Error monitoreando operación en {par}: {str(e)}")
            await asyncio.sleep(10)# ─── Comandos de Telegram ───────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ *ZafroBot PRO Scalper Inteligente* activo.\n\nSelecciona una opción:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def cmd_encender(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await message.answer("🟢 Bot encendido. Empezando a analizar mercado…")
        asyncio.create_task(ciclo_operativo())
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
    await message.answer(f"📊 Estado actual del bot: {estado}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_saldo(message: types.Message):
    saldo = await obtener_balance()
    await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def cmd_orden(message: types.Message):
    if operacion_activa:
        par, precio_entrada = operacion_activa
        precio_actual = await obtener_precio(par)
        diferencia = precio_actual - precio_entrada
        signo = "🟢" if diferencia > 0 else "🔴"
        await message.answer(f"{signo} {par}\nEntrada: {precio_entrada:.6f} ➔ Actual: {precio_actual:.6f}")
    else:
        await message.answer("ℹ️ No hay ninguna operación activa actualmente.")# ─── Ciclo Operativo del Bot ────────────────────────────────────────────────

async def ciclo_operativo():
    global operacion_activa
    while bot_encendido:
        try:
            saldo = await obtener_balance()

            if saldo < 5:
                await bot.send_message(CHAT_ID, "⚠️ Saldo insuficiente. Esperando...")
                await asyncio.sleep(60)
                continue

            par = random.choice(pares)
            oportunidad = await analizar_entrada(par)

            if oportunidad:
                precio_actual = await obtener_precio(par)
                monto_usdt = calcular_monto_kelly(saldo)
                orden = await ejecutar_compra(par, monto_usdt)

                if orden:
                    operacion_activa = (par, precio_actual)
                    await bot.send_message(
                        CHAT_ID,
                        f"✅ Nueva operación abierta en {par}.\nPrecio de entrada: {precio_actual:.6f} USDT\nMonto: {monto_usdt:.2f} USDT"
                    )
                    await monitorear_operacion(par, precio_actual)
                    operacion_activa = None

            await asyncio.sleep(15)  # Tiempo de espera entre análisis

        except Exception as e:
            logging.error(f"Error en ciclo operativo: {str(e)}")
            await asyncio.sleep(30)

# ─── Lanzamiento del Bot ───────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())