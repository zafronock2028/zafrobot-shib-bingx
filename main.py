import os
import requests
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import F

# Cargar las variables de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Inicializar el bot y el dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Función para consultar el saldo de USDT en BingX
async def consultar_saldo():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"
    headers = {
        "X-BX-APIKEY": API_KEY,
    }
    params = {
        "timestamp": str(int(asyncio.get_event_loop().time() * 1000)),
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    if data.get("code") == 0:
        balances = data.get("data", {}).get("balances", [])
        for balance in balances:
            if balance.get("asset") == "USDT":
                free_balance = balance.get("free")
                return free_balance
    return None

# Comando /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("🤖 ¡Hola! Soy ZafroBot Dinámico Pro. Estoy listo para ayudarte a consultar tu saldo de USDT en BingX. Usa el comando /saldo para ver tu saldo actual.")

# Comando /saldo
@dp.message(Command("saldo"))
async def saldo_command(message: types.Message):
    saldo = await consultar_saldo()
    if saldo is not None:
        await message.answer(f"💵 Tu saldo disponible en USDT es: {saldo}")
    else:
        await message.answer("⚠️ No se pudo obtener el saldo. Revisa tus credenciales o intenta más tarde.")

# Función principal para iniciar el bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())