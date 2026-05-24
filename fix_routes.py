import re
with open('backend/api/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_code = '''        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.bbands(length=20, std=2, append=True)'''

new_code = '''        df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss.replace(0, 0.001)
        df['RSI_14'] = 100 - (100 / (1 + rs))
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD_12_26_9'] = ema12 - ema26
        signal = df['MACD_12_26_9'].ewm(span=9, adjust=False).mean()
        df['MACDh_12_26_9'] = df['MACD_12_26_9'] - signal
        df['BBU_20_2.0_2.0'] = df['Close'].rolling(20).mean() + 2 * df['Close'].rolling(20).std()
        df['BBL_20_2.0_2.0'] = df['Close'].rolling(20).mean() - 2 * df['Close'].rolling(20).std()'''

c = c.replace(old_code, new_code)
c = c.replace('log_mod.error', 'log.error')

with open('backend/api/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)

