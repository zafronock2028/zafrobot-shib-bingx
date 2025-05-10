import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

# Configuración inicial
load_dotenv()

# Validación de variables de entorno requeridas
REQUIRED_ENV_VARS = ["TELEGRAM_TOKEN", "CHAT_ID", "API_KEY", "SECRET_KEY", "API_PASSPHRASE"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Faltan variables de entorno requeridas: {', '.join(missing_vars)}")

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_bot.log')
    ]
)
logger = logging.getLogger("KuCoinImpulseBot")

# Inicialización del bot de Telegram
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

# =================================================================
# ESTRATEGIA DE IMPULSO - CONFIGURACIÓN
# =================================================================

PARES_OPERABLES = {
    "SHIB-USDT": {
        "incremento": 1000,         # Incremento mínimo para cantidad
        "min_cantidad": 50000,      # Cantidad mínima a operar
        "volumen_minimo": 800000,    # Volumen mínimo en USDT (24h)
        "impulso_minimo": 0.008,     # % mínimo de momentum alcista
        "cooldown": 20,              # Minutos de espera entre operaciones
        "operaciones_diarias": 5,     # Máx operaciones por día
        "take_profit": 0.02,         # % TP inicial
        "stop_loss": 0.01            # % SL inicial
    },
    "PEPE-USDT": {
        "incremento": 100,
        "min_cantidad": 5000,
        "volumen_minimo": 600000,
        "impulso_minimo": 0.010,
        "cooldown": 25,
        "operaciones_diarias": 6,
        "take_profit": 0.025,
        "stop_loss": 0.012
    },
    "FLOKI-USDT": {
        "incremento": 100,
        "min_cantidad": 5000,
        "volumen_minimo": 700000,
        "impulso_minimo": 0.009,
        "cooldown": 30,
        "operaciones_diarias": 5,
        "take_profit": 0.022,
        "stop_loss": 0.011
    }
}

CONFIG_GLOBAL = {
    "porcentaje_saldo": 0.90,        # % del saldo a utilizar
    "max_operaciones": 1,            # Máx operaciones simultáneas
    "intervalo_analisis": 15,        # Segundos entre análisis
    "saldo_minimo": 36.00,           # Saldo mínimo en USDT para operar
    "ganancia_minima": 0.02,         # % mínimo de TP
    "proteccion": -0.01,             # % máximo de pérdida
    "duracion_maxima": 30            # Minutos máx por operación
}

# =================================================================
# ESTADO DEL BOT
# =================================================================

class EstadoBot:
    def __init__(self):
        self.operaciones_activas = []
        self.historial = []
        self.ultimas_operaciones = {}
        self.cooldowns = set()
        self.activo = False
        self.lock = asyncio.Lock()

estado = EstadoBot()

# =================================================================
# FUNCIONES PRINCIPALES - ESTRATEGIA DE IMPULSO
# =================================================================

async def verificar_cooldown(par):
    """Verifica si un par está en cooldown"""
    if par in estado.cooldowns:
        config = PARES_OPERABLES.get(par, {})
        tiempo_espera = config.get("cooldown", 30) * 60  # Convertir a segundos
        ultima_op = estado.ultimas_operaciones.get(par)
        
        if ultima_op and (datetime.now() - ultima_op).seconds < tiempo_espera:
            return True
        estado.cooldowns.discard(par)
    return False

async def detectar_impulso(par):
    """Detecta oportunidades basadas en momentum alcista"""
    try:
        # 1. Verificar volumen mínimo
        mercado = Market(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        stats = mercado.get_24h_stats(par)
        volumen = float(stats["volValue"])
        if volumen < PARES_OPERABLES[par]["volumen_minimo"]:
            return None
        
        # 2. Obtener velas recientes (1 minuto)
        velas = mercado.get_kline(symbol=par, kline_type="1min", limit=3)
        if len(velas) < 3:
            return None
            
        # Precios de las últimas 3 velas
        precios = [float(v[2]) for v in velas]  # Precios de cierre
        
        # 3. Verificar momentum alcista (3 velas consecutivas)
        if not (precios[2] > precios[1] > precios[0]):
            return None
            
        # 4. Calcular fuerza del impulso
        momentum = (precios[2] - precios[0]) / precios[0]
        if momentum < PARES_OPERABLES[par]["impulso_minimo"]:
            return None
            
        # 5. Verificar spread (diferencia compra/venta)
        ticker = mercado.get_ticker(par)
        spread = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
        if spread > 0.0015:  # 0.15%
            return None
            
        return {
            "par": par,
            "precio_actual": precios[2],
            "momentum": momentum,
            "take_profit": precios[2] * (1 + PARES_OPERABLES[par]["take_profit"]),
            "stop_loss": precios[2] * (1 - PARES_OPERABLES[par]["stop_loss"])
        }
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def calcular_posicion(par, saldo_disponible, precio):
    """Calcula tamaño de posición con gestión de riesgo"""
    config = PARES_OPERABLES[par]
    
    # 1. Ajustar por fees (0.2% estimado)
    monto_max = saldo_disponible * CONFIG_GLOBAL["porcentaje_saldo"] * 0.998
    cantidad = (monto_max / precio) // config["incremento"] * config["incremento"]
    
    # 2. Verificar mínimos de cantidad
    if cantidad < config["min_cantidad"]:
        return None
        
    return cantidad

async def ejecutar_compra(señal):
    """Ejecuta orden de compra con gestión de riesgo"""
    try:
        # 1. Obtener saldo disponible
        saldo = await obtener_saldo_disponible()
        if saldo < CONFIG_GLOBAL["saldo_minimo"]:
            return None
            
        # 2. Calcular tamaño de posición
        cantidad = await calcular_posicion(
            señal["par"], 
            saldo, 
            señal["precio_actual"]
        )
        if not cantidad:
            return None
            
        # 3. Ejecutar orden de compra
        trade = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        orden = trade.create_market_order(señal["par"], "buy", cantidad)
        fee = float(orden.get("fee", 0))
        
        operacion = {
            "par": señal["par"],
            "id_orden": orden["orderId"],
            "cantidad": cantidad,
            "precio_entrada": float(orden["price"]),
            "take_profit": señal["take_profit"],
            "stop_loss": señal["stop_loss"],
            "max_precio": float(orden["price"]),
            "hora_entrada": datetime.now(),
            "fee_compra": fee
        }
        
        # 4. Notificar entrada
        await bot.send_message(
            os.getenv("CHAT_ID"),
            f"🚀 ENTRADA {operacion['par']}\n"
            f"💵 Precio: {operacion['precio_entrada']:.8f}\n"
            f"📈 Objetivo: {operacion['take_profit']:.8f}\n"
            f"🛑 Stop: {operacion['stop_loss']:.8f}\n"
            f"📊 Cantidad: {operacion['cantidad']:.2f}"
        )
        
        # 5. Actualizar estado
        async with estado.lock:
            estado.operaciones_activas.append(operacion)
            estado.ultimas_operaciones[operacion["par"]] = datetime.now()
            estado.cooldowns.add(operacion["par"])
            
        return operacion
        
    except Exception as e:
        logger.error(f"Error ejecutando compra: {e}")
        return None

async def gestionar_operaciones():
    """Gestiona operaciones activas con trailing stop"""
    async with estado.lock:
        for op in estado.operaciones_activas[:]:
            try:
                # 1. Obtener precio actual
                mercado = Market(
                    key=os.getenv("API_KEY"),
                    secret=os.getenv("SECRET_KEY"),
                    passphrase=os.getenv("API_PASSPHRASE")
                )
                ticker = mercado.get_ticker(op["par"])
                precio_actual = float(ticker["price"])
                
                # 2. Actualizar precio máximo
                op["max_precio"] = max(op["max_precio"], precio_actual)
                
                # 3. Verificar Take Profit
                if precio_actual >= op["take_profit"]:
                    await cerrar_operacion(op, "TP")
                    continue
                    
                # 4. Verificar Stop Loss dinámico
                ganancia = (op["max_precio"] - op["precio_entrada"]) / op["precio_entrada"]
                
                # Si lleva +1.5%, ajustar SL al 0.5% de ganancia
                if ganancia > 0.015:
                    nuevo_sl = op["precio_entrada"] * 1.005
                    op["stop_loss"] = max(op["stop_loss"], nuevo_sl)
                
                if precio_actual <= op["stop_loss"]:
                    await cerrar_operacion(op, "SL")
                    continue
                    
                # 5. Verificar tiempo máximo
                if (datetime.now() - op["hora_entrada"]).seconds > CONFIG_GLOBAL["duracion_maxima"] * 60:
                    await cerrar_operacion(op, "Tiempo")
                    continue
                    
            except Exception as e:
                logger.error(f"Error gestionando operación {op['par']}: {e}")
                continue

async def cerrar_operacion(operacion, motivo):
    """Cierra una operación y registra resultados"""
    try:
        trade = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        orden = trade.create_market_order(operacion["par"], "sell", operacion["cantidad"])
        fee = float(orden.get("fee", 0))
        
        # Calcular resultados
        precio_salida = float(orden["price"])
        ganancia_pct = ((precio_salida - operacion["precio_entrada"]) / operacion["precio_entrada"]) * 100
        ganancia_usdt = (precio_salida * operacion["cantidad"]) - (operacion["precio_entrada"] * operacion["cantidad"]) - fee - operacion["fee_compra"]
        
        operacion.update({
            "precio_salida": precio_salida,
            "hora_salida": datetime.now(),
            "ganancia_pct": ganancia_pct,
            "ganancia_usdt": ganancia_usdt,
            "motivo_salida": motivo,
            "fee_venta": fee
        })
        
        # Notificar cierre
        emoji = "🟢" if ganancia_usdt >= 0 else "🔴"
        await bot.send_message(
            os.getenv("CHAT_ID"),
            f"{emoji} SALIDA {operacion['par']}\n"
            f"📌 Motivo: {motivo}\n"
            f"🔢 Entrada: {operacion['precio_entrada']:.8f}\n"
            f"💰 Salida: {operacion['precio_salida']:.8f}\n"
            f"📈 Ganancia: {operacion['ganancia_pct']:.2f}%\n"
            f"💵 Balance: {operacion['ganancia_usdt']:.4f} USDT"
        )
        
        # Actualizar estado
        estado.operaciones_activas.remove(operacion)
        estado.historial.append(operacion)
        
    except Exception as e:
        logger.error(f"Error cerrando operación: {e}")

async def ciclo_trading():
    """Ciclo principal de trading"""
    logger.info("Iniciando estrategia de impulso...")
    
    while estado.activo:
        try:
            # 1. Gestionar operaciones abiertas
            await gestionar_operaciones()
            
            # 2. Buscar nuevas oportunidades (si no estamos al límite)
            if len(estado.operaciones_activas) < CONFIG_GLOBAL["max_operaciones"]:
                for par in PARES_OPERABLES:
                    if await verificar_cooldown(par):
                        continue
                        
                    señal = await detectar_impulso(par)
                    if señal:
                        await ejecutar_compra(señal)
                        await asyncio.sleep(5)  # Espera entre operaciones
            
            await asyncio.sleep(CONFIG_GLOBAL["intervalo_analisis"])
            
        except Exception as e:
            logger.error(f"Error en ciclo de trading: {e}")
            await asyncio.sleep(30)

# =================================================================
# COMANDOS DE TELEGRAM
# =================================================================

@dp.message(Command("start"))
async def iniciar_bot(message: types.Message):
    """Inicia el bot de trading"""
    if not estado.activo:
        estado.activo = True
        asyncio.create_task(ciclo_trading())
        
        await message.answer(
            "🚀 Bot de trading ACTIVADO\n"
            "Estrategia: Impulso de Mercado\n"
            f"Pares activos: {', '.join(PARES_OPERABLES.keys())}\n"
            f"Saldo mínimo: {CONFIG_GLOBAL['saldo_minimo']} USDT"
        )
    else:
        await message.answer("⚠ El bot ya está en funcionamiento")

@dp.message(Command("stop"))
async def detener_bot(message: types.Message):
    """Detiene el bot de trading"""
    estado.activo = False
    await message.answer(
        "🛑 Bot de trading DETENIDO\n"
        f"Operaciones activas: {len(estado.operaciones_activas)}"
    )

@dp.message(Command("status"))
async def estado_actual(message: types.Message):
    """Muestra el estado actual del bot"""
    saldo = await obtener_saldo_disponible()
    
    mensaje = (
        "📊 Estado Actual\n"
        f"• Bot: {'ACTIVO' if estado.activo else 'INACTIVO'}\n"
        f"• Saldo: {saldo:.2f} USDT\n"
        f"• Operaciones activas: {len(estado.operaciones_activas)}\n"
        f"• Última señal: {estado.ultimas_operaciones.get(list(PARES_OPERABLES.keys())[0], 'N/A')}"
    )
    
    await message.answer(mensaje)

# =================================================================
# FUNCIONES AUXILIARES
# =================================================================

async def obtener_saldo_disponible():
    """Obtiene el saldo disponible en KuCoin"""
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
    """Guarda el historial de operaciones"""
    try:
        with open('historial_operaciones.json', 'w') as f:
            json.dump(estado.historial, f, indent=4, default=str)
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

# =================================================================
# EJECUCIÓN PRINCIPAL
# =================================================================

async def main():
    """Función principal"""
    logger.info("=== INICIANDO BOT DE TRADING ===")
    
    try:
        # Verificar conexión a KuCoin
        market = Market()
        await asyncio.to_thread(market.get_ticker, "BTC-USDT")
        logger.info("Conexión a KuCoin establecida")
        
        # Iniciar bot de Telegram
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical(f"Error al iniciar: {e}")
    finally:
        await guardar_historial()
        await bot.session.close()
        logger.info("Bot detenido correctamente")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.critical(f"Error no manejado: {e}")