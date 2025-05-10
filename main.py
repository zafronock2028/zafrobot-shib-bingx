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
logger = logging.getLogger("KuCoin1MinBot")

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

# Pares seleccionados
PARES = [
    "SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT",
    "SUI-USDT", "TURBO-USDT", "BONK-USDT", "WIF-USDT"
]

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

CONFIG = {
    "uso_saldo": 0.75,
    "max_operaciones": 2,
    "puntaje_minimo": 2.8,
    "reanalisis_segundos": 15,
    "max_duracion_minutos": 20,
    "spread_maximo": 0.0015,
    "saldo_minimo": 20.00,
    "vol_minima": 500000,
    "min_ganancia_objetivo": 0.01,
    "nivel_proteccion": -0.01,
    "max_ops_mismo_par": 3,
    "horas_reset_ops": 6
}

# Variables globales
operaciones_activas = []
historial_operaciones = []
operaciones_recientes = {}
cooldown_activo = set()
bot_activo = False
lock = asyncio.Lock()

async def guardar_historial():
    """Guarda el historial de operaciones en un archivo JSON"""
    try:
        with open('historial_operaciones.json', 'w') as f:
            json.dump(historial_operaciones, f, indent=4, default=str)
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

async def verificar_cooldown(par):
    """Verifica si un par está en cooldown"""
    if par in cooldown_activo:
        config = PARES_CONFIG.get(par, {})
        cooldown = config.get("cooldown", 30)
        ultima_op = operaciones_recientes.get(par)
        
        if ultima_op and (datetime.now() - ultima_op).seconds < cooldown * 60:
            return True
        else:
            cooldown_activo.discard(par)
    return False

async def obtener_saldo_disponible():
    """Obtiene el saldo disponible en USDT"""
    try:
        accounts = user.get_account_list(currency="USDT", account_type="trade")
        if accounts:
            return float(accounts[0]['available'])
        return 0.0
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {e}")
        return 0.0

async def analizar_impulso(par):
    """Analiza el impulso del mercado usando velas de 1 minuto con nuevo criterio de 3 velas"""
    try:
        # Verificar volumen mínimo primero
        stats_24h = market.get_24h_stats(par)
        volumen_usdt = float(stats_24h["volValue"])
        if volumen_usdt < CONFIG["vol_minima"]:
            logger.info(f"Volumen insuficiente para {par}: {volumen_usdt:.2f} USDT")
            return None
            
        # Obtener datos de mercado con velas de 1 minuto (ahora solo necesitamos 3)
        velas = market.get_kline(symbol=par, kline_type="1min", limit=3)
        if not velas or len(velas) < 3:
            return None
            
        # Extraer datos de las últimas 3 velas
        vela_actual = float(velas[-1][2])  # Precio cierre actual
        vela_anterior = float(velas[-2][2])  # Precio cierre anterior
        vela_anterior2 = float(velas[-3][2])  # Precio cierre antepenúltima
        
        # Verificar 2 velas alcistas consecutivas (nuevo requisito)
        if not (vela_actual > vela_anterior and vela_anterior > vela_anterior2):
            logger.info(f"{par} no cumple con 2 velas alcistas consecutivas")
            return None
            
        ticker = market.get_ticker(par)
        spread_actual = (float(ticker["bestAsk"]) - float(ticker["bestBid"])) / float(ticker["bestAsk"])
        
        # Filtros estrictos de entrada
        if spread_actual > CONFIG["spread_maximo"]:
            return None
            
        # Cálculo de momentum basado en las 3 velas
        momentum_3velas = (vela_actual - vela_anterior2) / vela_anterior2
        
        # Umbral mínimo de movimiento (0.5% en 3 velas)
        if momentum_3velas < 0.005:
            return None
            
        # Cálculo de puntaje ajustado para el nuevo criterio
        puntaje = (
            (momentum_3velas * 3.0) +  # Mayor peso al momentum reciente
            (min(volumen_usdt, 2000000) / 1500000) +  # Volumen ajustado
            (PARES_CONFIG[par]["volatilidad"] * 0.5) -
            (spread_actual * 800)  # Mayor penalización por spread
        )
        
        if puntaje < CONFIG["puntaje_minimo"]:
            return None
            
        return {
            "par": par,
            "precio": vela_actual,
            "puntaje": puntaje,
            "volumen": volumen_usdt,
            "momentum": momentum_3velas,
            "spread": spread_actual,
            "min_required": PARES_CONFIG[par]["min"] * vela_actual
        }
    except Exception as e:
        logger.error(f"Error analizando {par}: {e}")
        return None

async def ejecutar_compra(operacion):
    """Ejecuta una orden de compra con gestión de riesgo"""
    try:
        saldo_disponible = await obtener_saldo_disponible()
        if saldo_disponible < CONFIG["saldo_minimo"]:
            logger.warning("Saldo insuficiente para operar")
            return None
            
        monto_usdt = saldo_disponible * CONFIG["uso_saldo"] / CONFIG["max_operaciones"]
        cantidad = monto_usdt / operacion["precio"]
        
        # Ajustar cantidad según incrementos del par
        config_par = PARES_CONFIG[operacion["par"]]
        cantidad = cantidad - (cantidad % config_par["inc"])
        
        if cantidad < config_par["min"]:
            logger.warning(f"Cantidad muy pequeña para {operacion['par']}: {cantidad}")
            return None
            
        order = trade.create_market_order(operacion["par"], "buy", cantidad)
        logger.info(f"Orden de compra ejecutada: {order}")
        
        operacion.update({
            "id_orden": order["orderId"],
            "cantidad": cantidad,
            "precio_entrada": float(order["price"]),
            "hora_entrada": datetime.now(),
            "stop_loss": operacion["precio"] * (1 + CONFIG["nivel_proteccion"]),
            "take_profit": operacion["precio"] * (1 + CONFIG["min_ganancia_objetivo"]),
            "max_precio": operacion["precio"]
        })
        
        await bot.send_message(
            CHAT_ID,
            f"🚀 ENTRADA en {operacion['par']}\n"
            f"📊 Precio: {operacion['precio']:.8f}\n"
            f"💰 Cantidad: {cantidad:.2f}\n"
            f"📈 Objetivo: {operacion['take_profit']:.8f}\n"
            f"🛑 Stop: {operacion['stop_loss']:.8f}"
        )
        
        operaciones_activas.append(operacion)
        operaciones_recientes[operacion["par"]] = datetime.now()
        cooldown_activo.add(operacion["par"])
        
        return operacion
    except Exception as e:
        logger.error(f"Error ejecutando compra: {e}")
        return None

async def trailing_stop(operacion):
    """Actualiza el stop loss según el movimiento del precio"""
    try:
        ticker = market.get_ticker(operacion["par"])
        precio_actual = float(ticker["price"])
        
        # Actualizar precio máximo alcanzado
        if precio_actual > operacion["max_precio"]:
            operacion["max_precio"] = precio_actual
            nuevo_stop = precio_actual * (1 + CONFIG["nivel_proteccion"])
            if nuevo_stop > operacion["stop_loss"]:
                operacion["stop_loss"] = nuevo_stop
                logger.info(f"Actualizado stop loss para {operacion['par']} a {nuevo_stop:.8f}")
                
        # Verificar si se activó el stop loss
        if precio_actual <= operacion["stop_loss"]:
            logger.info(f"Stop loss alcanzado en {operacion['par']}")
            await ejecutar_venta(operacion, "stop_loss")
            return True
            
        # Verificar si se alcanzó el take profit
        if precio_actual >= operacion["take_profit"]:
            logger.info(f"Take profit alcanzado en {operacion['par']}")
            await ejecutar_venta(operacion, "take_profit")
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error en trailing stop: {e}")
        return False

async def ejecutar_venta(operacion, motivo):
    """Ejecuta una orden de venta y registra el resultado"""
    try:
        order = trade.create_market_order(operacion["par"], "sell", operacion["cantidad"])
        logger.info(f"Orden de venta ejecutada: {order}")
        
        precio_salida = float(order["price"])
        ganancia = (precio_salida - operacion["precio_entrada"]) / operacion["precio_entrada"]
        
        operacion.update({
            "id_orden_venta": order["orderId"],
            "precio_salida": precio_salida,
            "hora_salida": datetime.now(),
            "ganancia": ganancia,
            "motivo_salida": motivo
        })
        
        # Mensaje de Telegram con resultado
        emoji = "🔴" if ganancia < 0 else "🟢"
        await bot.send_message(
            CHAT_ID,
            f"{emoji} SALIDA en {operacion['par']}\n"
            f"Motivo: {motivo}\n"
            f"Entrada: {operacion['precio_entrada']:.8f}\n"
            f"Salida: {precio_salida:.8f}\n"
            f"Ganancia: {ganancia*100:.2f}%\n"
            f"Duración: {(operacion['hora_salida'] - operacion['hora_entrada']).seconds // 60} minutos"
        )
        
        # Mover a historial
        async with lock:
            operaciones_activas.remove(operacion)
            historial_operaciones.append(operacion)
            await guardar_historial()
            
        return True
    except Exception as e:
        logger.error(f"Error ejecutando venta: {e}")
        return False

async def ciclo_trading():
    """Ciclo principal de trading"""
    global bot_activo
    
    while bot_activo:
        try:
            async with lock:
                if len(operaciones_activas) >= CONFIG["max_operaciones"]:
                    await asyncio.sleep(CONFIG["reanalisis_segundos"])
                    continue
                    
                saldo = await obtener_saldo_disponible()
                if saldo < CONFIG["saldo_minimo"]:
                    logger.warning("Saldo insuficiente para operar")
                    await asyncio.sleep(60)
                    continue
                    
                # Analizar todos los pares posibles
                oportunidades = []
                for par in PARES:
                    if await verificar_cooldown(par):
                        continue
                        
                    # Verificar operaciones recientes en el mismo par
                    ops_mismo_par = sum(1 for op in operaciones_activas if op["par"] == par)
                    if ops_mismo_par >= CONFIG["max_ops_mismo_par"]:
                        continue
                        
                    analisis = await analizar_impulso(par)
                    if analisis:
                        oportunidades.append(analisis)
                
                # Ordenar oportunidades por puntaje
                oportunidades.sort(key=lambda x: x["puntaje"], reverse=True)
                
                # Ejecutar las mejores oportunidades
                for op in oportunidades[:CONFIG["max_operaciones"] - len(operaciones_activas)]:
                    await ejecutar_compra(op)
                    await asyncio.sleep(1)  # Pequeña pausa entre órdenes
                    
                # Gestionar operaciones activas
                for op in operaciones_activas[:]:
                    # Verificar tiempo máximo
                    if (datetime.now() - op["hora_entrada"]).seconds > CONFIG["max_duracion_minutos"] * 60:
                        await ejecutar_venta(op, "tiempo_excedido")
                        continue
                        
                    # Gestionar trailing stop
                    await trailing_stop(op)
                    
            await asyncio.sleep(CONFIG["reanalisis_segundos"])
            
        except Exception as e:
            logger.error(f"Error en ciclo de trading: {e}")
            await asyncio.sleep(30)

# Comandos de Telegram
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    global bot_activo
    if not bot_activo:
        bot_activo = True
        asyncio.create_task(ciclo_trading())
        await message.answer("🚀 Bot de trading iniciado")
    else:
        await message.answer("⚠ El bot ya está en funcionamiento")

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    global bot_activo
    bot_activo = False
    await message.answer("🛑 Bot de trading detenido")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    saldo = await obtener_saldo_disponible()
    status = (
        f"📊 Estado del Bot\n"
        f"🔵 Operaciones activas: {len(operaciones_activas)}\n"
        f"💰 Saldo disponible: {saldo:.2f} USDT\n"
        f"📈 Historial: {len(historial_operaciones)} operaciones\n"
        f"🔄 Estado: {'ACTIVO' if bot_activo else 'INACTIVO'}"
    )
    await message.answer(status)

@dp.message(Command("operaciones"))
async def cmd_operaciones(message: types.Message):
    if not operaciones_activas:
        await message.answer("No hay operaciones activas")
        return
        
    respuesta = "📈 Operaciones Activas:\n\n"
    for op in operaciones_activas:
        duracion = (datetime.now() - op["hora_entrada"]).seconds // 60
        ganancia_actual = ((op["max_precio"] - op["precio_entrada"]) / op["precio_entrada"]) * 100
        respuesta += (
            f"🔹 {op['par']}\n"
            f"Entrada: {op['precio_entrada']:.8f}\n"
            f"Actual: {op['max_precio']:.8f}\n"
            f"Ganancia: {ganancia_actual:.2f}%\n"
            f"Stop: {op['stop_loss']:.8f}\n"
            f"Duración: {duracion} min\n\n"
        )
    await message.answer(respuesta)

async def main():
    # Cargar historial previo si existe
    global historial_operaciones
    try:
        with open('historial_operaciones.json', 'r') as f:
            historial_operaciones = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"Error cargando historial: {e}")
    
    # Iniciar bot de Telegram
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())