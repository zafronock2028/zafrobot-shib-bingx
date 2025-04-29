# main.py
import os
import asyncio
import logging
import random
from kucoin.client import User as UserClient
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ─── Configuración KuCoin y Telegram ─────────────────────────────────────
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = UserClient(API_KEY, SECRET_KEY, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# ─── Variables globales ──────────────────────────────────────────────────
bot_encendido = False
operacion_abierta = False
precio_entrada = 0
par_operando = ""
cantidad_operada = 0

pares = ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT"]

# ─── Configurar teclado de Telegram ──────────────────────────────────────
keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
    [KeyboardButton(text="💰 Saldo"), KeyboardButton(text="📊 Estado Bot")],
    [KeyboardButton(text="📈 Estado Orden Actual")]
], resize_keyboard=True)# ─── Funciones de control del bot ────────────────────────────────────────

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Bienvenido al *Zafrobot Dinámico Pro Scalping*.\n\nUsa el teclado para controlar el bot.", reply_markup=keyboard, parse_mode="Markdown")

@dp.message()
async def manejar_mensajes(message: types.Message):
    global bot_encendido
    texto = message.text

    if texto == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("🚀 Bot encendido. Comenzando operaciones...")
            asyncio.create_task(loop_principal())
        else:
            await message.answer("⚠️ El bot ya está encendido.")

    elif texto == "🛑 Apagar Bot":
        if bot_encendido:
            bot_encendido = False
            await message.answer("🛑 Bot apagado manualmente.")
        else:
            await message.answer("⚠️ El bot ya está apagado.")

    elif texto == "💰 Saldo":
        saldo = await obtener_saldo()
        await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

    elif texto == "📊 Estado Bot":
        estado = "🟢 ENCENDIDO" if bot_encendido else "🔴 APAGADO"
        await message.answer(f"📊 Estado del bot: {estado}")

    elif texto == "📈 Estado Orden Actual":
        if operacion_abierta:
            await message.answer(f"📈 Orden abierta en {par_operando}.\nPrecio de entrada: {precio_entrada:.8f}\nCantidad: {cantidad_operada:.2f}")
        else:
            await message.answer("🚫 No hay orden activa actualmente.")# ─── Funciones principales del bot ───────────────────────────────────────

async def loop_principal():
    global bot_encendido
    while bot_encendido:
        try:
            if not operacion_abierta:
                mejor_par = await seleccionar_mejor_par()
                if mejor_par:
                    await abrir_operacion(mejor_par)
            await asyncio.sleep(2)  # Escaneo cada 2 segundos
        except Exception as e:
            logging.error(f"Error en loop principal: {e}")
            await asyncio.sleep(5)

async def seleccionar_mejor_par():
    mejor_par = None
    mejor_volumen = 0

    for par in pares:
        try:
            ticker = client.get_ticker(par)
            volumen_24h = float(ticker['volValue'])
            if volumen_24h > mejor_volumen:
                mejor_volumen = volumen_24h
                mejor_par = par
        except Exception as e:
            logging.error(f"Error obteniendo volumen de {par}: {e}")

    return mejor_par

async def abrir_operacion(par):
    global operacion_abierta, precio_entrada, par_operando, cantidad_operada

    saldo = await obtener_saldo()
    if saldo < 5:
        await bot.send_message(chat_id=message.chat.id, text="⚠️ Saldo insuficiente para operar.")
        return

    monto_a_usar = calcular_monto_kelly(saldo, par)
    if monto_a_usar < 5:
        monto_a_usar = saldo * 0.95  # Modo agresivo si Kelly da muy bajo

    try:
        precio = await obtener_precio_actual(par)
        cantidad = monto_a_usar / precio
        cantidad = round(cantidad, 4)

        # Aquí colocarías la orden real (simulado por ahora)
        operacion_abierta = True
        precio_entrada = precio
        par_operando = par
        cantidad_operada = cantidad

        await bot.send_message(chat_id=message.chat.id, text=f"✅ Orden abierta en {par}\nPrecio: {precio:.8f}\nCantidad: {cantidad:.2f}")

        asyncio.create_task(monitorear_orden())

    except Exception as e:
        logging.error(f"Error al abrir operación: {e}")async def monitorear_orden():
    global operacion_abierta, precio_entrada, par_operando, cantidad_operada

    try:
        objetivo_minimo = precio_entrada * 1.025  # 2.5% de ganancia mínima
        trailing_stop = precio_entrada * 0.92  # Trailing dinámico a -8%

        while bot_encendido and operacion_abierta:
            precio_actual = await obtener_precio_actual(par_operando)

            if precio_actual >= objetivo_minimo:
                # Subir trailing dinámicamente
                nuevo_stop = precio_actual * 0.92
                if nuevo_stop > trailing_stop:
                    trailing_stop = nuevo_stop

            if precio_actual <= trailing_stop:
                await cerrar_operacion(precio_actual)
                break

            await asyncio.sleep(2)

    except Exception as e:
        logging.error(f"Error en monitoreo de orden: {e}")

async def cerrar_operacion(precio_salida):
    global operacion_abierta, precio_entrada, par_operando, cantidad_operada

    try:
        ganancia = (precio_salida - precio_entrada) * cantidad_operada
        porcentaje_ganancia = ((precio_salida / precio_entrada) - 1) * 100

        await bot.send_message(chat_id=message.chat.id, text=f"🏁 Orden cerrada en {par_operando}\nPrecio de salida: {precio_salida:.8f}\nGanancia: {ganancia:.4f} USDT\n% Ganancia: {porcentaje_ganancia:.2f}%")

        operacion_abierta = False
        precio_entrada = 0
        par_operando = ""
        cantidad_operada = 0

    except Exception as e:
        logging.error(f"Error cerrando operación: {e}")# ─── Funciones auxiliares ───────────────────────────────────────────────

async def obtener_precio_actual(par):
    try:
        ticker = client.get_ticker(par)
        return float(ticker['price'])
    except Exception as e:
        logging.error(f"Error obteniendo precio de {par}: {e}")
        return 0.0

async def obtener_saldo():
    try:
        cuentas = client.get_account_list()
        cuenta_usdt = next((c for c in cuentas if c['currency'] == 'USDT' and c['type'] == 'trade'), None)
        if cuenta_usdt:
            return float(cuenta_usdt['available'])
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
    return 0.0

def calcular_monto_kelly(saldo, par):
    try:
        ticker = client.get_ticker(par)
        volumen_24h = float(ticker['volValue'])
        limite_por_volumen = volumen_24h * 0.04  # 4% del volumen 24h

        # Fórmula simplificada Kelly Criterion para scalping
        winrate = 0.85  # 85% winrate estimado
        reward_risk = 2.5  # Relación beneficio/riesgo
        kelly = (winrate * (reward_risk + 1) - 1) / reward_risk

        monto = saldo * kelly
        monto_final = min(monto, limite_por_volumen)
        return max(monto_final, 5)  # Nunca menos de 5 USDT

    except Exception as e:
        logging.error(f"Error calculando Kelly para {par}: {e}")
        return saldo * 0.8  # Modo agresivo de respaldo

# ─── Iniciar Bot ─────────────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())