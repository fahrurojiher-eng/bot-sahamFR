import yfinance as yf
import pandas as pd


def get_data(ticker, period="3mo", interval="1d"):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    return df


def hitung_indikator(df):
    df = df.copy()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()

    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    df["VolAvg20"] = df["Volume"].rolling(20).mean()
    return df


def ringkas_data(ticker):
    """Ambil data teknikal mentah (angka), dipakai sebagai bahan buat Gemini."""
    df = get_data(ticker)
    if df.empty or len(df) < 50:
        return None

    df = hitung_indikator(df)
    last = df.iloc[-1]

    return {
        "ticker": ticker,
        "harga": float(last["Close"]),
        "rsi": float(last["RSI"]) if pd.notna(last["RSI"]) else None,
        "ma20": float(last["MA20"]) if pd.notna(last["MA20"]) else None,
        "ma50": float(last["MA50"]) if pd.notna(last["MA50"]) else None,
        "volume": float(last["Volume"]),
        "vol_avg20": float(last["VolAvg20"]) if pd.notna(last["VolAvg20"]) else None,
        "perubahan_persen": float((last["Close"] - df.iloc[-2]["Close"]) / df.iloc[-2]["Close"] * 100),
    }
