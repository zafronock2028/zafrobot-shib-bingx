# main.py
import os
import asyncio
import logging
import datetime
from decimal import Decimal, ROUND_DOWN
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Configuración de Logging
logging.basicConfig(level=logging.INFO)

# Variables de Entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

# Conexiones
client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Estado Global
bot_encendido = False
operacion_activa = None
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]
modelo_predictor = None
ganancia_total_hoy = 0.0
operaciones_hoy = 0
modo_agresivo = True# Configurar Teclado de Telegram
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)

# Obtener saldo disponible en USDT
def obtener_saldo():
    try:
        cuentas = client.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
    return 0.0

# Redondear cantidad para cumplir mínimo de compra
def redondear_cantidad(par, cantidad):
    if "DOGE" in par:
        decimales = 2
    else:
        decimales = 0
    return float(Decimal(cantidad).quantize(Decimal(f'1e-{decimales}'), rounding=ROUND_DOWN))

# Cálculo de tamaño de inversión según Kelly Criterion
def calcular_inversion(saldo, probabilidad_éxito=0.6, ganancia_riesgo=1.5):
    try:
        kelly = (probabilidad_éxito * (ganancia_riesgo + 1) - 1) / ganancia_riesgo
        kelly = max(min(kelly, 1), 0.05)  # mínimo 5%
        monto = saldo * kelly

        if modo_agresivo:
            if monto < saldo * 0.4:
                monto = saldo * 0.5  # mínimo 50% en modo agresivo si Kelly es bajo
        else:
            if monto < saldo * 0.2:
                monto = saldo * 0.3  # en modo conservador, mínimo 30%

        return round(monto, 2)
    except:
        return round(saldo * 0.2, 2)  # fallback# Análisis de oportunidad (Volumen real + Liquidez real)
def analizar_par(par):
    try:
        simbolo = par.replace("/", "-")
        # Volumen
        velas = client.get_kline(symbol=simbolo, kline_type="1min", limit=10)
        volumenes = [float(v[5]) for v in velas]
        promedio_volumen = sum(volumenes[:-1]) / len(volumenes[:-1])
        volumen_actual = volumenes[-1]

        # Order Book
        order_book = client.get_order_book(symbol=simbolo, limit=10)
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])

        if not bids or not asks:
            return False

        mejor_bid = float(bids[0][0])
        mejor_ask = float(asks[0][0])
        spread = abs(mejor_ask - mejor_bid) / mejor_bid

        profundidad_bids = sum(float(bid[1]) * float(bid[0]) for bid in bids)
        profundidad_asks = sum(float(ask[1]) * float(ask[0]) for ask in asks)

        liquidez_total = profundidad_bids + profundidad_asks

        # Condiciones para operar:
        volumen_ok = volumen_actual >= promedio_volumen * 1.5
        spread_ok = spread <= 0.002  # 0.2%
        liquidez_ok = liquidez_total >= 1000  # mínimo $1000 de profundidad

        return volumen_ok and spread_ok and liquidez_ok
    except Exception as e:
        logging.error(f"Error analizando {par}: {e}")
        return False

# Buscar el mejor par para entrar
def seleccionar_mejor_par():
    mejores_pares = []
    for par in pares:
        if analizar_par(par):
            mejores_pares.append(par)
    if mejores_pares:
        return mejores_pares[0]  # Elegimos el primero que cumpla
    return None

# Ejecutar compra en modo Market
async def ejecutar_compra(par, saldo_usdt):
    try:
        simbolo = par.replace("/", "-")
        precio_actual = float(client.get_ticker(symbol=simbolo)["price"])
        cantidad = redondear_cantidad(par, saldo_usdt / precio_actual)

        if cantidad <= 0:
            return None

        orden = client.create_market_order(symbol=simbolo, side="buy", funds=str(saldo_usdt))
        logging.info(f"Compra ejecutada en {par}: {cantidad}")
        return {"par": par, "precio_entrada": precio_actual, "cantidad": cantidad}
    except Exception as e:
        logging.error(f"Error ejecutando compra de {par}: {e}")
        return None# Monitorear operación activa
async def monitorear_operacion(operacion):
    global ganancia_total_hoy, operaciones_hoy, operacion_activa

    par = operacion['par']
    precio_entrada = operacion['precio_entrada']
    cantidad = operacion['cantidad']
    simbolo = par.replace("/", "-")
    mejor_precio = precio_entrada
    trailing_gap = 0.007  # 0.7% trailing

    while bot_encendido and operacion_activa:
        try:
            precio_actual = float(client.get_ticker(symbol=simbolo)["price"])

            if precio_actual > mejor_precio:
                mejor_precio = precio_actual

            stop_trailing = mejor_precio * (1 - trailing_gap)

            if precio_actual <= stop_trailing or precio_actual >= precio_entrada * 1.025:
                # Aquí vendemos
                usdt_obtenido = precio_actual * cantidad
                ganancia = usdt_obtenido - (precio_entrada * cantidad)
                ganancia_total_hoy += ganancia
                operaciones_hoy += 1

                mensaje = f"✅ Venta completada\nPar: {par}\nEntrada: {precio_entrada:.8f}\nSalida: {precio_actual:.8f}\nGanancia: {ganancia:.4f} USDT"
                await bot.send_message(chat_id=CHAT_ID, text=mensaje)

                operacion_activa = None
                break

        except Exception as e:
            logging.error(f"Error monitoreando operación en {par}: {e}")

        await asyncio.sleep(2)# Comandos de Telegram

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ *ZafroBot Scalper Pro Avanzado* iniciado.\n\nSelecciona una opción:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        saldo = obtener_saldo()
        await message.answer(f"🟢 Bot encendido.\nSaldo disponible: {saldo:.2f} USDT\nAnalizando oportunidades...")
        asyncio.create_task(flujo_principal())
    else:
        await message.answer("⚠️ El bot ya está encendido.")

@dp.message(lambda m: m.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    global bot_encendido, operacion_activa
    bot_encendido = False
    operacion_activa = None
    await message.answer("🔴 Bot apagado.")

@dp.message(lambda m: m.text == "📊 Estado del Bot")
async def estado_bot(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await message.answer(f"📊 Estado actual: {estado}")

@dp.message(lambda m: m.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = obtener_saldo()
    await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def estado_orden(message: types.Message):
    if operacion_activa:
        await message.answer(f"📈 Operación activa:\nPar: {operacion_activa['par']}\nEntrada: {operacion_activa['precio_entrada']:.8f}")
    else:
        await message.answer("❌ No hay operación activa en este momento.")

# Flujo Principal
async def flujo_principal():
    global operacion_activa

    while bot_encendido:
        if not operacion_activa:
            saldo = obtener_saldo()

            if saldo < 5:
                await bot.send_message(CHAT_ID, "⚠️ Saldo insuficiente. Esperando...")
                await asyncio.sleep(10)
                continue

            par = seleccionar_mejor_par()

            if par:
                monto_inversion = calcular_inversion(saldo)
                operacion = await ejecutar_compra(par, monto_inversion)
                if operacion:
                    operacion_activa = operacion
                    await monitorear_operacion(operacion)
                else:
                    await asyncio.sleep(2)
            else:
                await asyncio.sleep(2)
        else:
            await asyncio.sleep(2)

# Lanzador
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())