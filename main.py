import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

# Configuración inicial
load_dotenv()

# Logger profesional
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("KuCoinImpulsePro")

# Configuración de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Clientes KuCoin
market = Market(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
trade = Trade(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
user = User(key=API_KEY, secret=SECRET_KEY, passphrase=API_PASSPHRASE)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Pares y configuración
PARES = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT", "TRUMP-USDT",
    "SUI-USDT", "TURBO-USDT", "BONK-USDT", "KAS-USDT", "WIF-USDT",
    "ADA-USDT", "AVAX-USDT", "XRP-USDT", "MATIC-USDT", "OP-USDT"
]

PARES_CONFIG = {
    "SHIB-USDT": {"inc": 1000, "min": 100000, "volatilidad": 1.8},
    "PEPE-USDT": {"inc": 100, "min": 10000, "volatilidad": 2.0},
    "FLOKI-USDT": {"inc": 100, "min": 10000, "volatilidad": 1.9},
    "DOGE-USDT": {"inc": 1, "min": 10, "volatilidad": 1.5},
    "TRUMP-USDT": {"inc": 1, "min": 1, "volatilidad": 2.5},
    "SUI-USDT": {"inc": 0.01, "min": 0.1, "volatilidad": 1.3},
    "TURBO-USDT": {"inc": 100, "min": 10000, "volatilidad": 2.2},
    "BONK-USDT": {"inc": 1000, "min": 100000, "volatilidad": 2.1},
    "KAS-USDT": {"inc": 0.001, "min": 0.1, "volatilidad": 1.4},
    "WIF-USDT": {"inc": 0.0001, "min": 0.01, "volatilidad": 2.3},
    "ADA-USDT": {"inc": 0.1, "min": 10, "volatilidad": 1.2},
    "AVAX-USDT": {"inc": 0.001, "min": 0.1, "volatilidad": 1.3},
    "XRP-USDT": {"inc": 0.1, "min": 10, "volatilidad": 1.1},
    "MATIC-USDT": {"inc": 0.1, "min": 10, "volatilidad": 1.2},
    "OP-USDT": {"inc": 0.01, "min": 1, "volatilidad": 1.4}
}

CONFIG = {
    "uso_saldo": 0.80,
    "max_operaciones": 3,
    "puntaje_minimo": 2.5,
    "reanalisis_segundos": 8,
    "max_duracion_minutos": 6,
    "spread_maximo": 0.002  # 0.2%
}

# Variables globales
operaciones_activas = []
historial_operaciones = []
bot_activo = False
lock = asyncio.Lock()

# Cargar historial al iniciar
try:
    with open('historial_operaciones.json', 'r') as f:
        historial_operaciones = json.load(f)
except:
    historial_operaciones = []

async def guardar_historial():
    """Guarda el historial de operaciones en un archivo JSON"""
    try:
        with open('historial_operaciones.json', 'w') as f:
            json.dump(historial_operaciones, f, indent=2)
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

async def obtener_saldo():
    """Obtiene el saldo disponible en USDT"""
    try:
        cuentas = user.get_account_list()
        usdt = next(c for c in cuentas if c["currency"] == "USDT" and c["type"] == "trade")
        saldo = float(usdt["balance"])
        logger.info(f"Saldo obtenido: {saldo:.2f} USDT")
        return saldo
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        await bot.send_message(CHAT_ID, f"⚠️ Error obteniendo saldo: {e}")
        return 0.0

async def analizar_impulso(par):
    """Analiza el impulso del mercado para un par específico"""
    try:
        # Obtener datos de mercado
        velas = market.get_kline(symbol=par, kline_type="1min", limit=5)
        precios = [float(v[2]) for v in velas]  # Precios de cierre
        volumen_24h = float(market.get_24h_stats(par)["volValue"])
        spread_actual = (float(market.get_ticker(par)["bestAsk"]) - float(market.get_ticker(par)["bestBid"])) / float(market.get_ticker(par)["bestAsk"])
        
        # Análisis técnico mejorado
        velas_positivas = sum(1 for i in range(1, len(precios)) if precios[i] > precios[i-1] * 1.001)
        momentum_corto = (precios[-1] - precios[-2]) / precios[-2]
        momentum_largo = (precios[-1] - precios[-3]) / precios[-3]
        volatilidad = PARES_CONFIG[par].get("volatilidad", 1.5)
        
        # Cálculo de puntaje mejorado
        puntaje = (
            (velas_positivas * 0.4) + 
            (momentum_corto * 1.5) + 
            (momentum_largo * 1.0) + 
            (volumen_24h / 3_000_000) + 
            (volatilidad * 0.8) -
            (spread_actual * 500)  # Penaliza spreads altos
        )
        
        return {
            "par": par,
            "precio": precios[-1],
            "puntaje": puntaje,
            "volumen": volumen_24h,
            "momentum": momentum_corto,
            "spread": spread_actual
        }
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def ejecutar_compra(par, precio, monto_usdt):
    """Ejecuta una orden de compra con gestión de riesgo"""
    try:
        # Verificar spread primero
        ticker = market.get_ticker(par)
        spread = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
        if spread > CONFIG["spread_maximo"]:
            logger.warning(f"Spread alto {spread*100:.2f}% en {par}, omitiendo")
            return False

        # Calcular tamaño de orden
        inc = Decimal(str(PARES_CONFIG[par]["inc"]))
        minsize = Decimal(str(PARES_CONFIG[par]["min"]))
        size = (Decimal(monto_usdt) / Decimal(precio)).quantize(inc)
        
        if size < minsize:
            logger.warning(f"Tamaño {size} < mínimo {minsize} para {par}")
            return False

        # Ejecutar orden
        order = trade.create_market_order(par, "buy", size=str(size))
        order_id = order["orderId"]
        
        # Registrar operación
        op = {
            "id": order_id,
            "par": par,
            "entrada": float(precio),
            "cantidad": float(size),
            "maximo": float(precio),
            "entrada_dt": datetime.now().isoformat(),
            "monto_usdt": float(monto_usdt),
            "estado": "activa",
            "spread_inicial": spread
        }
        
        operaciones_activas.append(op)
        
        # Notificación detallada
        await bot.send_message(
            CHAT_ID,
            f"🟢 *COMPRA EJECUTADA* 🟢\n\n"
            f"• Par: `{par}`\n"
            f"• Precio: `{precio:.8f}`\n"
            f"• Monto: `{monto_usdt:.2f} USDT`\n"
            f"• Cantidad: `{float(size):.2f}`\n"
            f"• Spread inicial: `{spread*100:.2f}%`\n"
            f"• Hora: `{datetime.now().strftime('%H:%M:%S')}`\n\n"
            f"📊 _Iniciando trailing stop..._",
            parse_mode="Markdown"
        )
        
        # Iniciar trailing stop
        asyncio.create_task(trailing_stop(op))
        return True
        
    except Exception as e:
        logger.error(f"Error en compra {par}: {str(e)}")
        await bot.send_message(
            CHAT_ID,
            f"❌ *ERROR EN COMPRA* ❌\n\n"
            f"• Par: `{par}`\n"
            f"• Error: `{str(e)}`\n\n"
            f"_Reintentando en próximo ciclo..._",
            parse_mode="Markdown"
        )
        return False

async def trailing_stop(op):
    """Gestión profesional de trailing stop dinámico"""
    par = op["par"]
    entrada_dt = datetime.fromisoformat(op["entrada_dt"])
    max_duracion = timedelta(minutes=CONFIG["max_duracion_minutos"])
    volatilidad = PARES_CONFIG[par].get("volatilidad", 1.5)
    
    while bot_activo and op in operaciones_activas:
        try:
            # Verificar timeout
            if datetime.now() - entrada_dt > max_duracion:
                logger.info(f"Timeout alcanzado para {par}")
                await ejecutar_venta(op, "timeout")
                break
                
            # Obtener precio actual
            ticker = market.get_ticker(par)
            precio_actual = float(ticker["price"])
            
            # Actualizar máximo
            if precio_actual > op["maximo"]:
                op["maximo"] = precio_actual
            
            # Calcular métricas
            ganancia_pct = (precio_actual - op["entrada"]) / op["entrada"] * 100
            retroceso_pct = (op["maximo"] - precio_actual) / op["maximo"] * 100
            spread_actual = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
            
            # Condiciones de salida dinámicas
            if ganancia_pct >= 2.0 * volatilidad and retroceso_pct >= 1.0 * volatilidad:
                await ejecutar_venta(op, "take_profit_2x")
                break
            elif ganancia_pct >= 1.5 * volatilidad and retroceso_pct >= 0.8 * volatilidad:
                await ejecutar_venta(op, "take_profit_1.5x")
                break
            elif ganancia_pct >= 1.0 * volatilidad and retroceso_pct >= 0.5 * volatilidad:
                await ejecutar_venta(op, "take_profit_1x")
                break
            elif spread_actual > CONFIG["spread_maximo"] * 2:  # Spread se duplica
                await ejecutar_venta(op, "spread_alto")
                break
                
            await asyncio.sleep(3)
            
        except Exception as e:
            logger.error(f"Error en trailing stop {par}: {str(e)}")
            await asyncio.sleep(5)

async def ejecutar_venta(op, razon):
    """Ejecuta la venta y registra los resultados"""
    try:
        par = op["par"]
        ticker = market.get_ticker(par)
        precio_venta = float(ticker["price"])
        spread_actual = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
        
        # Ejecutar orden de venta
        trade.create_market_order(par, "sell", size=str(Decimal(str(op["cantidad"]))))
        
        # Calcular métricas
        ganancia_usdt = (precio_venta - op["entrada"]) * op["cantidad"]
        rentabilidad_pct = (precio_venta - op["entrada"]) / op["entrada"] * 100
        duracion = (datetime.now() - datetime.fromisoformat(op["entrada_dt"])).total_seconds() / 60
        
        # Actualizar operación
        op.update({
            "salida": precio_venta,
            "salida_dt": datetime.now().isoformat(),
            "ganancia_usdt": ganancia_usdt,
            "rentabilidad_pct": rentabilidad_pct,
            "duracion_min": duracion,
            "razon_salida": razon,
            "spread_final": spread_actual,
            "estado": "cerrada"
        })
        
        # Mover a historial
        operaciones_activas.remove(op)
        historial_operaciones.append(op)
        await guardar_historial()
        
        # Preparar mensaje
        razones = {
            "timeout": "⏰ Tiempo máximo alcanzado",
            "take_profit_1x": "🎯 Take Profit 1X",
            "take_profit_1.5x": "🎯 Take Profit 1.5X",
            "take_profit_2x": "🎯 Take Profit 2X",
            "spread_alto": "📉 Spread demasiado alto"
        }
        
        emoji = "🟢" if ganancia_usdt >= 0 else "🔴"
        mensaje = (
            f"{emoji} *VENTA EJECUTADA* {emoji}\n\n"
            f"• Par: `{par}`\n"
            f"• Entrada: `{op['entrada']:.8f}`\n"
            f"• Salida: `{precio_venta:.8f}`\n"
            f"• Cantidad: `{op['cantidad']:.2f}`\n"
            f"• Ganancia: `{ganancia_usdt:.4f} USDT`\n"
            f"• Rentabilidad: `{rentabilidad_pct:.2f}%`\n"
            f"• Duración: `{duracion:.1f} minutos`\n"
            f"• Razón: `{razones.get(razon, razon)}`\n"
            f"• Spread final: `{spread_actual*100:.2f}%`\n\n"
            f"📊 _Actualizando historial..._"
        )
        
        await bot.send_message(CHAT_ID, mensaje, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error vendiendo {op['par']}: {str(e)}")
        await bot.send_message(
            CHAT_ID,
            f"❌ *ERROR EN VENTA* ❌\n\n"
            f"• Par: `{op['par']}`\n"
            f"• Error: `{str(e)}`\n\n"
            f"⚠️ _Intentando nuevamente..._",
            parse_mode="Markdown"
        )

async def ciclo_trading():
    """Ciclo principal de trading"""
    await asyncio.sleep(60)  # Espera inicial para evitar operar al inicio
    
    while bot_activo:
        try:
            async with lock:
                # Verificar límite de operaciones
                if len(operaciones_activas) >= CONFIG["max_operaciones"]:
                    await asyncio.sleep(CONFIG["reanalisis_segundos"])
                    continue
                    
                # Obtener saldo
                saldo = await obtener_saldo()
                if saldo <= 10:  # Mínimo 10 USDT para operar
                    await bot.send_message(
                        CHAT_ID,
                        f"⚠️ *SALDO INSUFICIENTE*\n\n"
                        f"Saldo disponible: `{saldo:.2f} USDT`\n"
                        f"Mínimo requerido: `10.00 USDT`",
                        parse_mode="Markdown"
                    )
                    await asyncio.sleep(60)
                    continue
                    
                # Calcular monto por operación
                ops_disponibles = CONFIG["max_operaciones"] - len(operaciones_activas)
                monto_por_op = (saldo * CONFIG["uso_saldo"]) / ops_disponibles
                
                # Analizar pares
                ya_usados = [op["par"] for op in operaciones_activas]
                candidatos = []
                
                for par in PARES:
                    if par in ya_usados:
                        continue
                        
                    analisis = await analizar_impulso(par)
                    if analisis and analisis["puntaje"] >= CONFIG["puntaje_minimo"]:
                        candidatos.append(analisis)
                
                if not candidatos:
                    await asyncio.sleep(CONFIG["reanalisis_segundos"])
                    continue
                
                # Seleccionar mejor oportunidad
                mejor = max(candidatos, key=lambda x: x["puntaje"])
                
                # Ejecutar compra
                if not await ejecutar_compra(mejor["par"], mejor["precio"], monto_por_op):
                    await asyncio.sleep(3)
                
            await asyncio.sleep(CONFIG["reanalisis_segundos"])
            
        except Exception as e:
            logger.error(f"Error en ciclo trading: {str(e)}")
            await bot.send_message(
                CHAT_ID,
                f"⚠️ *ERROR EN CICLO TRADING* ⚠️\n\n"
                f"`{str(e)}`\n\n"
                f"_Reintentando en 10 segundos..._",
                parse_mode="Markdown"
            )
            await asyncio.sleep(10)

def crear_teclado():
    """Crea el teclado interactivo de Telegram"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Iniciar Bot Trading"), KeyboardButton(text="⛔ Detener Bot Trading")],
            [KeyboardButton(text="💰 Saldo USDT"), KeyboardButton(text="📊 Operaciones Activas")],
            [KeyboardButton(text="📈 Historial Operaciones"), KeyboardButton(text="📉 Rendimiento Diario")],
            [KeyboardButton(text="⚙️ Configuración"), KeyboardButton(text="❓ Ayuda")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Selecciona una opción..."
    )

@dp.message(Command("start", "help"))
async def start_cmd(msg: types.Message):
    """Mensaje de inicio/ayuda"""
    await msg.answer(
        "🤖 *Bot de Trading Profesional KuCoin* 🤖\n\n"
        "🔹 *Estrategia:* Trading de impulso con trailing stop dinámico\n"
        "🔹 *Pares:* 15 principales criptomonedas\n"
        "🔹 *Gestión de riesgo:* Stop dinámico basado en volatilidad\n\n"
        "📌 *Comandos disponibles:*\n"
        "- 🚀 Iniciar Bot: Activa el sistema de trading\n"
        "- ⛔ Detener Bot: Pausa nuevas operaciones\n"
        "- 💰 Saldo USDT: Muestra tu balance disponible\n"
        "- 📊 Operaciones Activas: Trades abiertos con P&L\n"
        "- 📈 Historial Operaciones: Últimos trades cerrados\n"
        "- 📉 Rendimiento Diario: Resumen de ganancias/pérdidas\n"
        "- ⚙️ Configuración: Parámetros actuales del bot\n\n"
        "⚠️ *Aviso de riesgo:* El trading conlleva pérdidas potenciales. "
        "Este bot no garantiza ganancias y debe usarse con prudencia.",
        reply_markup=crear_teclado(),
        parse_mode="Markdown"
    )

@dp.message()
async def comandos(msg: types.Message):
    """Maneja todos los comandos del teclado"""
    global bot_activo
    
    if msg.text == "🚀 Iniciar Bot Trading":
        if not bot_activo:
            bot_activo = True
            asyncio.create_task(ciclo_trading())
            await msg.answer(
                "✅ *Bot de trading ACTIVADO* ✅\n\n"
                "🔍 Iniciando análisis de mercado...\n"
                "📊 Máximo de operaciones simultáneas: "
                f"`{CONFIG['max_operaciones']}`\n"
                "💰 % Saldo utilizado: "
                f"`{CONFIG['uso_saldo']*100:.0f}%`\n\n"
                "_Las operaciones comenzarán en breve..._",
                parse_mode="Markdown"
            )
        else:
            await msg.answer("⚠️ El bot ya está en funcionamiento")

    elif msg.text == "⛔ Detener Bot Trading":
        if bot_activo:
            bot_activo = False
            await msg.answer(
                "🔴 *Bot de trading DETENIDO* 🔴\n\n"
                "🛑 No se realizarán nuevas operaciones.\n"
                "📉 Las operaciones activas continuarán con su trailing stop.\n\n"
                f"ℹ️ Operaciones activas actuales: `{len(operaciones_activas)}`",
                parse_mode="Markdown"
            )
        else:
            await msg.answer("ℹ️ El bot ya está detenido")

    elif msg.text == "💰 Saldo USDT":
        saldo = await obtener_saldo()
        invertido = sum(op['cantidad'] * op['entrada'] for op in operaciones_activas)
        saldo_total = saldo + invertido
        
        await msg.answer(
            f"💵 *Balance KuCoin* 💵\n\n"
            f"• 💰 Saldo disponible: `{saldo:.2f} USDT`\n"
            f"• 📊 Invertido en operaciones: `{invertido:.2f} USDT`\n"
            f"• 🏦 Balance total estimado: `{saldo_total:.2f} USDT`\n\n"
            f"ℹ️ Operaciones activas: `{len(operaciones_activas)}`",
            parse_mode="Markdown"
        )

    elif msg.text == "📊 Operaciones Activas":
        if not operaciones_activas:
            await msg.answer("🟢 *No hay operaciones activas* 🟢\n\n_El bot está esperando oportunidades..._", parse_mode="Markdown")
        else:
            texto = "📊 *Operaciones Activas* 📊\n\n"
            for op in operaciones_activas:
                try:
                    ticker = market.get_ticker(op['par'])
                    precio_actual = float(ticker["price"])
                    ganancia_pct = (precio_actual - op['entrada']) / op['entrada'] * 100
                    emoji = "🟢" if ganancia_pct >= 0 else "🔴"
                    
                    texto += (
                        f"{emoji} *{op['par']}* {emoji}\n"
                        f"• 🎯 Entrada: `{op['entrada']:.8f}`\n"
                        f"• 📈 Precio actual: `{precio_actual:.8f}`\n"
                        f"• 💰 Ganancia: `{ganancia_pct:.2f}%`\n"
                        f"• 📦 Cantidad: `{op['cantidad']:.2f}`\n"
                        f"• ⏰ Hora entrada: `{datetime.fromisoformat(op['entrada_dt']).strftime('%H:%M:%S')}`\n\n"
                    )
                except Exception as e:
                    logger.error(f"Error obteniendo datos para {op['par']}: {e}")
                    texto += f"⚠️ Error obteniendo datos para {op['par']}\n\n"
            
            await msg.answer(texto, parse_mode="Markdown")

    elif msg.text == "📈 Historial Operaciones":
        if not historial_operaciones:
            await msg.answer("📭 *No hay historial de operaciones* 📭\n\n_El bot aún no ha completado ninguna operación._", parse_mode="Markdown")
        else:
            # Mostrar las últimas 5 operaciones
            ultimas_operaciones = sorted(historial_operaciones, key=lambda x: x['salida_dt'], reverse=True)[:5]
            
            texto = "📈 *Últimas Operaciones* 📈\n\n"
            total_ganado = 0
            ops_positivas = 0
            
            for op in ultimas_operaciones:
                emoji = "🟢" if op['ganancia_usdt'] >= 0 else "🔴"
                if op['ganancia_usdt'] >= 0:
                    ops_positivas += 1
                    total_ganado += op['ganancia_usdt']
                
                razones = {
                    "timeout": "⏰ Timeout",
                    "take_profit_1x": "🎯 TP 1X",
                    "take_profit_1.5x": "🎯 TP 1.5X",
                    "take_profit_2x": "🎯 TP 2X",
                    "spread_alto": "📉 Spread alto"
                }
                
                texto += (
                    f"{emoji} *{op['par']}* {emoji}\n"
                    f"• 🎯 Entrada: `{op['entrada']:.8f}`\n"
                    f"• 🏁 Salida: `{op['salida']:.8f}`\n"
                    f"• 💰 Ganancia: `{op['ganancia_usdt']:.4f} USDT`\n"
                    f"• 📊 Rentabilidad: `{op['rentabilidad_pct']:.2f}%`\n"
                    f"• ⏱ Duración: `{op['duracion_min']:.1f} min`\n"
                    f"• 🛑 Razón: `{razones.get(op['razon_salida'], op['razon_salida'])}`\n\n"
                )
            
            # Estadísticas
            total_ops = len(historial_operaciones)
            porcentaje_exito = (ops_positivas / total_ops * 100) if total_ops > 0 else 0
            
            texto += (
                "📊 *Estadísticas Generales* 📊\n"
                f"• 📅 Total operaciones: `{total_ops}`\n"
                f"• ✅ Operaciones positivas: `{ops_positivas}` (`{porcentaje_exito:.1f}%`)\n"
                f"• 💵 Ganancia total: `{total_ganado:.4f} USDT`\n"
                f"• 📌 Promedio por op: `{(total_ganado/total_ops):.4f} USDT`" if total_ops > 0 else ""
            )
            
            await msg.answer(texto, parse_mode="Markdown")

    elif msg.text == "📉 Rendimiento Diario":
        hoy = datetime.now().date()
        ops_hoy = [op for op in historial_operaciones 
                  if datetime.fromisoformat(op['salida_dt']).date() == hoy]
        
        if not ops_hoy:
            await msg.answer(
                f"📅 *Rendimiento {hoy.strftime('%d/%m/%Y')}* 📅\n\n"
                "_No hay operaciones hoy aún._",
                parse_mode="Markdown"
            )
        else:
            ganancia_total = sum(op['ganancia_usdt'] for op in ops_hoy)
            ops_positivas = sum(1 for op in ops_hoy if op['ganancia_usdt'] >= 0)
            
            await msg.answer(
                f"📅 *Rendimiento {hoy.strftime('%d/%m/%Y')}* 📅\n\n"
                f"• 📊 Operaciones totales: `{len(ops_hoy)}`\n"
                f"• ✅ Operaciones positivas: `{ops_positivas}` (`{ops_positivas/len(ops_hoy)*100:.1f}%`)\n"
                f"• 💰 Ganancia total: `{ganancia_total:.4f} USDT`\n"
                f"• 📌 Promedio por op: `{ganancia_total/len(ops_hoy):.4f} USDT`\n\n"
                f"📈 _Evolución del día:_\n"
                f"`{'🟢' * ops_positivas}{'🔴' * (len(ops_hoy) - ops_positivas)}`",
                parse_mode="Markdown"
            )

    elif msg.text == "⚙️ Configuración":
        await msg.answer(
            f"⚙️ *Configuración Actual* ⚙️\n\n"
            f"• 📊 Pares activos: `{len(PARES)}`\n"
            f"• 🏷 Máx. operaciones: `{CONFIG['max_operaciones']}`\n"
            f"• 💰 % Saldo usado: `{CONFIG['uso_saldo']*100:.0f}%`\n"
            f"• 📈 Puntaje mínimo: `{CONFIG['puntaje_minimo']}`\n"
            f"• ⏱ Intervalo análisis: `{CONFIG['reanalisis_segundos']} seg`\n"
            f"• 🕒 Duración máxima: `{CONFIG['max_duracion_minutos']} min`\n"
            f"• 📉 Spread máximo: `{CONFIG['spread_maximo']*100:.2f}%`\n\n"
            f"_Estos parámetros están optimizados para trading de impulso._",
            parse_mode="Markdown"
        )

    elif msg.text == "❓ Ayuda":
        await start_cmd(msg)

async def iniciar_bot():
    """Inicia el bot de Telegram"""
    await dp.start_polling(bot)

if __name__ == "__main__":
    logger.info("Iniciando KuCoin Impulse Pro Bot")
    try:
        asyncio.run(iniciar_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.error(f"Error fatal: {str(e)}")
    finally:
        logger.info("Guardando historial antes de salir...")
        asyncio.run(guardar_historial())