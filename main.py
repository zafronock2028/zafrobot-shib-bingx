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
logger = logging.getLogger("KuCoinLowBalanceBot")

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

# Pares optimizados para saldos pequeños (~$35)
PARES = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT",
    "SUI-USDT", "TURBO-USDT", "BONK-USDT"
]

# Configuración ajustada para saldos pequeños
PARES_CONFIG = {
    "SHIB-USDT": {"inc": 1000, "min": 50000, "volatilidad": 1.8},
    "PEPE-USDT": {"inc": 100, "min": 5000, "volatilidad": 2.0},
    "FLOKI-USDT": {"inc": 100, "min": 5000, "volatilidad": 1.9},
    "DOGE-USDT": {"inc": 1, "min": 5, "volatilidad": 1.5},
    "SUI-USDT": {"inc": 0.01, "min": 0.05, "volatilidad": 1.3},
    "TURBO-USDT": {"inc": 100, "min": 5000, "volatilidad": 2.2},
    "BONK-USDT": {"inc": 1000, "min": 50000, "volatilidad": 2.1}
}

CONFIG = {
    "uso_saldo": 0.90,           # Usamos el 90% del saldo disponible
    "max_operaciones": 2,        # Máximo 2 operaciones simultáneas
    "puntaje_minimo": 2.0,       # Puntaje mínimo más flexible
    "reanalisis_segundos": 10,   # Intervalo de análisis más largo
    "max_duracion_minutos": 5,   # Duración máxima reducida
    "spread_maximo": 0.0025,     # Spread máximo permitido (0.25%)
    "saldo_minimo": 5.00         # Mínimo USDT requerido por operación
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
    """Obtiene el saldo disponible en USDT con verificación de mínimo"""
    try:
        cuentas = user.get_account_list()
        usdt = next(c for c in cuentas if c["currency"] == "USDT" and c["type"] == "trade")
        saldo = float(usdt["balance"])
        logger.info(f"Saldo obtenido: {saldo:.2f} USDT")
        
        if saldo < CONFIG["saldo_minimo"]:
            await bot.send_message(
                CHAT_ID,
                f"⚠️ *SALDO MUY BAJO* ⚠️\n\n"
                f"Saldo actual: `{saldo:.2f} USDT`\n"
                f"Mínimo recomendado: `{CONFIG['saldo_minimo']:.2f} USDT`\n\n"
                f"_Deposita más fondos para operar adecuadamente._",
                parse_mode="Markdown"
            )
        return saldo
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        await bot.send_message(CHAT_ID, f"⚠️ Error obteniendo saldo: {e}")
        return 0.0

async def analizar_impulso(par):
    """Analiza el impulso del mercado para un par específico"""
    try:
        # Obtener datos de mercado
        velas = market.get_kline(symbol=par, kline_type="1min", limit=4)
        if not velas or len(velas) < 4:
            return None
            
        precios = [float(v[2]) for v in velas]  # Precios de cierre
        volumen_24h = float(market.get_24h_stats(par)["volValue"])
        ticker = market.get_ticker(par)
        spread_actual = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
        
        # Análisis técnico para saldos pequeños
        velas_positivas = sum(1 for i in range(1, len(precios)) if precios[i] > precios[i-1] * 1.0015)  # Subida > 0.15%
        momentum = (precios[-1] - precios[-3]) / precios[-3]  # Momentum de 3 velas
        volatilidad = PARES_CONFIG[par].get("volatilidad", 1.5)
        
        # Cálculo de puntaje ajustado
        puntaje = (
            (velas_positivas * 0.5) + 
            (momentum * 2.0) + 
            (min(volumen_24h, 2_000_000) / 1_500_000) +  # Cap volumen a 2M
            (volatilidad * 0.7) -
            (spread_actual * 400)  # Penaliza spreads altos
        )
        
        return {
            "par": par,
            "precio": precios[-1],
            "puntaje": puntaje,
            "volumen": volumen_24h,
            "spread": spread_actual,
            "min_required": PARES_CONFIG[par]["min"] * precios[-1]  # Mínimo requerido en USDT
        }
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def ejecutar_compra(par, precio, monto_usdt):
    """Ejecuta una orden de compra con validación para saldos pequeños"""
    try:
        config_par = PARES_CONFIG.get(par)
        if not config_par:
            logger.error(f"Configuración no encontrada para {par}")
            return False

        # Verificar spread primero
        ticker = market.get_ticker(par)
        spread = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
        if spread > CONFIG["spread_maximo"]:
            logger.warning(f"Spread alto {spread*100:.2f}% en {par}, omitiendo")
            return False

        # Calcular tamaño de orden
        inc = Decimal(str(config_par["inc"]))
        minsize = Decimal(str(config_par["min"]))
        size = (Decimal(monto_usdt) / Decimal(precio)).quantize(inc)
        
        # Verificar mínimo requerido
        min_required = float(minsize) * precio
        if monto_usdt < min_required:
            logger.warning(f"Saldo insuficiente para {par}. Necesitas {min_required:.2f} USDT, tienes {monto_usdt:.2f}")
            await bot.send_message(
                CHAT_ID,
                f"⚠️ *SALDO INSUFICIENTE* ⚠️\n\n"
                f"• Par: `{par}`\n"
                f"• Mínimo requerido: `{min_required:.2f} USDT`\n"
                f"• Saldo asignado: `{monto_usdt:.2f} USDT`\n\n"
                f"_Considera depositar más fondos o elegir otro par._",
                parse_mode="Markdown"
            )
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
            f"• Mínimo requerido: `{min_required:.2f} USDT`\n"
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
    """Trailing stop optimizado para saldos pequeños"""
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
            spread_actual = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
            
            # Actualizar máximo
            if precio_actual > op["maximo"]:
                op["maximo"] = precio_actual
            
            # Calcular métricas
            ganancia_pct = (precio_actual - op["entrada"]) / op["entrada"] * 100
            retroceso_pct = (op["maximo"] - precio_actual) / op["maximo"] * 100
            
            # Condiciones de salida ajustadas para saldos pequeños
            if ganancia_pct >= 1.8 * volatilidad and retroceso_pct >= 1.0 * volatilidad:
                await ejecutar_venta(op, "take_profit_2x")
                break
            elif ganancia_pct >= 1.2 * volatilidad and retroceso_pct >= 0.7 * volatilidad:
                await ejecutar_venta(op, "take_profit_1.5x")
                break
            elif ganancia_pct >= 0.8 * volatilidad and retroceso_pct >= 0.4 * volatilidad:
                await ejecutar_venta(op, "take_profit_1x")
                break
            elif spread_actual > CONFIG["spread_maximo"] * 1.5:  # Spread aumenta 50%
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
            "take_profit_1x": "🎯 Take Profit 1X (0.8%)",
            "take_profit_1.5x": "🎯 Take Profit 1.5X (1.2%)",
            "take_profit_2x": "🎯 Take Profit 2X (1.8%)",
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
    """Ciclo principal de trading optimizado para saldos pequeños"""
    await asyncio.sleep(10)  # Espera inicial más corta
    
    while bot_activo:
        try:
            async with lock:
                # Verificar límite de operaciones
                if len(operaciones_activas) >= CONFIG["max_operaciones"]:
                    await asyncio.sleep(CONFIG["reanalisis_segundos"])
                    continue
                    
                # Obtener saldo
                saldo = await obtener_saldo()
                if saldo < CONFIG["saldo_minimo"]:
                    await asyncio.sleep(30)  # Espera más larga si saldo es muy bajo
                    continue
                    
                # Calcular monto por operación
                ops_disponibles = max(1, CONFIG["max_operaciones"] - len(operaciones_activas))
                monto_por_op = (saldo * CONFIG["uso_saldo"]) / ops_disponibles
                
                # Analizar pares disponibles
                ya_usados = [op["par"] for op in operaciones_activas]
                candidatos = []
                
                for par in PARES:
                    if par in ya_usados:
                        continue
                        
                    analisis = await analizar_impulso(par)
                    if analisis and analisis["puntaje"] >= CONFIG["puntaje_minimo"]:
                        # Verificar que tenemos suficiente saldo para este par
                        if monto_por_op >= analisis["min_required"] * 1.1:  # 10% de margen
                            candidatos.append(analisis)
                
                if not candidatos:
                    await asyncio.sleep(CONFIG["reanalisis_segundos"])
                    continue
                
                # Seleccionar mejor oportunidad con saldo suficiente
                mejor = max(candidatos, key=lambda x: x["puntaje"])
                
                # Ejecutar compra si tenemos saldo suficiente
                if monto_por_op >= mejor["min_required"]:
                    if not await ejecutar_compra(mejor["par"], mejor["precio"], monto_por_op):
                        await asyncio.sleep(3)
                
            await asyncio.sleep(CONFIG["reanalisis_segundos"])
            
        except Exception as e:
            logger.error(f"Error en ciclo trading: {str(e)}")
            await bot.send_message(
                CHAT_ID,
                f"⚠️ *ERROR EN CICLO TRADING* ⚠️\n\n"
                f"`{str(e)}`\n\n"
                f"_Reintentando en 15 segundos..._",
                parse_mode="Markdown"
            )
            await asyncio.sleep(15)

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
    """Mensaje de inicio/ayuda optimizado"""
    await msg.answer(
        "🤖 *Bot de Trading KuCoin - Versión Saldo Pequeño* 🤖\n\n"
        "🔹 *Saldo actual:* ~$35 USDT\n"
        "🔹 *Pares disponibles:* 7 (optimizados para bajo capital)\n"
        "🔹 *Estrategia:* Impulso con gestión de riesgo ajustada\n\n"
        "📌 *Comandos principales:*\n"
        "- 🚀 Iniciar: Activa el trading (máx 2 operaciones)\n"
        "- ⛔ Detener: Pausa nuevas operaciones\n"
        "- 💰 Saldo: Muestra tu balance actual\n"
        "- 📊 Operaciones: Muestra trades activos con P&L\n\n"
        "⚠️ *Aviso importante:* Con saldos pequeños:\n"
        "- Los spreads afectan más tu rentabilidad\n"
        "- Algunos pares pueden no estar disponibles\n"
        "- Considera depositar más fondos cuando puedas",
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
            saldo = await obtener_saldo()
            await msg.answer(
                "✅ *Bot de trading ACTIVADO* ✅\n\n"
                f"• Saldo disponible: `{saldo:.2f} USDT`\n"
                f"• Monto por operación: `{(saldo * CONFIG['uso_saldo']) / CONFIG['max_operaciones']:.2f} USDT`\n"
                f"• Máx. operaciones simultáneas: `{CONFIG['max_operaciones']}`\n\n"
                "_Buscando oportunidades..._",
                parse_mode="Markdown"
            )
        else:
            await msg.answer("ℹ️ El bot ya está en funcionamiento")

    elif msg.text == "⛔ Detener Bot Trading":
        if bot_activo:
            bot_activo = False
            await msg.answer(
                "🔴 *Bot de trading DETENIDO* 🔴\n\n"
                "🛑 No se realizarán nuevas operaciones.\n"
                f"📉 Operaciones activas: `{len(operaciones_activas)}`\n\n"
                "_Los trailing stops seguirán activos._",
                parse_mode="Markdown"
            )
        else:
            await msg.answer("ℹ️ El bot ya está detenido")

    elif msg.text == "💰 Saldo USDT":
        saldo = await obtener_saldo()
        invertido = sum(op['cantidad'] * op['entrada'] for op in operaciones_activas)
        saldo_total = saldo + invertido
        
        await msg.answer(
            f"💵 *Balance Actual* 💵\n\n"
            f"• 💰 Disponible: `{saldo:.2f} USDT`\n"
            f"• 📊 Invertido: `{invertido:.2f} USDT`\n"
            f"• 🏦 Total: `{saldo_total:.2f} USDT`\n"
            f"• 📈 Operaciones activas: `{len(operaciones_activas)}`\n\n"
            f"💡 _Consejo: Para mejor rendimiento, considera llegar a al menos $100 USDT_",
            parse_mode="Markdown"
        )

    elif msg.text == "📊 Operaciones Activas":
        if not operaciones_activas:
            await msg.answer(
                "🟢 *Sin operaciones activas* 🟢\n\n"
                "_El bot está analizando el mercado..._",
                parse_mode="Markdown"
            )
        else:
            texto = "📊 *Operaciones en Curso* 📊\n\n"
            for op in operaciones_activas:
                try:
                    ticker = market.get_ticker(op['par'])
                    precio_actual = float(ticker["price"])
                    ganancia_pct = (precio_actual - op['entrada']) / op['entrada'] * 100
                    ganancia_usdt = (precio_actual - op['entrada']) * op['cantidad']
                    emoji = "🟢" if ganancia_pct >= 0 else "🔴"
                    duracion = (datetime.now() - datetime.fromisoformat(op['entrada_dt'])).total_seconds() / 60
                    
                    texto += (
                        f"{emoji} *{op['par']}* {emoji}\n"
                        f"• 🎯 Entrada: `{op['entrada']:.8f}`\n"
                        f"• 📈 Actual: `{precio_actual:.8f}`\n"
                        f"• 📊 Rentabilidad: `{ganancia_pct:.2f}%`\n"
                        f"• 💰 Ganancia: `{ganancia_usdt:.4f} USDT`\n"
                        f"• ⏱ Duración: `{duracion:.1f} min`\n\n"
                    )
                except Exception as e:
                    logger.error(f"Error obteniendo datos para {op['par']}: {e}")
                    texto += f"⚠️ Error obteniendo datos para {op['par']}\n\n"
            
            await msg.answer(texto, parse_mode="Markdown")

    elif msg.text == "📈 Historial Operaciones":
        if not historial_operaciones:
            await msg.answer(
                "📭 *Historial vacío* 📭\n\n"
                "_Aún no se han completado operaciones._",
                parse_mode="Markdown"
            )
        else:
            ultimas_operaciones = sorted(historial_operaciones, key=lambda x: x['salida_dt'], reverse=True)[:3]
            
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
                    "take_profit_1x": "🎯 TP 0.8%",
                    "take_profit_1.5x": "🎯 TP 1.2%",
                    "take_profit_2x": "🎯 TP 1.8%",
                    "spread_alto": "📉 Spread alto"
                }
                
                texto += (
                    f"{emoji} *{op['par']}* {emoji}\n"
                    f"• 🎯 Entrada: `{op['entrada']:.8f}`\n"
                    f"• � Salida: `{op['salida']:.8f}`\n"
                    f"• 📊 Rentabilidad: `{op['rentabilidad_pct']:.2f}%`\n"
                    f"• 💰 Ganancia: `{op['ganancia_usdt']:.4f} USDT`\n"
                    f"• ⏱ Duración: `{op['duracion_min']:.1f} min`\n"
                    f"• 🛑 Razón: `{razones.get(op['razon_salida'], op['razon_salida'])}`\n\n"
                )
            
            total_ops = len(historial_operaciones)
            porcentaje_exito = (ops_positivas / total_ops * 100) if total_ops > 0 else 0
            
            texto += (
                "📊 *Estadísticas* 📊\n"
                f"• 📅 Total operaciones: `{total_ops}`\n"
                f"• ✅ Operaciones positivas: `{ops_positivas}` (`{porcentaje_exito:.1f}%`)\n"
                f"• 💵 Ganancia total: `{total_ganado:.4f} USDT`\n"
                f"• 📌 Promedio/op: `{(total_ganado/total_ops):.4f} USDT`" if total_ops > 0 else ""
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
                f"• 📊 Operaciones: `{len(ops_hoy)}`\n"
                f"• ✅ Positivas: `{ops_positivas}` (`{ops_positivas/len(ops_hoy)*100:.1f}%`)\n"
                f"• 💰 Ganancia: `{ganancia_total:.4f} USDT`\n"
                f"• 📌 Promedio: `{ganancia_total/len(ops_hoy):.4f} USDT`\n\n"
                f"📈 _Resumen:_\n"
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
            f"_Configuración optimizada para saldo de ~$35 USDT_",
            parse_mode="Markdown"
        )

    elif msg.text == "❓ Ayuda":
        await start_cmd(msg)

async def iniciar_bot():
    """Inicia el bot de Telegram"""
    await dp.start_polling(bot)

if __name__ == "__main__":
    logger.info("Iniciando KuCoin Low Balance Trading Bot")
    try:
        asyncio.run(iniciar_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.error(f"Error fatal: {str(e)}")
    finally:
        logger.info("Guardando historial antes de salir...")
        asyncio.run(guardar_historial())