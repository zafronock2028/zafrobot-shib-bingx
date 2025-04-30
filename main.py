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

# Teclado Telegram
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

# Comandos
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
                    f"📈 Par: {op['par']}\n"
                    f"Entrada: {op['entrada']:.6f} USDT\n"
                    f"Actual: {op['actual']:.6f} USDT\n"
                    f"Ganancia: {op['ganancia']:.6f} USDT ({estado})\n\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ No hay operaciones activas actualmente.")

    elif message.text == "🧾 Historial de Ganancias":
        if historial_operaciones:
            mensaje = "🧾 *Últimas ganancias:*\n\n"
            for h in historial_operaciones[-10:]:
                mensaje += (
                    f"{h['fecha']} | {h['par']} | {h['resultado']} | "
                    f"{h['ganancia']:.4f} USDT | Saldo: {h['saldo']:.2f}\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ Aún no hay historial de operaciones.")

# Funciones principales
async def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        saldo = next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
        return saldo
    except Exception as e:
        logging.error(f"[Error] Obteniendo saldo: {e}")
        return 0.0

def analizar_par(par):
    try:
        velas = market_client.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(x[2]) for x in velas]
        promedio = sum(precios) / len(precios)
        actual = precios[-1]
        volumen_24h = float(market_client.get_24h_stats(par)["volValue"])
        spread = abs(actual - promedio) / promedio
        puntaje = 0
        if actual > promedio:
            puntaje += 1
        if spread < 0.02:
            puntaje += 1
        if volumen_24h > 500000:
            puntaje += 1

        # Mostrar análisis solo en consola
        logging.info(f"[ANÁLISIS] {par} | Puntaje: {puntaje} | Precio: {actual:.8f} | Promedio: {promedio:.8f} | Volumen: {volumen_24h:.2f} | Spread: {spread:.5f}")
        
        return {
            "puntaje": puntaje,
            "precio": actual,
            "volumen": volumen_24h
        }
    except Exception as e:
        logging.error(f"[Error] Analizando par {par}: {e}")
        return {"puntaje": 0, "precio": 0.0, "volumen": 0.0}

async def loop_operaciones():
    global bot_encendido, operaciones_activas
    while bot_encendido:
        if len(operaciones_activas) >= max_operaciones:
            await asyncio.sleep(5)
            continue

        saldo = await obtener_saldo_disponible()
        if saldo < min_orden_usdt:
            await asyncio.sleep(10)
            continue

        for par in pares:
            if len(operaciones_activas) >= max_operaciones:
                break

            analisis = analizar_par(par)
            if analisis["puntaje"] >= 2:
                monto_inversion = max(min(saldo * 0.1, max_orden_usdt), min_orden_usdt)
                if monto_inversion > saldo:
                    continue

                cantidad = round(monto_inversion / analisis["precio"], 2)
                try:
                    trade_client.create_market_order(symbol=par, side="buy", size=str(cantidad))
                    operacion = {
                        "par": par,
                        "entrada": analisis["precio"],
                        "cantidad": cantidad,
                        "ganancia": 0.0,
                        "actual": analisis["precio"]
                    }
                    operaciones_activas.append(operacion)
                    await bot.send_message(
                        CHAT_ID,
                        f"✅ *COMPRA EJECUTADA*\nPar: `{par}`\nEntrada: `{analisis['precio']:.6f}`\nCantidad: `{cantidad}`"
                    )
                    asyncio.create_task(monitorear_salida(operacion))
                except Exception as e:
                    logging.error(f"[Error] Ejecutando orden en {par}: {e}")
        await asyncio.sleep(5)

async def monitorear_salida(operacion):
    global operaciones_activas, historial_operaciones
    entrada = operacion["entrada"]
    cantidad = operacion["cantidad"]
    par = operacion["par"]
    max_precio = entrada

    while True:
        try:
            actual = float(market_client.get_ticker(par)["price"])
            max_precio = max(max_precio, actual)
            variacion = (actual - entrada) / entrada
            trailing_stop_pct = trailing_stop_base + min(variacion / 2, 0.05)
            ganancia = (actual - entrada) * cantidad
            operacion["actual"] = actual
            operacion["ganancia"] = ganancia

            if variacion >= ganancia_objetivo or ((actual - max_precio) / max_precio) <= trailing_stop_pct:
                trade_client.create_market_order(symbol=par, side="sell", size=str(cantidad))
                operaciones_activas.remove(operacion)
                resultado = "✅ GANADA" if ganancia >= 0 else "❌ PERDIDA"
                saldo_actual = await obtener_saldo_disponible()
                historial_operaciones.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "par": par,
                    "ganancia": ganancia,
                    "resultado": resultado,
                    "saldo": saldo_actual
                })
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 *VENTA EJECUTADA*\nPar: `{par}`\nSalida: `{actual:.6f}`\nGanancia: `{ganancia:.4f} USDT`\nResultado: {resultado}"
                )
                break
        except Exception as e:
            logging.error(f"[Error] Monitoreando salida de {par}: {e}")
        await asyncio.sleep(4)

# Función de resumen diario y cierre
async def resumen_diario_y_reset():
    global bot_encendido, operaciones_activas, historial_operaciones
    while True:
        ahora = datetime.now()
        mañana = ahora + timedelta(days=1)
        proximo_reset = datetime(mañana.year, mañana.month, mañana.day, 0, 0)
        espera = (proximo_reset - ahora).total_seconds()
        await asyncio.sleep(espera)

        if operaciones_activas:
            for op in list(operaciones_activas):
                try:
                    trade_client.create_market_order(symbol=op['par'], side="sell", size=str(op['cantidad']))
                    operaciones_activas.remove(op)
                    resultado = "✅ GANADA" if op["ganancia"] >= 0 else "❌ PERDIDA"
                    saldo_actual = await obtener_saldo_disponible()
                    historial_operaciones.append({
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "par": op["par"],
                        "ganancia": op["ganancia"],
                        "resultado": resultado,
                        "saldo": saldo_actual
                    })
                    await bot.send_message(
                        CHAT_ID,
                        f"🔴 *CIERRE FORZADO*\nPar: `{op['par']}`\nPrecio: `{op['actual']:.6f}`\nGanancia: `{op['ganancia']:.4f} USDT`\nResultado: {resultado}"
                    )
                except Exception as e:
                    logging.error(f"[Error] Cierre forzado: {e}")

        if historial_operaciones:
            mensaje = "📊 *Resumen Diario Zafrobot*\n\n"
            total = 0
            for h in historial_operaciones:
                total += h["ganancia"]
                mensaje += (
                    f"{h['fecha']} | {h['par']} | {h['resultado']} | "
                    f"{h['ganancia']:.4f} USDT | Saldo: {h['saldo']:.2f}\n"
                )
            mensaje += f"\n🧮 *Ganancia Total del Día:* `{total:.4f} USDT`"
            await bot.send_message(CHAT_ID, mensaje)

        historial_operaciones.clear()
        operaciones_activas.clear()
        bot_encendido = True
        logging.info("Nuevo ciclo diario iniciado.")

# Inicio
async def main():
    logging.basicConfig(level=logging.INFO)
    asyncio.create_task(resumen_diario_y_reset())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())