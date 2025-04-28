# main.py
import os
import asyncio
import logging
import datetime
import random
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ─── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── Configuración ─────────────────────────────────────────────────────────
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID        = int(os.getenv("CHAT_ID", 0))

# ─── Cliente de KuCoin ─────────────────────────────────────────────────────
kucoin = Client(API_KEY, API_SECRET, API_PASSPHRASE)

# ─── Cliente de Telegram ───────────────────────────────────────────────────
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ─── Variables Globales ────────────────────────────────────────────────────
_last_balance: float = 0.0
bot_encendido = False
pares = ["PEPE/USDT", "FLOKI/USDT", "SHIB/USDT", "DOGE/USDT"]

operacion_activa = None
operaciones_hoy = 0
ganancia_total_hoy = 0.0

volumen_anterior = {}

# ─── Teclado de Comandos ────────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot"), KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="📊 Estado del Bot"), KeyboardButton(text="💰 Actualizar Saldo")],
        [KeyboardButton(text="📈 Estado de Orden Actual")],
    ],
    resize_keyboard=True,
)

# ─── Funciones de Análisis ──────────────────────────────────────────────────

async def analizar_mercado_real(par):
    try:
        simbolo = par.replace("/", "-")
        order_book = await asyncio.to_thread(kucoin.get_order_book, symbol=simbolo, depth=20)

        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])

        if not bids or not asks:
            return False

        mejor_bid = float(bids[0][0])
        mejor_ask = float(asks[0][0])
        spread = (mejor_ask - mejor_bid) / mejor_bid * 100

        volumen_bids = sum(float(bid[1]) for bid in bids[:5])
        volumen_asks = sum(float(ask[1]) for ask in asks[:5])

        if spread > 0.2:
            return False
        if volumen_bids < volumen_asks:
            return False
        if volumen_bids < 50:
            return False

        return True

    except Exception as e:
        logging.error(f"Error en analizar_mercado_real para {par}: {str(e)}")
        return False

# ─── Funciones de Gestión de Operaciones ────────────────────────────────────

async def registrar_operacion(par, precio_entrada, cantidad, saldo_usado):
    global operacion_activa
    operacion_activa = {
        "par": par,
        "precio_entrada": precio_entrada,
        "cantidad": cantidad,
        "saldo_usado": saldo_usado,
        "hora": datetime.datetime.now(),
        "mejor_precio": precio_entrada
    }

async def limpiar_operacion():
    global operacion_activa
    operacion_activa = None

async def actualizar_estadisticas(porcentaje_ganancia):
    global operaciones_hoy, ganancia_total_hoy
    operaciones_hoy += 1
    ganancia_total_hoy += porcentaje_ganancia

# ─── Funciones Internas ─────────────────────────────────────────────────────

async def obtener_balance():
    cuenta = await asyncio.to_thread(kucoin.get_accounts, currency="USDT", type="trade")
    if cuenta:
        return float(cuenta[0].get('available', 0))
    return 0.0

def obtener_precio(par):
    simbolo = par.replace("/", "-")
    ticker = kucoin.get_ticker(symbol=simbolo)
    return float(ticker["price"])

def ejecutar_compra(par, cantidad):
    simbolo = par.replace("/", "-")
    try:
        orden = kucoin.create_market_order(symbol=simbolo, side="buy", size=cantidad)
        return orden
    except Exception as e:
        logging.error(f"Error comprando {par}: {str(e)}")
        return None

# ─── Lógica de Trading ──────────────────────────────────────────────────────

async def operar():
    global _last_balance
    _last_balance = await obtener_balance()

    while bot_encendido:
        try:
            balance = await obtener_balance()

            if balance < 5:
                await bot.send_message(CHAT_ID, f"⚠️ Saldo insuficiente ({balance:.2f} USDT). Esperando...")
                await asyncio.sleep(60)
                continue

            if operacion_activa is not None:
                await asyncio.sleep(2)
                continue

            par = random.choice(pares)

            analisis_ok = await analizar_mercado_real(par)

            if analisis_ok:
                precio_actual = await asyncio.to_thread(obtener_precio, par)
                porcentaje = 0.9 if balance < 300 else 0.5
                saldo_usar = balance * porcentaje
                cantidad = saldo_usar / precio_actual

                orden = await asyncio.to_thread(ejecutar_compra, par, cantidad)
                if orden:
                    await bot.send_message(CHAT_ID, f"✅ *Compra ejecutada*\n\nPar: {par}\nPrecio: {precio_actual:.8f}\nSaldo usado: {saldo_usar:.2f} USDT", parse_mode="Markdown")
                    await registrar_operacion(par, precio_actual, cantidad, saldo_usar)
                    asyncio.create_task(monitorear_operacion(par, precio_actual, cantidad))
            await asyncio.sleep(2)

        except Exception as e:
            logging.error(f"Error general: {str(e)}")
            await asyncio.sleep(60)

async def monitorear_operacion(par, precio_entrada, cantidad):
    global operacion_activa

    simbolo = par.replace("/", "-")
    objetivo_inicial = precio_entrada * 1.025
    trailing_stop = 0.98

    while bot_encendido and operacion_activa is not None:
        precio_actual = await asyncio.to_thread(obtener_precio, par)

        porcentaje_cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100

        if precio_actual > operacion_activa["mejor_precio"]:
            operacion_activa["mejor_precio"] = precio_actual

        mejor_precio = operacion_activa["mejor_precio"]
        nuevo_stop = mejor_precio * 0.985

        if precio_actual >= objetivo_inicial:
            if precio_actual <= nuevo_stop:
                await bot.send_message(CHAT_ID, f"🎯 *Take Profit alcanzado con Trailing Stop*\n\nGanancia asegurada: +{porcentaje_cambio:.2f}%", parse_mode="Markdown")
                await actualizar_estadisticas(porcentaje_cambio)
                await limpiar_operacion()
                break

        elif precio_actual <= precio_entrada * trailing_stop:
            await bot.send_message(CHAT_ID, f"⚡ *Stop Loss base activado*\n\nPérdida: {porcentaje_cambio:.2f}%", parse_mode="Markdown")
            await actualizar_estadisticas(porcentaje_cambio)
            await limpiar_operacion()
            break

        await asyncio.sleep(2)

# ─── Sistema de Alertas de Volumen Anormal ──────────────────────────────────

async def inicializar_volumenes():
    global volumen_anterior
    for par in pares:
        simbolo = par.replace("/", "-")
        try:
            ticker = await asyncio.to_thread(kucoin.get_ticker, symbol=simbolo)
            volumen_anterior[par] = float(ticker['vol'])
        except Exception as e:
            logging.error(f"Error inicializando volumen de {par}: {str(e)}")
            volumen_anterior[par] = 0.0

async def escanear_volumenes():
    global volumen_anterior
    await inicializar_volumenes()
    
    while True:
        try:
            for par in pares:
                simbolo = par.replace("/", "-")
                ticker = await asyncio.to_thread(kucoin.get_ticker, symbol=simbolo)
                volumen_actual = float(ticker['vol'])

                volumen_ant = volumen_anterior.get(par, 0.0)
                if volumen_ant == 0.0:
                    volumen_anterior[par] = volumen_actual
                    continue

                incremento = ((volumen_actual - volumen_ant) / volumen_ant) * 100

                if incremento >= 500:
                    await bot.send_message(CHAT_ID,
                        f"🚨 *ALERTA de Volumen Anormal*\n\n"
                        f"Par: {par}\n"
                        f"Incremento: +{incremento:.2f}%\n"
                        f"Acción: Monitorear posible oportunidad.",
                        parse_mode="Markdown"
                    )
                
                volumen_anterior[par] = volumen_actual

            await asyncio.sleep(60)

        except Exception as e:
            logging.error(f"Error en escaneo de volumen: {str(e)}")
            await asyncio.sleep(60)

# ─── Comandos de Telegram ───────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ *ZafroBot Scalper PRO V3* iniciado.\n\nSelecciona una opción:",
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
async def cmd_actualizar_saldo(message: types.Message):
    balance = await obtener_balance()
    await message.answer(f"💰 Saldo disponible: {balance:.2f} USDT")

@dp.message(lambda m: m.text == "📈 Estado de Orden Actual")
async def cmd_estado_orden(message: types.Message):
    if operacion_activa is None:
        await message.answer("⚠️ No hay operaciones abiertas en este momento.")
    else:
        par = operacion_activa["par"]
        precio_entrada = operacion_activa["precio_entrada"]
        cantidad = operacion_activa["cantidad"]
        saldo_usado = operacion_activa["saldo_usado"]
        precio_actual = await asyncio.to_thread(obtener_precio, par)

        porcentaje_cambio = ((precio_actual - precio_entrada) / precio_entrada) * 100

        estado = "🟢 En Ganancia" if porcentaje_cambio > 0 else "🔴 En Pérdida"

        await message.answer(
            f"📈 Estado de Orden Actual:\n\n"
            f"Par: {par}\n"
            f"Precio Entrada: {precio_entrada:.8f}\n"
            f"Precio Actual: {precio_actual:.8f}\n"
            f"{estado}: {porcentaje_cambio:.2f}%\n"
            f"Saldo Invertido: {saldo_usado:.2f} USDT"
        )

# ─── Lanzamiento del Bot ────────────────────────────────────────────────────

async def main():
    asyncio.create_task(escanear_volumenes())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())