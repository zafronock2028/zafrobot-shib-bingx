import os
import logging
import asyncio
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from kucoin.client import Trade, Market, User
from dotenv import load_dotenv

load_dotenv()

# =================================================================
# VALIDACIÓN DE VARIABLES DE ENTORNO
# =================================================================
REQUIRED_ENV_VARS = ["TELEGRAM_TOKEN", "CHAT_ID", "API_KEY", "SECRET_KEY", "API_PASSPHRASE"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Faltan variables de entorno: {', '.join(missing_vars)}")

# =================================================================
# CONFIGURACIÓN DE LOGGING
# =================================================================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_bot.log')
    ]
)
logger = logging.getLogger("KuCoinProTrader")

# =================================================================
# CONFIGURACIÓN PRINCIPAL
# =================================================================
CONFIG = {
    "uso_saldo": 0.85,
    "max_operaciones": 3,
    "intervalo_analisis": 6,
    "saldo_minimo": 1.00,
    "proteccion_ganancia": 0.010,
    "lock_ganancia": 0.003,
    "max_duracion": 25,
    "hora_reseteo": "00:00",
    "seleccion": {
        "volumen_minimo": 250000,
        "precio_minimo": 0.000003,
        "spread_maximo": 0.006,
        "max_pares": 12,
        "config_base": {
            "min": 1.50,
            "momentum_min": 0.0020,
            "cooldown": 6,
            "max_ops_dia": 10,
            "tp": 0.017,
            "sl": 0.009,
            "trailing_stop": True,
            "trailing_offset": 0.0026,
            "slippage": 0.0025
        }
    }
}

PARES_CONFIG = {}

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
# MÓDULO DE SELECCIÓN DE PARES
# =================================================================
def determinar_incremento(simbolo: str) -> float:
    simbolo = simbolo.upper()
    if '3L' in simbolo: return 0.01
    if 'SHIB' in simbolo: return 1000
    if 'PEPE' in simbolo: return 100000
    if 'FLOKI' in simbolo or 'BONK' in simbolo: return 10000
    if 'WIF' in simbolo: return 1
    if 'JUP' in simbolo: return 10
    return 100

async def obtener_pares_candidatos() -> List[Dict]:
    try:
        market = Market()
        todos_tickers = await asyncio.to_thread(market.get_all_tickers)
        pares_usdt = [ticker for ticker in todos_tickers['ticker'] if ticker['symbol'].endswith('USDT')]
        pares_ordenados = sorted(pares_usdt, key=lambda x: float(x['volValue']), reverse=True)[:20]
        
        pares_filtrados = []
        for par in pares_ordenados:
            symbol = par['symbol']
            try:
                ticker = await asyncio.to_thread(market.get_ticker, symbol)
                stats = await asyncio.to_thread(market.get_24h_stats, symbol)
                
                vol_value = float(stats['volValue'])
                precio = float(ticker['price'])
                best_ask = float(ticker['bestAsk'])
                best_bid = float(ticker['bestBid'])
                spread = (best_ask - best_bid) / best_ask
                
                if (vol_value > CONFIG["seleccion"]["volumen_minimo"] and
                    precio > CONFIG["seleccion"]["precio_minimo"] and
                    spread < CONFIG["seleccion"]["spread_maximo"]):
                    
                    pares_filtrados.append({
                        'symbol': symbol,
                        'volumen': vol_value,
                        'precio': precio,
                        'spread': spread
                    })
                
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error analizando {symbol}: {str(e)}")
                continue
                
        return pares_filtrados[:CONFIG["seleccion"]["max_pares"]]
    except Exception as e:
        logger.error(f"Error obteniendo pares candidatos: {str(e)}")
        return []

async def generar_nueva_configuracion(pares: List[Dict]) -> Dict:
    try:
        market = Market()
        todos_symbols = await asyncio.to_thread(market.get_symbol_list)
        
        nueva_config = {}
        for par in pares:
            symbol = par['symbol']
            symbol_info = next((s for s in todos_symbols if s['symbol'] == symbol), None)
            
            if not symbol_info:
                logger.error(f"Symbol {symbol} no encontrado, omitiendo")
                continue
                
            config = CONFIG["seleccion"]["config_base"].copy()
            config.update({
                'vol_min': par['volumen'] * 0.75,
                'inc': determinar_incremento(symbol),
                'minSize': float(symbol_info['baseMinSize'])
            })
            
            if '3L' in symbol:
                config.update({
                    'min': 7.00,
                    'momentum_min': 0.0085,
                    'tp': 0.045,
                    'sl': 0.022
                })
            
            nueva_config[symbol] = config
        return nueva_config
    except Exception as e:
        logger.error(f"Error generando configuración: {str(e)}")
        return {}

async def actualizar_configuracion_diaria():
    while True:
        try:
            now = datetime.utcnow()
            next_reset = estado.obtener_hora_reseteo()
            
            if next_reset < now:
                next_reset += timedelta(days=1)
            
            await asyncio.sleep((next_reset - now).total_seconds())
            
            pares_candidatos = await obtener_pares_candidatos()
            nueva_config = await generar_nueva_configuracion(pares_candidatos)
            
            if not nueva_config:
                logger.error("Manteniendo configuración actual.")
                continue
                
            async with estado.lock:
                global PARES_CONFIG
                PARES_CONFIG.clear()
                PARES_CONFIG.update(nueva_config)
                estado.contador_operaciones.clear()
                estado.cooldowns.clear()
            
            market = Market()
            for par in PARES_CONFIG:
                try:
                    stats = await asyncio.to_thread(market.get_24h_stats, par)
                    PARES_CONFIG[par]['vol_min'] = float(stats['volValue']) * 0.75
                except Exception as e:
                    logger.error(f"Error actualizando {par}: {str(e)}")
            
            mensaje = "🔄 Configuración Actualizada\n📊 Nuevos pares:\n"
            for par in PARES_CONFIG:
                mensaje += f"• {par} (Vol: {PARES_CONFIG[par]['vol_min']:,.2f} USDT)\n"
            await bot.send_message(os.getenv("CHAT_ID"), mensaje)
            logger.info("Configuración actualizada exitosamente")

        except Exception as e:
            logger.error(f"Error actualización diaria: {str(e)}")
            await asyncio.sleep(3600)

# =================================================================
# CORE DEL TRADING
# =================================================================
async def verificar_conexion_kucoin():
    try:
        market = Market()
        await asyncio.to_thread(market.get_ticker, "BTC-USDT")
        estado.ultima_conexion = datetime.now()
        return True
    except Exception as e:
        logger.error(f"Error de conexión KuCoin: {e}")
        return False

async def obtener_saldo_disponible():
    try:
        user_client = User(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        cuentas = await asyncio.to_thread(user_client.get_account_list)
        total = 0.0
        for acc in cuentas:
            if acc['currency'] == 'USDT' and acc['type'] in ['trade', 'main']:
                total += float(acc['available'])
        return total
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
        
        mensaje_base = (
            f"❌ {par} - Operación abortada:\n"
            f"• Cantidad calculada: {cantidad}\n"
            f"• Mínimo KuCoin: {config['minSize']}\n"
            f"• Valor operación: {valor_operacion:.2f} USDT\n"
            f"• Mínimo config: {config['min']} USDT"
        )

        if cantidad < config['minSize']:
            logger.warning(f"{par} - Cantidad bajo mínimo KuCoin ({cantidad} < {config['minSize']})")
            await notificar_error(f"{par} - Cantidad menor al mínimo permitido\n{cantidad} < {config['minSize']}")
            await notificar_error(mensaje_base)
            return None
            
        logger.info(f"{par} - Incremento usado: {config['inc']}")
        logger.info(f"{par} - Cantidad calculada: {cantidad}")
        logger.info(f"{par} - Valor operación: {valor_operacion:.2f} USDT (mínimo: {config['min']})")
        
        if valor_operacion < config["min"]:
            logger.warning(f"{par} - Operación bajo mínimo ({valor_operacion:.2f} < {config['min']})")
            await notificar_error(mensaje_base)
            return None

        if valor_operacion < CONFIG["saldo_minimo"]:
            logger.warning(f"{par} - Valor bajo mínimo de saldo ({valor_operacion:.2f} < {CONFIG['saldo_minimo']})")
            await notificar_error(f"❌ {par} - Saldo insuficiente\nValor operación: {valor_operacion:.2f} < {CONFIG['saldo_minimo']} USDT")
            return None
            
        return cantidad
    except Exception as e:
        error_msg = f"❌ Error cálculo posición {par}: {str(e)}"
        logger.error(error_msg)
        await notificar_error(error_msg)
        return None

async def detectar_oportunidad(par):
    try:
        if not await verificar_conexion_kucoin():
            return None

        market = Market(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )

        stats = await asyncio.to_thread(market.get_24h_stats, par)
        vol_actual = float(stats["volValue"])
        if vol_actual < PARES_CONFIG[par]["vol_min"]:
            logger.info(f"DESCARTADO {par} - Volumen insuficiente ({vol_actual:.2f} < {PARES_CONFIG[par]['vol_min']})")
            return None

        velas = await asyncio.to_thread(market.get_kline, par, "1min")
        velas = velas[-3:]

        if len(velas) < 3:
            logger.info(f"DESCARTADO {par} - Menos de 3 velas disponibles")
            return None

        umbral_volumen = (vol_actual / 1440) * 2
        volumen_vela = float(velas[-1][5])
        if volumen_vela < umbral_volumen:
            logger.info(f"DESCARTADO {par} - Volumen de impulso bajo ({volumen_vela:.2f} < {umbral_volumen:.2f})")
            return None

        cierres = [float(v[2]) for v in velas]
        logger.info(f"Analizando {par} - Cierres: {cierres}")

        if cierres[2] < cierres[1] or cierres[1] < cierres[0]:
            logger.info(f"DESCARTADO {par} - Tendencia de impulso rota")
            return None

        momentum = (cierres[2] - cierres[0]) / cierres[0]
        logger.info(f"Momentum {par}: {momentum:.4f}")

        if momentum < PARES_CONFIG[par]["momentum_min"]:
            logger.info(f"DESCARTADO {par} - Momentum insuficiente ({momentum:.4f} < {PARES_CONFIG[par]['momentum_min']})")
            return None

        ticker = await asyncio.to_thread(market.get_ticker, par)
        best_ask = float(ticker["bestAsk"])
        best_bid = float(ticker["bestBid"])
        spread = (best_ask - best_bid) / best_ask
        
        if spread > CONFIG["seleccion"]["spread_maximo"]:
            logger.info(f"DESCARTADO {par} - Spread alto ({spread:.4f} > {CONFIG['seleccion']['spread_maximo']})")
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
    operacion = None
    try:
        logger.info(f"\n{'='*40}")
        logger.info(f"🚀 Iniciando ejecución para {señal['par']}")
        logger.info(f"📈 Señal recibida: {señal}")

        saldo = await obtener_saldo_disponible()
        logger.info(f"💰 Saldo disponible: {saldo:.2f} USDT")

        cantidad = await calcular_posicion(señal["par"], saldo, señal["precio"])
        logger.info(f"🧮 Cálculo posición: {cantidad or 'NO VÁLIDA'}")

        if not cantidad:
            logger.warning("❌ Abortando - Cantidad no válida")
            return None

        valor_operacion = cantidad * señal["precio"]
        min_operacion = PARES_CONFIG[señal["par"]]["min"]
        logger.info(f"📦 Valor operación: {valor_operacion:.2f} USDT (Mínimo requerido: {min_operacion} USDT)")

        if valor_operacion < min_operacion:
            logger.warning(f"❌ Abortando - Valor bajo el mínimo ({valor_operacion:.2f} < {min_operacion})")
            return None

        if valor_operacion < CONFIG["saldo_minimo"]:
            error_msg = f"❌ Valor bajo el mínimo de saldo ({valor_operacion:.2f} < {CONFIG['saldo_minimo']} USDT)"
            logger.warning(error_msg)
            await notificar_error(error_msg)
            return None

        async with estado.lock:
            if len(estado.operaciones_activas) >= CONFIG["max_operaciones"]:
                logger.warning("❌ Bloqueado - Máximo de operaciones simultáneas alcanzado")
                return None

            ops_diarias = estado.contador_operaciones.get(señal["par"], 0)
            if ops_diarias >= PARES_CONFIG[señal["par"]]["max_ops_dia"]:
                logger.warning(f"❌ Bloqueado - Límite diario ({ops_diarias}/{PARES_CONFIG[señal['par']]['max_ops_dia']})")
                return None

        try:
            trade = Trade(
                key=os.getenv("API_KEY"),
                secret=os.getenv("SECRET_KEY"),
                passphrase=os.getenv("API_PASSPHRASE")
            )
            
            # Precisión máxima en el cálculo
            config_par = PARES_CONFIG[señal["par"]]
            incremento = config_par["inc"]
            cantidad_redondeada = round(cantidad / incremento) * incremento
            
            # Formateo del tamaño según requerimientos de KuCoin
            decimales = abs(int(f"{incremento:.10f}".split('.')[1].rstrip('0'))) if '.' in f"{incremento}" else 0
            size_str = format(cantidad_redondeada, f".{decimales}f").rstrip('0').rstrip('.') if decimales > 0 else str(int(cantidad_redondeada))
            
            logger.info(f"🛒 Ejecutando orden en KuCoin: {señal['par']}")
            logger.info(f"• Cantidad redondeada: {cantidad_redondeada}")
            logger.info(f"• Tamaño enviado: {size_str}")

            # Ejecución robusta de la orden
            orden = await asyncio.to_thread(
                trade.create_market_order,
                symbol=señal["par"],
                side="buy",
                size=size_str
            )
            
            # Validación crítica de la respuesta
            if not orden or "orderId" not in orden:
                error_msg = f"❌ Respuesta inválida de KuCoin:\n{json.dumps(orden, indent=2)}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.info(f"✅ Orden ejecutada - ID: {orden.get('orderId')}")
            logger.info(f"🧾 Detalles completos:\n{json.dumps(orden, indent=2, default=str)}")

            # Manejo seguro del precio
            precio_entrada = orden.get("price")
            if not precio_entrada or float(precio_entrada) <= 0:
                logger.warning("⚠ Usando precio de señal por respuesta inválida")
                precio_entrada = señal["precio"]
            else:
                precio_entrada = float(precio_entrada)

        except Exception as e:
            # Log detallado de errores
            error_msg = f"🔥 Error crítico en orden:\n{str(e)}"
            if hasattr(e, 'response') and e.response:
                try:
                    error_details = json.loads(e.response.text)
                    error_msg += f"\nCódigo: {error_details.get('code')}\nMensaje: {error_details.get('msg')}\nInfo: {error_details.get('data')}"
                except Exception as parse_error:
                    error_msg += f"\nError parseando respuesta: {str(parse_error)}"
            
            logger.error(error_msg)
            await notificar_error(f"Fallo en {señal['par']}:\n{error_msg}")
            return None

        operacion = {
            "par": señal["par"],
            "id_orden": orden["orderId"],
            "cantidad": cantidad_redondeada,
            "precio_entrada": precio_entrada,
            "take_profit": señal["take_profit"],
            "stop_loss": señal["stop_loss"],
            "max_precio": precio_entrada,
            "hora_entrada": datetime.now(),
            "fee_compra": float(orden.get("fee", 0))
        }

        async with estado.lock:
            estado.operaciones_activas.append(operacion)
            estado.cooldowns.add(operacion["par"])
            estado.contador_operaciones[señal["par"]] = ops_diarias + 1

        await notificar_operacion(operacion, "ENTRADA")
        logger.info(f"🏁 Operación registrada exitosamente\n{'='*40}")
        return operacion

    except Exception as e:
        logger.error(f"🚨 Error fatal en ejecutar_operacion: {traceback.format_exc()}")
        await notificar_error(f"Fallo en ejecución:\n{str(e)}")
        return None
    finally:
        if operacion is None:
            logger.warning(f"❌ La operación para {señal['par']} no se ejecutó correctamente.")

async def cerrar_operacion(operacion, motivo):
    try:
        trade = Trade(
            key=os.getenv("API_KEY"),
            secret=os.getenv("SECRET_KEY"),
            passphrase=os.getenv("API_PASSPHRASE")
        )
        
        # Formateo preciso para la venta
        config_par = PARES_CONFIG[operacion["par"]]
        incremento = config_par["inc"]
        cantidad_redondeada = round(operacion["cantidad"] / incremento) * incremento
        
        decimales = abs(int(f"{incremento:.10f}".split('.')[1].rstrip('0'))) if '.' in f"{incremento}" else 0
        size_str = format(cantidad_redondeada, f".{decimales}f").rstrip('0').rstrip('.') if decimales > 0 else str(int(cantidad_redondeada))
        
        orden_venta = await asyncio.to_thread(
            trade.create_market_order,
            symbol=operacion["par"],
            side="sell",
            size=size_str
        )
        
        precio_salida = float(orden_venta.get("price", 0))
        fee_venta = float(orden_venta.get("fee", 0))
        ganancia_neto = (precio_salida * cantidad_redondeada) - (operacion["precio_entrada"] * cantidad_redondeada) - operacion["fee_compra"] - fee_venta
        
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
        await notificar_error(f"Error al cerrar {operacion['par']}:\n{str(e)}")

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
                if precio_actual >= op["take_profit"]: motivo = "TP"
                elif precio_actual <= op["stop_loss"]: motivo = "SL"
                elif (datetime.now() - op["hora_entrada"]).seconds > CONFIG["max_duracion"] * 60: motivo = "TIEMPO"
                
                if motivo: 
                    logger.info(f"Cerrando operación {op['par']} - Motivo: {motivo}")
                    await cerrar_operacion(op, motivo)
            except Exception as e:
                logger.error(f"Error gestionando operación {op['par']}: {e}")

async def verificar_cooldown(par):
    ahora = datetime.utcnow()
    if ahora > estado.ultimo_reseteo + timedelta(days=1):
        estado.contador_operaciones = {}
        estado.ultimo_reseteo = estado.obtener_hora_reseteo()
    
    if estado.contador_operaciones.get(par, 0) >= PARES_CONFIG[par]["max_ops_dia"]:
        logger.info(f"Cooldown por límite diario en {par}")
        return True
    
    if par in estado.cooldowns:
        ultima_op = next((op for op in estado.historial if op["par"] == par), None)
        if ultima_op and (ahora - ultima_op["hora_entrada"]).seconds < PARES_CONFIG[par]["cooldown"] * 60:
            logger.info(f"Cooldown activo para {par}")
            return True
    
    return False

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
                f"📊 Cantidad: {operacion['cantidad']:.8f}\n"
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
        await bot.send_message(os.getenv("CHAT_ID"), f"🚨 ERROR CRÍTICO 🚨\n{mensaje}")
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
            InlineKeyboardButton(text="📜 Historial", callback_data="ver_historial")
        ]
    ])

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
            await callback.answer()
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
                duracion = (op["hora_salida"] - op["hora_entrada"]).seconds // 60
                mensaje += (
                    f"🔹 {op['par']} ({op['motivo_salida']})\n"
                    f"📈 {ganancia:.2f}% | ⏱ {duracion} min\n"
                    f"🕒 {op['hora_entrada'].strftime('%H:%M')} - {op['hora_salida'].strftime('%H:%M')}\n\n"
                )

            await callback.message.edit_text(mensaje, reply_markup=await crear_menu_principal())
            await callback.answer()
        except Exception as e:
            logger.error(f"Error mostrando historial: {e}")

    @dp.callback_query(lambda c: c.data == "ver_balance")
    async def mostrar_balance(callback: types.CallbackQuery):
        try:
            saldo = await obtener_saldo_disponible()
            mensaje = f"💰 Balance disponible: {saldo:.2f} USDT"
            await callback.message.edit_text(mensaje, reply_markup=await crear_menu_principal())
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
            
            await callback.message.edit_text(mensaje, reply_markup=await crear_menu_principal())
            await callback.answer()
        except Exception as e:
            logger.error(f"Error mostrando operaciones: {e}")

# =================================================================
# CICLO PRINCIPAL DE TRADING
# =================================================================
async def ciclo_trading():
    logger.info("Iniciando ciclo de trading...")
    logger.info(f"Pares configurados: {list(PARES_CONFIG.keys())}")
    
    while estado.activo:
        try:
            if not await verificar_conexion_kucoin():
                logger.warning("Error de conexión con KuCoin")
                await asyncio.sleep(30)
                continue
                
            await gestionar_operaciones_activas()
            
            async with estado.lock:
                if len(estado.operaciones_activas) < CONFIG["max_operaciones"]:
                    logger.info("=== Iterando pares disponibles ===")
                    logger.info(f"PARES DISPONIBLES: {list(PARES_CONFIG.keys())}")
                    
                    for par in PARES_CONFIG:
                        if par in estado.pares_en_analisis:
                            logger.info(f"SKIP {par} - Ya en análisis")
                            continue
                            
                        estado.pares_en_analisis.add(par)
                        try:
                            logger.info(f"Iniciando análisis de {par}")
                            
                            if await verificar_cooldown(par):
                                logger.info(f"Cooldown activo en {par}")
                                continue
                                
                            señal = await detectar_oportunidad(par)
                            if señal:
                                logger.info(f"Señal detectada en {par}")
                                operacion = await ejecutar_operacion(señal)
                                if operacion:
                                    await asyncio.sleep(1.5)
                            else:
                                logger.info(f"Sin señal en {par}")
                        except Exception as e:
                            logger.error(f"Error analizando {par}: {e}")
                        finally:
                            estado.pares_en_analisis.discard(par)
                            logger.info(f"✔ Análisis completado: {par}")
            
            await asyncio.sleep(CONFIG["intervalo_analisis"])
        except Exception as e:
            logger.error(f"Error en ciclo trading: {e}")

# =================================================================
# EJECUCIÓN PRINCIPAL
# =================================================================
async def ejecutar_bot():
    logger.info("=== INICIANDO BOT ===")
    global bot
    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
    dp = Dispatcher()

    try:
        await register_handlers(dp)

        pares_iniciales = await obtener_pares_candidatos()
        nueva_config = await generar_nueva_configuracion(pares_iniciales)

        if nueva_config:
            global PARES_CONFIG
            PARES_CONFIG.update(nueva_config)
            logger.info(f"Pares configurados: {list(PARES_CONFIG.keys())}")
        else:
            logger.error("No se pudieron cargar pares iniciales.")

        asyncio.create_task(actualizar_configuracion_diaria())

        if not await verificar_conexion_kucoin():
            logger.error("Error de conexión inicial con KuCoin")
            return

        if os.path.exists('historial_operaciones.json') and os.path.getsize('historial_operaciones.json') > 0:
            with open('historial_operaciones.json', 'r') as f:
                estado.historial = json.load(f)
            logger.info(f"Historial cargado ({len(estado.historial)} ops)")

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