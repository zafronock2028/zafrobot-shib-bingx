import os
import asyncio
from kucoin.client import User as UserClient
from kucoin.client import Market as MarketClient
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Credenciales de KuCoin
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Crear cliente de KuCoin
user_client = UserClient(API_KEY, SECRET_KEY, API_PASSPHRASE)
market_client = MarketClient()

# Crear Bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Configurar teclado
keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🚀 Encender Bot")],
    [KeyboardButton(text="🛑 Apagar Bot")],
    [KeyboardButton(text="💰 Saldo")],
    [KeyboardButton(text="📊 Estado Bot")],
    [KeyboardButton(text="📈 Estado de Orden")]
], resize_keyboard=True)

# Variables Globales
bot_encendido = False
pares = ["SHIB-USDT", "PEPE-USDT", "FLOKI-USDT", "DOGE-USDT"]

operacion_activa = False
par_actual = None
precio_entrada = 0.0
cantidad_comprada = 0.0@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("¡Bienvenido al Zafrobot Dinámico Pro Scalping!", reply_markup=keyboard)

@dp.message()
async def manejar_mensajes(message: types.Message):
    global bot_encendido
    texto = message.text

    if texto == "🚀 Encender Bot":
        if not bot_encendido:
            bot_encendido = True
            await message.answer("✅ Bot encendido. Analizando oportunidades...")
            asyncio.create_task(iniciar_operacion())
        else:
            await message.answer("⚠️ El bot ya está encendido.")

    elif texto == "🛑 Apagar Bot":
        if bot_encendido:
            bot_encendido = False
            await message.answer("🛑 Bot apagado manualmente.")
        else:
            await message.answer("⚠️ El bot ya está apagado.")

    elif texto == "💰 Saldo":
        saldo = obtener_saldo()
        await message.answer(f"💰 Saldo disponible en Spot: {saldo:.2f} USDT")

    elif texto == "📊 Estado Bot":
        estado = "✅ ENCENDIDO" if bot_encendido else "🛑 APAGADO"
        await message.answer(f"📊 Estado actual: {estado}")

    elif texto == "📈 Estado de Orden":
        if operacion_activa:
            await message.answer(f"📈 Orden activa en {par_actual}\nEntrada: {precio_entrada:.8f} USDT\nCantidad: {cantidad_comprada}")
        else:
            await message.answer("📈 Actualmente no hay ninguna orden activa.")

def obtener_saldo():
    try:
        cuentas = user_client.get_account_list()
        usdt_cuenta = next((c for c in cuentas if c['currency'] == 'USDT' and c['type'] == 'trade'), None)
        if usdt_cuenta:
            return float(usdt_cuenta['available'])
    except Exception as e:
        print(f"Error obteniendo saldo: {e}")
    return 0.0async def iniciar_operacion():
    global bot_encendido
    while bot_encendido:
        try:
            for par in pares:
                if not bot_encendido:
                    break
                await analizar_par(par)
            await asyncio.sleep(2)  # Escaneo cada 2 segundos
        except Exception as e:
            print(f"Error en el análisis: {e}")
            await asyncio.sleep(5)

async def analizar_par(par):
    global operacion_activa, par_actual, precio_entrada, cantidad_comprada

    if operacion_activa:
        return  # No analizar si ya hay una operación abierta

    try:
        # Volumen de 24h del par
        ticker = market_client.get_ticker(symbol=par)
        volumen_24h = float(ticker["volValue"])

        # No operar si el volumen es muy bajo
        if volumen_24h < 50000:
            return

        # Precios recientes para cálculo de media
        klines = market_client.get_kline_data(symbol=par, kline_type="1min", limit=5)
        precios = [float(k[2]) for k in klines]
        promedio = sum(precios) / len(precios)
        precio_actual = float(ticker["price"])

        # Análisis de oportunidad
        if precio_actual < promedio * 0.99:  # Precio actual 1% por debajo de la media
            saldo = obtener_saldo()
            monto_ideal = calcular_kelly(saldo, volumen_24h)
            cantidad = (monto_ideal / precio_actual)
            cantidad = redondear_cantidad(cantidad, par)

            if cantidad > 0:
                # Ejecutar orden de compra
                ejecutar_compra(par, cantidad, precio_actual)
    except Exception as e:
        print(f"Error analizando {par}: {e}")def calcular_kelly(saldo, volumen_24h):
    porcentaje_kelly = 0.8  # 80% modo agresivo
    monto = saldo * porcentaje_kelly
    maximo_por_volumen = volumen_24h * 0.04  # No superar el 4% del volumen de 24h
    return min(monto, maximo_por_volumen)

def redondear_cantidad(cantidad, par):
    if "DOGE" in par:
        return round(cantidad, 2)
    else:
        return round(cantidad, 0)

def ejecutar_compra(par, cantidad, precio_actual):
    global operacion_activa, par_actual, precio_entrada, cantidad_comprada
    try:
        simbolo = par
        orden = user_client.create_market_order(symbol=simbolo, side="buy", size=str(cantidad))
        operacion_activa = True
        par_actual = par
        precio_entrada = precio_actual
        cantidad_comprada = cantidad
        print(f"✅ Compra ejecutada en {par} a {precio_actual:.8f} USDT con cantidad {cantidad}")

        asyncio.create_task(monitorear_venta(par))  # Monitorear la operación
    except Exception as e:
        print(f"Error ejecutando compra: {e}")

async def monitorear_venta(par):
    global operacion_activa, par_actual, precio_entrada, cantidad_comprada

    objetivo_ganancia = precio_entrada * 1.025  # +2.5% mínimo
    stop_loss = precio_entrada * 0.92  # -8%

    while operacion_activa:
        try:
            ticker = market_client.get_ticker(symbol=par)
            precio_actual = float(ticker["price"])

            if precio_actual >= objetivo_ganancia:
                ejecutar_venta(par)
                break
            elif precio_actual <= stop_loss:
                ejecutar_venta(par)
                break

            await asyncio.sleep(2)  # Vigilar cada 2 segundos
        except Exception as e:
            print(f"Error monitoreando venta: {e}")
            await asyncio.sleep(5)def ejecutar_venta(par):
    global operacion_activa, par_actual, precio_entrada, cantidad_comprada
    try:
        simbolo = par
        user_client.create_market_order(symbol=simbolo, side="sell", size=str(cantidad_comprada))
        print(f"✅ Venta ejecutada en {par}. Operación cerrada exitosamente.")
        # Resetear variables
        operacion_activa = False
        par_actual = None
        precio_entrada = 0.0
        cantidad_comprada = 0.0
    except Exception as e:
        print(f"Error ejecutando venta: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())