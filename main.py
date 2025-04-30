import os
import asyncio
import logging
from datetime import datetime
from kucoin.client import Market, Trade, User
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# Configuración inicial
load_dotenv()
logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode="Markdown")
dp = Dispatcher()
market_client = Market()
trade_client = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
user_client = User(API_KEY, SECRET_KEY, API_PASSPHRASE)

bot_encendido = False
operaciones_activas = []
max_operaciones = 3
pares = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT", "SUI-USDT",
    "TURBO-USDT", "BONK-USDT", "KAS-USDT", "WIF-USDT", "XMR-USDT", "HYPE-USDT",
    "HYPER-USDT", "OM-USDT", "ENA-USDT"
]
trailing_stop_pct = -0.08
ganancia_objetivo = 0.008
historial_operaciones = {"ganadas": 1, "perdidas": 1}
min_orden_usdt = 5.0

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="🛑 Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Estado de Orden Actual")]
    ],
    resize_keyboard=True
)

# Registra los handlers en Aiogram 3
dp.message.register(start, Command("start"))
dp.message.register(comandos)

async def comandos(message: types.Message):
    global bot_encendido

    if message.text == "💰 Saldo":
        saldo = obtener_saldo_disponible()
        await message.answer(f"💰 Tu saldo disponible es: {saldo:.2f} USDT")

    elif message.text == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido. Analizando oportunidades...")
            asyncio.create_task(loop_operaciones())
        else:
            await message.answer("⚠️ El bot ya está encendido.")

    elif message.text == "🛑 Apagar Bot":
        bot_encendido = False
        await message.answer("🛑 Bot apagado manualmente.")

    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_encendido else "🛑 APAGADO"
        await message.answer(f"📊 Estado actual del bot: {estado}")

    elif message.text == "📈 Estado de Orden Actual":
        if operaciones_activas:
            mensaje = ""
            for op in operaciones_activas:
                estado = "GANANCIA ✅" if op["ganancia"] >= 0 else "PÉRDIDA ❌"
                mensaje += (
                    f"📈 Par: {op['par']}\n"
                    f"Entrada: {op['entrada']:.6f} USDT\n"
                    f"Actual: {op['actual']:.6f} USDT\n"
                    f"Ganancia: {op['ganancia']:.6f} USDT ({estado})\n\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ No hay operaciones activas actualmente.")

def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        saldo = next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
        return saldo
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

def calcular_kelly(win_rate, avg_win=1, avg_loss=1):
    kelly = (win_rate * avg_win - (1 - win_rate)) / avg_loss
    return max(min(kelly, 1), 0.05)

async def loop_operaciones():
    global bot_encendido, operaciones_activas

    while bot_encendido:
        if len(operaciones_activas) >= max_operaciones:
            await asyncio.sleep(3)
            continue

        saldo = obtener_saldo_disponible()
        if saldo < min_orden_usdt:
            await asyncio.sleep(5)
            continue

        win_rate = historial_operaciones["ganadas"] / (historial_operaciones["ganadas"] + historial_operaciones["perdidas"])
        porcentaje_kelly = calcular_kelly(win_rate)

        for par in pares:
            if len(operaciones_activas) >= max_operaciones:
                break

            info = analizar_par(par)
            if info["puntaje"] >= 2:
                monto_inversion = min(saldo * porcentaje_kelly, saldo / (max_operaciones - len(operaciones_activas)))
                if monto_inversion < min_orden_usdt:
                    logging.info(f"⛔ Monto insuficiente para operar {par}: {monto_inversion:.2f} USDT")
                    continue

                cantidad = monto_inversion / info["precio"]
                resultado = ejecutar_compra(par, cantidad)

                if resultado:
                    operacion = {
                        "par": par,
                        "entrada": info["precio"],
                        "cantidad": cantidad,
                        "ganancia": 0.0,
                        "id": resultado["orderOid"]
                    }
                    operaciones_activas.append(operacion)
                    logging.info(f"🟢 COMPRA: {par} | Entrada: {info['precio']} | Cantidad: {cantidad}")
                    await bot.send_message(CHAT_ID, f"🟢 COMPRA EJECUTADA\nPar: {par}\nEntrada: {info['precio']:.6f} USDT")

                    asyncio.create_task(monitorear_salida(operacion))
        await asyncio.sleep(3)

def analizar_par(par):
    try:
        velas = market_client.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(x[2]) for x in velas]
        promedio = sum(precios) / len(precios)
        actual = precios[-1]
        volumen_24h = float(market_client.get_24h_stats(par)["volValue"])
        volumen_reciente = float(velas[-1][5])
        puntaje = 0

        if actual > promedio:
            puntaje += 1
        if volumen_reciente > volumen_24h * 0.001:
            puntaje += 1
        if abs(actual - promedio) / promedio >= 0.005:
            puntaje += 1

        logging.info(f"🔍 {par} | Puntaje: {puntaje} | Precio: {actual:.6f} | Volumen24h: {volumen_24h:.2f}")
        return {"par": par, "precio": actual, "puntaje": puntaje}
    except Exception as e:
        logging.warning(f"Error analizando {par}: {e}")
        return {"par": par, "precio": 0, "puntaje": 0}

def ejecutar_compra(par, cantidad):
    try:
        orden = trade_client.create_market_order(symbol=par, side="buy", size=round(cantidad, 6))
        return orden
    except Exception as e:
        logging.error(f"Error ejecutando compra en {par}: {e}")
        return None

async def monitorear_salida(operacion):
    global historial_operaciones, operaciones_activas
    try:
        entrada = operacion["entrada"]
        cantidad = operacion["cantidad"]
        par = operacion["par"]
        max_precio = entrada

        while True:
            actual = float(market_client.get_ticker(par)["price"])
            max_precio = max(max_precio, actual)
            cambio_pct = (actual - entrada) / entrada
            trailing_trigger = (max_precio - actual) / max_precio

            operacion["actual"] = actual
            operacion["ganancia"] = (actual - entrada) * cantidad

            if cambio_pct >= ganancia_objetivo or trailing_trigger >= abs(trailing_stop_pct):
                trade_client.create_market_order(symbol=par, side="sell", size=round(cantidad, 6))
                operaciones_activas.remove(operacion)
                historial_operaciones["ganadas" if cambio_pct > 0 else "perdidas"] += 1

                resultado = "✅ GANANCIA" if cambio_pct > 0 else "❌ PÉRDIDA"
                logging.info(f"🔴 VENTA: {par} | Salida: {actual:.6f} | Ganancia: {operacion['ganancia']:.4f}")
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 VENTA EJECUTADA\nPar: {par}\nSalida: {actual:.6f} USDT\nGanancia: {operacion['ganancia']:.4f} USDT\nResultado: {resultado}"
                )
                break
            await asyncio.sleep(5)
    except Exception as e:
        logging.error(f"Error en monitoreo de salida: {e}")
        if operacion in operaciones_activas:
            operaciones_activas.remove(operacion)

# Iniciar el bot
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))