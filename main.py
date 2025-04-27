import logging
import requests
import time
import hmac
import hashlib
import asyncio
import websockets
import gzip
import json
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from flask import Flask
import threading
import os

# --- Tus Credenciales ---
api_key = 'LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA'
secret_key = 'Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg'
BOT_TOKEN = '7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM'
# --------------------------

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
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

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

                # Subscribirse al canal de balance
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
                    
                    # Descomprimir la respuesta si está comprimida
                    try:
                        decompressed_data = gzip.decompress(response).decode('utf-8')
                        data = json.loads(decompressed_data)
                    except:
                        # Si no está comprimido, leer como texto normal
                        data = json.loads(response)
                    
                    if "data" in data and "balances" in data["data"]:
                        balances = data["data"]["balances"]
                        for asset in balances:
                            if asset['asset'] == 'USDT':
                                saldo_actual_spot = float(asset['availableMargin'])  # saldo disponible actualizado
                                logging.info(f"Nuevo saldo Spot detectado: {saldo_actual_spot} USDT")
        except Exception as e:
            logging.error(f"Error en WebSocket: {e}")
            await asyncio.sleep(5)

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
        mensaje_espera = await message.answer(
            "💸 *Consultando saldo en tiempo real...*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await asyncio.sleep(1.5)

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