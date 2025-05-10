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
        "operaciones_diarias": 5,    # Máx operaciones por día
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
# FUNCIONES PARA BOTONES DE TELEGRAM
# =================================================================

async def crear_menu_principal():
    """Crea el menú principal con botones inline"""
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
            InlineKeyboardButton(text="⚙ Configuración", callback_data="ver_config")
        ]
    ])
    return keyboard

async def crear_menu_operacion(par):
    """Crea menú para una operación específica"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Ver Detalles", callback_data=f"detalles_{par}"),
            InlineKeyboardButton(text="🗑 Cerrar Manual", callback_data=f"cerrar_{par}")
        ],
        [
            InlineKeyboardButton(text="🔙 Menú Principal", callback_data="menu_principal")
        ]
    ])
    return keyboard

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
        
        # 4. Notificar entrada con botones
        keyboard = await crear_menu_operacion(señal["par"])
        await bot.send_message(
            os.getenv("CHAT_ID"),
            f"🚀 ENTRADA {operacion['par']}\n"
            f"💵 Precio: {operacion['precio_entrada']:.8f}\n"
            f"📈 Objetivo: {operacion['take_profit']:.8f}\n"
            f"🛑 Stop: {operacion['stop_loss']:.8f}\n"
            f"📊 Cantidad: {operacion['cantidad']:.2f}",
            reply_markup=keyboard
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
        
        # Notificar cierre con botones
        emoji = "🟢" if ganancia_usdt >= 0 else "🔴"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Ver Historial", callback_data="ver_historial")]
        ])
        
        await bot.send_message(
            os.getenv("CHAT_ID"),
            f"{emoji} SALIDA {operacion['par']}\n"
            f"📌 Motivo: {motivo}\n"
            f"🔢 Entrada: {operacion['precio_entrada']:.8f}\n"
            f"💰 Salida: {operacion['precio_salida']:.8f}\n"
            f"📈 Ganancia: {operacion['ganancia_pct']:.2f}%\n"
            f"💵 Balance: {operacion['ganancia_usdt']:.4f} USDT",
            reply_markup=keyboard
        )
        
        # Actualizar estado
        estado.operaciones_activas.remove(operacion)
        estado.historial.append(operacion)
        
    except Exception as e:
        logger.error(f"Error cerrando operación: {e}")

# =================================================================
# HANDLERS DE COMANDOS Y CALLBACKS
# =================================================================

@dp.message(Command("start", "menu"))
async def comando_inicio(message: types.Message):
    """Muestra el menú principal"""
    await message.answer(
        "🤖 KuCoin Trading Bot - Estrategia de Impulso\n"
        "Selecciona una opción:",
        reply_markup=await crear_menu_principal()
    )

@dp.callback_query(lambda c: c.data == "menu_principal")
async def volver_menu(callback: types.CallbackQuery):
    """Vuelve al menú principal"""
    await callback.message.edit_text(
        "🤖 KuCoin Trading Bot - Estrategia de Impulso\n"
        "Selecciona una opción:",
        reply_markup=await crear_menu_principal()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "iniciar_bot")
async def iniciar_bot(callback: types.CallbackQuery):
    """Inicia el bot de trading"""
    if not estado.activo:
        estado.activo = True
        asyncio.create_task(ciclo_trading())
        
        await callback.message.edit_text(
            "🚀 Bot de trading ACTIVADO\n"
            "Estrategia: Impulso de Mercado\n"
            f"Pares activos: {', '.join(PARES_OPERABLES.keys())}",
            reply_markup=await crear_menu_principal()
        )
    else:
        await callback.answer("⚠ El bot ya está en funcionamiento", show_alert=True)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "ver_balance")
async def mostrar_balance(callback: types.CallbackQuery):
    """Muestra el balance actual"""
    saldo = await obtener_saldo_disponible()
    pares_viables = [p for p in PARES_OPERABLES if PARES_OPERABLES[p]["min_cantidad"] * 0.001 <= saldo * 0.9]
    
    await callback.message.edit_text(
        f"💰 Balance Actual:\n"
        f"• Saldo disponible: {saldo:.2f} USDT\n"
        f"• Mínimo requerido: {CONFIG_GLOBAL['saldo_minimo']:.2f} USDT\n"
        f"• Pares viables: {', '.join(pares_viables[:5])}...",
        reply_markup=await crear_menu_principal()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("detalles_"))
async def ver_detalles_operacion(callback: types.CallbackQuery):
    """Muestra detalles de una operación específica"""
    par = callback.data.replace("detalles_", "")
    operacion = next((op for op in estado.operaciones_activas if op["par"] == par), None)
    
    if not operacion:
        await callback.answer("Operación no encontrada", show_alert=True)
        return
    
    duracion = (datetime.now() - operacion["hora_entrada"]).seconds // 60
    ganancia_actual = ((operacion["max_precio"] - operacion["precio_entrada"]) / operacion["precio_entrada"]) * 100
    
    mensaje = (
        f"📊 Detalles de {par}\n"
        f"🕒 Hora entrada: {operacion['hora_entrada'].strftime('%H:%M:%S')}\n"
        f"⏱ Duración: {duracion} minutos\n"
        f"💰 Precio entrada: {operacion['precio_entrada']:.8f}\n"
        f"📈 Precio actual: {operacion['max_precio']:.8f}\n"
        f"🚀 Ganancia actual: {ganancia_actual:.2f}%\n"
        f"🎯 Take Profit: {operacion['take_profit']:.8f}\n"
        f"🛑 Stop Loss: {operacion['stop_loss']:.8f}"
    )
    
    await callback.message.edit_text(
        mensaje,
        reply_markup=await crear_menu_operacion(par)
    )
    await callback.answer()

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
        await bot.session.close()
        logger.info("Bot detenido correctamente")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.critical(f"Error no manejado: {e}")