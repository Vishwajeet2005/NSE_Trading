with open('backend/engine/strategy.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('import pandas_ta as ta', '')
with open('backend/engine/strategy.py', 'w', encoding='utf-8') as f:
    f.write(c)
