import os
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
import joblib
from backend.core import logger as log_mod
from backend.core.settings import NSE_WATCHLIST

log = log_mod.get(__name__)

def add_features(df):
    if len(df) < 60: return None
    
    # Calculate identical indicators to strategy.py
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.ema(length=9, append=True)
    df.ta.ema(length=21, append=True)
    df.ta.ema(length=50, append=True)
    df.ta.bbands(length=20, std=2, append=True)
    
    df.dropna(inplace=True)
    if len(df) < 10: return None
    
    close = df['Close']
    df['rsi'] = df['RSI_14']
    df['macd_hist'] = df['MACDh_12_26_9']
    
    df['ema9_dist'] = (close - df['EMA_9']) / df['EMA_9']
    df['ema21_dist'] = (close - df['EMA_21']) / df['EMA_21']
    df['ema50_dist'] = (close - df['EMA_50']) / df['EMA_50']
    
    bb_upper = df['BBU_20_2.0_2.0']
    bb_lower = df['BBL_20_2.0_2.0']
    bb_range = bb_upper - bb_lower
    bb_range = bb_range.replace(0, 1e-5)
    df['bb_pos'] = (close - bb_lower) / bb_range
    
    # Targets
    df['fwd_ret_1w'] = df['Close'].shift(-5) / df['Close'] - 1
    df['fwd_ret_1m'] = df['Close'].shift(-20) / df['Close'] - 1
    
    df['bias'] = 0
    df.loc[df['fwd_ret_1w'] > 0.015, 'bias'] = 1
    df.loc[df['fwd_ret_1w'] < -0.015, 'bias'] = -1
    
    df.dropna(inplace=True)
    return df

def train_models():
    log.info("Starting ML Training Pipeline...")
    all_data = []
    
    tickers = NSE_WATCHLIST[:10] + ["BTC-USD", "ETH-USD", "CL=F"]
    
    for ticker in tickers:
        yf_sym = ticker if ("-" in ticker or "=" in ticker) else f"{ticker}.NS"
        log.info(f"Downloading historical data for {yf_sym}...")
        try:
            df = yf.Ticker(yf_sym).history(period="15y")
            df = add_features(df)
            if df is not None:
                all_data.append(df)
        except Exception as e:
            log.error(f"Failed to fetch {ticker}: {e}")
            
    if not all_data:
        log.error("No data fetched.")
        return
        
    master_df = pd.concat(all_data)
    log.info(f"Master Dataset Shape: {master_df.shape}")
    
    features = ['rsi', 'macd_hist', 'ema9_dist', 'ema21_dist', 'ema50_dist', 'bb_pos']
    
    X = master_df[features]
    y_bias = master_df['bias']
    y_target_1w = master_df['fwd_ret_1w']
    y_target_1m = master_df['fwd_ret_1m']
    
    log.info("Training Bias Classifier...")
    clf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    clf.fit(X, y_bias)
    
    log.info("Training Target Regressors...")
    reg_1w = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
    reg_1w.fit(X, y_target_1w)
    
    reg_1m = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
    reg_1m.fit(X, y_target_1m)
    
    models = {
        'classifier': clf,
        'regressor_1w': reg_1w,
        'regressor_1m': reg_1m,
        'features': features
    }
    
    save_path = os.path.join(os.path.dirname(__file__), "model.joblib")
    joblib.dump(models, save_path)
    log.info(f"Models successfully saved to {save_path}")

if __name__ == "__main__":
    train_models()
