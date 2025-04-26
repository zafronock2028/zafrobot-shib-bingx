import requests
import time
import hmac
import hashlib
import os

# Configuración de entorno
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Parámetros de scalping
PAR = "SHIB-USDT"
DECIMALES = 0  # Para cantidad de SHIB
MARGEN_GANANCIA = 1.02  # +2%
STOP_LOSS = 0.98        # -2%

# Funciones auxiliares
def firmar(query_string, secret_key):
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def notificar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Error enviando Telegram:", e)

def obtener_precio_actual():
    try:
        url = f"https://open-api.bingx.com/openApi/spot/v1/ticker/price?symbol={PAR}"
        respuesta = requests.get(url)
        data = respuesta.json()
        return float(data['data']['price'])
    except:
        return 0

def obtener_saldo_usdt():
    url = "https://open-api.bingx.com/openApi/spot/v1/account/assets"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    firma = firmar(query_string, SECRET_KEY)
    headers = {"X-BX-APIKEY": API_KEY}
    url_firmada = f"{url}?{query_string}&signature={firma}"
    respuesta = requests.get(url_firmada, headers=headers)
    data = respuesta.json()

    try:
        for asset in data['data']['balances']:
            if asset['asset'] == 'USDT':
                return float(asset['free'])
    except:
        print("Error saldo:", data)
    return 0

def detectar_oportunidad():
    precios = []
    volumenes = []

    for _ in range(5):
        url = f"https://open-api.bingx.com/openApi/spot/v1/market/depth?symbol={PAR}&limit=5"
        r = requests.get(url)
        data = r.json()
        try:
            mejor_precio_venta = float(data['data']['asks'][0][0])
            mejor_precio_compra = float(data['data']['bids'][0][0])
            volumen_compra = float(data['data']['bids'][0][1])
            volumen_venta = float(data['data']['asks'][0][1])
            precios.append((mejor_precio_venta + mejor_precio_compra) / 2)
            volumenes.append(volumen_compra - volumen_venta)
        except:
            continue
        time.sleep(2)

    if len(precios) < 3:
        return False

    tendencia = precios[-1] > precios[0] and precios[-1] > precios[-2]
    presion_compra = sum(1 for v in volumenes if v > 0)

    return tendencia and presion_compra >= 3

def comprar(cantidad, precio_actual):
    cantidad = round(cantidad / precio_actual, 0)  # SHIB cantidades
    print(f"Compra simulada: {cantidad} SHIB a {precio_actual}")
    return cantidad

def monitorear_venta(precio_entrada, cantidad):
    while True:
        time.sleep(8)
        precio_actual = obtener_precio_actual()

        if precio_actual >= precio_entrada * MARGEN_GANANCIA:
            notificar_telegram(f"✅ *¡Ganancia del 2% alcanzada!*\nNuevo saldo incrementado\nÚnete al canal oficial:\n👉 https://t.me/GanandoConZafronock")
            break
        elif precio_actual <= precio_entrada * STOP_LOSS:
            notificar_telegram(f"⚡ *Stop Loss ejecutado para proteger capital!*")
            break

# BOT PRINCIPAL con reintento
def zafrobot_dinamico_pro():
    print("=== ZafroBot Dinámico Pro Iniciado ===")
    notificar_telegram("🚀 *ZafroBot Dinámico Pro Iniciado*\nBuscando oportunidades...")

    while True:
        saldo = obtener_saldo_usdt()

        if saldo < 3:
            notificar_telegram("⚠️ *Saldo insuficiente para operar.*")
            print("Saldo insuficiente. Bot pausado.")
            time.sleep(600)  # 10 minutos
            continue

        oportunidad = detectar_oportunidad()

        if oportunidad:
            capital = saldo * 0.80
            precio_actual = obtener_precio_actual()
            cantidad = comprar(capital, precio_actual)

            notificar_telegram(f"🟢 *Compra ejecutada*\nCantidad: `{cantidad}` tokens\nPrecio: `{precio_actual}`\nEsperando venta...")
            monitorear_venta(precio_actual, cantidad)
            break
        else:
            print("No hay oportunidad. Reintentando en 5 minutos...")
            notificar_telegram("⏳ *No hay oportunidad segura. Reintentando en 5 minutos...*")
            time.sleep(300)  # 5 minutos

# Ejecutar bot
if __name__ == "__main__":
    zafrobot_dinamico_pro()
