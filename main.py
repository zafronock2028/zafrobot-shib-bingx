import logging
import requests
import time
import hmac
import hashlib
import asyncio
import websockets
import json
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from flask import Flask
import threading
import os

# Credenciales de BingX
api_key = 'LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA'
secret_key = 'Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg'

# Token del bot de Telegram
BOT_TOKEN = '7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM'

# Inicializar bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Flask para mantener Render activo
app = Flask(__name__)

@app.route('/')
def home():
    return "ZafroBot Notifier PRO corriendo."

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    server = threading.Thread(target=run)
    server.start()

# Variable global para saldo actualizado
saldo_actual_spot = 0.0

# Función para firmar WebSocket auth
def create_signature(secret_key, timestamp):
    payload = f"timestamp={timestamp}"
    signature = hmac.new(secret_key.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

# WebSocket privado para actualizar saldo en vivo
async def websocket_saldo_bingx():
    global saldo_actual_spot
    url = "wss://open-api-swap.bingx.com/swap-market"
    while True:
        try:
            async with websockets.connect(url) as websocket:
                timestamp = str(int(time.time() * 1000))
                sign = create_signature(secret_key, timestamp)
                
                auth_payload = {
                    "id": "auth",
                    "reqType": "subscribe",
                    "data": {
                        "apiKey": api_key,
                        "timestamp": timestamp,
                        "signature": sign
                    }
                }
                
                await websocket.send(json.dumps(auth_payload))
                logging.info("Autenticado al WebSocket de BingX.")

                # Subscribirse a balance updates
                subscribe_payload = {
                    "id": "balance_subscribe",
                    "reqType": "subscribe",
                    "data": {
                        "channel": "balance"
                    }
                }
                
                await websocket.send(json.dumps(subscribe_payload))
                logging.info("Suscripto al canal de balance.")
                
                while True:
                    response = await websocket.recv()
                    data = json.loads(response)
                    
                    if "data" in data and "balances" in data["data"]:
                        balances = data["data"]["balances"]
                        for asset in balances:
                            if asset['asset'] == 'USDT':
                                saldo_actual_spot = float(asset['availableMargin'])  # saldo disponible actualizado
                                logging.info(f"Nuevo saldo Spot detectado: {saldo_actual_spot} USDT")
        except Exception as e:
            logging.error(f"Error en WebSocket: {e}")
            await asyncio.sleep(5)  # Reintentar conexión después de un error

# Comando /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "**Bienvenido a ZafroBot Notifier PRO**\n\n"
        "✅ Bot activo y listo.\n"
        "👉 Usa /saldo para ver tu saldo Spot actualizado en tiempo real.",
        parse_mode=ParseMode.MARKDOWN
    )

# Comando /saldo con efecto animado y tarjeta elegante
@dp.message(Command("saldo"))
async def saldo_handler(message: Message):
    if saldo_actual_spot > 0:
        # Primero manda el mensaje de "Consultando..."
        mensaje_espera = await message.answer(
            "💸 *Consultando saldo en tiempo real...*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await asyncio.sleep(1.5)  # Pequeño efecto de espera (1.5 segundos)

        # Luego edita el mensaje anterior con el saldo real
        await mensaje_espera.edit_text(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *ZafroBot Wallet*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 *Saldo disponible en Spot:*\n"
            f"`{saldo_actual_spot:.2f} USDT`\n\n"
            f"🕒 _Actualizado en tiempo real_\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await message.answer(
            "⚠️ *El saldo aún no ha sido detectado.*\n"
            "_Por favor intenta en unos segundos._",
            parse_mode=ParseMode.MARKDOWN
        )

# Función principal segura
async def start_bot():
    while True:
        try:
            await asyncio.gather(
                dp.start_polling(bot),
                websocket_saldo_bingx()
            )
        except Exception as e:
            logging.error(f"Error general: {e}")
            logging.info("Reintentando en 5 segundos...")
            await asyncio.sleep(5)

# Lanzar Flask y Bot
if __name__ == "__main__":
    keep_alive()
    asyncio.run(start_bot())