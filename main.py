# --- ZAFROBOT SCALPER ULTRA PRO MICROGANANCIAS FINAL ---
import os
import logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
import asyncio
from datetime import datetime
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

bot = Bot(token=TOKEN, parse_mode="Markdown")
dp = Dispatcher()
market_client = Market()
trade_client = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)
user_client = User(API_KEY, SECRET_KEY, API_PASS)

# Configuración general
bot_encendido = False
operaciones_activas = []
historial_operaciones = []
ultimos_pares_operados = {}
lock_operaciones = asyncio.Lock()
pares = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT",
    "SUI-USDT", "TURBO-USDT", "BONK-USDT", "KAS-USDT", "WIF-USDT",
    "XMR-USDT", "HYPE-USDT", "HYPER-USDT", "OM-USDT", "ENA-USDT"
]

tiempo_espera_reentrada = 600
max_operaciones = 3
uso_saldo_total = 0.80
trailing_stop_base = -0.008
ganancia_objetivo = 0.005
min_orden_usdt = 2.5

step_size_por_par = {
    "SUI-USDT": 0.1, "TRUMP-USDT": 0.01, "OM-USDT": 0.01, "ENA-USDT": 0.01,
    "HYPE-USDT": 0.01, "HYPER-USDT": 0.01, "BONK-USDT": 0.01, "TURBO-USDT": 0.01
}

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="⛔ Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Ordenes Activas")],
        [KeyboardButton(text="🧾 Historial")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Bot activo. Usa los botones para controlarlo.", reply_markup=keyboard)

@dp.message()
async def comandos(message: types.Message):
    global bot_encendido
    if message.text == "💰 Saldo":
        saldo = await obtener_saldo_disponible()
        await message.answer(f"💰 Saldo disponible: `{saldo:.2f}` USDT")
    elif message.text == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido.")
            asyncio.create_task(ciclo_completo())
        else:
            await message.answer("⚠️ Ya está encendido.")
    elif message.text == "⛔ Apagar Bot":
        bot_encendido = False
        await message.answer("⛔ Bot apagado.")
    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_encendido else "⛔ APAGADO"
        await message.answer(f"📊 Estado: {estado}")
    elif message.text == "📈 Ordenes Activas":
        if operaciones_activas:
            mensaje = ""
            for op in operaciones_activas:
                mensaje += (
                    f"Par: {op['par']}\n"
                    f"Entrada: {op['entrada']:.6f}\n"
                    f"Actual: {op['actual']:.6f}\n"
                    f"Ganancia neta: {op['ganancia']:.4f} USDT\n\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ No hay operaciones activas.")
    elif message.text == "🧾 Historial":
        if historial_operaciones:
            mensaje = "*Últimas operaciones:*\n\n"
            for h in historial_operaciones[-10:]:
                mensaje += (
                    f"{h['fecha']} | {h['par']} | {h['resultado']} | "
                    f"{h['ganancia']:.4f} | Saldo: {h['saldo']:.2f}\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ Historial vacío.")

async def obtener_saldo_disponible():
    try:
        cuentas = user_client.get_account_list()
        return next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
    except Exception as e:
        logging.error(f"[Saldo] Error: {e}")
        return 0.0

def corregir_cantidad(orden_usdt, precio_token, par):
    step = Decimal(str(step_size_por_par.get(par, 0.0001)))
    cantidad = Decimal(str(orden_usdt)) / Decimal(str(precio_token))
    cantidad_corr = (cantidad // step) * step
    return str(cantidad_corr.quantize(step, rounding=ROUND_DOWN))

def analizar_par(par):
    try:
        velas = market_client.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(x[2]) for x in velas]
        ultimo = precios[-1]
        promedio = sum(precios) / len(precios)
        spread = abs(ultimo - promedio) / promedio
        volumen = float(market_client.get_24h_stats(par)["volValue"])
        impulso = (precios[-1] - precios[-2]) / precios[-2]
        if impulso > 0 and spread < 0.02 and volumen > 500000:
            logging.info(f"[Análisis] {par} | Precio: {ultimo:.6f} | Volumen: {volumen:.0f} | Impulso: {impulso:.4f}")
            return {"par": par, "precio": ultimo, "valido": True, "vol": volumen}
    except Exception as e:
        logging.error(f"[Análisis] {par} Error: {e}")
    return {"par": par, "valido": False}

async def ciclo_completo():
    global operaciones_activas
    await asyncio.sleep(4)
    while bot_encendido:
        async with lock_operaciones:
            if len(operaciones_activas) >= max_operaciones:
                await asyncio.sleep(4)
                continue

            saldo = await obtener_saldo_disponible()
            monto = (saldo * uso_saldo_total) / max_operaciones

            for par in pares:
                if par in [op["par"] for op in operaciones_activas]:
                    continue
                if par in ultimos_pares_operados and (datetime.now() - ultimos_pares_operados[par]).total_seconds() < tiempo_espera_reentrada:
                    continue

                analisis = analizar_par(par)
                if not analisis["valido"]:
                    continue

                cantidad = corregir_cantidad(monto, analisis["precio"], par)
                try:
                    trade_client.create_market_order(symbol=par, side="buy", size=cantidad)
                    op = {
                        "par": par,
                        "entrada": analisis["precio"],
                        "cantidad": float(cantidad),
                        "actual": analisis["precio"],
                        "ganancia": 0.0
                    }
                    operaciones_activas.append(op)
                    logging.info(f"[COMPRA] {par} | Entrada: {analisis['precio']:.6f} | Cantidad: {cantidad}")
                    await bot.send_message(CHAT_ID, f"✅ *Compra ejecutada*\nPar: `{par}`\nEntrada: `{analisis['precio']:.6f}`")
                    asyncio.create_task(monitorear(op))
                    break
                except Exception as e:
                    logging.error(f"[Compra] {par}: {e}")
        await asyncio.sleep(2)

async def monitorear(operacion):
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
            trailing = max(trailing_stop_base, -0.002)

            ganancia_bruta = (actual - entrada) * cantidad
            comision_total = entrada * cantidad * 0.0016  # 0.08% compra + 0.08% venta
            ganancia_neta = ganancia_bruta - comision_total
            operacion.update({"actual": actual, "ganancia": ganancia_neta})

            if variacion >= ganancia_objetivo or ((actual - max_precio) / max_precio) <= trailing:
                trade_client.create_market_order(symbol=par, side="sell", size=str(cantidad))
                operaciones_activas.remove(operacion)
                ultimos_pares_operados[par] = datetime.now()
                resultado = "✅ GANADA" if ganancia_neta >= 0 else "❌ PERDIDA"
                saldo_actual = await obtener_saldo_disponible()
                historial_operaciones.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "par": par,
                    "ganancia": ganancia_neta,
                    "resultado": resultado,
                    "saldo": saldo_actual
                })
                logging.info(f"[VENTA] {par} | Entrada: {entrada:.6f} | Salida: {actual:.6f} | Bruta: {ganancia_bruta:.4f} | Comisión: {comision_total:.4f} | Neta: {ganancia_neta:.4f}")
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 *VENTA EJECUTADA*\nPar: `{par}`\n"
                    f"Entrada: `{entrada:.6f}`\nSalida: `{actual:.6f}`\n"
                    f"Ganancia bruta: `{ganancia_bruta:.4f}`\n"
                    f"Comisiones: `-{comision_total:.4f}`\n"
                    f"Ganancia neta: `{ganancia_neta:.4f}` {resultado}"
                )
                break
        except Exception as e:
            logging.error(f"[Monitoreo] {par}: {e}")
        await asyncio.sleep(3)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())