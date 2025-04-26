from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
import asyncio
import os
from keep_alive import keep_alive

# Variables de entorno
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Función para enviar mensaje
async def enviar_mensaje(texto):
    await bot.send_message(chat_id=CHAT_ID, text=texto)

# Comando /start actualizado
@dp.message(CommandStart())
async def start_handler(message):
    await message.answer("✅ ZafroBot está activo y funcionando correctamente.")

async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())