import requests
import time
import hmac
import hashlib
import os

# === CONFIGURACIÓN DESDE VARIABLES DE ENTORNO ===
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SYMBOL = "SHIB-USDT"
PRECISION = 4
TAKE_PROFIT = 0.02   # 2% ganancia
STOP_LOSS = 0.02     # 2% pérdida
RETROCESO_MIN = 0.003  # 0.3%
RETROCESO_MAX = 0.007  # 0.7%
RECUPERACION_CONFIRMADA = 0.0015  # 0.15%

# === FUNCIONES ===
def enviar_mensaje_telegram(mensaje):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=data)

def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/user/balance"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {"X-BX-APIKEY": API_KEY}
    params = {"timestamp": timestamp, "signature": signature}
    
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    for asset in data['data']['balances']:
        if asset['asset'] == 'USDT':
            return float(asset['free'])
    return 0.0

def obtener_precio_actual():
    url = f"https://open-api.bingx.com/openApi/market/getLatestPrice?symbol={SYMBOL}"
    response = requests.get(url)
    return float(response.json()['data'][0]['price'])

def colocar_orden(tipo, cantidad, precio):
    url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
    timestamp = str(int(time.time() * 1000))
    body = f"symbol={SYMBOL}&price={precio}&quantity={cantidad}&side={tipo}&type=LIMIT&timestamp={timestamp}"
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BX-APIKEY": API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "symbol": SYMBOL,
        "price": precio,
        "quantity": cantidad,
        "side": tipo,
        "type": "LIMIT",
        "timestamp": timestamp,
        "signature": signature
    }
    response = requests.post(url, headers=headers, data=data)
    return response.json()

# === LÓGICA DEL BOT ===
def zafrobot_dinamico_pro():
    print("=== ZafroBot PRO Iniciado ===")
    saldo = obtener_saldo_usdt()
    if saldo < 1:
        print("Saldo insuficiente.")
        enviar_mensaje_telegram("*ZafroBot:* Saldo insuficiente para operar.")
        return

    capital_usar = saldo * 0.80

    precio_inicial = obtener_precio_actual()
    print(f"Precio inicial: {precio_inicial}")

    fondo_detectado = precio_inicial
    while True:
        precio_actual = obtener_precio_actual()
        variacion = (precio_actual - precio_inicial) / precio_inicial

        if precio_actual < fondo_detectado:
            fondo_detectado = precio_actual

        retroceso = (fondo_detectado - precio_actual) / fondo_detectado

        # Detectar retroceso
        if RETROCESO_MIN <= retroceso <= RETROCESO_MAX:
            print(f"Retroceso detectado: {retroceso*100:.2f}%")
            
            # Esperar confirmación de recuperación
            while True:
                precio_confirmacion = obtener_precio_actual()
                recuperacion = (precio_confirmacion - fondo_detectado) / fondo_detectado
                if recuperacion >= RECUPERACION_CONFIRMADA:
                    cantidad = round(capital_usar / precio_confirmacion, PRECISION)
                    colocar_orden("BUY", cantidad, precio_confirmacion)
                    print(f"Compra ejecutada en recuperación a {precio_confirmacion}")
                    break
                time.sleep(5)
            
            # Luego de comprar, definir objetivos
            precio_objetivo = precio_confirmacion * (1 + TAKE_PROFIT)
            precio_stop = precio_confirmacion * (1 - STOP_LOSS)

            while True:
                precio_actual2 = obtener_precio_actual()
                print(f"Monitoreando operación: {precio_actual2}")
                if precio_actual2 >= precio_objetivo:
                    colocar_orden("SELL", cantidad, precio_actual2)
                    nuevo_saldo = obtener_saldo_usdt()
                    mensaje = (
                        "✅ *¡Ganancia alcanzada!* +2%\n\n"
                        f"💰 *Nuevo saldo:* `${nuevo_saldo:.2f}`\n\n"
                        "🔗 [Únete a mi canal oficial](https://t.me/GanandoConZafronock)"
                    )
                    enviar_mensaje_telegram(mensaje)
                    return
                elif precio_actual2 <= precio_stop:
                    colocar_orden("SELL", cantidad, precio_actual2)
                    enviar_mensaje_telegram("⚠️ *¡Stop Loss activado!* Capital protegido.")
                    return
                time.sleep(5)

        time.sleep(5)

# === INICIAR BOT ===
if __name__ == "__main__":
    zafrobot_dinamico_pro()
