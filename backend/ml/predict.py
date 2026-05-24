import os
import joblib
import numpy as np
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()
except ImportError:
    analyzer = None

def generate_prediction(payload: dict) -> dict:
    model_path = os.path.join(os.path.dirname(__file__), "model.joblib")
    if not os.path.exists(model_path):
        return {
            "bias": "NEUTRAL",
            "confidence": 0,
            "entry_zone": "N/A",
            "target_1w": 0,
            "target_1m": 0,
            "stop_loss": 0,
            "support": 0,
            "resistance": 0,
            "risk_reward": "N/A",
            "strategy": "Model not trained yet. Run `python -m backend.ml.train` first.",
            "key_risks": [],
            "catalysts": [],
            "summary": "Model not found."
        }
        
    models = joblib.load(model_path)
    clf = models['classifier']
    reg_1w = models['regressor_1w']
    reg_1m = models['regressor_1m']
    
    indicators = payload.get("indicators", {})
    candles = payload.get("candles", [])
    news = payload.get("news", [])
    
    if not candles:
        return {"summary": "No price data provided."}
        
    current_price = candles[-1]['close']
    
    rsi = indicators.get("rsi", 50)
    macd_hist = indicators.get("macd", 0)
    
    ema9 = indicators.get("ema9", current_price)
    ema21 = indicators.get("ema21", current_price)
    ema50 = indicators.get("ema50", current_price)
    
    ema9_dist = (current_price - ema9) / ema9
    ema21_dist = (current_price - ema21) / ema21
    ema50_dist = (current_price - ema50) / ema50
    
    bb_upper = indicators.get("bbUpper", current_price)
    bb_lower = indicators.get("bbLower", current_price)
    bb_range = bb_upper - bb_lower if (bb_upper - bb_lower) != 0 else 1e-5
    bb_pos = (current_price - bb_lower) / bb_range
    
    X = np.array([[rsi, macd_hist, ema9_dist, ema21_dist, ema50_dist, bb_pos]])
    
    bias_pred = clf.predict(X)[0]
    bias_str = "BULLISH" if bias_pred == 1 else ("BEARISH" if bias_pred == -1 else "NEUTRAL")
    
    probs = clf.predict_proba(X)[0]
    confidence = int(np.max(probs) * 100)
    
    # News Sentiment Modification
    sentiment_score = 0
    news_summary = ""
    catalysts = ["Technical structure", "Moving average distance"]
    key_risks = ["Algorithmic prediction", "Market volatility"]
    
    if analyzer and news:
        scores = [analyzer.polarity_scores(headline)['compound'] for headline in news]
        sentiment_score = sum(scores) / len(scores) if scores else 0
        
        if sentiment_score > 0.2:
            news_summary = f"Positive news sentiment ({sentiment_score:.2f}) supports the thesis."
            if bias_str == "BEARISH":
                bias_str = "NEUTRAL"
                confidence = max(0, confidence - 20)
            elif bias_str == "BULLISH":
                confidence = min(100, confidence + 10)
            catalysts.append(f"Positive News: {news[0]}"[:100])
        elif sentiment_score < -0.2:
            news_summary = f"Negative news sentiment ({sentiment_score:.2f}) weakens the thesis."
            if bias_str == "BULLISH":
                bias_str = "NEUTRAL"
                confidence = max(0, confidence - 20)
            elif bias_str == "BEARISH":
                confidence = min(100, confidence + 10)
            key_risks.append(f"Negative News: {news[0]}"[:100])
        else:
            news_summary = "Recent news sentiment is neutral."
            
    target_1w_pct = reg_1w.predict(X)[0]
    target_1m_pct = reg_1m.predict(X)[0]
    
    target_1w = current_price * (1 + target_1w_pct)
    target_1m = current_price * (1 + target_1m_pct)
    
    stop_loss = current_price * 0.95 if bias_str == "BULLISH" else current_price * 1.05
    
    summary = f"The model is {confidence}% confident in a {bias_str} trend over the next week. {news_summary}"
    
    return {
        "bias": bias_str,
        "confidence": confidence,
        "entry_zone": f"₹{current_price*0.99:.1f}-₹{current_price*1.01:.1f}",
        "target_1w": round(target_1w, 1),
        "target_1m": round(target_1m, 1),
        "stop_loss": round(stop_loss, 1),
        "support": round(bb_lower, 1),
        "resistance": round(bb_upper, 1),
        "risk_reward": "1:2",
        "strategy": f"Local ML Model predicts {bias_str} bias. {news_summary}",
        "key_risks": key_risks,
        "catalysts": catalysts,
        "summary": summary.strip()
    }
