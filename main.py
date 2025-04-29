import os
import asyncio
import logging
from kucoin.client import Client
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Inicializar cliente de KuCoin
client = Client(API_KEY, SECRET_KEY, API_PASSPHRASE)

# Inicializar Bot de Telegram
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)# Función para obtener saldo disponible en la Wallet de Trading de KuCoin
async def obtener_saldo():
    try:
        cuentas = client.get_accounts()
        for cuenta in cuentas:
            if cuenta['currency'] == 'USDT' and cuenta['type'] == 'trade':
                return float(cuenta['available'])
        return 0.0
    except Exception as e:
        logger.error(f"Error al obtener saldo: {e}")
        return 0.0

# Función para enviar mensajes de texto
async def enviar_mensaje(texto):
    await bot.send_message(chat_id=CHAT_ID, text=texto)

# Botones principales del menú
botones_principales = ReplyKeyboardMarkup(resize_keyboard=True)
botones_principales.add(
    KeyboardButton("🚀 Encender Bot"),
    KeyboardButton("🛑 Apagar Bot")
)
botones_principales.add(
    KeyboardButton("📊 Estado del Bot"),
    KeyboardButton("💰 Actualizar Saldo")
)
botones_principales.add(
    KeyboardButton("📈 Estado de Orden Actual")
)# Función para escanear pares y detectar oportunidad
async def escanear_mercado():
    try:
        while bot_encendido:
            saldo_disponible = await obtener_saldo()

            if saldo_disponible <= 0:
                logger.warning("Saldo insuficiente para operar.")
                await enviar_mensaje("⚠️ Saldo insuficiente para operar.")
                await asyncio.sleep(5)
                continue

            mejor_par = None
            mejor_variacion = 0

            for par in PARES:
                try:
                    ticker = client.get_ticker(symbol=par)
                    volumen_24h = float(ticker['volValue'])
                    precio_actual = float(ticker['price'])

                    if volumen_24h == 0:
                        continue

                    # Análisis adicional: lógica basada en volumen, liquidez y movimiento de precio
                    variacion = random.uniform(0.01, 0.05)  # Simulación (sustituiremos luego por análisis real)

                    if variacion > mejor_variacion:
                        mejor_variacion = variacion
                        mejor_par = par

                except Exception as e:
                    logger.error(f"Error al analizar {par}: {e}")

            if mejor_par:
                logger.info(f"Mejor par encontrado: {mejor_par} con variación estimada {mejor_variacion:.2%}")
                await operar_en_par(mejor_par, saldo_disponible)
            else:
                logger.info("No se encontró oportunidad en este ciclo.")

            await asyncio.sleep(2)  # Espera antes de volver a escanear
    except Exception as e:
        logger.error(f"Error en escaneo de mercado: {e}")

# Comando de encender el bot
@dp.message_handler(lambda message: message.text == "🚀 Encender Bot")
async def encender_bot(message: types.Message):
    global bot_encendido
    if not bot_encendido:
        bot_encendido = True
        await enviar_mensaje("🟢 Bot encendido. Escaneando mercado...")
        asyncio.create_task(escanear_mercado())
    else:
        await enviar_mensaje("⚠️ El bot ya está encendido.")async def operar_en_par(par, saldo_disponible):
    try:
        # Obtener información de volumen 24h del par
        ticker_info = client.get_ticker(symbol=par)
        volumen_24h = float(ticker_info['volValue'])

        # Aplicar Kelly Criterion (dinámico)
        kelly = calcular_kelly()
        cantidad_invertir = saldo_disponible * kelly

        # Límite: No usar más del 4% del volumen 24h
        limite_operacion = volumen_24h * 0.04

        if cantidad_invertir > limite_operacion:
            cantidad_invertir = limite_operacion

        # Ajustar a un mínimo de compra para el par si necesario
        if cantidad_invertir < 5:
            cantidad_invertir = 5

        cantidad_invertir = round(cantidad_invertir, 2)

        await enviar_mensaje(f"🛒 Ejecutando compra en {par} por {cantidad_invertir} USDT...")

        # Simulación de compra (reemplazar con lógica real)
        precio_compra = float(client.get_ticker(symbol=par)['price'])
        logger.info(f"Compra simulada en {par} a {precio_compra}")

        await monitorear_venta(par, precio_compra, cantidad_invertir)

    except Exception as e:
        logger.error(f"Error al operar en {par}: {e}")
        await enviar_mensaje(f"❌ Error al operar en {par}: {e}")

def calcular_kelly():
    # Suposición temporal: Kelly fijo
    # Se puede conectar con predicción real o probabilidad calculada
    win_probability = 0.6  # Ejemplo 60%
    win_loss_ratio = 1.5   # Ejemplo 1.5 a 1
    kelly = (win_probability * (win_loss_ratio + 1) - 1) / win_loss_ratio
    return max(0.05, min(kelly, 0.25))  # entre 5% y 25% como límite seguro

async def monitorear_venta(par, precio_compra, cantidad):
    try:
        mejor_profit = 0
        trailing_stop = -0.08  # -8%

        while True:
            ticker = client.get_ticker(symbol=par)
            precio_actual = float(ticker['price'])

            ganancia_actual = (precio_actual - precio_compra) / precio_compra

            if ganancia_actual > mejor_profit:
                mejor_profit = ganancia_actual

            retroceso = (precio_actual - precio_compra) / precio_compra - mejor_profit

            if retroceso <= trailing_stop:
                logger.info(f"🚀 Vendiendo {par} con {ganancia_actual:.2%} de ganancia.")
                await enviar_mensaje(f"🚀 Vendiendo {par} con {ganancia_actual:.2%} de ganancia.")

                # Simulación de venta (reemplazar con API real)
                break

            await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Error en monitoreo de venta: {e}")
        await enviar_mensaje(f"❌ Error en monitoreo de venta: {e}")# Comando para apagar el bot
@dp.message_handler(lambda message: message.text == "🛑 Apagar Bot")
async def apagar_bot(message: types.Message):
    global bot_encendido
    if bot_encendido:
        bot_encendido = False
        await enviar_mensaje("🔴 Bot apagado.")
    else:
        await enviar_mensaje("⚠️ El bot ya estaba apagado.")

# Comando para ver estado actual del bot
@dp.message_handler(lambda message: message.text == "📊 Estado del Bot")
async def estado_del_bot(message: types.Message):
    estado = "🟢 Encendido" if bot_encendido else "🔴 Apagado"
    await enviar_mensaje(f"📊 Estado actual: {estado}")

# Comando para actualizar saldo
@dp.message_handler(lambda message: message.text == "💰 Actualizar Saldo")
async def actualizar_saldo(message: types.Message):
    saldo = await obtener_saldo()
    await enviar_mensaje(f"💰 Saldo disponible: {saldo:.2f} USDT")

# Comando para ver estado de orden activa
@dp.message_handler(lambda message: message.text == "📈 Estado de Orden Actual")
async def estado_orden_actual(message: types.Message):
    if bot_encendido:
        await enviar_mensaje("🚀 Bot actualmente analizando mercado...")
    else:
        await enviar_mensaje("🔴 No hay orden activa.")

# Comando de inicio del bot
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await enviar_mensaje("✅ *ZafroBot Scalper PRO* listo.\nSelecciona una opción:", reply_markup=botones_principales)

# Función principal
async def main():
    await dp.start_polling()

# Lanzar bot
if __name__ == "__main__":
    asyncio.run(main())