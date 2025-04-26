import hmac
import hashlib
import time

async def obtener_saldo():
    url = "https://open-api.bingx.com/openApi/user/spot/assets"
    timestamp = str(int(time.time() * 1000))
    params = f"timestamp={timestamp}"

    sign = hmac.new(
        BINGX_API_SECRET.encode('utf-8'),
        params.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BX-APIKEY": BINGX_API_KEY,
    }

    url_final = f"{url}?{params}&signature={sign}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url_final, headers=headers) as response:
                data = await response.json()
                if data['code'] == 0:
                    for asset in data['data']['assets']:
                        if asset['asset'] == 'USDT':
                            return float(asset['balance'])
                return None
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None