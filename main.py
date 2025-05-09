# --- ZAFROBOT SCALPER IMPULSO PRO V2 ---
import os
import logging
import asyncio
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from kucoin.client import Market, Trade, User

# Configurar logs visibles en consola
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

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

# Configuración de trading
pares = [
    "SHIB-USDT", "PEPE-USDT", "DOGE-USDT", "TRUMP-USDT", "SUI-USDT",
    "FLOKI-USDT", "BONK-USDT", "WIF-USDT", "XMR-USDT", "HYPE-USDT",
    "HYPER-USDT", "OM-USDT", "ENA-USDT", "KAS-USDT", "TURBO-USDT"
]
step_size = {p: 0.01 for p in pares}
uso_total = 0.80
max_ops = 3
espera_reentrada = 600
ganancia_objetivo = 0.007
trailing_stop = -0.008
min_usdt = 2.5

# Variables de estado
bot_activo = False
ops_activas = []
historial = []
lock = asyncio.Lock()
ultimos = {}

# Botones Telegram
teclado = ReplyKeyboardMarkup(
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
    await message.answer("✅ Bienvenido al ZafroBot Impulso Pro V2", reply_markup=teclado)

@dp.message()
async def comandos(message: types.Message):
    global bot_activo
    if message.text == "🚀 Encender Bot":
        if not bot_activo:
            bot_activo = True
            await message.answer("✅ Bot encendido.")
            asyncio.create_task(ciclo())
        else:
            await message.answer("⚠️ Ya está encendido.")
    elif message.text == "⛔ Apagar Bot":
        bot_activo = False
        await message.answer("⛔ Bot apagado.")
    elif message.text == "💰 Saldo":
        saldo = await obtener_saldo()
        await message.answer(f"💰 Saldo disponible: `{saldo:.2f}` USDT")
    elif message.text == "📊 Estado Bot":
        estado = "ENCENDIDO ✅" if bot_activo else "APAGADO ⛔"
        await message.answer(f"📊 Estado actual: {estado}")
    elif message.text == "📈 Ordenes Activas":
        if ops_activas:
            msg = ""
            for op in ops_activas:
                msg += (
                    f"Par: {op['par']}\nEntrada: {op['entrada']:.6f}\n"
                    f"Actual: {op['actual']:.6f}\nGanancia: {op['ganancia']:.4f} USDT\n\n"
                )
            await message.answer(msg)
        else:
            await message.answer("⚠️ No hay órdenes activas.")
    elif message.text == "🧾 Historial":
        if historial:
            msg = "*Últimas operaciones:*\n\n"
            for h in historial[-10:]:
                msg += (
                    f"{h['fecha']} | {h['par']} | {h['resultado']} | "
                    f"{h['ganancia']:.4f} | Saldo: {h['saldo']:.2f}\n"
                )
            await message.answer(msg)
        else:
            await message.answer("⚠️ Historial vacío.")

async def obtener_saldo():
    try:
        cuentas = user.get_account_list()
        return next((float(x["available"]) for x in cuentas if x["currency"] == "USDT"), 0.0)
    except Exception as e:
        logging.error(f"[Saldo] Error: {e}")
        return 0.0

def corregir_cantidad(monto, precio, par):
    step = Decimal(str(step_size.get(par, 0.0001)))
    cantidad = Decimal(str(monto)) / Decimal(str(precio))
    cantidad_corr = (cantidad // step) * step
    return str(cantidad_corr.quantize(step, rounding=ROUND_DOWN))

def analizar(par):
    try:
        velas = market.get_kline(symbol=par, kline_type="1min", limit=4)
        precios = [float(v[2]) for v in velas]
        ultimo = precios[-1]
        impulso = all(precios[i] > precios[i-1] for i in range(1, 4))
        spread = abs(ultimo - sum(precios)/len(precios)) / (sum(precios)/len(precios))
        volumen = float(market.get_24h_stats(par)["volValue"])
        if impulso and spread < 0.02 and volumen > 500000:
            logging.info(f"[Análisis] {par} | Impulso 3 velas | Precio: {ultimo:.6f} | Vol: {volumen:.0f}")
            return {"par": par, "precio": ultimo, "valido": True}
    except Exception as e:
        logging.error(f"[Análisis] {par} Error: {e}")
    return {"valido": False}

async def ciclo():
    await asyncio.sleep(4)
    while bot_activo:
        async with lock:
            if len(ops_activas) >= max_ops:
                await asyncio.sleep(4)
                continue
            saldo = await obtener_saldo()
            monto = (saldo * uso_total) / max_ops
            for par in pares:
                if par in [x["par"] for x in ops_activas]: continue
                if par in ultimos and (datetime.now() - ultimos[par]).total_seconds() < espera_reentrada: continue
                analisis = analizar(par)
                if not analisis["valido"]: continue
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
                    ops_activas.append(op)
                    logging.info(f"[COMPRA] {par} | {analisis['precio']:.6f} | {cantidad}")
                    await bot.send_message(CHAT_ID, f"✅ *COMPRA*\nPar: `{par}`\nEntrada: `{analisis['precio']:.6f}`")
                    asyncio.create_task(monitorear(op))
                    break
                except Exception as e:
                    logging.error(f"[Compra] {par}: {e}")
        await asyncio.sleep(3)

async def monitorear(op):
    global ops_activas, historial
    entrada = op["entrada"]
    cantidad = op["cantidad"]
    par = op["par"]
    max_precio = entrada

    while True:
        try:
            actual = float(market.get_ticker(par)["price"])
            max_precio = max(max_precio, actual)
            variacion = (actual - entrada) / entrada
            ganancia = (actual - entrada) * cantidad
            op.update({"actual": actual, "ganancia": ganancia})
            stop = max(trailing_stop, -0.004)

            if variacion >= ganancia_objetivo or ((actual - max_precio) / max_precio) <= stop:
                trade.create_market_order(symbol=par, side="sell", size=str(cantidad))
                ops_activas.remove(op)
                ultimos[par] = datetime.now()
                resultado = "✅ GANADA" if ganancia > 0 else "❌ PERDIDA"
                saldo = await obtener_saldo()
                historial.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "par": par,
                    "ganancia": ganancia,
                    "resultado": resultado,
                    "saldo": saldo
                })
                logging.info(f"[VENTA] {par} | {actual:.6f} | {ganancia:.4f} | {resultado}")
                await bot.send_message(
                    CHAT_ID,
                    f"🔴 *VENTA*\nPar: `{par}`\nSalida: `{actual:.6f}`\nGanancia: `{ganancia:.4f}` {resultado}"
                )
                break
        except Exception as e:
            logging.error(f"[Monitoreo] {par}: {e}")
        await asyncio.sleep(3)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())