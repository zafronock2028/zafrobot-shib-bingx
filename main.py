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

load_dotenv()

# Validación de variables de entorno
REQUIRED_ENV_VARS = ["TELEGRAM_TOKEN", "CHAT_ID", "API_KEY", "SECRET_KEY", "API_PASSPHRASE"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Faltan variables de entorno: {', '.join(missing_vars)}")

# Configuración de logging profesional
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
# CONFIGURACIÓN OPTIMIZADA DE ESTRATEGIA
# =================================================================

PARES_CONFIG = {
    "SHIB-USDT": {
        "inc": 1000,
        "min": 3.80,
        "vol_min": 1200000,
        "momentum_min": 0.006,
        "cooldown": 15,
        "max_ops_dia": 6,
        "tp": 0.022,
        "sl": 0.013,
        "trailing_stop": True,
        "trailing_offset": 0.003,
        "slippage": 0.0025
    },
    "PEPE-USDT": {
        "inc": 100000,
        "min": 4.20,
        "vol_min": 1500000,
        "momentum_min": 0.007,
        "cooldown": 20,
        "max_ops_dia": 7,
        "tp": 0.028,
        "sl": 0.015,
        "trailing_stop": True,
        "trailing_offset": 0.004,
        "slippage": 0.0028
    },
    "FLOKI-USDT": {
        "inc": 1000,
        "min": 3.80,
        "vol_min": 1400000,
        "momentum_min": 0.0065,
        "cooldown": 25,
        "max_ops_dia": 6,
        "tp": 0.024,
        "sl": 0.013,
        "trailing_stop": True,
        "trailing_offset": 0.0035,
        "slippage": 0.0026
    },
    "WIF-USDT": {
        "inc": 1,
        "min": 4.50,
        "vol_min": 2000000,
        "momentum_min": 0.010,
        "cooldown": 15,
        "max_ops_dia": 5,
        "tp": 0.038,
        "sl": 0.018,
        "trailing_stop": True,
        "trailing_offset": 0.005,
        "slippage": 0.0030
    },
    "BONK-USDT": {
        "inc": 10000,
        "min": 4.20,
        "vol_min": 2500000,
        "momentum_min": 0.008,
        "cooldown": 20,
        "max_ops_dia": 6,
        "tp": 0.032,
        "sl": 0.016,
        "trailing_stop": True,
        "trailing_offset": 0.004,
        "slippage": 0.0027
    },
    "BTC3L-USDT": {
        "inc": 0.01,
        "min": 7.00,
        "vol_min": 4000000,
        "momentum_min": 0.012,
        "cooldown": 12,
        "max_ops_dia": 4,
        "tp": 0.055,
        "sl": 0.028,
        "trailing_stop": True,
        "trailing_offset": 0.006,
        "slippage": 0.0035
    },
    "ETH3L-USDT": {
        "inc": 0.01,
        "min": 6.50,
        "vol_min": 3500000,
        "momentum_min": 0.011,
        "cooldown": 12,
        "max_ops_dia": 4,
        "tp": 0.048,
        "sl": 0.022,
        "trailing_stop": True,
        "trailing_offset": 0.005,
        "slippage": 0.0032
    },
    "JUP-USDT": {
        "inc": 10,
        "min": 4.75,
        "vol_min": 1800000,
        "momentum_min": 0.009,
        "cooldown": 25,
        "max_ops_dia": 5,
        "tp": 0.030,
        "sl": 0.015,
        "trailing_stop": True,
        "trailing_offset": 0.003,
        "slippage": 0.0025
    }
}

CONFIG = {
    "uso_saldo": 0.85,
    "max_operaciones": 2,
    "intervalo_analisis": 8,
    "saldo_minimo": 10.00,
    "proteccion_ganancia": 0.012,
    "lock_ganancia": 0.004,
    "max_duracion": 25,
    "max_slippage": 0.002,
    "hora_reseteo": "00:00"
}

# =================================================================
# SISTEMA DE ESTADO
# =================================================================

class EstadoTrading:
    def __init__(self):
        self.operaciones_activas = []
        self.historial = []
        self.cooldowns = set()
        self.activo = False
        self.lock = asyncio.Lock()
        self.ultima_conexion = None
        self.pares_en_analisis = set()
        self.contador_operaciones = {}
        self.ultimo_reseteo = self.obtener_hora_reseteo()
        
    def obtener_hora_reseteo(self):
        hoy = datetime.utcnow().date()
        hora, minuto = map(int, CONFIG["hora_reseteo"].split(':'))
        return datetime.combine(hoy, datetime.min.time()).replace(hour=hora, minute=minuto)

estado = EstadoTrading()

# =================================================================
# MONITOR DE PRECIOS
# =================================================================

class PriceMonitor:
    def __init__(self):
        self.precios = {}
        self.ws_task = None
        
    async def conectar_websocket(self):
        while True:
            try:
                await asyncio.sleep(1)
                for par in PARES_CONFIG:
                    market = Market()
                    ticker = await asyncio.to_thread(market.get_ticker, par)
                    self.precios[par] = float(ticker["price"])
            except Exception as e:
                logger.error(f"Error en WebSocket: {e}")
                await asyncio.sleep(5)

price_monitor = PriceMonitor()

# =================================================================
# CORE DEL BOT - FUNCIONES PRINCIPALES
# =================================================================

async def verificar_conexion_kucoin():
    try:
        market = Market()
        ticker = await asyncio.to_thread(market.get_ticker, "BTC-USDT")
        estado.ultima_conexion = datetime.now()
        return True
    except Exception as e:
        logger.error(f"Error de conexión con KuCoin: {e}")
        return False

async def obtener_saldo_disponible():
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

async def calcular_posicion(par, saldo_disponible, precio_entrada):
    try:
        config = PARES_CONFIG[par]
        saldo_asignado = saldo_disponible * CONFIG["uso_saldo"]
        
        cantidad = (saldo_asignado / precio_entrada) * 0.995
        cantidad = (cantidad // config["inc"]) * config["inc"]
        
        valor_operacion = cantidad * precio_entrada
        
        logger.info(f"{par} - Cálculo posición: "
                   f"Cantidad={cantidad:.8f}, "
                   f"Valor={valor_operacion:.2f} USDT, "
                   f"Mínimo={config['min']} USDT")
        
        if valor_operacion < config["min"]:
            logger.warning(f"{par} - Operación bajo mínimo: {valor_operacion:.2f} < {config['min']}")
            return None
            
        return cantidad if valor_operacion >= CONFIG["saldo_minimo"] else None
        
    except Exception as e:
        logger.error(f"Error calculando posición {par}: {e}")
        return None

async def detectar_oportunidad(par):
    try:
        if not await verificar_conexion_kucoin():
            logger.warning(f"{par} - Descartado: Error de conexión")
            return None

        market = Market(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        stats = await asyncio.to_thread(market.get_24h_stats, par)
        volumen_actual = float(stats["volValue"])
        if volumen_actual < PARES_CONFIG[par]["vol_min"]:
            logger.warning(f"{par} - Descartado: Volumen insuficiente ({volumen_actual:.2f} < {PARES_CONFIG[par]['vol_min']})")
            return None

        velas = await asyncio.to_thread(
            market.get_kline, 
            symbol=par, 
            kline_type="1min", 
            limit=3
        )
        
        if len(velas) < 3:
            logger.warning(f"{par} - Descartado: Datos insuficientes ({len(velas)} velas)")
            return None

        cierres = [float(v[2]) for v in velas]
        if not (cierres[2] > cierres[1] > cierres[0]):
            logger.warning(f"{par} - Descartado: Tendencia no alcista ({cierres[0]} > {cierres[1]} > {cierres[2]})")
            return None

        momentum = (cierres[2] - cierres[0]) / cierres[0]
        if momentum < PARES_CONFIG[par]["momentum_min"]:
            logger.warning(f"{par} - Descartado: Momentum insuficiente ({momentum:.4%} < {PARES_CONFIG[par]['momentum_min']:.4%})")
            return None

        ticker = await asyncio.to_thread(market.get_ticker, par)
        best_ask = float(ticker["bestAsk"])
        best_bid = float(ticker["bestBid"])
        spread = (best_ask - best_bid) / best_ask
        if spread > 0.002:
            logger.warning(f"{par} - Descartado: Spread demasiado alto ({spread:.4%})")
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
    try:
        async with estado.lock:
            if len(estado.operaciones_activas) >= CONFIG["max_operaciones"]:
                return None

            if estado.contador_operaciones.get(señal["par"], 0) >= PARES_CONFIG[señal["par"]]["max_ops_dia"]:
                return None

        if not await verificar_slippage(señal["par"], señal["precio"]):
            return None

        saldo = await obtener_saldo_disponible()
        if saldo < CONFIG["saldo_minimo"]:
            return None

        cantidad = await calcular_posicion(señal["par"], saldo, señal["precio"])
        if not cantidad:
            return None

        trade = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        for intento in range(3):
            try:
                orden = await asyncio.to_thread(
                    trade.create_market_order,
                    señal["par"], "buy", cantidad
                )
                break
            except Exception as e:
                if intento == 2:
                    await notificar_error(f"Error crítico en {señal['par']}: {str(e)}")
                    return None
                await asyncio.sleep(1)
        
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

        await notificar_operacion(operacion, "ENTRADA")
        
        async with estado.lock:
            estado.operaciones_activas.append(operacion)
            estado.cooldowns.add(operacion["par"])
            estado.contador_operaciones[señal["par"]] = estado.contador_operaciones.get(señal["par"], 0) + 1
            
        return operacion

    except Exception as e:
        logger.error(f"Error ejecutando operación: {e}")
        return None

async def cerrar_operacion(operacion, motivo):
    try:
        trade = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        for intento in range(3):
            try:
                orden_venta = await asyncio.to_thread(
                    trade.create_market_order,
                    operacion["par"], "sell", operacion["cantidad"]
                )
                break
            except Exception as e:
                if intento == 2:
                    raise
                await asyncio.sleep(2)
        
        precio_salida = float(orden_venta["price"])
        fee_venta = float(orden_venta.get("fee", 0))
        ganancia_neto = (precio_salida * operacion["cantidad"]) - (operacion["precio_entrada"] * operacion["cantidad"]) - operacion["fee_compra"] - fee_venta
        
        operacion.update({
            "precio_salida": precio_salida,
            "hora_salida": datetime.now(),
            "motivo_salida": motivo,
            "fee_venta": fee_venta,
            "ganancia_neto": ganancia_neto
        })
        
        await notificar_operacion(operacion, "SALIDA")
        
        async with estado.lock:
            estado.historial.append(operacion)
            estado.operaciones_activas.remove(operacion)
            estado.cooldowns.add(operacion["par"])
            
        await guardar_historial()
        
    except Exception as e:
        logger.error(f"Error cerrando operación {operacion['par']}: {e}")
        await notificar_error(f"Error al cerrar {operacion['par']}: {str(e)}")

async def gestionar_operaciones_activas():
    async with estado.lock:
        for op in estado.operaciones_activas[:]:
            try:
                market = Market(
                    key=os.getenv("API_KEY"),
                    secret=os.getenv("SECRET_KEY"),
                    passphrase=os.getenv("API_PASSPHRASE")
                )
                ticker = await asyncio.to_thread(market.get_ticker, op["par"])
                precio_actual = float(ticker["price"])
                
                op["max_precio"] = max(op["max_precio"], precio_actual)
                max_ganancia = (op["max_precio"] - op["precio_entrada"]) / op["precio_entrada"]
                
                if PARES_CONFIG[op["par"]]["trailing_stop"] and max_ganancia > CONFIG["proteccion_ganancia"]:
                    nuevo_sl = op["precio_entrada"] * (1 + max_ganancia - PARES_CONFIG[op["par"]]["trailing_offset"])
                    op["stop_loss"] = max(op["stop_loss"], nuevo_sl)
                
                motivo = None
                if precio_actual >= op["take_profit"]:
                    motivo = "TP"
                elif precio_actual <= op["stop_loss"]:
                    motivo = "SL"
                elif (datetime.now() - op["hora_entrada"]).seconds > CONFIG["max_duracion"] * 60:
                    motivo = "TIEMPO"
                
                if motivo:
                    await cerrar_operacion(op, motivo)
                    
            except Exception as e:
                logger.error(f"Error gestionando operación {op['par']}: {e}")

async def verificar_cooldown(par):
    ahora = datetime.utcnow()
    if ahora > estado.ultimo_reseteo + timedelta(days=1):
        estado.contador_operaciones = {}
        estado.ultimo_reseteo = estado.obtener_hora_reseteo()
    
    if estado.contador_operaciones.get(par, 0) >= PARES_CONFIG[par]["max_ops_dia"]:
        return True
    
    if par in estado.cooldowns:
        ultima_op = next((op for op in estado.historial if op["par"] == par), None)
        if ultima_op and (ahora - ultima_op["hora_entrada"]).seconds < PARES_CONFIG[par]["cooldown"] * 60:
            return True
    
    return False

async def verificar_slippage(par, precio_esperado):
    market = Market(
        key=os.getenv("API_KEY"),
        secret=os.getenv("SECRET_KEY"),
        passphrase=os.getenv("API_PASSPHRASE")
    )
    ticker = await asyncio.to_thread(market.get_ticker, par)
    best_ask = float(ticker["bestAsk"])
    
    slippage = abs(best_ask - precio_esperado) / precio_esperado
    if slippage > PARES_CONFIG[par]["slippage"]:
        logger.warning(f"Slippage excesivo en {par}: {slippage:.4%}")
        return False
    return True

async def guardar_historial():
    try:
        async with estado.lock:
            with open('historial_operaciones.json', 'w') as f:
                json.dump(estado.historial, f, indent=4, default=str)
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

# =================================================================
# INTERFAZ DE TELEGRAM
# =================================================================

async def notificar_operacion(operacion, tipo):
    try:
        if tipo == "ENTRADA":
            mensaje = (
                f"🚀 ENTRADA {operacion['par']}\n"
                f"📊 Cantidad: {operacion['cantidad']:.2f}\n"
                f"💰 Precio: {operacion['precio_entrada']:.8f}\n"
                f"🎯 TP: {operacion['take_profit']:.8f}\n"
                f"🛑 SL: {operacion['stop_loss']:.8f}"
            )
        else:
            ganancia_pct = ((operacion["precio_salida"] - operacion["precio_entrada"]) / operacion["precio_entrada"]) * 100
            mensaje = (
                f"{'🟢' if operacion['ganancia_neto'] >= 0 else '🔴'} SALIDA {operacion['par']}\n"
                f"📌 Motivo: {operacion['motivo_salida']}\n"
                f"💵 Entrada: {operacion['precio_entrada']:.8f}\n"
                f"💰 Salida: {operacion['precio_salida']:.8f}\n"
                f"📈 Ganancia: {ganancia_pct:.2f}%\n"
                f"⏱ Duración: {(operacion['hora_salida'] - operacion['hora_entrada']).seconds // 60} min"
            )
        
        await bot.send_message(os.getenv("CHAT_ID"), mensaje)
        
    except Exception as e:
        logger.error(f"Error en notificación: {e}")

async def notificar_error(mensaje):
    try:
        await bot.send_message(
            os.getenv("CHAT_ID"),
            f"🚨 ERROR CRÍTICO 🚨\n{mensaje}"
        )
    except Exception as e:
        logger.error(f"Error notificando error: {e}")

async def crear_menu_principal():
    return InlineKeyboardMarkup(inline_keyboard=[
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

# =================================================================
# REGISTRO DE HANDLERS CORREGIDO
# =================================================================

async def register_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def comando_inicio(message: types.Message):
        try:
            if not await verificar_conexion_kucoin():
                await message.answer("⚠ Error de conexión con KuCoin")
                return
                
            await message.answer(
                "🤖 KuCoin Pro Bot - Listo",
                reply_markup=await crear_menu_principal()
            )
        except Exception as e:
            logger.error(f"Error en comando inicio: {e}")

    @dp.message(Command("stop"))
    async def comando_stop(message: types.Message):
        estado.activo = False
        await message.answer("🛑 Bot detenido manualmente")

    @dp.callback_query(lambda c: c.data == "iniciar_bot")
    async def iniciar_bot(callback: types.CallbackQuery):
        try:
            if estado.activo:
                await callback.answer("⚠ Bot ya activo")
                return

            if not await verificar_conexion_kucoin():
                await callback.answer("⚠ Error de conexión")
                return

            estado.activo = True
            asyncio.create_task(ciclo_trading())

            await callback.message.edit_text(
                "🚀 Bot ACTIVADO\n"
                f"🔹 Pares activos: {len(PARES_CONFIG)}\n"
                f"🔹 Saldo mínimo: {CONFIG['saldo_minimo']} USDT",
                reply_markup=await crear_menu_principal()
            )
        except Exception as e:
            logger.error(f"Error al iniciar bot: {e}")

    @dp.callback_query(lambda c: c.data == "detener_bot")
    async def detener_bot(callback: types.CallbackQuery):
        try:
            estado.activo = False
            mensaje = "🛑 Bot detenido"
            
            if callback.message.text != mensaje:
                await callback.message.edit_text(
                    mensaje,
                    reply_markup=await crear_menu_principal()
                )
            else:
                await callback.answer("✅ Bot ya estaba detenido")
                
        except Exception as e:
            logger.error(f"Error deteniendo bot: {e}")

    @dp.callback_query(lambda c: c.data == "ver_historial")
    async def mostrar_historial(callback: types.CallbackQuery):
        try:
            if not estado.historial:
                await callback.answer("No hay operaciones en el historial", show_alert=True)
                return
                
            historial_reverso = estado.historial[-5:][::-1]
            mensaje = "📜 Últimas 5 operaciones:\n\n"
            
            for op in historial_reverso:
                ganancia = ((op["precio_salida"] - op["precio_entrada"]) / op["precio_entrada"]) * 100
                mensaje += (
                    f"🔹 {op['par']} ({op['motivo_salida']})\n"
                    f"📈 {ganancia:.2f}% | ⏱ {((op['hora_salida'] - op['hora_entrada']).seconds // 60} min\n"
                    f"🕒 {op['hora_entrada'].strftime('%H:%M')} - {op['hora_salida'].strftime('%H:%M')}\n\n"
                )
            
            if callback.message.text != mensaje.strip():
                await callback.message.edit_text(
                    mensaje,
                    reply_markup=await crear_menu_principal()
                )
            else:
                await callback.answer("✅ Datos actualizados")
                
        except Exception as e:
            logger.error(f"Error mostrando historial: {e}")

    @dp.callback_query(lambda c: c.data == "ver_balance")
    async def mostrar_balance(callback: types.CallbackQuery):
        try:
            saldo = await obtener_saldo_disponible()
            mensaje = f"💰 Balance disponible: {saldo:.2f} USDT"
            
            if callback.message.text != mensaje:
                await callback.message.edit_text(
                    mensaje,
                    reply_markup=await crear_menu_principal()
                )
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Error mostrando balance: {e}")
            await callback.answer("⚠ Error obteniendo balance", show_alert=True)

    @dp.callback_query(lambda c: c.data == "ver_operaciones")
    async def mostrar_operaciones(callback: types.CallbackQuery):
        try:
            if not estado.operaciones_activas:
                await callback.answer("No hay operaciones activas", show_alert=True)
                return
                
            mensaje = "📊 Operaciones activas:\n\n"
            market = Market()
            
            for op in estado.operaciones_activas:
                ticker = await asyncio.to_thread(market.get_ticker, op["par"])
                precio_actual = float(ticker["price"])
                ganancia_pct = ((precio_actual - op["precio_entrada"]) / op["precio_entrada"]) * 100
                
                mensaje += (
                    f"🔹 {op['par']}\n"
                    f"• Entrada: {op['precio_entrada']:.8f}\n"
                    f"• Actual: {precio_actual:.8f}\n"
                    f"• Ganancia: {ganancia_pct:.2f}%\n"
                    f"• Hora entrada: {op['hora_entrada'].strftime('%H:%M:%S')}\n\n"
                )
            
            if callback.message.text != mensaje.strip():
                await callback.message.edit_text(
                    mensaje,
                    reply_markup=await crear_menu_principal()
                )
            else:
                await callback.answer("✅ Datos actualizados")
                
        except Exception as e:
            logger.error(f"Error mostrando operaciones: {e}")
            await callback.answer("⚠ Error obteniendo operaciones", show_alert=True)

# =================================================================
# CICLO PRINCIPAL
# =================================================================

async def ciclo_trading():
    logger.info("Iniciando ciclo de trading...")
    asyncio.create_task(price_monitor.conectar_websocket())
    
    while estado.activo:
        logger.info(f"Estado activo: {estado.activo}")
        try:
            if not await verificar_conexion_kucoin():
                await asyncio.sleep(30)
                continue
                
            await gestionar_operaciones_activas()
            
            async with estado.lock:
                if len(estado.operaciones_activas) < CONFIG["max_operaciones"]:
                    logger.info(f"Escaneando {len(PARES_CONFIG)} pares | Operaciones activas: {len(estado.operaciones_activas)}")
                    for par in PARES_CONFIG:
                        if par in estado.pares_en_analisis:
                            continue
                            
                        estado.pares_en_analisis.add(par)
                        try:
                            if await verificar_cooldown(par):
                                logger.debug(f"{par} en cooldown")
                                continue
                                
                            señal = await detectar_oportunidad(par)
                            if señal:
                                logger.info(f"Señal detectada en {par} | Momentum: {señal['momentum']:.4%}")
                                if await verificar_slippage(par, señal["precio"]):
                                    operacion = await ejecutar_operacion(señal)
                                    if operacion:
                                        await asyncio.sleep(1.5)
                        finally:
                            estado.pares_en_analisis.discard(par)
            
            await asyncio.sleep(CONFIG["intervalo_analisis"])
            
        except Exception as e:
            logger.error(f"Error en ciclo trading: {e}")

async def ejecutar_bot():
    logger.info("=== INICIANDO BOT ===")
    global bot
    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
    dp = Dispatcher()
    
    try:
        await register_handlers(dp)
        
        if not await verificar_conexion_kucoin():
            logger.error("Error de conexión inicial con KuCoin")
            return
            
        try:
            if os.path.exists('historial_operaciones.json') and os.path.getsize('historial_operaciones.json') > 0:
                with open('historial_operaciones.json', 'r') as f:
                    estado.historial = json.load(f)
                logger.info(f"Historial cargado ({len(estado.historial)} ops)")
            else:
                logger.info("Sin historial previo o archivo vacío")
        except Exception as e:
            logger.error(f"Error cargando historial: {e}")
            
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
    finally:
        estado.activo = False
        await guardar_historial()
        await bot.close()
        logger.info("Bot detenido correctamente")

if __name__ == "__main__":
    try:
        asyncio.run(ejecutar_bot())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.critical(f"Error crítico: {e}")