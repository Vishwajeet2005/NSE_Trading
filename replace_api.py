import re

with open('frontend/src/NSETradingTerminal.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """async function getAIPrediction(stock, candles, indicators) {
  try {
    const res = await fetch(`${BACKEND}/api/ml/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        stock: stock.s,
        candles: candles,
        indicators: indicators,
      }),
    });
    const data = await res.json();
    return data;
  } catch (e) {
    console.error("AI prediction failed:", e);
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════════"""

# We might have mangled it in the previous step, so let's match whatever is there now and ends with UI COMPONENTS
content = re.sub(
    r'async function getAIPrediction\(stock, candles, indicators\) \{.*?\n// [^\n]*\n// UI COMPONENTS',
    new_func + '\n// UI COMPONENTS',
    content,
    flags=re.DOTALL
)

with open('frontend/src/NSETradingTerminal.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
