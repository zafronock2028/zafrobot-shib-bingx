import time
import hmac
import hashlib

def obtener_saldo_spot():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/balance"

    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"

    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BX-APIKEY": API_KEY
    }

    params = {
        "timestamp": timestamp,
        "signature": signature
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if data['code'] == 0:
            balances = data['data']['balances']
            for balance in balances:
                if balance['asset'] == 'USDT':
                    return float(balance['free'])
            return 0.0
        else:
            print(f"Error en la API: {data}")
            return 0.0
    except Exception as e:
        print(f"Error consultando saldo: {e}")
        return 0.0