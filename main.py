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
logger = logging.getLogger("KuCoinAntiPrematureBot")

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

# Pares seleccionados (optimizados para evitar cierres prematuros)
PARES = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT",
    "SUI-USDT", "TURBO-USDT", "BONK-USDT", "WIF-USDT"
]

# Configuración por par (cooldowns y requisitos ajustados)
PARES_CONFIG = {
    "SHIB-USDT": {"inc": 1000, "min": 50000, "volatilidad": 1.5, "cooldown": 30},
    "PEPE-USDT": {"inc": 100, "min": 5000, "volatilidad": 1.8, "cooldown": 30},
    "FLOKI-USDT": {"inc": 100, "min": 5000, "volatilidad": 1.7, "cooldown": 45},
    "DOGE-USDT": {"inc": 1, "min": 5, "volatilidad": 1.3, "cooldown": 30},
    "SUI-USDT": {"inc": 0.01, "min": 0.05, "volatilidad": 1.2, "cooldown": 30},
    "TURBO-USDT": {"inc": 100, "min": 5000, "volatilidad": 1.9, "cooldown": 45},
    "BONK-USDT": {"inc": 1000, "min": 50000, "volatilidad": 1.6, "cooldown": 45},
    "WIF-USDT": {"inc": 0.0001, "min": 0.01, "volatilidad": 1.4, "cooldown": 30}
}

# Configuración global optimizada (para evitar cierres prematuros)
CONFIG = {
    "uso_saldo": 0.75,            # 75% del saldo para operaciones
    "max_operaciones": 2,         # Menos operaciones simultáneas
    "puntaje_minimo": 3.0,        # Filtro más estricto para entradas
    "reanalisis_segundos": 20,    # Intervalo de análisis más largo
    "max_duracion_minutos": 30,   # Duración máxima extendida (30 min)
    "spread_maximo": 0.001,       # Spread máximo reducido (0.1%)
    "saldo_minimo": 20.00,        # Mínimo recomendado por operación
    "vol_minima": 1000000,        # Volumen mínimo en USDT (24h) - $1M
    "min_ganancia_objetivo": 0.015,  # 1.5% ganancia mínima esperada
    "nivel_proteccion": -0.01,    # Stop loss del 1% (más flexible)
    "max_ops_mismo_par": 3,       # Máx operaciones consecutivas por par
    "horas_reset_ops": 6          # Horas para resetear contadores
}

# Variables globales
operaciones_activas = []
historial_operaciones = []
operaciones_recientes = {}  # {par: {"last_op": datetime, "count": int}}
cooldown_activo = set()
bot_activo = False
lock = asyncio.Lock()

# Cargar historial al iniciar
try:
    with open('historial_operaciones.json', 'r') as f:
        historial_operaciones = json.load(f)
    # Cargar operaciones recientes desde el historial
    for op in historial_operaciones[-50:]:  # Últimas 50 operaciones
        par = op["par"]
        op_time = datetime.fromisoformat(op["entrada_dt"])
        if par in operaciones_recientes:
            if op_time > operaciones_recientes[par]["last_op"]:
                operaciones_recientes[par] = {"last_op": op_time, "count": operaciones_recientes[par]["count"] + 1}
        else:
            operaciones_recientes[par] = {"last_op": op_time, "count": 1}
except Exception as e:
    logger.warning(f"Error cargando historial: {e}")
    historial_operaciones = []

async def guardar_historial():
    """Guarda el historial de operaciones en un archivo JSON"""
    try:
        with open('historial_operaciones.json', 'w') as f:
            json.dump(historial_operaciones, f, indent=2)
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

async def verificar_cooldown(par):
    """Verifica si un par está en periodo de cooldown o ha alcanzado el límite de operaciones"""
    ahora = datetime.now()
    
    # Verificar si ha alcanzado el máximo de operaciones consecutivas
    if par in operaciones_recientes:
        # Resetear contador si ha pasado el tiempo definido
        if (ahora - operaciones_recientes[par]["last_op"]).total_seconds() > CONFIG["horas_reset_ops"] * 3600:
            operaciones_recientes[par]["count"] = 0
        
        if operaciones_recientes[par]["count"] >= CONFIG["max_ops_mismo_par"]:
            logger.info(f"Par {par} alcanzó el máximo de operaciones consecutivas")
            return True
    
    # Verificar cooldown normal
    if par in cooldown_activo:
        cooldown_min = PARES_CONFIG.get(par, {}).get("cooldown", 30)
        if par in operaciones_recientes:
            tiempo_desde_ultima = (ahora - operaciones_recientes[par]["last_op"]).total_seconds()
            if tiempo_desde_ultima < cooldown_min * 60:
                return True
            else:
                cooldown_activo.remove(par)
    return False

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
    """Analiza el impulso del mercado con filtros mejorados para evitar entradas prematuras"""
    try:
        # Verificar volumen mínimo primero
        stats_24h = market.get_24h_stats(par)
        volumen_usdt = float(stats_24h["volValue"])
        if volumen_usdt < CONFIG["vol_minima"]:
            logger.info(f"Volumen insuficiente para {par}: {volumen_usdt:.2f} USDT")
            return None
            
        # Obtener datos de mercado con velas de 5 minutos
        velas = market.get_kline(symbol=par, kline_type="5min", limit=6)
        if not velas or len(velas) < 6:
            return None
            
        precios = [float(v[2]) for v in velas]  # Precios de cierre
        ticker = market.get_ticker(par)
        spread_actual = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
        
        # Filtros estrictos de entrada
        if spread_actual > CONFIG["spread_maximo"]:
            return None
            
        # Análisis técnico mejorado
        velas_positivas = sum(1 for i in range(1, len(precios)) if precios[i] > precios[i-1] * 1.003)  # Subida > 0.3%
        momentum_corto = (precios[-1] - precios[-2]) / precios[-2]
        momentum_largo = (precios[-1] - precios[-4]) / precios[-4]  # Comparación con 20 minutos atrás
        volatilidad = PARES_CONFIG[par].get("volatilidad", 1.5)
        
        # Requerir al menos 4 velas alcistas de 6
        if velas_positivas < 4:
            return None
            
        # Cálculo de puntaje ajustado
        puntaje = (
            (velas_positivas * 0.6) + 
            (momentum_corto * 2.0) + 
            (momentum_largo * 1.5) + 
            (min(volumen_usdt, 3000000) / 2000000) +  # Cap volumen a 3M
            (volatilidad * 0.8) -
            (spread_actual * 800)  # Penalización fuerte por spread
        )
        
        if puntaje < CONFIG["puntaje_minimo"]:
            return None
            
        return {
            "par": par,
            "precio": precios[-1],
            "puntaje": puntaje,
            "volumen": volumen_usdt,
            "momentum": momentum_corto,
            "spread": spread_actual,
            "min_required": PARES_CONFIG[par]["min"] * precios[-1]
        }
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def ejecutar_compra(par, precio, monto_usdt):
    """Ejecuta una orden de compra con validación mejorada"""
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
        
        # Actualizar operaciones recientes
        ahora = datetime.now()
        if par in operaciones_recientes:
            # Resetear contador si ha pasado el tiempo definido
            if (ahora - operaciones_recientes[par]["last_op"]).total_seconds() > CONFIG["horas_reset_ops"] * 3600:
                operaciones_recientes[par]["count"] = 1
            else:
                operaciones_recientes[par]["count"] += 1
            operaciones_recientes[par]["last_op"] = ahora
        else:
            operaciones_recientes[par] = {"last_op": ahora, "count": 1}
        
        cooldown_activo.add(par)
        
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
            f"• Operaciones recientes: `{operaciones_recientes[par]['count']}/{CONFIG['max_ops_mismo_par']}`\n"
            f"• Hora: `{ahora.strftime('%H:%M:%S')}`\n\n"
            f"📊 _Iniciando trailing stop (duración máxima: {CONFIG['max_duracion_minutos']} min)..._",
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
    """Trailing stop optimizado para evitar cierres prematuros"""
    par = op["par"]
    entrada_dt = datetime.fromisoformat(op["entrada_dt"])
    max_duracion = timedelta(minutes=CONFIG["max_duracion_minutos"])
    volatilidad = PARES_CONFIG[par].get("volatilidad", 1.5)
    spread_inicial = op["spread_inicial"]
    
    # Variables para seguimiento mejorado
    ultimo_maximo = op["entrada"]
    precio_objetivo = op["entrada"] * (1 + CONFIG["min_ganancia_objetivo"])
    check_interval = 15  # Verificar cada 15 segundos (menos frecuente)
    timeout_inicio = datetime.now() + timedelta(minutes=15)  # Sólo verificar timeout después de 15 min
    
    while bot_activo and op in operaciones_activas:
        try:
            ahora = datetime.now()
            
            # Verificar timeout sólo después de 15 minutos
            if ahora > timeout_inicio and (ahora - entrada_dt) > max_duracion:
                logger.info(f"Timeout alcanzado para {par} después de {CONFIG['max_duracion_minutos']} min")
                await ejecutar_venta(op, "timeout")
                break
                
            # Obtener precio actual
            ticker = market.get_ticker(par)
            precio_actual = float(ticker["price"])
            spread_actual = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
            
            # Actualizar máximo
            if precio_actual > ultimo_maximo:
                ultimo_maximo = precio_actual
                # Ajustar objetivo dinámicamente (nuevo máximo + 0.8%)
                precio_objetivo = max(precio_objetivo, precio_actual * 1.008)
                timeout_inicio = ahora + timedelta(minutes=15)  # Resetear timeout
            
            # Calcular métricas
            ganancia_pct = (precio_actual - op["entrada"]) / op["entrada"] * 100
            retroceso_pct = (ultimo_maximo - precio_actual) / ultimo_maximo * 100
            
            # Condiciones de salida optimizadas:
            
            # 1. Take Profit principal (alcanzó objetivo mínimo)
            if precio_actual >= precio_objetivo:
                await ejecutar_venta(op, f"take_profit_{ganancia_pct:.1f}%")
                break
                
            # 2. Take Profit parcial (cierre con ganancia si el mercado se vuelve adverso)
            elif (ganancia_pct >= 1.0 and 
                  spread_actual > spread_inicial * 2 and 
                  retroceso_pct >= 1.0):
                await ejecutar_venta(op, f"take_profit_parcial_{ganancia_pct:.1f}%")
                break
                
            # 3. Protección contra spread excesivo
            elif spread_actual > CONFIG["spread_maximo"] * 3:
                await ejecutar_venta(op, "spread_excesivo")
                break
                
            # 4. Stop loss flexible
            elif ganancia_pct <= CONFIG["nivel_proteccion"] * 100:
                await ejecutar_venta(op, f"stop_loss_{ganancia_pct:.1f}%")
                break
                
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            logger.error(f"Error en trailing stop {par}: {str(e)}")
            await asyncio.sleep(20)

async def ejecutar_venta(op, razon):
    """Ejecuta la venta y registra los resultados con cooldown"""
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
            "take_profit": "🎯 Take Profit alcanzado",
            "take_profit_parcial": "🎯 Take Profit parcial",
            "spread_excesivo": "📉 Spread excesivo",
            "stop_loss": "🛑 Stop Loss"
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
            f"• Razón: `{razones.get(razon.split('_')[0], razon)}`\n"
            f"• Spread final: `{spread_actual*100:.2f}%`\n"
            f"• Operaciones recientes: `{operaciones_recientes.get(par, {}).get('count', 1)}/{CONFIG['max_ops_mismo_par']}`\n\n"
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
    """Ciclo principal con gestión mejorada de rotación de pares"""
    await asyncio.sleep(20)  # Espera inicial más larga
    
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
                    await asyncio.sleep(30)
                    continue
                    
                # Calcular monto por operación
                ops_disponibles = max(1, CONFIG["max_operaciones"] - len(operaciones_activas))
                monto_por_op = (saldo * CONFIG["uso_saldo"]) / ops_disponibles
                
                # Analizar pares disponibles
                candidatos = []
                for par in PARES:
                    # Verificar cooldown y límites de operaciones
                    if await verificar_cooldown(par):
                        continue
                        
                    analisis = await analizar_impulso(par)
                    if analisis and analisis["puntaje"] >= CONFIG["puntaje_minimo"]:
                        # Verificar que tenemos suficiente saldo para este par
                        if monto_por_op >= analisis["min_required"] * 1.1:  # 10% de margen
                            candidatos.append(analisis)
                
                if not candidatos:
                    await asyncio.sleep(CONFIG["reanalisis_segundos"])
                    continue
                
                # Ordenar candidatos por puntaje y rotación
                candidatos.sort(key=lambda x: (
                    -x["puntaje"],  # Primero por puntaje
                    operaciones_recientes.get(x["par"], {}).get("count", 0)  # Luego por operaciones recientes
                ))
                
                # Seleccionar mejor opción con rotación
                mejor = candidatos[0]
                if await ejecutar_compra(mejor["par"], mejor["precio"], monto_por_op):
                    await asyncio.sleep(5)  # Pequeña pausa entre operaciones
                
            await asyncio.sleep(CONFIG["reanalisis_segundos"])
            
        except Exception as e:
            logger.error(f"Error en ciclo trading: {str(e)}")
            await bot.send_message(
                CHAT_ID,
                f"⚠️ *ERROR EN CICLO TRADING* ⚠️\n\n"
                f"`{str(e)}`\n\n"
                f"_Reintentando en 20 segundos..._",
                parse_mode="Markdown"
            )
            await asyncio.sleep(20)

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
        "🤖 *Bot de Trading KuCoin - Anti Cierres Prematuros* 🤖\n\n"
        "🔹 *Características clave:*\n"
        "- Duración extendida (30 min máximo)\n"
        "- Take Profit dinámico (1.5% mínimo)\n"
        "- Filtros de entrada más estrictos\n"
        "- Rotación inteligente entre pares\n\n"
        "📌 *Comandos principales:*\n"
        "- 🚀 Iniciar: Activa el trading\n"
        "- ⛔ Detener: Pausa nuevas operaciones\n"
        "- 💰 Saldo: Muestra tu balance\n"
        "- 📊 Operaciones: Trades activos\n\n"
        "⚠️ *Aviso:* El bot ahora evita cierres prematuros",
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
                "🔍 Iniciando análisis con protección contra cierres prematuros...\n"
                f"⏳ Duración máxima por operación: `{CONFIG['max_duracion_minutos']} min`\n"
                f"🎯 Objetivo de ganancia mínimo: `{CONFIG['min_ganancia_objetivo']*100:.1f}%`\n\n"
                "_Buscando oportunidades de calidad..._",
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
                "_Los trailing stops seguirán activos hasta su cierre natural._",
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
            f"💡 _Configuración actual: {CONFIG['uso_saldo']*100:.0f}% del saldo en {CONFIG['max_operaciones']} operaciones_",
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
                        f"• ⏱ Duración: `{duracion:.1f} min`\n"
                        f"• 🕒 Tiempo restante: `{max(0, CONFIG['max_duracion_minutos'] - duracion):.1f} min`\n\n"
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
                    "take_profit": "🎯 Take Profit",
                    "take_profit_parcial": "🎯 TP Parcial",
                    "spread_excesivo": "📉 Spread Alto",
                    "stop_loss": "🛑 Stop Loss"
                }
                
                texto += (
                    f"{emoji} *{op['par']}* {emoji}\n"
                    f"• 🎯 Entrada: `{op['entrada']:.8f}`\n"
                    f"• 🏁 Salida: `{op['salida']:.8f}`\n"
                    f"• 📊 Rentabilidad: `{op['rentabilidad_pct']:.2f}%`\n"
                    f"• 💰 Ganancia: `{op['ganancia_usdt']:.4f} USDT`\n"
                    f"• ⏱ Duración: `{op['duracion_min']:.1f} min`\n"
                    f"• 🛑 Razón: `{razones.get(op['razon_salida'].split('_')[0], op['razon_salida'])}`\n\n"
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
            f"• 📉 Spread máximo: `{CONFIG['spread_maximo']*100:.2f}%`\n"
            f"• 🎯 Ganancia mínima: `{CONFIG['min_ganancia_objetivo']*100:.1f}%`\n"
            f"• 🛑 Stop loss: `{CONFIG['nivel_proteccion']*100:.1f}%`\n\n"
            f"_Configuración optimizada para evitar cierres prematuros_",
            parse_mode="Markdown"
        )

    elif msg.text == "❓ Ayuda":
        await start_cmd(msg)

async def iniciar_bot():
    """Inicia el bot de Telegram"""
    await dp.start_polling(bot)

if __name__ == "__main__":
    logger.info("Iniciando KuCoin Anti-Premature Bot")
    try:
        asyncio.run(iniciar_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.error(f"Error fatal: {str(e)}")
    finally:
        logger.info("Guardando historial antes de salir...")
        asyncio.run(guardar_historial())