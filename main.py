import os
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

# ---------------------- CONFIG INICIAL ----------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scalper.log")
    ]
)
logger = logging.getLogger("ZafroBot")

# Entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

market = Market(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
trade = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
user = User(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

PARES = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT",
    "SUI-USDT", "TURBO-USDT", "BONK-USDT", "KAS-USDT", "WIF-USDT",
    "ADA-USDT", "AVAX-USDT", "XRP-USDT", "MATIC-USDT", "OP-USDT"
]

PARES_CONFIG = {
    "SHIB-USDT": {"inc": 1000, "min": 100000},
    "PEPE-USDT": {"inc": 100, "min": 10000},
    "FLOKI-USDT": {"inc": 100, "min": 10000},
    "DOGE-USDT": {"inc": 1, "min": 10},
    "TRUMP-USDT": {"inc": 1, "min": 1},
    "SUI-USDT": {"inc": 0.01, "min": 0.1},
    "TURBO-USDT": {"inc": 100, "min": 10000},
    "BONK-USDT": {"inc": 1000, "min": 100000},
    "KAS-USDT": {"inc": 0.001, "min": 0.1},
    "WIF-USDT": {"inc": 0.0001, "min": 0.01},
    "ADA-USDT": {"inc": 0.1, "min": 10},
    "AVAX-USDT": {"inc": 0.001, "min": 0.1},
    "XRP-USDT": {"inc": 0.1, "min": 10},
    "MATIC-USDT": {"inc": 0.1, "min": 10},
    "OP-USDT": {"inc": 0.01, "min": 1}
}

CONFIG = {
    "uso_saldo": 0.80,
    "max_operaciones": 3,
    "puntaje_minimo": 2.5,
    "reanalisis_segundos": 8
}

operaciones_activas = []
bot_activo = False
lock = asyncio.Lock()

# ---------------------- FUNCIONES BASE ----------------------
async def obtener_saldo():
    try:
        cuentas = user.get_account_list()
        usdt = next(c for c in cuentas if c["currency"] == "USDT" and c["type"] == "trade")
        return float(usdt["balance"])
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        return 0.0

async def analizar_impulso(par):
    try:
        velas = market.get_kline(symbol=par, kline_type="1min", limit=4)
        precios = [float(v[2]) for v in velas]
        volumen = float(market.get_24h_stats(par)["volValue"])
        spread = abs(precios[-1] - precios[0]) / precios[0]
        velas_positivas = sum(1 for i in range(1, len(precios)) if precios[i] > precios[i - 1])
        impulso = (velas_positivas / 3)
        momentum = (precios[-1] - precios[-2]) / precios[-2]
        puntaje = impulso + momentum + (volumen / 1_000_000) + (spread * 10)
        logger.info(f"[{par}] Puntuación: {puntaje:.2f} | Impulso: {impulso:.2f} | Spread: {spread:.4f} | Volumen: {volumen:.0f}")
        return {"par": par, "precio": precios[-1], "puntaje": puntaje}
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def ejecutar_compra(par, precio, monto_usdt):
    try:
        inc = Decimal(str(PARES_CONFIG[par]["inc"]))
        minsize = Decimal(str(PARES_CONFIG[par]["min"]))
        size = Decimal(monto_usdt) / Decimal(precio)
        size = (size // inc) * inc
        if size < minsize:
            raise Exception(f"Mínimo no alcanzado: {minsize} {par}")
        trade.create_market_order(par, "buy", size=str(size))
        logger.info(f"COMPRA {par} {size:.4f} @ {precio:.4f}")
        await bot.send_message(CHAT_ID, f"🟢 COMPRA: {par}\nPrecio: {precio:.4f}\nMonto: {monto_usdt:.2f} USDT")
        op = {
            "par": par,
            "entrada": float(precio),
            "cantidad": float(size),
            "maximo": float(precio),
            "entrada_dt": datetime.now()
        }
        operaciones_activas.append(op)
        asyncio.create_task(trailing_stop(op))
    except Exception as e:
        logger.error(f"Error en compra {par}: {e}")
        await bot.send_message(CHAT_ID, f"❌ ERROR en compra {par}:\n{e}")

async def trailing_stop(op):
    await asyncio.sleep(60)
    while bot_activo and op in operaciones_activas:
        try:
            ticker = market.get_ticker(op["par"])
            precio_actual = float(ticker["price"])
            if precio_actual > op["maximo"]:
                op["maximo"] = precio_actual
            ganancia_pct = (precio_actual - op["entrada"]) / op["entrada"]
            retroceso_pct = (precio_actual - op["maximo"]) / op["maximo"]
            if ganancia_pct >= 0.018 and retroceso_pct <= -0.01:
                await ejecutar_venta(op, precio_actual)
                break
            elif ganancia_pct >= 0.012 and retroceso_pct <= -0.006:
                await ejecutar_venta(op, precio_actual)
                break
            elif ganancia_pct >= 0.009 and retroceso_pct <= -0.004:
                await ejecutar_venta(op, precio_actual)
                break
            elif ganancia_pct >= 0.006 and retroceso_pct <= -0.0025:
                await ejecutar_venta(op, precio_actual)
                break
            elif ganancia_pct >= 0.0035 and retroceso_pct <= -0.0015:
                await ejecutar_venta(op, precio_actual)
                break
            if datetime.now() - op["entrada_dt"] > timedelta(minutes=4):
                await ejecutar_venta(op, precio_actual)
                break
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Error en trailing stop de {op['par']}: {e}")
            await asyncio.sleep(5)

async def ejecutar_venta(op, precio_venta):
    try:
        trade.create_market_order(symbol=op["par"], side="sell", size=str(op["cantidad"]))
        ganancia = (precio_venta - op["entrada"]) * op["cantidad"]
        porcentaje = ((precio_venta - op["entrada"]) / op["entrada"]) * 100
        logger.info(f"VENTA {op['par']} @ {precio_venta:.4f} | GANANCIA: {ganancia:.4f} USD ({porcentaje:.2f}%)")
        await bot.send_message(CHAT_ID, f"🔴 VENTA: {op['par']}\nPrecio: {precio_venta:.4f}\nGanancia: {ganancia:.4f} USD\nRentabilidad: {porcentaje:.2f}%")
        operaciones_activas.remove(op)
    except Exception as e:
        logger.error(f"Error al vender {op['par']}: {e}")
        await bot.send_message(CHAT_ID, f"❌ ERROR al vender {op['par']}:\n{e}")

# ---------------------- CICLO PRINCIPAL ----------------------
async def ciclo_trading():
    await asyncio.sleep(60)
    while bot_activo:
        try:
            async with lock:
                if len(operaciones_activas) >= CONFIG["max_operaciones"]:
                    await asyncio.sleep(CONFIG["reanalisis_segundos"])
                    continue
                saldo = await obtener_saldo()
                if saldo <= 0:
                    logger.warning("Saldo insuficiente")
                    await asyncio.sleep(10)
                    continue
                monto = (saldo * CONFIG["uso_saldo"]) / CONFIG["max_operaciones"]
                logger.info(f"Saldo: {saldo:.2f} USDT | Monto por operación: {monto:.2f}")
                for par in PARES:
                    if not bot_activo or any(op["par"] == par for op in operaciones_activas):
                        continue
                    analisis = await analizar_impulso(par)
                    if not analisis or analisis["puntaje"] < CONFIG["puntaje_minimo"]:
                        continue
                    await ejecutar_compra(par, analisis["precio"], monto)
                    await asyncio.sleep(3)
                    break
            await asyncio.sleep(CONFIG["reanalisis_segundos"])
        except Exception as e:
            logger.error(f"Error en ciclo: {e}")
            await asyncio.sleep(5)

# ---------------------- TELEGRAM ----------------------
def crear_teclado():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="⛔ Apagar Bot")],
        [KeyboardButton(text="💰 Saldo")],
        [KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Operaciones")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    await msg.answer("🤖 Bot ZafroBot Scalper listo", reply_markup=crear_teclado())

@dp.message()
async def comandos(msg: types.Message):
    global bot_activo
    if msg.text == "🚀 Encender Bot":
        if not bot_activo:
            bot_activo = True
            asyncio.create_task(ciclo_trading())
            await msg.answer("✅ Bot activado")
        else:
            await msg.answer("Ya está activo")
    elif msg.text == "⛔ Apagar Bot":
        bot_activo = False
        await msg.answer("🔴 Bot apagado")
    elif msg.text == "💰 Saldo":
        saldo = await obtener_saldo()
        await msg.answer(f"💵 Saldo disponible: {saldo:.2f} USDT")
    elif msg.text == "📊 Estado Bot":
        estado = "🟢 ACTIVO" if bot_activo else "🔴 INACTIVO"
        await msg.answer(f"{estado} | Operaciones: {len(operaciones_activas)}")
    elif msg.text == "📈 Operaciones":
        if not operaciones_activas:
            await msg.answer("Sin operaciones activas")
        else:
            texto = "📊 Operaciones activas:\n\n"
            for op in operaciones_activas:
                texto += (
                    f"{op['par']}\nEntrada: {op['entrada']:.4f}\n"
                    f"Máximo: {op['maximo']:.4f}\nCantidad: {op['cantidad']:.4f}\n\n"
                )
            await msg.answer(texto)

# ---------------------- INICIO ----------------------
async def iniciar_bot():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logger.info("ZafroBot Scalper Impulso Pro V2 iniciado")
    try:
        asyncio.run(iniciar_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")