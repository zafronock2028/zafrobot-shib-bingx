# --- ZAFROBOT SCALPER V1 ULTRA CONSERVADOR FINALIZADO ---

import os
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Market, Trade, User

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASS = os.getenv("API_PASSPHRASE")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicialización
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
pares = []
lock_operaciones = asyncio.Lock()
tiempo_espera_reentrada = 600
max_operaciones = 2
ganancia_objetivo = 0.015
trailing_stop_base = -0.04
min_orden_usdt = 2.5# Tamaños mínimos por par
step_size_por_par = {
    "SUI-USDT": 0.1, "TRUMP-USDT": 0.01, "OM-USDT": 0.01, "ENA-USDT": 0.01,
    "HYPE-USDT": 0.01, "HYPER-USDT": 0.01, "BONK-USDT": 0.01, "TURBO-USDT": 0.01
}

# Teclado del bot
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
    await message.answer("✅ ¡Bienvenido al ZafroBot Scalper V1 Ultra Conservador!", reply_markup=keyboard)

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
            asyncio.create_task(ciclo_completo())
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
                    f"Entrada: {op['entrada']:.6f}\n"
                    f"Actual: {op['actual']:.6f}\n"
                    f"Ganancia: {op['ganancia']:.6f} ({estado})\n\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ No hay operaciones activas.")
    elif message.text == "🧾 Historial de Ganancias":
        if historial_operaciones:
            mensaje = "🧾 *Últimas ganancias:*\n\n"
            for h in historial_operaciones[-10:]:
                mensaje += (
                    f"{h['fecha']} | {h['par']} | {h['resultado']} | "
                    f"{h['ganancia']:.4f} | Saldo: {h['saldo']:.2f}\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ Aún no hay historial.")# Obtener saldo disponible
async def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        return next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
    except Exception as e:
        logging.error(f"[Error] Obteniendo saldo: {e}")
        return 0.0

# Calcular porcentaje de uso por operación
def calcular_porcentaje_saldo(saldo):
    return 0.75 / max_operaciones

# Corregir cantidad según el step_size
def corregir_cantidad(orden_usdt, precio_token, par):
    step = Decimal(str(step_size_por_par.get(par, 0.0001)))
    cantidad = Decimal(str(orden_usdt)) / Decimal(str(precio_token))
    cantidad_corr = (cantidad // step) * step
    return str(cantidad_corr.quantize(step, rounding=ROUND_DOWN))

# Análisis técnico simple del par
def analizar_par(par):
    try:
        velas = market_client.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(x[2]) for x in velas]
        ultimo = precios[-1]
        penultimo = precios[-2]
        impulso = (ultimo - penultimo) / penultimo
        promedio = sum(precios) / len(precios)
        volumen_24h = float(market_client.get_24h_stats(par)["volValue"])
        spread = abs(ultimo - promedio) / promedio
        puntaje = (
            (ultimo > promedio)
            + (spread < 0.02)
            + (volumen_24h > 800000)
            + (impulso > 0.002)
        )
        logging.info(f"[Análisis] {par} | Precio: {ultimo:.6f} | Puntaje: {puntaje} | Impulso: {impulso:.4f} | Vol24h: {volumen_24h:.2f}")
        return {"par": par, "puntaje": puntaje, "precio": ultimo, "volumen": volumen_24h}
    except Exception as e:
        logging.error(f"[Error] Análisis en {par}: {e}")
        return {"par": par, "puntaje": 0, "precio": 0, "volumen": 0}

# Actualizar pares top
async def actualizar_pares_rentables():
    global pares
    try:
        tickers = market_client.get_all_tickers()["ticker"]
        candidatos = [t["symbol"] for t in tickers if "-USDT" in t["symbol"]]
        top = sorted(candidatos, key=lambda s: float(market_client.get_24h_stats(s)["volValue"]), reverse=True)
        pares = top[:15]
        logging.info(f"[Actualización de pares] {pares}")
    except Exception as e:
        logging.error(f"[Error] Actualizando pares: {e}")

# Ciclo principal de escaneo y operación
async def ciclo_completo():
    global bot_encendido, operaciones_activas
    await asyncio.sleep(10)
    while bot_encendido:
        async with lock_operaciones:
            if len(operaciones_activas) >= max_operaciones:
                await asyncio.sleep(10)
                continue

            saldo = await obtener_saldo_disponible()
            if saldo < min_orden_usdt:
                await asyncio.sleep(15)
                continue

            await actualizar_pares_rentables()
            mejores = []
            for _ in range(6):
                resultados = [
                    analizar_par(p) for p in pares
                    if p not in [op["par"] for op in operaciones_activas]
                ]
                mejores.extend([r for r in resultados if r["puntaje"] >= 3])
                await asyncio.sleep(1)

            if not mejores:
                logging.info("[Análisis] No se encontraron oportunidades.")
                await asyncio.sleep(10)
                continue

            mejores = sorted(mejores, key=lambda x: x["volumen"] * x["puntaje"], reverse=True)
            disponibles = [
                m for m in mejores
                if m["par"] not in ultimos_pares_operados or
                (datetime.now() - ultimos_pares_operados[m["par"]]).total_seconds() >= tiempo_espera_reentrada
            ]

            for analisis in disponibles:
                if analisis["par"] not in [op["par"] for op in operaciones_activas]:
                    await ejecutar_compra(analisis)
                    break

        await asyncio.sleep(5)

# Ejecutar compra
async def ejecutar_compra(analisis):
    global operaciones_activas
    saldo = await obtener_saldo_disponible()
    porcentaje = calcular_porcentaje_saldo(saldo)
    monto = max(saldo * porcentaje, min_orden_usdt)
    if monto > saldo:
        return
    cantidad = corregir_cantidad(monto, analisis["precio"], analisis["par"])
    try:
        trade_client.create_market_order(symbol=analisis["par"], side="buy", size=cantidad)
        op = {
            "par": analisis["par"],
            "entrada": analisis["precio"],
            "cantidad": float(cantidad),
            "ganancia": 0.0,
            "actual": analisis["precio"]
        }
        operaciones_activas.append(op)
        logging.info(f"[COMPRA] {analisis['par']} a {analisis['precio']:.6f} | Cantidad: {cantidad}")
        await bot.send_message(
            CHAT_ID,
            f"✅ *COMPRA REALIZADA*\nPar: `{analisis['par']}`\nPrecio: `{analisis['precio']:.6f}`\nCantidad: `{cantidad}`"
        )
        asyncio.create_task(monitorear_salida(op))
    except Exception as e:
        logging.error(f"[Error] Compra en {analisis['par']}: {e}")

# Monitorear operación
async def monitorear_salida(operacion):
    global operaciones_activas, historial_operaciones
    entrada, cantidad, par = operacion["entrada"], operacion["cantidad"], operacion["par"]
    max_precio = entrada
    while True:
        try:
            actual = float(market_client.get_ticker(par)["price"])
            max_precio = max(max_precio, actual)
            variacion = (actual - entrada) / entrada
            trailing_stop = max(-0.02, trailing_stop_base + min(variacion / (1.5 if variacion >= ganancia_objetivo else 2), 0.04))
            ganancia = (actual - entrada) * cantidad
            operacion.update({"actual": actual, "ganancia": ganancia})

            if variacion >= ganancia_objetivo or ((actual - max_precio) / max_precio) <= trailing_stop:
                trade_client.create_market_order(symbol=par, side="sell", size=str(cantidad))
                operaciones_activas.remove(operacion)
                ultimos_pares_operados[par] = datetime.now()
                resultado = "✅ GANADA" if ganancia >= 0 else "❌ PERDIDA"
                saldo_actual = await obtener_saldo_disponible()
                historial_operaciones.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "par": par,
                    "ganancia": ganancia,
                    "resultado": resultado,
                    "saldo": saldo_actual
                })
                logging.info(f"[VENTA] {par} | Precio: {actual:.6f} | Ganancia: {ganancia:.4f}")
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 *VENTA EJECUTADA*\nPar: `{par}`\nPrecio: `{actual:.6f}`\nGanancia: `{ganancia:.4f}`\n{resultado}"
                )
                break
        except Exception as e:
            logging.error(f"[Error] Monitoreando {par}: {e}")
        await asyncio.sleep(4)

# Resumen diario automático
async def resumen_diario_y_reset():
    global operaciones_activas, historial_operaciones, bot_encendido
    while True:
        ahora = datetime.now()
        mañana = ahora + timedelta(days=1)
        espera = (datetime(mañana.year, mañana.month, mañana.day) - ahora).total_seconds()
        await asyncio.sleep(espera)

        for op in list(operaciones_activas):
            try:
                trade_client.create_market_order(symbol=op['par'], side="sell", size=str(op['cantidad']))
                operaciones_activas.remove(op)
                ultimos_pares_operados[op['par']] = datetime.now()
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
                    f"🔴 *CIERRE DIARIO*\nPar: `{op['par']}`\nGanancia: `{op['ganancia']:.4f}`"
                )
            except Exception as e:
                logging.error(f"[Error] Cierre: {e}")

        if historial_operaciones:
            total = sum(h["ganancia"] for h in historial_operaciones)
            resumen = "📊 *Resumen Diario*\n\n" + "\n".join(
                f"{h['fecha']} | {h['par']} | {h['resultado']} | {h['ganancia']:.4f} | Saldo: {h['saldo']:.2f}"
                for h in historial_operaciones
            ) + f"\n\n🧮 Total del día: `{total:.4f} USDT`"
            await bot.send_message(CHAT_ID, resumen)

        historial_operaciones.clear()
        operaciones_activas.clear()
        await actualizar_pares_rentables()
        bot_encendido = True

# Arranque del bot
async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    asyncio.create_task(resumen_diario_y_reset())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())