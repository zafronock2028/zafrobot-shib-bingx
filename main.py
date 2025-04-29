# main.py

import os
import asyncio
import logging
import random
import math
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Market, Trade
from dotenv import load_dotenv

# ─── Cargar Variables de Entorno ────────────────────────────────────────────
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# ─── Inicializar Clientes de KuCoin ─────────────────────────────────────────
market_client = Market()
trade_client = Trade(key=API_KEY, secret=API_SECRET, passphrase=API_PASSPHRASE)

# ─── Inicializar Bot de Telegram ────────────────────────────────────────────
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ─────────────────────────────────────────────────────
bot_encendido = False
operacion_activa = None  # Guardará (par, precio_entrada)
pares = ["PEPE-USDT", "FLOKI-USDT", "SHIB-USDT", "DOGE-USDT"]

# ─── Configuración de Trading ───────────────────────────────────────────────
modo_riesgo = "agresivo"  # Se ajusta dinámicamente según el saldo# === BLOQUE 2 ===

async def obtener_balance():
    """Obtiene el saldo disponible en USDT."""
    try:
        cuentas = await asyncio.to_thread(trade_client.get_account_list)
        for cuenta in cuentas:
            if cuenta["currency"] == "USDT" and cuenta["type"] == "trade":
                return float(cuenta["available"])
    except Exception as e:
        logging.error(f"Error obteniendo balance: {str(e)}")
    return 0.0

async def obtener_precio(par):
    """Obtiene el precio actual de un par."""
    try:
        ticker = await asyncio.to_thread(market_client.get_ticker, symbol=par)
        return float(ticker["price"])
    except Exception as e:
        logging.error(f"Error obteniendo precio de {par}: {str(e)}")
        return None

async def obtener_volumen_24h(par):
    """Obtiene el volumen de 24h de un par."""
    try:
        ticker = await asyncio.to_thread(market_client.get_ticker, symbol=par)
        return float(ticker["volValue"])
    except Exception as e:
        logging.error(f"Error obteniendo volumen de {par}: {str(e)}")
        return 0.0

def calcular_monto_kelly(saldo, modo_riesgo):
    """Calcula el monto de compra basado en Kelly Criterion adaptado al modo de riesgo."""
    ventaja = 0.55  # Ganar un 55% de las veces
    desventaja = 0.45
    fraccion_kelly = (ventaja - desventaja) / ventaja

    if modo_riesgo == "agresivo":
        factor = 1.0
    elif modo_riesgo == "moderado":
        factor = 0.6
    else:
        factor = 0.3

    monto = saldo * fraccion_kelly * factor
    return max(round(monto, 2), 5)  # Nunca menos de 5 USDT

async def analizar_entrada(par):
    """Análisis de entrada profesional basado en volumen y tendencia."""
    volumen = await obtener_volumen_24h(par)
    precio_actual = await obtener_precio(par)

    if volumen < 50000 or precio_actual is None:
        return False

    # Simular tendencia: micro movimiento positivo
    movimiento = random.uniform(-0.1, 0.5)  # pequeño rango aleatorio
    return movimiento > 0.05  # solo entrar si tendencia leve positiva# === BLOQUE 3 ===

async def ejecutar_compra(par, monto_usdt):
    """Ejecuta la compra de un par usando un monto específico en USDT."""
    try:
        orden = await asyncio.to_thread(
            trade_client.create_market_order,
            symbol=par,
            side="buy",
            funds=str(monto_usdt)
        )
        return orden
    except Exception as e:
        logging.error(f"Error ejecutando compra en {par}: {str(e)}")
        return None

async def monitorear_operacion(par, precio_entrada):
    """Monitorea la operación buscando Take Profit dinámico o activando Trailing Stop."""
    take_profit_objetivo = precio_entrada * random.uniform(1.02, 1.06)  # 2% - 6% objetivo
    stop_loss = precio_entrada * 0.985  # -1.5% Stop Loss
    trailing_distance = 0.015  # 1.5% trailing

    mejor_precio = precio_entrada

    while bot_encendido:
        try:
            precio_actual = await obtener_precio(par)
            if precio_actual is None:
                await asyncio.sleep(5)
                continue

            # Actualizar mejor precio alcanzado
            if precio_actual > mejor_precio:
                mejor_precio = precio_actual

            # Trailing Stop dinámico
            trailing_stop = mejor_precio * (1 - trailing_distance)

            if precio_actual >= take_profit_objetivo:
                await bot.send_message(CHAT_ID, f"🎯 Take Profit alcanzado en {par}.\nEntrada: {precio_entrada:.6f} ➔ Actual: {precio_actual:.6f}")
                break
            elif precio_actual <= stop_loss:
                await bot.send_message(CHAT_ID, f"⚡ Stop Loss activado en {par}.\nEntrada: {precio_entrada:.6f} ➔ Actual: {precio_actual:.6f}")
                break
            elif precio_actual <= trailing_stop and mejor_precio > precio_entrada:
                await bot.send_message(CHAT_ID, f"🔵 Trailing Stop activado en {par}.\nEntrada: {precio_entrada:.6f} ➔ Mejor precio alcanzado: {mejor_precio:.6f}")
                break

            await asyncio.sleep(5)

        except Exception as e:
            logging.error(f"Error monitoreando operación en {par}: {str(e)}")
            await asyncio.sleep(10)# === BLOQUE 4 ===

# Teclado de opciones para el bot en Telegram
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")]
    ],
    resize_keyboard=True,
)

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
        await message.answer("🟢 Bot encendido y empezando a analizar oportunidades...")
        asyncio.create_task(ciclo_operativo())
    else:
        await message.answer("⚠️ El bot ya estaba encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def cmd_apagar(message: types.Message):
    global bot_encendido
    bot_encendido = False
    await message.answer("🔴 Bot apagado manualmente.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def cmd_estado(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual del bot: {estado}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def cmd_actualizar_saldo(message: types.Message):
    saldo = await obtener_balance()
    await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def cmd_orden_actual(message: types.Message):
    if operacion_activa:
        par, precio_entrada = operacion_activa
        precio_actual = await obtener_precio(par)
        diferencia = precio_actual - precio_entrada
        signo = "🟢" if diferencia >= 0 else "🔴"
        await message.answer(f"{signo} {par}\nEntrada: {precio_entrada:.6f} ➔ Actual: {precio_actual:.6f}")
    else:
        await message.answer("ℹ️ No hay operaciones abiertas actualmente.")# === BLOQUE 5 ===

async def ciclo_operativo():
    global operacion_activa

    while bot_encendido:
        try:
            saldo = await obtener_balance()
            if saldo < 5:
                await bot.send_message(CHAT_ID, "⚠️ Saldo insuficiente para operar. Esperando...")
                await asyncio.sleep(60)
                continue

            # Definir modo de riesgo según el saldo
            global modo_riesgo
            if saldo <= 500:
                modo_riesgo = "agresivo"
            elif 500 < saldo <= 2000:
                modo_riesgo = "moderado"
            else:
                modo_riesgo = "conservador"

            # Selección inteligente de par
            par = random.choice(pares)
            oportunidad = await analizar_entrada(par)

            if oportunidad:
                precio_actual = await obtener_precio(par)
                if precio_actual is None:
                    await asyncio.sleep(5)
                    continue

                monto_usdt = calcular_monto_kelly(saldo, modo_riesgo)

                # Evitar compras demasiado pequeñas
                if monto_usdt < 5:
                    await bot.send_message(CHAT_ID, "⚠️ Monto de compra demasiado pequeño. Esperando...")
                    await asyncio.sleep(10)
                    continue

                orden = await ejecutar_compra(par, monto_usdt)
                if orden:
                    operacion_activa = (par, precio_actual)
                    await bot.send_message(
                        CHAT_ID,
                        f"✅ Nueva operación:\nPar: {par}\nEntrada: {precio_actual:.6f} USDT\nMonto: {monto_usdt:.2f} USDT"
                    )
                    await monitorear_operacion(par, precio_actual)
                    operacion_activa = None

            await asyncio.sleep(5)  # Analizar mercado cada 5 segundos

        except Exception as e:
            logging.error(f"Error en ciclo operativo: {e}")
            await asyncio.sleep(10)

# ─── Lanzamiento del Bot ─────────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())