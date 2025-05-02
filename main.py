# --- ZAFROBOT SCALPER MICRO-PRO FINAL ---
import os
import logging
import asyncio
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from kucoin.client import Market, Trade, User
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

# Variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASS = os.getenv("API_PASSPHRASE")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicialización
bot = Bot(token=TOKEN, parse_mode="Markdown")
dp = Dispatcher()
market = Market()
trade = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASS)
user = User(API_KEY, SECRET_KEY, API_PASS)

# Configuración
bot_encendido = False
max_operaciones = 3
trailing_stop = -0.008
min_usdt = 2.5
step_size = 0.0001
pares_analisis = []
operaciones_activas = []
lock = asyncio.Lock()

# Teclado
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="⛔ Apagar Bot")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="💰 Saldo Disponible")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Bienvenido al ZafroBot Scalper Micro-Pro", reply_markup=keyboard)

@dp.message()
async def comandos(message: types.Message):
    global bot_encendido
    if message.text == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido.")
            asyncio.create_task(ciclo_operativo())
        else:
            await message.answer("⚠️ El bot ya está encendido.")
    elif message.text == "⛔ Apagar Bot":
        bot_encendido = False
        await message.answer("⛔ Bot apagado.")
    elif message.text == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_encendido else "⛔ APAGADO"
        await message.answer(f"📊 Estado: {estado}")
    elif message.text == "💰 Saldo Disponible":
        saldo = await obtener_saldo()
        await message.answer(f"💰 Saldo disponible: {saldo:.2f} USDT")

async def obtener_saldo():
    try:
        cuentas = user.get_account_list()
        return next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
    except Exception as e:
        logging.error(f"Error obteniendo saldo: {e}")
        return 0.0

def redondear_cantidad(usdt, precio):
    cantidad = Decimal(str(usdt)) / Decimal(str(precio))
    cantidad = (cantidad // Decimal(str(step_size))) * Decimal(str(step_size))
    return str(cantidad.quantize(Decimal(str(step_size)), rounding=ROUND_DOWN))

def analizar_par(par):
    try:
        velas = market.get_kline(symbol=par, kline_type="1min", limit=3)
        precios = [float(x[2]) for x in velas]
        impulso = (precios[-1] - precios[-2]) / precios[-2]
        spread = abs(precios[-1] - sum(precios)/len(precios)) / sum(precios)/len(precios)
        vol = float(market.get_24h_stats(par)["volValue"])
        puntaje = (
            (impulso > 0.002)
            + (spread < 0.015)
            + (vol > 500000)
        )
        logging.info(f"[{par}] Impulso: {impulso:.4f} | Spread: {spread:.4f} | Vol: {vol:.2f} | Puntaje: {puntaje}")
        return {"par": par, "precio": precios[-1], "puntaje": puntaje}
    except Exception as e:
        logging.warning(f"Error analizando {par}: {e}")
        return {"par": par, "precio": 0, "puntaje": 0}

async def ciclo_operativo():
    await asyncio.sleep(5)
    while bot_encendido:
        async with lock:
            if len(operaciones_activas) < max_operaciones:
                saldo = await obtener_saldo()
                monto = (saldo * 0.80) / max_operaciones
                if monto < min_usdt:
                    await asyncio.sleep(10)
                    continue
                mejores = []
                for par in pares_analisis:
                    datos = analizar_par(par)
                    if datos["puntaje"] >= 2:
                        mejores.append(datos)
                    await asyncio.sleep(0.5)
                if mejores:
                    mejor = sorted(mejores, key=lambda x: x["puntaje"], reverse=True)[0]
                    await ejecutar_compra(mejor["par"], mejor["precio"], monto)
        await asyncio.sleep(5)

async def ejecutar_compra(par, precio, usdt):
    try:
        cantidad = redondear_cantidad(usdt, precio)
        trade.create_market_order(symbol=par, side="buy", size=cantidad)
        operacion = {
            "par": par,
            "entrada": float(precio),
            "cantidad": float(cantidad),
            "maximo": float(precio)
        }
        operaciones_activas.append(operacion)
        logging.info(f"[COMPRA] {par} a {precio:.6f} | Cant: {cantidad}")
        await bot.send_message(CHAT_ID, f"✅ COMPRA {par} | Precio: `{precio}`")
        asyncio.create_task(monitorear_salida(operacion))
    except Exception as e:
        logging.error(f"Error al comprar {par}: {e}")

async def monitorear_salida(operacion):
    try:
        while True:
            ticker = market.get_ticker(operacion["par"])
            actual = float(ticker["price"])
            operacion["maximo"] = max(operacion["maximo"], actual)
            variacion = (actual - operacion["entrada"]) / operacion["entrada"]
            retroceso = (actual - operacion["maximo"]) / operacion["maximo"]
            if variacion > 0 and retroceso <= trailing_stop:
                trade.create_market_order(symbol=operacion["par"], side="sell", size=str(operacion["cantidad"]))
                operaciones_activas.remove(operacion)
                ganancia = (actual - operacion["entrada"]) * operacion["cantidad"]
                logging.info(f"[VENTA] {operacion['par']} a {actual} | Ganancia: {ganancia:.4f}")
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 VENTA {operacion['par']} | Precio: `{actual}`\nGanancia: `{ganancia:.4f}`"
                )
                break
            await asyncio.sleep(3)
    except Exception as e:
        logging.error(f"Error monitoreando salida {operacion['par']}: {e}")

async def actualizar_pares():
    global pares_analisis
    while True:
        try:
            tickers = market.get_all_tickers()["ticker"]
            candidatos = [x["symbol"] for x in tickers if "-USDT" in x["symbol"]]
            top = sorted(candidatos, key=lambda s: float(market.get_24h_stats(s)["volValue"]), reverse=True)
            pares_analisis = top[:15]
            logging.info(f"[PARES] {pares_analisis}")
        except Exception as e:
            logging.error(f"Error actualizando pares: {e}")
        await asyncio.sleep(3600)

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    asyncio.create_task(actualizar_pares())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())