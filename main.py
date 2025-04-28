import asyncio
import aiohttp
import hmac
import hashlib
import time
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
PASSPHRASE = os.getenv('PASSPHRASE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Estado del bot
bot_active = False

# Plantilla de mensajes de victoria
VICTORY_MESSAGES = [
    "🏆 ¡Victoria asegurada, seguimos sumando!",
    "🚀 ¡Otra ganancia más para Zafronock!",
    "💎 ¡Rentabilidad desbloqueada!",
    "🔥 ¡Sigamos rompiendo el mercado!",
    "⚡ ¡Operación cerrada con éxito!",
    "📈 ¡Subimos un escalón más!",
    "🥇 ¡Rentabilidad alcanzada como un campeón!",
    "🤑 ¡Dinero ganado, dinero trabajando!"
]

# Función para firmar las solicitudes a KuCoin
def sign_request(endpoint, params):
    now = str(int(time.time() * 1000))
    str_to_sign = now + 'GET' + endpoint + params
    signature = hmac.new(API_SECRET.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    signature_b64 = signature.hex()
    return now, signature_b64

# Función para obtener el saldo de la cuenta principal de trading en KuCoin
async def get_account_balance():
    endpoint = "/api/v1/accounts"
    params = "?currency=USDT&type=trade"
    url = "https://api.kucoin.com" + endpoint + params

    now, signature = sign_request(endpoint, params)
    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": now,
        "KC-API-PASSPHRASE": PASSPHRASE,
        "KC-API-KEY-VERSION": "2"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                return None
            data = await response.json()
            if data.get("code") == "200000" and data.get("data"):
                return float(data["data"]["available"])
            else:
                return None

# Función para construir el teclado principal
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Encender Bot", callback_data="encender")],
        [InlineKeyboardButton(text="⛔ Apagar Bot", callback_data="apagar")],
        [InlineKeyboardButton(text="ℹ️ Estado", callback_data="estado")],
        [InlineKeyboardButton(text="💰 Actualizar Saldo", callback_data="actualizar_saldo")],
    ])
    return keyboard

@dp.message(commands=["start"])
async def start_command(message: types.Message):
    await message.answer(
        "✅ Bienvenido a ZafroBot Scalper PRO\n"
        "Listo para operar de forma profesional en KuCoin.\n\n"
        "📊 Opciones disponibles:",
        reply_markup=main_menu()
    )
    await message.answer(
        "🔹 ZafroBot Scalper PRO v1.0 - By @Zafronockbitfratsg"
    )

@dp.callback_query()
async def handle_buttons(callback_query: types.CallbackQuery):
    global bot_active

    if callback_query.data == "encender":
        if not bot_active:
            bot_active = True
            await callback_query.message.answer("✅ Bot encendido. Escaneando saldo y mercado...")
            asyncio.create_task(trading_loop())
        else:
            await callback_query.message.answer("⚡ El bot ya está encendido.")
    elif callback_query.data == "apagar":
        if bot_active:
            bot_active = False
            await callback_query.message.answer("⛔ Bot apagado. Se detienen las operaciones.")
        else:
            await callback_query.message.answer("⚡ El bot ya está apagado.")
    elif callback_query.data == "estado":
        status = "✅ El bot está actualmente encendido." if bot_active else "⛔ El bot está actualmente apagado."
        await callback_query.message.answer(status)
    elif callback_query.data == "actualizar_saldo":
        balance = await get_account_balance()
        if balance is not None:
            await callback_query.message.answer(f"💵 Saldo disponible en Spot: {balance:.2f} USDT")
        else:
            await callback_query.message.answer("⚠️ No se pudo obtener el saldo. Verifica tu conexión o tu cuenta.")

async def trading_loop():
    while bot_active:
        # Aquí irá la lógica de trading en producción (por ahora placeholder)
        await asyncio.sleep(5)  # Simulamos escaneo del mercado cada 5 segundos
        # Aquí puedes agregar la simulación de envío de mensajes de victoria
        # await bot.send_message(chat_id=CHAT_ID, text=random.choice(VICTORY_MESSAGES))
        pass

async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())