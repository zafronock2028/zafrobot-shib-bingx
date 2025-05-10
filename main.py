import os
import logging
import asyncio
import json
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

# Configuración inicial
load_dotenv()

# Validación de variables de entorno
REQUIRED_ENV_VARS = ["TELEGRAM_TOKEN", "CHAT_ID", "API_KEY", "SECRET_KEY", "API_PASSPHRASE"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Faltan variables de entorno: {', '.join(missing_vars)}")

# Configuración avanzada de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_bot.log')
    ]
)
logger = logging.getLogger("KuCoinProTrader")

# =================================================================
# CONFIGURACIÓN DE LA ESTRATEGIA (Optimizada por trader profesional)
# =================================================================

PARES_CONFIG = {
    "SHIB-USDT": {
        "inc": 1000,
        "min": 50000,
        "vol_min": 800000,
        "momentum_min": 0.008,
        "cooldown": 20,
        "max_ops_dia": 5,
        "tp": 0.02,       # Take Profit del 2%
        "sl": 0.01        # Stop Loss del 1%
    },
    "PEPE-USDT": {
        "inc": 100,
        "min": 5000,
        "vol_min": 600000,
        "momentum_min": 0.010,
        "cooldown": 25,
        "max_ops_dia": 6,
        "tp": 0.025,      # Take Profit del 2.5%
        "sl": 0.012       # Stop Loss del 1.2%
    },
    "FLOKI-USDT": {
        "inc": 100,
        "min": 5000,
        "vol_min": 700000,
        "momentum_min": 0.009,
        "cooldown": 30,
        "max_ops_dia": 5,
        "tp": 0.022,      # Take Profit del 2.2%
        "sl": 0.011       # Stop Loss del 1.1%
    },
    # ... (otros pares con misma estructura)
}

CONFIG = {
    "uso_saldo": 0.90,           # Usar 90% del saldo disponible
    "max_operaciones": 1,        # Solo 1 operación a la vez
    "intervalo_analisis": 15,    # Segundos entre análisis
    "saldo_minimo": 36.00,       # Mínimo $36 para operar
    "proteccion_ganancia": 0.015, # Bloquear ganancias al 1.5%
    "lock_ganancia": 0.005,      # Bloquear 0.5% de ganancia
    "max_duracion": 30           # 30 minutos máximo por operación
}

# =================================================================
# ESTADO DEL BOT (Gestionado profesionalmente)
# =================================================================

class EstadoTrading:
    def __init__(self):
        self.operaciones_activas = []
        self.historial = []
        self.cooldowns = set()
        self.activo = False
        self.lock = asyncio.Lock()
        self.ultima_conexion = None

estado = EstadoTrading()

# =================================================================
# FUNCIONES AUXILIARES (Robustas y con manejo de errores)
# =================================================================

async def verificar_conexion_kucoin():
    """Verifica la conexión con KuCoin"""
    try:
        market = Market()
        ticker = await asyncio.to_thread(market.get_ticker, "BTC-USDT")
        estado.ultima_conexion = datetime.now()
        return True
    except Exception as e:
        logger.error(f"Error de conexión con KuCoin: {e}")
        return False

async def obtener_saldo_disponible():
    """Obtiene el saldo disponible con manejo profesional de errores"""
    try:
        user_client = User(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        accounts = await asyncio.to_thread(
            user_client.get_account_list, 
            currency="USDT", 
            account_type="trade"
        )
        return float(accounts[0]['available']) if accounts else 0.0
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        return 0.0

async def guardar_historial():
    """Guarda el historial de operaciones de forma segura"""
    try:
        async with estado.lock:
            with open('historial_operaciones.json', 'w') as f:
                json.dump(estado.historial, f, indent=4, default=str)
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

async def verificar_cooldown(par):
    """Verifica si un par está en cooldown"""
    if par in estado.cooldowns:
        config = PARES_CONFIG.get(par, {})
        cooldown = config.get("cooldown", 30) * 60  # Convertir a segundos
        
        ultima_op = next(
            (op for op in estado.historial if op["par"] == par), 
            None
        )
        
        if ultima_op and (datetime.now() - ultima_op["hora_entrada"]).seconds < cooldown:
            return True
        estado.cooldowns.discard(par)
    return False

# =================================================================
# NÚCLEO DE LA ESTRATEGIA (Implementación profesional)
# =================================================================

async def detectar_oportunidad(par):
    """Detecta oportunidades de trading basadas en impulso"""
    try:
        # 1. Verificar conexión
        if not await verificar_conexion_kucoin():
            return None

        # 2. Verificar volumen mínimo
        market = Market(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        stats = await asyncio.to_thread(market.get_24h_stats, par)
        if float(stats["volValue"]) < PARES_CONFIG[par]["vol_min"]:
            return None

        # 3. Obtener velas recientes
        velas = await asyncio.to_thread(
            market.get_kline, 
            symbol=par, 
            kline_type="1min", 
            limit=3
        )
        
        if len(velas) < 3:
            return None

        # 4. Análisis técnico (3 velas alcistas consecutivas)
        cierres = [float(v[2]) for v in velas]  # Precios de cierre
        if not (cierres[2] > cierres[1] > cierres[0]):
            return None

        # 5. Verificar momentum mínimo
        momentum = (cierres[2] - cierres[0]) / cierres[0]
        if momentum < PARES_CONFIG[par]["momentum_min"]:
            return None

        # 6. Verificar spread
        ticker = await asyncio.to_thread(market.get_ticker, par)
        spread = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
        if spread > 0.0015:  # Máx 0.15% de spread
            return None

        return {
            "par": par,
            "precio": cierres[2],
            "momentum": momentum,
            "take_profit": cierres[2] * (1 + PARES_CONFIG[par]["tp"]),
            "stop_loss": cierres[2] * (1 - PARES_CONFIG[par]["sl"])
        }

    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def ejecutar_operacion(señal):
    """Ejecuta una operación con gestión profesional de riesgo"""
    try:
        # 1. Verificar límite de operaciones
        async with estado.lock:
            if len(estado.operaciones_activas) >= CONFIG["max_operaciones"]:
                return None

        # 2. Obtener saldo disponible
        saldo = await obtener_saldo_disponible()
        if saldo < CONFIG["saldo_minimo"]:
            return None

        # 3. Calcular tamaño de posición
        cantidad = await calcular_posicion(señal["par"], saldo, señal["precio"])
        if not cantidad:
            return None

        # 4. Ejecutar orden de compra
        trade = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        orden = await asyncio.to_thread(
            trade.create_market_order,
            señal["par"], "buy", cantidad
        )
        
        # 5. Registrar operación
        operacion = {
            "par": señal["par"],
            "id_orden": orden["orderId"],
            "cantidad": cantidad,
            "precio_entrada": float(orden["price"]),
            "take_profit": señal["take_profit"],
            "stop_loss": señal["stop_loss"],
            "max_precio": float(orden["price"]),
            "hora_entrada": datetime.now(),
            "fee_compra": float(orden.get("fee", 0))
        }

        # 6. Notificar y actualizar estado
        await notificar_operacion(operacion, "ENTRADA")
        
        async with estado.lock:
            estado.operaciones_activas.append(operacion)
            estado.cooldowns.add(operacion["par"])
            
        return operacion

    except Exception as e:
        logger.error(f"Error ejecutando operación: {e}")
        return None

async def gestionar_operaciones_activas():
    """Gestiona operaciones activas con trailing stop profesional"""
    async with estado.lock:
        for op in estado.operaciones_activas[:]:
            try:
                # 1. Obtener precio actual
                market = Market(
                    key=os.getenv("API_KEY"),
                    secret=os.getenv("SECRET_KEY"),
                    passphrase=os.getenv("API_PASSPHRASE")
                )
                
                ticker = await asyncio.to_thread(market.get_ticker, op["par"])
                precio_actual = float(ticker["price"])
                
                # 2. Actualizar precio máximo
                op["max_precio"] = max(op["max_precio"], precio_actual)
                
                # 3. Verificar Take Profit
                if precio_actual >= op["take_profit"]:
                    await cerrar_operacion(op, "TP")
                    continue
                    
                # 4. Verificar Stop Loss dinámico
                ganancia = (op["max_precio"] - op["precio_entrada"]) / op["precio_entrada"]
                
                # Bloquear ganancias si supera el nivel de protección
                if ganancia > CONFIG["proteccion_ganancia"]:
                    nuevo_sl = op["precio_entrada"] * (1 + CONFIG["lock_ganancia"])
                    op["stop_loss"] = max(op["stop_loss"], nuevo_sl)
                
                if precio_actual <= op["stop_loss"]:
                    await cerrar_operacion(op, "SL")
                    continue
                    
                # 5. Verificar tiempo máximo
                if (datetime.now() - op["hora_entrada"]).seconds > CONFIG["max_duracion"] * 60:
                    await cerrar_operacion(op, "TIEMPO")
                    continue
                    
            except Exception as e:
                logger.error(f"Error gestionando operación {op['par']}: {e}")
                continue

# =================================================================
# FUNCIONES DE INTERFAZ (Mejoradas para experiencia profesional)
# =================================================================

async def notificar_operacion(operacion, tipo):
    """Notifica sobre operaciones con formato profesional"""
    try:
        if tipo == "ENTRADA":
            mensaje = (
                f"🚀 ENTRADA {operacion['par']}\n"
                f"📊 Cantidad: {operacion['cantidad']:.2f}\n"
                f"💰 Precio: {operacion['precio_entrada']:.8f}\n"
                f"🎯 TP: {operacion['take_profit']:.8f} ({PARES_CONFIG[operacion['par']]['tp']*100:.1f}%)\n"
                f"🛑 SL: {operacion['stop_loss']:.8f} ({PARES_CONFIG[operacion['par']]['sl']*100:.1f}%)"
            )
        else:
            ganancia_usdt = (operacion["precio_salida"] * operacion["cantidad"]) - (operacion["precio_entrada"] * operacion["cantidad"])
            ganancia_pct = ((operacion["precio_salida"] - operacion["precio_entrada"]) / operacion["precio_entrada"]) * 100
            
            mensaje = (
                f"{'🟢' if ganancia_usdt >= 0 else '🔴'} SALIDA {operacion['par']}\n"
                f"📌 Motivo: {operacion['motivo_salida']}\n"
                f"💵 Entrada: {operacion['precio_entrada']:.8f}\n"
                f"💰 Salida: {operacion['precio_salida']:.8f}\n"
                f"📈 Ganancia: {ganancia_pct:.2f}% | {ganancia_usdt:.4f} USDT\n"
                f"⏱ Duración: {(operacion['hora_salida'] - operacion['hora_entrada']).seconds // 60} min"
            )
        
        await bot.send_message(os.getenv("CHAT_ID"), mensaje)
        
    except Exception as e:
        logger.error(f"Error en notificación: {e}")

async def crear_menu_principal():
    """Crea el menú principal interactivo"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Iniciar Bot", callback_data="iniciar_bot"),
            InlineKeyboardButton(text="🛑 Detener Bot", callback_data="detener_bot")
        ],
        [
            InlineKeyboardButton(text="💰 Balance", callback_data="ver_balance"),
            InlineKeyboardButton(text="📊 Operaciones", callback_data="ver_operaciones")
        ],
        [
            InlineKeyboardButton(text="📜 Historial", callback_data="ver_historial"),
            InlineKeyboardButton(text="⚙ Config", callback_data="ver_config")
        ]
    ])
    return keyboard

# =================================================================
# HANDLERS DE COMANDOS (Implementación profesional)
# =================================================================

@dp.message(Command("start"))
async def comando_inicio(message: types.Message):
    """Maneja el comando de inicio con verificación de conexión"""
    try:
        if not await verificar_conexion_kucoin():
            await message.answer("⚠ Error de conexión con KuCoin. Verifica tu configuración.")
            return
            
        await message.answer(
            "🤖 KuCoin Pro Bot - Listo\n"
            "Selecciona una opción:",
            reply_markup=await crear_menu_principal()
        )
    except Exception as e:
        logger.error(f"Error en comando inicio: {e}")
        await message.answer("⚠ Error al iniciar el bot. Consulta los logs.")

@dp.callback_query(lambda c: c.data == "iniciar_bot")
async def iniciar_bot(callback: types.CallbackQuery):
    """Inicia el bot de trading con verificaciones"""
    try:
        if estado.activo:
            await callback.answer("⚠ El bot ya está activo", show_alert=True)
            return
            
        if not await verificar_conexion_kucoin():
            await callback.answer("⚠ Error de conexión con KuCoin", show_alert=True)
            return
            
        estado.activo = True
        asyncio.create_task(ciclo_trading())
        
        await callback.message.edit_text(
            "🚀 Bot de trading ACTIVADO\n"
            "Estrategia: Impulso de Mercado\n"
            f"🔹 Pares activos: {len(PARES_CONFIG)}\n"
            f"🔹 Saldo mínimo: {CONFIG['saldo_minimo']} USDT",
            reply_markup=await crear_menu_principal()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error al iniciar bot: {e}")
        await callback.answer("⚠ Error al iniciar el bot", show_alert=True)

@dp.callback_query(lambda c: c.data == "ver_historial")
async def mostrar_historial(callback: types.CallbackQuery):
    """Muestra el historial de operaciones"""
    try:
        if not estado.historial:
            await callback.answer("No hay operaciones en el historial", show_alert=True)
            return
            
        # Mostrar las últimas 5 operaciones
        historial_reverso = estado.historial[-5:][::-1]
        mensaje = "📜 Últimas 5 operaciones:\n\n"
        
        for op in historial_reverso:
            ganancia = ((op["precio_salida"] - op["precio_entrada"]) / op["precio_entrada"]) * 100
            mensaje += (
                f"🔹 {op['par']} ({op['motivo_salida']})\n"
                f"📈 {ganancia:.2f}% | ⏱ {((op['hora_salida'] - op['hora_entrada']).seconds // 60)} min\n"
                f"🕒 {op['hora_entrada'].strftime('%H:%M')} - {op['hora_salida'].strftime('%H:%M')}\n\n"
            )
            
        await callback.message.edit_text(
            mensaje,
            reply_markup=await crear_menu_principal()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error mostrando historial: {e}")
        await callback.answer("⚠ Error al mostrar historial", show_alert=True)

# =================================================================
# CICLO PRINCIPAL DE TRADING (Implementación robusta)
# =================================================================

async def ciclo_trading():
    """Ciclo principal de trading con manejo profesional de errores"""
    logger.info("Iniciando ciclo de trading...")
    
    while estado.activo:
        try:
            # 1. Verificar conexiones
            if not await verificar_conexion_kucoin():
                await asyncio.sleep(30)
                continue
                
            # 2. Gestionar operaciones activas
            await gestionar_operaciones_activas()
            
            # 3. Buscar nuevas oportunidades (si hay capacidad)
            async with estado.lock:
                if len(estado.operaciones_activas) < CONFIG["max_operaciones"]:
                    for par in PARES_CONFIG:
                        if await verificar_cooldown(par):
                            continue
                            
                        señal = await detectar_oportunidad(par)
                        if señal:
                            await ejecutar_operacion(señal)
                            await asyncio.sleep(5)  # Espera entre operaciones
            
            await asyncio.sleep(CONFIG["intervalo_analisis"])
            
        except aiohttp.ClientError as e:
            logger.error(f"Error de red: {e}. Reintentando en 30 segundos...")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Error en ciclo de trading: {e}")
            await asyncio.sleep(30)

# =================================================================
# EJECUCIÓN PRINCIPAL (Implementación profesional)
# =================================================================

async def ejecutar_bot():
    """Función principal con manejo profesional de errores"""
    logger.info("=== INICIANDO KUCOIN PRO BOT ===")
    
    try:
        # 1. Verificar conexión inicial
        if not await verificar_conexion_kucoin():
            logger.error("No se pudo conectar a KuCoin. Verifica tus credenciales.")
            return
            
        # 2. Cargar historial previo si existe
        try:
            with open('historial_operaciones.json', 'r') as f:
                estado.historial = json.load(f)
            logger.info(f"Historial cargado ({len(estado.historial)} operaciones)")
        except FileNotFoundError:
            logger.info("No se encontró historial previo")
        except Exception as e:
            logger.error(f"Error cargando historial: {e}")
            
        # 3. Iniciar bot de Telegram
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
    finally:
        # Guardar estado y cerrar conexiones
        await guardar_historial()
        await bot.session.close()
        logger.info("Bot detenido correctamente")

if __name__ == "__main__":
    try:
        asyncio.run(ejecutar_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.critical(f"Error no manejado: {e}")