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

CONFIG = {
    "uso_saldo": 0.80,
    "max_operaciones": 3,
    "reanalisis_segundos": 8,
    "cooldown_por_par": 1800,
    "min_hold_time": 60,
    "breakout_timeout": 240
}

bot_activo = False
operaciones_activas = []
historial_operaciones = []
ultimos_usos = {}
lock = asyncio.Lock()
tiempo_activacion = None

# ---------------------- FUNCIONES AUXILIARES ----------------------
async def obtener_saldo():
    try:
        cuentas = user.get_account_list()
        usdt = next(c for c in cuentas if c["currency"] == "USDT" and c["type"] == "trade")
        return float(usdt["balance"])
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        return 0.0

async def analizar_par(par):
    try:
        velas = market.get_kline(symbol=par, kline_type="1min", limit=4)
        precios = [float(v[2]) for v in velas]
        volumen = float(market.get_24h_stats(par)["volValue"])
        spread = abs(precios[-1] - precios[0]) / precios[0]
        velas_verdes = sum(1 for i in range(1, len(precios)) if precios[i] > precios[i-1])
        impulso = velas_verdes / 3
        momentum = (precios[-1] - precios[-2]) / precios[-2]
        puntaje = impulso + momentum + (volumen / 1_000_000) + (spread * 10)
        logger.info(f"[{par}] Score: {puntaje:.2f} | Impulso: {impulso:.2f} | Volumen: {volumen:.0f} | Spread: {spread:.4f}")
        return {"par": par, "precio": precios[-1], "puntaje": puntaje}
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def ejecutar_compra(par, precio, monto):
    try:
        symbol_info = market.get_symbol_list()
        current = next(s for s in symbol_info if s["symbol"] == par)
        base_increment = float(current["baseIncrement"])
        min_size = float(current["baseMinSize"])
        size = Decimal(monto) / Decimal(precio)
        size = (size // Decimal(base_increment)) * Decimal(base_increment)
        if size < Decimal(min_size):
            raise Exception(f"Size menor al mínimo permitido: {min_size}")
        trade.create_market_order(par, "buy", size=str(size))
        logger.info(f"COMPRA {par} {size:.4f} @ {precio:.4f}")
        await bot.send_message(CHAT_ID, f"🟢 COMPRA: {par}\nPrecio: {precio:.4f}\nMonto: {monto:.2f} USDT")
        op = {
            "par": par,
            "entrada": float(precio),
            "cantidad": float(size),
            "maximo": float(precio),
            "inicio": datetime.utcnow()
        }
        operaciones_activas.append(op)
        ultimos_usos[par] = datetime.utcnow()
        asyncio.create_task(trailing_stop(op))
    except Exception as e:
        logger.error(f"Error en compra: {e}")
        await bot.send_message(CHAT_ID, f"❌ Error al comprar {par}:\n{e}")

async def trailing_stop(op):
    while bot_activo and op in operaciones_activas:
        try:
            await asyncio.sleep(3)
            ticker = market.get_ticker(op["par"])
            precio_actual = float(ticker["price"])
            if precio_actual > op["maximo"]:
                op["maximo"] = precio_actual

            tiempo_en_op = (datetime.utcnow() - op["inicio"]).total_seconds()
            ganancia_pct = (precio_actual - op["entrada"]) / op["entrada"]
            retroceso = (precio_actual - op["maximo"]) / op["maximo"]

            if tiempo_en_op >= CONFIG["breakout_timeout"] and ganancia_pct < 0.0035:
                await ejecutar_venta(op, precio_actual, forzado=True)
                break

            if tiempo_en_op < CONFIG["min_hold_time"]:
                continue

            escalas = [
                (0.018, -0.010),
                (0.012, -0.006),
                (0.009, -0.004),
                (0.006, -0.0025),
                (0.0035, -0.0015),
            ]
            for g, r in escalas:
                if ganancia_pct >= g and retroceso <= r:
                    await ejecutar_venta(op, precio_actual)
                    return

        except Exception as e:
            logger.error(f"Error en trailing de {op['par']}: {e}")

async def ejecutar_venta(op, precio_venta, forzado=False):
    try:
        trade.create_market_order(op["par"], "sell", size=str(op["cantidad"]))
        ganancia = (precio_venta - op["entrada"]) * op["cantidad"]
        pct = ((precio_venta - op["entrada"]) / op["entrada"]) * 100
        operaciones_activas.remove(op)
        historial_operaciones.append({
            "fecha": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            "par": op["par"],
            "ganancia": ganancia,
            "porcentaje": pct,
            "tipo": "Forzada" if forzado else "Normal"
        })
        logger.info(f"VENTA {op['par']} @ {precio_venta:.4f} | G: {ganancia:.4f} USD ({pct:.2f}%)")
        await bot.send_message(CHAT_ID, f"🔴 VENTA {op['par']} ({'⏱️' if forzado else '✅'})\n"
                                         f"Salida: {precio_venta:.4f}\n"
                                         f"Ganancia: {ganancia:.4f} USD\nRentabilidad: {pct:.2f}%")
    except Exception as e:
        logger.error(f"Error al vender: {e}")

async def ciclo_trading():
    global tiempo_activacion
    tiempo_activacion = datetime.utcnow()
    await bot.send_message(CHAT_ID, "⏳ Analizando el mercado antes de operar...")
    await asyncio.sleep(60)
    while bot_activo:
        try:
            async with lock:
                if len(operaciones_activas) >= CONFIG["max_operaciones"]:
                    await asyncio.sleep(CONFIG["reanalisis_segundos"])
                    continue
                saldo = await obtener_saldo()
                if saldo <= 5:
                    logger.warning("Saldo muy bajo")
                    await asyncio.sleep(10)
                    continue
                monto = (saldo * CONFIG["uso_saldo"]) / CONFIG["max_operaciones"]
                for par in PARES:
                    if any(op["par"] == par for op in operaciones_activas):
                        continue
                    if par in ultimos_usos:
                        delta = (datetime.utcnow() - ultimos_usos[par]).total_seconds()
                        if delta < CONFIG["cooldown_por_par"]:
                            continue
                    analisis = await analizar_par(par)
                    if analisis and analisis["puntaje"] >= 2.5:
                        await ejecutar_compra(par, analisis["precio"], monto)
                        await asyncio.sleep(3)
                        break
            await asyncio.sleep(CONFIG["reanalisis_segundos"])
        except Exception as e:
            logger.error(f"Error en ciclo: {e}")
            await asyncio.sleep(5)

# ---------------- TELEGRAM ----------------
def crear_teclado():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀 Encender Bot")],
        [KeyboardButton(text="⛔ Apagar Bot")],
        [KeyboardButton(text="💰 Saldo"), KeyboardButton(text="📊 Estado Bot")],
        [KeyboardButton(text="📈 Operaciones"), KeyboardButton(text="📜 Historial")]
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
        await msg.answer(f"{estado} | Operaciones activas: {len(operaciones_activas)}")
    elif msg.text == "📈 Operaciones":
        if not operaciones_activas:
            await msg.answer("No hay operaciones activas")
        else:
            texto = "📊 Operaciones activas:\n\n"
            for op in operaciones_activas:
                texto += (
                    f"{op['par']}\nEntrada: {op['entrada']:.4f}\n"
                    f"Máximo: {op['maximo']:.4f}\nCantidad: {op['cantidad']:.4f}\n\n"
                )
            await msg.answer(texto)
    elif msg.text == "📜 Historial":
        if not historial_operaciones:
            await msg.answer("Sin operaciones cerradas aún.")
        else:
            texto = "📜 HISTORIAL DE OPERACIONES\n\n"
            for op in historial_operaciones[-10:][::-1]:
                texto += (
                    f"⏰ {op['fecha']}\nPar: {op['par']}\n"
                    f"Resultado: {'✅ Ganancia' if op['ganancia'] > 0 else '❌ Pérdida'}\n"
                    f"{op['ganancia']:.2f} USDT ({op['porcentaje']:.2f}%)\n───────────────\n"
                )
            await msg.answer(texto)

async def iniciar_bot():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logger.info("ZafroBot Scalper Profesional Iniciado")
    try:
        asyncio.run(iniciar_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")