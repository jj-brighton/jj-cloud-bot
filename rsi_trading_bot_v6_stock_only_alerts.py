print("🚀 JJ Bot Launching — Hello from Render!")

import requests
import pandas as pd
import time
from datetime import datetime

# === CONFIGURATION ===
API_KEY = "PKH23G0PEVRWLQ7R8I4B"
SECRET_KEY = "rRZdI3fMeSkZLIwLZmRK3168PJLNbYhzWf3koyeP"
BASE_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets/v2"
POSITION_LIMIT = 3
DAILY_LOSS_LIMIT = -10.00
TRADE_AMOUNT = 20
RSI_PERIOD = 14
RSI_OVERBOUGHT = 80
RSI_OVERSOLD = 20
MACD_FAST = 10
MACD_SLOW = 20
MACD_SIGNAL = 7
FAST_MA = 10
SLOW_MA = 20
SLEEP_TIME = 15 * 60

STOCK_SYMBOLS = ["AAPL", "TSLA", "AMZN", "MSFT", "GOOGL", "NVDA", "META", "NFLX"]

HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}

# === TELEGRAM ===
TELEGRAM_TOKEN = "7925490909:AAGh250SSg9LGkAhAgcqkez_DtrohfQbDpM"
TELEGRAM_CHAT_ID = "6649018072"

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram alert failed: {e}")

print("✅ Bot started... connecting to Alpaca...")
send_telegram_alert("📡 *JJ Bot Online* — monitoring the markets now...")

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def calculate_mas(series):
    return series.rolling(window=FAST_MA).mean(), series.rolling(window=SLOW_MA).mean()

def get_stock_bars(symbol):
    url = f"{DATA_URL}/stocks/{symbol}/bars"
    params = {"timeframe": "15Min", "limit": 100}
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    bars = r.json()["bars"]
    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"])
    df.set_index("t", inplace=True)
    return df

def place_order(symbol, side, notional):
    url = f"{BASE_URL}/v2/orders"
    order = {
        "symbol": symbol,
        "notional": str(notional),
        "side": side,
        "type": "market",
        "time_in_force": "gtc"
    }
    r = requests.post(url, headers=HEADERS, json=order)
    return r.json()

def get_account():
    r = requests.get(f"{BASE_URL}/v2/account", headers=HEADERS)
    return r.json()

def get_positions():
    r = requests.get(f"{BASE_URL}/v2/positions", headers=HEADERS)
    return r.json()

def should_trade(symbol):
    try:
        df = get_stock_bars(symbol)
        close = df["c"]
        price = close.iloc[-1]
        rsi = calculate_rsi(close, RSI_PERIOD).iloc[-1]
        macd_line, signal_line = calculate_macd(close, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
        macd = macd_line.iloc[-1]
        signal = signal_line.iloc[-1]
        fast_ma, slow_ma = calculate_mas(close)

        if pd.isna(rsi) or pd.isna(macd) or pd.isna(fast_ma.iloc[-1]) or pd.isna(slow_ma.iloc[-1]):
            return "SKIP", price, rsi, macd, signal, fast_ma.iloc[-1], slow_ma.iloc[-1], None

        action = "HOLD"
        if rsi < RSI_OVERSOLD and fast_ma.iloc[-1] > slow_ma.iloc[-1] and macd > signal:
            action = "BUY"
        elif rsi > RSI_OVERBOUGHT and fast_ma.iloc[-1] < slow_ma.iloc[-1] and macd < signal:
            action = "SELL"
        return action, price, rsi, macd, signal, fast_ma.iloc[-1], slow_ma.iloc[-1], None
    except Exception as e:
        return "ERROR", None, None, None, None, None, None, str(e)

def run_bot():
    print("✅ Running main trading loop...")
    while True:
        positions = get_positions()
        account = get_account()
        daily_pl = float(account.get("equity", 0)) - float(account.get("last_equity", 0))
        if daily_pl < DAILY_LOSS_LIMIT:
            print("Daily loss limit reached. Pausing trading.")
            time.sleep(SLEEP_TIME)
            continue

        active_positions = len(positions)

        for symbol in STOCK_SYMBOLS:
            action, price, rsi, macd, signal, fast_ma, slow_ma, error = should_trade(symbol)

            if action == "ERROR":
                print(f"[{symbol}] Error: {error}")
                continue
            elif action == "SKIP":
                print(f"[{symbol}] Not enough data. Skipping.")
                continue

            log = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {symbol} | Price: {price:.2f} | RSI: {rsi:.2f} | MACD: {macd:.2f} | Signal: {signal:.2f} | Fast MA: {fast_ma:.2f} | Slow MA: {slow_ma:.2f} | Action: {action}"
            print(log)

            if action in ["BUY", "SELL"] and active_positions < POSITION_LIMIT:
                try:
                    response = place_order(symbol, action.lower(), TRADE_AMOUNT)
                    log += f" | ORDERED | Response: {response}"
                    msg = f"📈 *TRADE ALERT*\nStock: `{symbol}`\nAction: *{action}*\nPrice: `${price:.2f}`\nRSI: `{rsi:.1f}` | MACD: `{macd:.2f}`"
                    send_telegram_alert(msg)
                    active_positions += 1 if action == "BUY" else 0
                except Exception as e:
                    log += f" | Order failed: {e}"

            with open("trading_log.txt", "a") as f:
                f.write(log + "\n")

        print(f"Sleeping {SLEEP_TIME / 60} minutes...")
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    run_bot()
