import asyncio
import time
import aiohttp
import hmac
import hashlib
import base64
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- TUS VARIABLES ---
import os

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
PASSPHRASE = os.getenv("PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK = os.getenv("WEBHOOK")

# --- CONFIGURACIÓN DEL BOT ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Estado del bot (Encendido/Apagado)
bot_activo = False

# URL de KuCoin para consulta de saldo
KUCOIN_BALANCE_URL = "https://api.kucoin.com/api/v1/accounts"

# --- FUNCIONES AUXILIARES ---
async def consultar_saldo_kucoin():
    now = int(time.time() * 1000)
    str_to_sign = str(now) + 'GET' + '/api/v1/accounts'
    signature = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    )
    passphrase = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), PASSPHRASE.encode('utf-8'), hashlib.sha256).digest()
    )

    headers = {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature.decode(),
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": passphrase.decode(),
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(KUCOIN_BALANCE_URL, headers=headers) as resp:
                response = await resp.json()
                if resp.status == 200 and response.get("code") == "200000":
                    for account in response["data"]:
                        if account["currency"] == "USDT" and account["type"] == "trade":
                            return float(account["available"])
        except Exception as e:
            print(f"Error al consultar saldo: {e}")
    return None

def get_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Encender Bot", callback_data="encender")],
        [InlineKeyboardButton(text="⛔ Apagar Bot", callback_data="apagar")],
        [InlineKeyboardButton(text="ℹ️ Ver Estado", callback_data="estado")],
        [InlineKeyboardButton(text="🔄 Actualizar Saldo", callback_data="saldo")]
    ])
    return keyboard

# --- HANDLERS ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "**Bienvenido a ZafroBot Scalper PRO v1**\n\nSelecciona una opción:",
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "encender")
async def encender_bot(callback_query: types.CallbackQuery):
    global bot_activo
    bot_activo = True
    await callback_query.message.answer("✅ ZafroBot Scalper PRO ACTIVADO. ¡A ganar!")
    saldo = await consultar_saldo_kucoin()
    if saldo is not None:
        await callback_query.message.answer(
            f"⚡ Recarga detectada.\nSaldo disponible: **{saldo:.2f} USDT**\n✅ Bot listo para operar.",
            parse_mode="Markdown"
        )
    else:
        await callback_query.message.answer(
            "⚠️ No se detectó saldo disponible.\nEl bot permanecerá en espera."
        )

@dp.callback_query(lambda c: c.data == "apagar")
async def apagar_bot(callback_query: types.CallbackQuery):
    global bot_activo
    bot_activo = False
    await callback_query.message.answer("⛔ ZafroBot Scalper PRO apagado. En pausa.")

@dp.callback_query(lambda c: c.data == "estado")
async def estado_bot(callback_query: types.CallbackQuery):
    estado = "✅ Bot Activo" if bot_activo else "⛔ Bot en Pausa"
    await callback_query.message.answer(estado)

@dp.callback_query(lambda c: c.data == "saldo")
async def actualizar_saldo(callback_query: types.CallbackQuery):
    saldo = await consultar_saldo_kucoin()
    if saldo is not None:
        await callback_query.message.answer(
            f"🔄 Saldo actualizado:\n**{saldo:.2f} USDT** disponibles en Trading Wallet.",
            parse_mode="Markdown"
        )
    else:
        await callback_query.message.answer(
            "⚠️ No se pudo consultar el saldo."
        )

async def main():
    await bot.send_message(CHAT_ID, "✅ ZafroBot Scalper PRO ha iniciado correctamente. Listo para recibir comandos.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())