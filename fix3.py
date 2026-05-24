import re
with open('frontend/src/pages/TerminalPage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix computeIndicators
new_ci = '''function computeIndicators(candles) {
  if (candles.length < 20) return {};
  const closes = candles.map(c => c.close);
  
  // EMA
  const ema = (period, data = closes) => {
    const k = 2 / (period + 1);
    let ema = data[0];
    return data.map(p => (ema = p * k + ema * (1 - k)));
  };
  
  // RSI
  const deltas = closes.slice(1).map((c, i) => c - closes[i]);
  const gains = deltas.map(d => Math.max(d, 0));
  const losses = deltas.map(d => Math.max(-d, 0));
  const avgGain = gains.slice(-14).reduce((a, b) => a + b, 0) / 14;
  const avgLoss = losses.slice(-14).reduce((a, b) => a + b, 0) / 14;
  const rs = avgGain / (avgLoss || 0.001);
  const rsi = 100 - 100 / (1 + rs);
'''
content = re.sub(r'function computeIndicators\(candles\).*?// MACD', new_ci + '  // MACD', content, flags=re.DOTALL)

# Fix computeBuyScore
new_cbs = '''function computeBuyScore(ind) {
  let score = 0;
  const reasons = [];
  if (ind.trendUp) { score += 20; reasons.push("Price above EMA50 (uptrend)"); }
  else reasons.push("Price below EMA50");
  
  if (ind.emaBull) { score += 20; reasons.push("EMA9 > EMA21 (short-term bullish)"); }
  else reasons.push("EMA9 < EMA21");
  
  if (ind.rsi > 40 && ind.rsi < 60) { score += 20; reasons.push("RSI Neutral/Rising"); }
  else if (ind.rsi <= 30) { score += 40; reasons.push("Oversold Bounce (Strong Buy)"); }
  else { score -= 10; reasons.push("RSI Overbought or Weak"); }
  
  if (ind.macdBull) { score += 20; reasons.push("MACD Bullish Crossover"); }
  else reasons.push("MACD Bearish");
  
  if (ind.bbPct < 20) { score += 20; reasons.push("Near Lower Bollinger Band"); }
  
  return { score: Math.min(100, Math.max(0, score)), reasons };
}
'''
content = re.sub(r'function computeBuyScore\(ind\).*?// UI COMPONENTS', new_cbs + '\n// UI COMPONENTS', content, flags=re.DOTALL)

with open('frontend/src/pages/TerminalPage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
