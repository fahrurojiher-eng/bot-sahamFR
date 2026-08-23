import time
import yfinance as yf
import pandas as pd


def get_data(ticker, period="3mo", interval="1d"):
    # Catatan: JANGAN pasang session curl_cffi manual - yfinance versi baru
    # sudah otomatis pakai curl_cffi sendiri di dalam (asal library-nya terinstall).
    # Memasang session manual malah bikin error "'str' object has no attribute 'name'".
    for percobaan in range(3):
        try:
            t = yf.Ticker(ticker)
            df = t.history(period=period, interval=interval, auto_adjust=True)
            if df is not None and not df.empty:
                return df
            else:
                print(f"[{ticker}] Percobaan {percobaan+1}: data kosong.")
        except Exception as e:
            print(f"[{ticker}] Percobaan {percobaan+1} gagal: {e}")
        time.sleep(2)

    print(f"[{ticker}] TIDAK BISA AMBIL DATA setelah 3 percobaan.")
    return pd.DataFrame()


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
    if df.empty:
        print(f"[{ticker}] Data kosong, dilewati.")
        return None
    if len(df) < 50:
        print(f"[{ticker}] Data cuma {len(df)} baris (butuh minimal 50), dilewati.")
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
