import os
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Market, Trade, User

# Configurar logs
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASS = os.getenv("API_PASSPHRASE")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN, parse_mode="Markdown")
dp = Dispatcher()
market = Market()
trade = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)
user = User(API_KEY, SECRET_KEY, API_PASS)

# Variables de control
bot_activo = False
operaciones = []
historial = []
ultimos_pares = {}
lock = asyncio.Lock()

# Lista de pares a analizar
pares = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT",
    "SUI-USDT", "TURBO-USDT", "BONK-USDT", "KAS-USDT", "WIF-USDT",
    "XMR-USDT", "HYPE-USDT", "HYPER-USDT", "OM-USDT", "ENA-USDT"
]

# Configuración
uso_saldo = 0.80
max_ops = 3
espera_reentrada = 600
ganancia_obj = 0.004
trailing_stop = -0.007
min_orden = 2.5

step_size = {
    "SUI-USDT": 0.1, "TRUMP-USDT": 0.01, "OM-USDT": 0.01, "ENA-USDT": 0.01,
    "HYPE-USDT": 0.01, "HYPER-USDT": 0.01, "BONK-USDT": 0.01, "TURBO-USDT": 0.01
}

# Teclado Telegram
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
    await message.answer("✅ Bot operativo. Usa los botones para controlarlo.", reply_markup=keyboard)

@dp.message()
async def comandos(message: types.Message):
    global bot_activo
    if message.text == "🚀 Encender Bot":
        if not bot_activo:
            bot_activo = True
            await message.answer("✅ Bot encendido.")
            asyncio.create_task(ciclo())
        else:
            await message.answer("⚠️ El bot ya está encendido.")
    elif message.text == "⛔ Apagar Bot":
        bot_activo = False
        await message.answer("⛔ Bot apagado.")
    elif message.text == "💰 Saldo":
        saldo = await saldo_disponible()
        await message.answer(f"💰 Saldo disponible: `{saldo:.2f}` USDT")
    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_activo else "⛔ APAGADO"
        await message.answer(f"📊 Estado: {estado}")
    elif message.text == "📈 Ordenes Activas":
        if operaciones:
            mensaje = ""
            for op in operaciones:
                mensaje += (
                    f"Par: {op['par']}\n"
                    f"Entrada: {op['entrada']:.6f}\n"
                    f"Actual: {op['actual']:.6f}\n"
                    f"Ganancia: {op['ganancia']:.4f} USDT\n\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ No hay operaciones activas.")
    elif message.text == "🧾 Historial":
        if historial:
            mensaje = "*Últimas operaciones:*\n\n"
            for h in historial[-10:]:
                mensaje += (
                    f"{h['fecha']} | {h['par']} | {h['resultado']} | "
                    f"{h['ganancia']:.4f} | Saldo: {h['saldo']:.2f}\n"
                )
            await message.answer(mensaje)
        else:
            await message.answer("⚠️ Historial vacío.")

async def saldo_disponible():
    try:
        cuentas = user.get_account_list()
        return next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
    except Exception as e:
        logging.error(f"[Saldo] Error: {e}")
        return 0.0

def corregir_cantidad(usdt, precio, par):
    step = Decimal(str(step_size.get(par, 0.0001)))
    cantidad = Decimal(str(usdt)) / Decimal(str(precio))
    cantidad_corr = (cantidad // step) * step
    return str(cantidad_corr.quantize(step, rounding=ROUND_DOWN))

def analizar(par):
    try:
        velas = market.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(x[2]) for x in velas]
        ultimo = precios[-1]
        promedio = sum(precios) / len(precios)
        spread = abs(ultimo - promedio) / promedio
        volumen = float(market.get_24h_stats(par)["volValue"])
        impulso = (precios[-1] - precios[-2]) / precios[-2]
        if impulso > 0.001 and spread < 0.02 and volumen > 500000:
            logging.info(f"[Análisis] {par} | Precio: {ultimo:.6f} | Volumen: {volumen:.0f} | Impulso: {impulso:.4f}")
            return {"par": par, "precio": ultimo, "valido": True}
    except Exception as e:
        logging.error(f"[Análisis] {par}: {e}")
    return {"par": par, "valido": False}

async def ciclo():
    global operaciones
    await asyncio.sleep(5)
    while bot_activo:
        async with lock:
            if len(operaciones) >= max_ops:
                await asyncio.sleep(3)
                continue

            saldo = await saldo_disponible()
            monto = (saldo * uso_saldo) / max_ops

            for par in pares:
                if par in [o["par"] for o in operaciones]:
                    continue
                if par in ultimos_pares and (datetime.now() - ultimos_pares[par]).total_seconds() < espera_reentrada:
                    continue

                analisis = analizar(par)
                if not analisis["valido"]:
                    continue

                cantidad = corregir_cantidad(monto, analisis["precio"], par)
                try:
                    trade.create_market_order(symbol=par, side="buy", size=cantidad)
                    op = {
                        "par": par,
                        "entrada": analisis["precio"],
                        "cantidad": float(cantidad),
                        "actual": analisis["precio"],
                        "ganancia": 0.0
                    }
                    operaciones.append(op)
                    logging.info(f"[COMPRA] {par} | Entrada: {analisis['precio']:.6f} | Cantidad: {cantidad}")
                    await bot.send_message(CHAT_ID, f"✅ *Compra ejecutada*\nPar: `{par}`\nEntrada: `{analisis['precio']:.6f}`")
                    asyncio.create_task(monitorear(op))
                    break
                except Exception as e:
                    logging.error(f"[Error Compra] {par}: {e}")
        await asyncio.sleep(2)

async def monitorear(op):
    global operaciones, historial
    entrada = op["entrada"]
    cantidad = op["cantidad"]
    par = op["par"]
    max_precio = entrada

    while True:
        try:
            actual = float(market.get_ticker(par)["price"])
            max_precio = max(max_precio, actual)
            variacion = (actual - entrada) / entrada
            ganancia_bruta = (actual - entrada) * cantidad
            comision_aprox = entrada * cantidad * 0.002  # entrada + salida
            ganancia_neta = ganancia_bruta - comision_aprox
            op.update({"actual": actual, "ganancia": ganancia_neta})

            if variacion >= ganancia_obj or ((actual - max_precio) / max_precio) <= trailing_stop:
                trade.create_market_order(symbol=par, side="sell", size=str(cantidad))
                operaciones.remove(op)
                ultimos_pares[par] = datetime.now()
                resultado = "✅ GANADA" if ganancia_neta > 0 else "❌ PERDIDA"
                saldo_actual = await saldo_disponible()
                historial.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "par": par,
                    "ganancia": ganancia_neta,
                    "resultado": resultado,
                    "saldo": saldo_actual
                })
                logging.info(f"[VENTA] {par} | Salida: {actual:.6f} | Neta: {ganancia_neta:.4f}")
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 *VENTA EJECUTADA*\nPar: `{par}`\nSalida: `{actual:.6f}`\nGanancia: `{ganancia_neta:.4f}` {resultado}"
                )
                break
        except Exception as e:
            logging.error(f"[Monitoreo] {par}: {e}")
        await asyncio.sleep(3)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())