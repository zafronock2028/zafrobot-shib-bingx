import time
import hmac
import hashlib
import requests
from aiogram import Bot, Dispatcher, executor, types

# ====== TUS CREDENCIALES API (ya integradas) ======
API_KEY = "RA2cfzSaJKWxDrVEXitoiLZK1dpfEQLaCe8TIdG77Nl2GJEiImL7eXRRWIJDdjwYpakLIa37EQIpI6jpQ"
API_SECRET = "VlwOFCk2hsJxth98TQLZoHf7HLDxDCNHuGmIKyhHgh9UoturNTon3rkiLwtbsr1zxqZcOvVyWNCILFDzVVLg"

# ====== TU TOKEN DE TELEGRAM (ya lo tienes configurado en Render) ======
BOT_TOKEN = "TU_TELEGRAM_BOT_TOKEN"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ====== FUNCIÓN PARA OBTENER EL SALDO USDT EN SPOT ======
def get_spot_usdt_balance():
    url = "https://open-api.bingx.com/openApi/user/getBalance"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {
        'X-BX-APIKEY': API_KEY
    }
    params = {
        'timestamp': timestamp,
        'signature': signature
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        if data.get('code') == 0:
            balances = data['data']['balances']
            for asset in balances:
                if asset['asset'] == 'USDT':
                    return float(asset['balance'])
            return None
        else:
            return None
    except Exception as e:
        return None

# ====== COMANDO /start ======
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    text = (
        "**[[ ZafroBot Dinámico Pro ]]**\n\n"
        "🤖 ¡Estoy listo para ayudarte a consultar tu saldo real de **USDT** en tu cuenta **SPOT** de BingX!\n\n"
        "Usa el comando /saldo para verlo en **tiempo real**."
    )
    await message.answer(text, parse_mode="Markdown")

# ====== COMANDO /saldo ======
@dp.message_handler(commands=['saldo'])
async def saldo(message: types.Message):
    retry_count = 0
    balance = None
    while retry_count < 3 and balance is None:
        balance = get_spot_usdt_balance()
        if balance is None:
            time.sleep(2)
            retry_count += 1

    if balance is not None:
        text = (
            "**[[ ZafroBot Dinámico Pro ]]**\n\n"
            "💰 Tu saldo actual en Spot es:\n\n"
            f"**{balance:.2f} USDT**"
        )
    else:
        text = (
            "**[[ ZafroBot Dinámico Pro ]]**\n\n"
            "⚠️ No fue posible obtener tu saldo actual.\n\n"
            "_Por favor intenta nuevamente en unos minutos._"
        )

    await message.answer(text, parse_mode="Markdown")

# ====== INICIAR BOT ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)