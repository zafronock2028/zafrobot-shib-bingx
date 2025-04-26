from aiogram import Bot, Dispatcher, executor, types
import os
from keep_alive import keep_alive

# Configura tu bot de Telegram
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Función para enviar mensaje
async def enviar_mensaje(texto):
    await bot.send_message(chat_id=CHAT_ID, text=texto)

# Comando /start para probar
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.reply("✅ ZafroBot está activo y listo para enviarte notificaciones.")

# Arranca el servidor web para mantener vivo en Render
keep_alive()

# Ejecutar el bot
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)