import requests
import time
import hashlib
import hmac

# === CONFIGURACIÓN ===
API_KEY = "LCRNrSVWUf1crSsLEEtrdDzyIUWdNVtelJTnypigJV9HQ1AfMYhkIxiNazKDNcrGq3vgQjuKspQTjFHeA"
SECRET_KEY = "Kckg5g1hCDsE9N83n8wpxDjUWk0fGI7VWKVyKRX4wzHIgmi7dXj09B4NdA2MnKTCIw7MhtLV6YLHcemS3Yjg"
TELEGRAM_BOT_TOKEN = "7768905391:AAGn5T2JiPe4RU_pmFWlhXc2Sn4OriV0CGM"
TELEGRAM_CHAT_ID = "291650"  # Verificado desde la imagen
SYMBOL = "SHIB-USDT"
PRECISION = 1000000  # Para evitar errores por decimales
GANANCIA_DIARIA = 0
UMBRAL_TAKE_PROFIT = 1.0108
UMBRAL_STOP_LOSS = 0.98

# === FUNCIONES DE API ===

def firmar(params):
    query_string = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
    firma = hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    return firma, query_string

def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/user/balance"
    timestamp = str(int(time.time() * 1000))
    params = {"timestamp": timestamp}
    firma, query_string = firmar(params)

    headers = {
        "X-BX-APIKEY": API_KEY
    }

    response = requests.get(f"{url}?{query_string}&signature={firma}", headers=headers)
    data = response.json()
    for asset in data['data']['balances']:
        if asset['asset'] == 'USDT':
            return float(asset['free'])
    return 0.0

def obtener_precio_actual():
    url = f"https://open-api.bingx.com/openApi/market/ticker?symbol={SYMBOL}"
    response = requests.get(url)
    return float(response.json()['data'][0]['price'])

def enviar_mensaje_telegram(saldo):
    mensaje = (
        "✅ *¡Operación ganada!*\n"
        f"📈 *Ganancia:* +1.08%\n"
        f"💰 *Nuevo saldo:* ${saldo:.2f}\n\n"
        "🔗 *Únete a mi canal oficial:* [GanandoConZafronock](https://t.me/GanandoConZafronock)"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

# === BOT PRINCIPAL ===

def zafrobot_dinamico():
    print("=== ZafroBot Dinámico Iniciado ===")
    global GANANCIA_DIARIA
    while True:
        saldo = obtener_saldo_usdt()
        capital = saldo * 0.80

        if capital < 1:
            print("Saldo insuficiente para operar.")
            break

        precio_entrada = obtener_precio_actual()
        cantidad = capital / precio_entrada
        print(f"Comprando SHIB con ${capital:.2f} a precio {precio_entrada:.9f}")

        while True:
            time.sleep(10)
            precio_actual = obtener_precio_actual()

            if precio_actual >= precio_entrada * UMBRAL_TAKE_PROFIT:
                saldo_nuevo = capital * UMBRAL_TAKE_PROFIT
                GANANCIA_DIARIA += saldo_nuevo - capital
                print(f"Venta con ganancia: {precio_actual:.9f} | Nuevo saldo: {saldo_nuevo:.2f}")
                enviar_mensaje_telegram(saldo_nuevo)
                break

            elif precio_actual <= precio_entrada * UMBRAL_STOP_LOSS:
                saldo_nuevo = capital * UMBRAL_STOP_LOSS
                GANANCIA_DIARIA += saldo_nuevo - capital
                print(f"Stop loss activado: {precio_actual:.9f} | Nuevo saldo: {saldo_nuevo:.2f}")
                break

        time.sleep(5)  # Pausa antes de nueva operación

# === EJECUCIÓN ===
if __name__ == "__main__":
    zafrobot_dinamico()
